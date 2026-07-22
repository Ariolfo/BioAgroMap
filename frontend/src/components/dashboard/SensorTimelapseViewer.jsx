import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** Índices agrupados; clave de vigor en inventario: KNDVI. */
const INDEX_CATEGORY_GROUPS = [
  { label: "Vigor", keys: ["NDVI", "EVI", "MSAVI2", "MTVI2", "KNDVI"] },
  { label: "Nutrición", keys: ["NDRE", "CIre", "MCARI"] },
  { label: "Agua", keys: ["NDWI"] },
  { label: "Estructura", keys: ["VARI", "TGI", "GIYI", "RSTRUCTURE"] },
];

const GROUPED_INDEX_KEYS_NORM = new Set(
  INDEX_CATEGORY_GROUPS.flatMap((g) => g.keys.map((k) => String(k).toUpperCase()))
);

/** Alinea catálogo con claves del inventario (p. ej. CIre vs CIRE tras toUpperCase en dashboard). */
function normIndexKey(k) {
  return String(k || "").toUpperCase();
}

function labelIndexOption(key) {
  const k = String(key || "");
  if (k === "VV") return "solo VV";
  if (k === "VH") return "solo VH";
  if (k === "VV_VH") return "VV/VH";
  if (k === "VH_VV") return "VH/VV";
  return k;
}

function formatDate(iso) {
  if (!iso) return "—";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return String(iso);
  return `${m[3]}/${m[2]}/${m[1]}`;
}

