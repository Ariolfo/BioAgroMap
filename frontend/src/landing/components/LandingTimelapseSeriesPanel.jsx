import { useCallback, useEffect, useMemo, useState } from "react";
import SensorTimelapseViewer from "../../components/dashboard/SensorTimelapseViewer";
import VegetationTimeSeriesCharts from "../../components/VegetationTimeSeriesCharts";
import ClimateTimeSeriesChart, {
  CLIMATE_SERIES_COLORS,
} from "../../components/dashboard/ClimateTimeSeriesChart";
import {
  SENSOR_META,
  buildIndexPreviewEndpoint,
  buildRecorteRgbEndpoint,
  buildS1Sigma0PreviewEndpoint,
  fetchPreviewDataUrl,
  findRecortePathForSceneDate,
  isS1SigmaVisualKey,
  resolveInventoryIndexKey,
} from "../previewUtils";

export default function LandingTimelapseSeriesPanel({
  sensorKey,
  projectId,
  token,
  adapted,
  extras,
  getCachedPreview,
  onReloadSeries,
  hideTitle = false,
}) {
  const sensorBlock = adapted?.sensorData?.[sensorKey];
  const availableIndices = sensorBlock?.indices || [];

  const defaultIndex = useMemo(() => {
    return (
      resolveInventoryIndexKey(availableIndices, SENSOR_META[sensorKey]?.defaultIndex) ||
      resolveInventoryIndexKey(availableIndices, "NDVI") ||
      availableIndices[0] ||
      ""
    );
  }, [sensorKey, availableIndices.join("|")]);

  const [selectedIndex, setSelectedIndex] = useState(defaultIndex);
  const [frameIdx, setFrameIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [opacity, setOpacity] = useState(1);
  const [indexSrc, setIndexSrc] = useState("");
  const [rgbSrc, setRgbSrc] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [roiMode, setRoiMode] = useState(false);
  const [roiSelection, setRoiSelection] = useState(null);
  const [pointSelection, setPointSelection] = useState(null);
  const [climateVars, setClimateVars] = useState({
    precip: true,
    temp: true,
    humidity: false,
    radiation: false,
  });

  useEffect(() => {
    setSelectedIndex(defaultIndex);
    setFrameIdx(0);
    setIsPlaying(false);
  }, [defaultIndex]);

  const frames = useMemo(
    () => sensorBlock?.framesByIndex?.[selectedIndex] || [],
    [sensorBlock, selectedIndex]
  );

  const currentFrame = frames[frameIdx] || null;

  useEffect(() => {
    if (frameIdx >= frames.length) setFrameIdx(0);
  }, [frames.length, frameIdx]);

  useEffect(() => {
    if (!isPlaying || frames.length < 2) return undefined;
    const t = window.setInterval(() => {
      setFrameIdx((i) => (i + 1) % frames.length);
    }, 1400);
    return () => window.clearInterval(t);
  }, [isPlaying, frames.length]);

  const loadRgbForFrame = useCallback(
    async (frame) => {
      if (!projectId || !frame) return "";
      if (sensorKey === "s1") {
        const relSigma = findRecortePathForSceneDate(adapted?.s1PrepSigmaItems || [], frame.date);
        if (relSigma) {
          const key = `${projectId}|s1sigma|${relSigma}`;
          return getCachedPreview(key, () =>
            fetchPreviewDataUrl(buildS1Sigma0PreviewEndpoint(projectId, relSigma), token)
          );
        }
        return "";
      }
      const recItems = adapted?.recorteInventory?.[sensorKey] || [];
      const rel = findRecortePathForSceneDate(recItems, frame.date);
      if (!rel) return "";
      const pv = SENSOR_META[sensorKey].variant;
      const key = `${projectId}|rgb|${pv}|${rel}`;
      return getCachedPreview(key, () =>
        fetchPreviewDataUrl(buildRecorteRgbEndpoint(projectId, rel, pv), token)
      );
    },
    [projectId, adapted, sensorKey, getCachedPreview, token]
  );

  const loadIndexForFrame = useCallback(
    async (frame) => {
      if (!projectId || !frame) return "";
      const pol =
        frame.kind === "s1-sigma"
          ? frame.pol
          : isS1SigmaVisualKey(selectedIndex)
            ? String(selectedIndex).toUpperCase() === "VH"
              ? "vh"
              : "vv"
            : null;
      const cacheKey =
        pol != null
          ? `${projectId}|s1sigma|${pol}|${frame.relativePath}`
          : `${projectId}|idx|${sensorKey}|${frame.id}`;
      return getCachedPreview(cacheKey, () =>
        fetchPreviewDataUrl(
          pol != null
            ? buildS1Sigma0PreviewEndpoint(projectId, frame.relativePath, pol)
            : buildIndexPreviewEndpoint(sensorKey, projectId, frame),
          token
        )
      );
    },
    [projectId, sensorKey, selectedIndex, getCachedPreview, token]
  );

  useEffect(() => {
    if (!currentFrame || !projectId) return undefined;
    let cancelled = false;
    async function run() {
      setPreviewError("");
      try {
        const [idx, rgb] = await Promise.all([
          loadIndexForFrame(currentFrame),
          loadRgbForFrame(currentFrame),
        ]);
        if (cancelled) return;
        if (idx) setIndexSrc(idx);
        if (rgb) setRgbSrc(rgb);
      } catch (e) {
        if (!cancelled) setPreviewError(String(e?.message || e));
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [currentFrame, projectId, loadIndexForFrame, loadRgbForFrame]);

  const roiPointCount = Array.isArray(roiSelection?.polygon_points)
    ? roiSelection.polygon_points.length
    : 0;

  useEffect(() => {
    if (roiPointCount >= 3 && typeof onReloadSeries === "function") {
      onReloadSeries({ roiSelection, pointSelection });
    }
  }, [roiPointCount, roiSelection, pointSelection, onReloadSeries]);

  const handleMediaClick = useCallback(
    (e) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / Math.max(rect.width, 1)));
      const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / Math.max(rect.height, 1)));
      if (roiMode) {
        setRoiSelection((prev) => {
          const current = Array.isArray(prev?.polygon_points) ? prev.polygon_points : [];
          return { polygon_points: [...current, { x, y }] };
        });
        return;
      }
      setPointSelection({ x, y });
    },
    [roiMode]
  );

  const seriesData = extras?.seriesBySensor?.[sensorKey];
  const climateData = extras?.climateBySensor?.[sensorKey] || [];
  const seriesLoading = extras?.seriesLoading;

  if (!availableIndices.length) {
    return (
      <div className="landing-subsection landing-timelapse-dashboard">
        {!hideTitle ? <h3 className="landing-subsection-title">Serie temporal interactiva</h3> : null}
        <p className="landing-hint">No hay inventario de índices para este sensor.</p>
      </div>
    );
  }

  return (
    <div className="landing-subsection landing-timelapse-dashboard">
      {!hideTitle ? (
        <>
          <h3 className="landing-subsection-title">Serie temporal interactiva</h3>
          <p className="landing-timelapse-lead">
            Compare el índice con la vista RGB en la misma fecha, explore el timelapse y consulte las
            series de índice y clima — igual que en el dashboard técnico, sin capas de cluster.
          </p>
        </>
      ) : null}
      {previewError ? <p className="landing-error">{previewError}</p> : null}
      <div className="landing-adv-split">
        <div className="adv-timelapse-column landing-adv-timelapse-column">
          <div className="adv-timelapse-main">
            <SensorTimelapseViewer
              sensorTitle={SENSOR_META[sensorKey].title}
              omitSensorTitle
              indices={availableIndices}
              selectedIndex={selectedIndex}
              onChangeIndex={(k) => {
                setSelectedIndex(k);
                setFrameIdx(0);
              }}
              frames={frames}
              currentIdx={frameIdx}
              onChangeFrameIdx={setFrameIdx}
              isPlaying={isPlaying}
              onPlayPause={() => setIsPlaying((p) => !p)}
              onStop={() => {
                setIsPlaying(false);
                setFrameIdx(0);
              }}
              imageSrc={indexSrc}
              imageAlt={`${selectedIndex} ${currentFrame?.date || ""}`}
              dualPaneRgb={sensorKey !== "s1"}
              rgbImageSrc={rgbSrc}
              rgbAlt={
                sensorKey === "s1"
                  ? `SAR VV ${currentFrame?.date || ""}`
                  : `RGB ${currentFrame?.date || ""}`
              }
              rightPaneLabel={sensorKey === "s1" ? "SAR VV" : "RGB"}
              rgbEmptyMessage={
                sensorKey === "s1"
                  ? "Sin Sigma0 VV para esta fecha."
                  : "Sin recorte RGB para esta fecha."
              }
              opacity={opacity}
              onOpacity={setOpacity}
              hideOpacityControl
              hideSceneCounter
              interactive
              roiMode={roiMode}
              onToggleRoi={() => setRoiMode((v) => !v)}
              onClearRoi={() => setRoiSelection(null)}
              roiSelection={roiSelection}
              clusterVisible={false}
              onMediaMouseMove={() => {}}
              onMediaMouseDown={() => {}}
              onMediaMouseUp={() => {}}
              onMediaClick={handleMediaClick}
            />
          </div>
        </div>

        <div className="adv-series-column landing-adv-series-column">
          <div className="adv-series-column-inner">
            <div className="adv-series-primary">
              {seriesLoading ? <p className="landing-hint">Cargando series…</p> : null}
              {!seriesLoading && seriesData ? (
                <VegetationTimeSeriesCharts
                  data={seriesData}
                  onlyIndexKey={isS1SigmaVisualKey(selectedIndex) ? null : selectedIndex}
                  activeSceneDate={currentFrame?.date || null}
                  chartPixelHeight={230}
                  chartHeadingOverride="SERIE TEMPORAL DE INDICES"
                />
              ) : null}
              {!seriesLoading && !seriesData ? (
                <p className="adv-series-empty">Sin serie para este sensor.</p>
              ) : null}
              <div className="adv-climate-panel adv-climate-panel--inline">
                <ClimateTimeSeriesChart
                  data={climateData}
                  activeVars={climateVars}
                  activeSceneDate={currentFrame?.date || null}
                  chartHeight={170}
                />
              </div>
              <div className="adv-climate-toggles adv-climate-toggles--compact">
                {[
                  ["precip", "Precipitación"],
                  ["temp", "Temperatura"],
                  ["humidity", "Humedad"],
                  ["radiation", "Radiación solar"],
                ].map(([k, label]) => (
                  <label key={k}>
                    <input
                      type="checkbox"
                      checked={!!climateVars[k]}
                      onChange={(e) => setClimateVars((p) => ({ ...p, [k]: e.target.checked }))}
                    />
                    <span
                      className="adv-climate-toggle-line"
                      style={{ "--climate-toggle-color": CLIMATE_SERIES_COLORS[k] }}
                      aria-hidden="true"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