export default function SensorTimelapseViewer({
  sensorTitle,
  omitSensorTitle = false,
  indices,
  selectedIndex,
  onChangeIndex,
  frames,
  currentIdx,
  onChangeFrameIdx,
  isPlaying,
  onPlayPause,
  onStop,
  imageSrc,
  imageAlt,
  dualPaneRgb = false,
  rgbImageSrc = "",
  rgbAlt = "RGB",
  rightPaneLabel = "RGB",
  rgbEmptyMessage = "Sin recorte RGB para esta fecha.",
  opacity,
  onOpacity,
  hideOpacityControl = false,
  hideSceneCounter = false,
  onOpenClientVisualization,
  interactive = false,
  roiMode = false,
  onToggleRoi,
  onClearRoi,
  roiSelection = null,
  clusterPreviewB64 = null,
  clusterVisible = false,
  onToggleClusterVisible,
  clusterOptions = [],
  selectedClusterKey = "",
  onChangeClusterKey,
  onMediaMouseMove,
  onMediaMouseDown,
  onMediaMouseUp,
  onMediaClick,
}) {
  const [dualZoomOpen, setDualZoomOpen] = useState(false);
  const [dzScale, setDzScale] = useState(1);
  const [dzPan, setDzPan] = useState({ x: 0, y: 0 });
  const [dzDragging, setDzDragging] = useState(false);
  const dzDragRef = useRef({ dragging: false, startX: 0, startY: 0, panX: 0, panY: 0 });

  const current = frames[currentIdx] || null;
  const roiPoints = Array.isArray(roiSelection?.polygon_points) ? roiSelection.polygon_points : [];
  const roiPointsSvg = roiPoints.map((p) => `${p.x * 100},${p.y * 100}`).join(" ");
  const roiHasShape = roiPoints.length > 0;
  const roiCanClose = roiPoints.length >= 3;
  const showTimelineFoot =
    !hideSceneCounter ||
    !hideOpacityControl ||
    typeof onOpenClientVisualization === "function";

  const mediaHandlers = useMemo(
    () =>
      interactive
        ? {
            onMouseMove: onMediaMouseMove,
            onMouseDown: onMediaMouseDown,
            onMouseUp: onMediaMouseUp,
            onClick: onMediaClick,
          }
        : {},
    [interactive, onMediaMouseMove, onMediaMouseDown, onMediaMouseUp, onMediaClick]
  );

  const showRoi = typeof onToggleRoi === "function";
  const dateStr = formatDate(current?.date);
  const roiOverlay = roiHasShape ? (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      aria-hidden="true"
    >
      {roiCanClose ? (
        <polygon points={roiPointsSvg} fill="rgba(0, 140, 255, 0.18)" stroke="#008cff" strokeWidth="0.7" />
      ) : (
        <polyline points={roiPointsSvg} fill="none" stroke="#008cff" strokeWidth="0.7" />
      )}
      {roiPoints.map((p, idx) => (
        <circle key={`roi-pt-${idx}`} cx={p.x * 100} cy={p.y * 100} r="0.8" fill="#008cff" />
      ))}
    </svg>
  ) : null;

  const resetDualZoom = useCallback(() => {
    setDzScale(1);
    setDzPan({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    if (!dualZoomOpen) resetDualZoom();
  }, [dualZoomOpen, resetDualZoom]);

  useEffect(() => {
    if (dzScale <= 1.01) setDzPan({ x: 0, y: 0 });
  }, [dzScale]);

  const onDualZoomWheel = useCallback((e) => {
    if (!dualPaneRgb || !dualZoomOpen) return;
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    setDzScale((prev) => {
      const next = Math.max(1, Math.min(4, Number((prev + delta).toFixed(3))));
      if (next <= 1.01) setDzPan({ x: 0, y: 0 });
      return next;
    });
  }, [dualPaneRgb, dualZoomOpen]);

  const onDualPanMouseDown = useCallback(
    (e) => {
      if (e.button !== 0) return;
      if (!dualZoomOpen || dzScale <= 1.01) return;
      dzDragRef.current = {
        dragging: true,
        startX: e.clientX,
        startY: e.clientY,
        panX: dzPan.x,
        panY: dzPan.y,
      };
      setDzDragging(true);
    },
    [dualZoomOpen, dzScale, dzPan.x, dzPan.y]
  );

  const onDualPanMouseMove = useCallback((e) => {
    if (!dzDragRef.current.dragging) return;
    const dx = e.clientX - dzDragRef.current.startX;
    const dy = e.clientY - dzDragRef.current.startY;
    setDzPan({ x: dzDragRef.current.panX + dx, y: dzDragRef.current.panY + dy });
  }, []);

  const onDualPanMouseUp = useCallback(() => {
    if (!dzDragRef.current.dragging) return;
    dzDragRef.current.dragging = false;
    setDzDragging(false);
  }, []);

  useEffect(() => {
    if (!dzDragging) return undefined;
    const up = () => onDualPanMouseUp();
    window.addEventListener("mouseup", up);
    return () => window.removeEventListener("mouseup", up);
  }, [dzDragging, onDualPanMouseUp]);

  const indexSelectContent = useMemo(() => {
    const list = indices || [];
    if (!list.length) return null;
    const availableByNorm = new Map();
    for (const k of list) {
      availableByNorm.set(normIndexKey(k), k);
    }
    const anyGrouped = list.some((k) => GROUPED_INDEX_KEYS_NORM.has(normIndexKey(k)));
    if (!anyGrouped) {
      return list.map((k) => (
        <option key={k} value={k}>
          {labelIndexOption(k)}
        </option>
      ));
    }

    const used = new Set();
    const groups = [];

    for (const g of INDEX_CATEGORY_GROUPS) {
      const keysInGroup = [];
      for (const catalogKey of g.keys) {
        const actual = availableByNorm.get(normIndexKey(catalogKey));
        if (actual) {
          keysInGroup.push(actual);
          used.add(actual);
        }
      }
      groups.push(
        <optgroup key={g.label} label={g.label}>
          {keysInGroup.length > 0 ? (
            keysInGroup.map((k) => (
              <option key={k} value={k}>
                {labelIndexOption(k)}
              </option>
            ))
          ) : (
            <option key={`${g.label}__vacío`} disabled value="">
              —
            </option>
          )}
        </optgroup>
      );
    }

    const rest = list.filter((k) => !used.has(k));
    if (rest.length) {
      groups.push(
        <optgroup key="otros" label="Otros">
          {rest.map((k) => (
            <option key={k} value={k}>
              {labelIndexOption(k)}
            </option>
          ))}
        </optgroup>
      );
    }

    return groups;
  }, [indices]);

  const indexPane = (
    <div
      className={`adv-viewer-pane adv-viewer-pane--index${interactive ? " adv-viewer-media--interactive" : ""}${
        dualPaneRgb ? " adv-viewer-pane--dual" : ""
      }`}
      {...(interactive ? mediaHandlers : {})}
    >
      <span className="adv-viewer-pane-label">Índice</span>
      {imageSrc ? (
        interactive ? (
          <>
            <img className="adv-viewer-stack-img" src={imageSrc} alt={imageAlt} style={{ opacity }} />
            {clusterVisible && clusterPreviewB64 ? (
              <img
                className="adv-viewer-stack-cluster"
                src={`data:image/png;base64,${clusterPreviewB64}`}
                alt=""
              />
            ) : null}
            {roiOverlay}
          </>
        ) : (
          <img className="adv-viewer-stack-img" src={imageSrc} alt={imageAlt} style={{ opacity }} />
        )
      ) : (
        <div className="adv-viewer-empty">Sin preview para esta escena.</div>
      )}
    </div>
  );

  const rgbPane = dualPaneRgb ? (
    <div className="adv-viewer-pane adv-viewer-pane--rgb adv-viewer-pane--dual">
      <span className="adv-viewer-pane-label">{rightPaneLabel}</span>
      {rgbImageSrc ? (
        <img className="adv-viewer-rgb-img" src={rgbImageSrc} alt={rgbAlt} />
      ) : (
        <div className="adv-viewer-empty">{rgbEmptyMessage}</div>
      )}
    </div>
  ) : null;

  const singleMedia = (
    <div
      className={`adv-viewer-media${interactive ? " adv-viewer-media--interactive" : ""}`}
      {...(interactive && !dualPaneRgb ? mediaHandlers : {})}
    >
      {imageSrc ? (
        interactive ? (
          <>
            <img className="adv-viewer-stack-img" src={imageSrc} alt={imageAlt} style={{ opacity }} />
            {clusterVisible && clusterPreviewB64 ? (
              <img
                className="adv-viewer-stack-cluster"
                src={`data:image/png;base64,${clusterPreviewB64}`}
                alt=""
              />
            ) : null}
            {roiOverlay}
          </>
        ) : (
          <img src={imageSrc} alt={imageAlt} style={{ opacity }} />
        )
      ) : (
        <div className="adv-viewer-empty">Sin preview para esta escena.</div>
      )}
    </div>
  );

  return (
    <section className="adv-viewer">
      {!omitSensorTitle ? (
        <div className="adv-viewer-head">
          <strong>{sensorTitle}</strong>
          <span className="adv-date-chip">{dateStr}</span>
        </div>
      ) : (
        <div className="adv-viewer-head adv-viewer-head--compact" aria-hidden="true" />
      )}
      <div className="adv-viewer-controls">
        <select value={selectedIndex} onChange={(e) => onChangeIndex(e.target.value)}>
          {indexSelectContent}
        </select>
        {omitSensorTitle ? <span className="adv-date-chip adv-viewer-controls-date">{dateStr}</span> : null}
        <button type="button" onClick={() => onChangeFrameIdx(Math.max(0, currentIdx - 1))} disabled={currentIdx <= 0}>
          ◀
        </button>
        <button type="button" onClick={onPlayPause}>
          {isPlaying ? "Pause" : "Play"}
        </button>
        {typeof onStop === "function" ? (
          <button type="button" onClick={onStop} title="Detener y volver al inicio">
            Stop
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onChangeFrameIdx(Math.min(Math.max(frames.length - 1, 0), currentIdx + 1))}
          disabled={currentIdx >= frames.length - 1}
        >
          ▶
        </button>
        {showRoi ? (
          <button
            type="button"
            onClick={() => onToggleRoi()}
            className={roiMode ? "adv-btn-active adv-viewer-roi-btn" : "adv-viewer-roi-btn"}
            title={roiMode ? "Modo ROI activo: haz clic para agregar vértices del polígono" : "Activar selección ROI"}
          >
            {roiMode ? "ROI activo" : "ROI"}
          </button>
        ) : null}
        {dualPaneRgb ? (
          <button
            type="button"
            className="adv-viewer-zoom-open-btn"
            onClick={() => setDualZoomOpen(true)}
            title="Ampliar Índice y RGB con zoom sincrónico (rueda del ratón; arrastrar si hay zoom)"
          >
            <svg
              className="adv-viewer-zoom-open-icon"
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              aria-hidden
            >
              <circle cx="10" cy="10" r="6" />
              <path d="M16 16l6 6" />
            </svg>
            Zoom
          </button>
        ) : null}
        {showRoi && roiHasShape && typeof onClearRoi === "function" ? (
          <button
            type="button"
            onClick={() => onClearRoi()}
            className="adv-viewer-roi-btn"
            title="Quitar polígono ROI"
          >
            Limpiar ROI
          </button>
        ) : null}
      </div>
      {dualPaneRgb ? (
        <div className="adv-viewer-media-dual">
          {indexPane}
          {rgbPane}
        </div>
      ) : (
        singleMedia
      )}
      <div className="adv-viewer-timeline">
        <input
          type="range"
          min={0}
          max={Math.max(frames.length - 1, 0)}
          step={1}
          value={Math.min(currentIdx, Math.max(frames.length - 1, 0))}
          onChange={(e) => onChangeFrameIdx(Number(e.target.value))}
          disabled={!frames.length}
        />
        {showTimelineFoot ? (
          <div className="adv-viewer-foot">
            {!hideSceneCounter ? (
              <span>
                Escena {frames.length ? currentIdx + 1 : 0}/{frames.length}
              </span>
            ) : null}
            {!hideOpacityControl ? (
              <label>
                Opacidad
                <input
                  type="range"
                  min={0.1}
                  max={1}
                  step={0.05}
                  value={opacity}
                  onChange={(e) => onOpacity(Number(e.target.value))}
                />
              </label>
            ) : null}
            {typeof onOpenClientVisualization === "function" ? (
              <button
                type="button"
                className="adv-viewer-historic-btn"
                onClick={() => onOpenClientVisualization()}
                title="Abrir la ventana de visualización histórica (Sentinel-1, Sentinel-2, Alta resolución)"
              >
                Visual histórica
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
      {dualZoomOpen && dualPaneRgb ? (
        <div className="adv-viewer-zoom-overlay" role="dialog" aria-modal="true" aria-labelledby="adv-viewer-zoom-title">
          <div className="adv-viewer-zoom-backdrop" onClick={() => setDualZoomOpen(false)} />
          <div className="adv-viewer-zoom-window" onClick={(e) => e.stopPropagation()}>
            <div className="adv-viewer-zoom-header">
              <h3 id="adv-viewer-zoom-title">Índice y RGB — zoom sincrónico</h3>
              <button type="button" className="adv-close-btn" onClick={() => setDualZoomOpen(false)} aria-label="Cerrar">
                ×
              </button>
            </div>
            <p className="adv-viewer-zoom-hint">
              Rueda del ratón para acercar o alejar en cualquier panel. Con zoom, arrastre para mover (ambas vistas a la vez).
            </p>
            {(clusterOptions && clusterOptions.length > 0) || typeof onToggleClusterVisible === "function" ? (
              <div className="adv-timelapse-toolbar adv-viewer-zoom-cluster-row">
                {clusterOptions && clusterOptions.length > 0 ? (
                  <label className="adv-timelapse-toolbar-field">
                    <span className="adv-timelapse-toolbar-label">Cluster</span>
                    <select
                      value={selectedClusterKey || ""}
                      onChange={(e) =>
                        typeof onChangeClusterKey === "function" && onChangeClusterKey(e.target.value)
                      }
                    >
                      {clusterOptions.map((r) => (
                        <option key={r.key} value={r.key}>
                          {r.label || r.key}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {typeof onToggleClusterVisible === "function" ? (
                  <label className="adv-inline-check adv-timelapse-toolbar-check">
                    <input
                      type="checkbox"
                      checked={clusterVisible}
                      onChange={(e) => onToggleClusterVisible(e.target.checked)}
                    />
                    Overlay
                  </label>
                ) : null}
              </div>
            ) : null}
            <div className="adv-viewer-controls adv-viewer-zoom-controls">
              <select value={selectedIndex} onChange={(e) => onChangeIndex(e.target.value)}>
                {indexSelectContent}
              </select>
              <span className="adv-date-chip adv-viewer-controls-date">{dateStr}</span>
              <button
                type="button"
                onClick={() => onChangeFrameIdx(Math.max(0, currentIdx - 1))}
                disabled={currentIdx <= 0}
              >
                ◀
              </button>
              <button type="button" onClick={onPlayPause}>
                {isPlaying ? "Pause" : "Play"}
              </button>
              {typeof onStop === "function" ? (
                <button type="button" onClick={onStop} title="Detener y volver al inicio">
                  Stop
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => onChangeFrameIdx(Math.min(Math.max(frames.length - 1, 0), currentIdx + 1))}
                disabled={currentIdx >= frames.length - 1}
              >
                ▶
              </button>
            </div>
            <div className="adv-viewer-zoom-toolbar">
              <button type="button" onClick={() => setDzScale((z) => Math.max(1, Number((z - 0.2).toFixed(2))))} aria-label="Alejar">
                −
              </button>
              <input
                type="range"
                min={1}
                max={4}
                step={0.05}
                value={dzScale}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setDzScale(v);
                  if (v <= 1.01) setDzPan({ x: 0, y: 0 });
                }}
                aria-label="Nivel de zoom"
              />
              <button type="button" onClick={() => setDzScale((z) => Math.min(4, Number((z + 0.2).toFixed(2))))} aria-label="Acercar">
                +
              </button>
              <button type="button" onClick={resetDualZoom}>
                Reset
              </button>
              <span className="adv-viewer-zoom-pct">{Math.round(dzScale * 100)}%</span>
            </div>
            <div
              className={`adv-viewer-zoom-dual${dzDragging ? " is-dragging" : ""}`}
              onWheel={onDualZoomWheel}
              onMouseDown={onDualPanMouseDown}
              onMouseMove={onDualPanMouseMove}
              onMouseUp={onDualPanMouseUp}
              onMouseLeave={onDualPanMouseUp}
            >
              <div className="adv-viewer-zoom-col adv-viewer-zoom-col--index">
                <span className="adv-viewer-pane-label">Índice</span>
                <div className="adv-viewer-zoom-frame">
                  <div
                    className="adv-viewer-zoom-inner"
                    style={{
                      transform: `translate(${dzPan.x}px, ${dzPan.y}px) scale(${dzScale})`,
                      transformOrigin: "center center",
                    }}
                  >
                    {imageSrc ? (
                      <div className="adv-viewer-zoom-img-stack">
                        <img className="adv-viewer-stack-img" src={imageSrc} alt={imageAlt} style={{ opacity }} draggable={false} />
                        {clusterVisible && clusterPreviewB64 ? (
                          <img
                            className="adv-viewer-stack-cluster"
                            src={`data:image/png;base64,${clusterPreviewB64}`}
                            alt=""
                            draggable={false}
                          />
                        ) : null}
                        {roiOverlay}
                      </div>
                    ) : (
                      <div className="adv-viewer-empty">Sin preview para esta escena.</div>
                    )}
                  </div>
                </div>
              </div>
              <div className="adv-viewer-zoom-col adv-viewer-zoom-col--rgb">
                <span className="adv-viewer-pane-label">{rightPaneLabel}</span>
                <div className="adv-viewer-zoom-frame">
                  <div
                    className="adv-viewer-zoom-inner"
                    style={{
                      transform: `translate(${dzPan.x}px, ${dzPan.y}px) scale(${dzScale})`,
                      transformOrigin: "center center",
                    }}
                  >
                    {rgbImageSrc ? (
                      <div className="adv-viewer-zoom-img-stack">
                        <img className="adv-viewer-rgb-img" src={rgbImageSrc} alt={rgbAlt} draggable={false} />
                      </div>
                    ) : (
                      <div className="adv-viewer-empty">{rgbEmptyMessage}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
