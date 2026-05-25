import { useCallback, useEffect, useRef, useState } from "react";
import api, { API_URL, formatApiErrorDetail, loadStoredAuth, setAuthToken } from "../../api";
import { SoilClusterSampleBars, SoilFcmSampleTriangles, SoilQCurveChart } from "./SmartSoilModal";

async function fetchPreviewObjectUrl(fullUrl, token) {
  const url = String(fullUrl || "").trim();
  if (!url) throw new Error("URL de preview vacia");
  const { access } = loadStoredAuth();
  const tok = access || token;
  if (tok) setAuthToken(tok);
  const resp = await api.get(url, { responseType: "blob" });
  const blob = resp?.data instanceof Blob ? resp.data : new Blob([resp?.data ?? ""]);
  if (!blob || blob.size <= 0) throw new Error("Preview vacio");
  const ab = await blob.arrayBuffer();
  const bytes = new Uint8Array(ab);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return `data:image/png;base64,${btoa(binary)}`;
}

function safeRevoke(url) {
  if (url && String(url).startsWith("blob:")) URL.revokeObjectURL(url);
}

export default function ClientSoilViewModal({
  open,
  onClose,
  token,
  projectId,
  projectName = "",
  initialVariant = "fast",
}) {
  const effectiveToken = token || loadStoredAuth().access || "";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [variants, setVariants] = useState([]);
  const [activeVariant, setActiveVariant] = useState("fast");
  const [saved, setSaved] = useState(null);
  const [imgs, setImgs] = useState({ dem: "", cv: "", fcm: "", aspect: "", slope: "" });
  const imgUrlsRef = useRef({ dem: "", cv: "", fcm: "", aspect: "", slope: "" });

  const [soilClusterZoom, setSoilClusterZoom] = useState(1);
  const [soilClusterPan, setSoilClusterPan] = useState({ x: 0, y: 0 });
  const [soilClusterDragging, setSoilClusterDragging] = useState(false);
  const [soilClusterNaturalSize, setSoilClusterNaturalSize] = useState({ w: 0, h: 0 });
  const soilDragRef = useRef({ dragging: false, startX: 0, startY: 0, panX: 0, panY: 0 });

  const revokeAllImgs = useCallback(() => {
    const b = imgUrlsRef.current || {};
    for (const u of Object.values(b)) safeRevoke(u);
    imgUrlsRef.current = { dem: "", cv: "", fcm: "", aspect: "", slope: "" };
    setImgs({ dem: "", cv: "", fcm: "", aspect: "", slope: "" });
  }, []);

  const soilClusterViewW =
    soilClusterNaturalSize.w || Number(saved?.raster_shape?.width) || 0;
  const soilClusterViewH =
    soilClusterNaturalSize.h || Number(saved?.raster_shape?.height) || 0;

  const soilSamplingPlan = saved
    ? {
        samples_per_cluster: saved.samples_per_cluster,
        samples_requested_per_cluster: saved.samples_requested_per_cluster,
        total_samples: saved.total_samples,
        total_samples_placed: saved.total_samples_placed,
        total_samples_inferred: saved.total_samples_inferred,
        sample_points: saved.sample_points,
        raster_shape: saved.raster_shape,
        n_clusters: saved.n_clusters,
        fishnet_step: saved.fishnet_step,
        cv_run: saved.cv_run,
        window_size: saved.window_size,
      }
    : null;

  const soilVars = saved?.terrain || {};
  const soilQCurve = saved?.q_curve ?? null;
  const nClusters = Math.max(2, Number(saved?.n_clusters) || 2);
  const cvEngineSlug = String(saved?.cv_engine_slug || activeVariant || "fast");
  const isMat = cvEngineSlug === "matlab" || activeVariant === "matlab";
  const cmap = String(saved?.cv_colormap || "jet");
  const ws = Number(saved?.window_size) || "—";

  useEffect(() => {
    setSoilClusterNaturalSize({ w: 0, h: 0 });
  }, [imgs.fcm]);

  useEffect(() => {
    if (!open || !projectId || !effectiveToken) {
      setVariants([]);
      setSaved(null);
      setError("");
      revokeAllImgs();
      return undefined;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        setAuthToken(effectiveToken);
        const { data: summaryRes } = await api.get(`/preprocess/soilplus-saved-summary/${projectId}`);
        const vList = [];
        const vars = summaryRes?.variants || {};
        if (vars.fast) vList.push("fast");
        if (vars.matlab) vList.push("matlab");
        if (cancelled) return;
        setVariants(vList);
        const pick =
          vList.includes(initialVariant) ? initialVariant : vList[0] || "fast";
        setActiveVariant(pick);
      } catch (e) {
        if (!cancelled) setError(formatApiErrorDetail(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, projectId, effectiveToken, initialVariant, revokeAllImgs]);

  useEffect(() => {
    if (!open || !projectId || !effectiveToken || !variants.length) return undefined;
    let cancelled = false;
    const vk = activeVariant;
    if (!variants.includes(vk)) return undefined;

    (async () => {
      setLoading(true);
      setError("");
      revokeAllImgs();
      try {
        setAuthToken(effectiveToken);
        const { data: json } = await api.get(`/preprocess/soilplus-saved-json/${projectId}`, {
          params: { variant: vk },
        });
        if (cancelled) return;
        setSaved(json || null);
        const base = API_URL.replace(/\/$/, "");
        const kinds = ["dem", "cv", "fcm", "aspect", "slope"];
        const next = { dem: "", cv: "", fcm: "", aspect: "", slope: "" };
        for (const k of kinds) {
          try {
            next[k] = await fetchPreviewObjectUrl(
              `${base}/preprocess/soilplus-saved-img/${projectId}?variant=${vk}&kind=${k}`,
              effectiveToken
            );
          } catch {
            next[k] = "";
          }
        }
        if (cancelled) {
          for (const u of Object.values(next)) safeRevoke(u);
          return;
        }
        imgUrlsRef.current = next;
        setImgs(next);
        setSoilClusterZoom(1);
        setSoilClusterPan({ x: 0, y: 0 });
      } catch (e) {
        if (!cancelled) {
          setSaved(null);
          setError(formatApiErrorDetail(e));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, projectId, effectiveToken, activeVariant, variants, revokeAllImgs]);

  const handleSoilClusterWheel = (e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    setSoilClusterZoom((prev) => {
      const next = Math.max(1, Math.min(6, Number((prev + delta).toFixed(2))));
      if (next === 1) setSoilClusterPan({ x: 0, y: 0 });
      return next;
    });
  };

  const handleSoilClusterMouseDown = (e) => {
    if (!imgs.fcm) return;
    soilDragRef.current = {
      dragging: true,
      startX: e.clientX,
      startY: e.clientY,
      panX: soilClusterPan.x,
      panY: soilClusterPan.y,
    };
    setSoilClusterDragging(true);
  };

  const handleSoilClusterMouseMove = (e) => {
    if (!soilDragRef.current.dragging) return;
    const dx = e.clientX - soilDragRef.current.startX;
    const dy = e.clientY - soilDragRef.current.startY;
    setSoilClusterPan({ x: soilDragRef.current.panX + dx, y: soilDragRef.current.panY + dy });
  };

  const handleSoilClusterMouseUp = () => {
    if (!soilDragRef.current.dragging) return;
    soilDragRef.current.dragging = false;
    setSoilClusterDragging(false);
  };

  if (!open) return null;

  return (
    <div className="adv-soilplus-overlay" role="dialog" aria-modal="true" aria-label="Smart Soil — visualización">
      <div className="adv-soilplus-backdrop" onClick={onClose} />
      <div className="adv-soilplus-window adv-client-soil-view-window">
        <div className="adv-soilplus-header">
          <h3>Smart Soil — resultados guardados (solo lectura)</h3>
          <button type="button" className="adv-close-btn" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </div>
        <p className="adv-soilplus-note">
          Vista ampliada de los mapas DEM, CV, FCM, aspecto y pendiente publicados para{" "}
          <strong>{projectName || `proyecto ${projectId}`}</strong>. Sin edición ni ejecución en servidor.
        </p>
        {variants.length > 1 ? (
          <div className="adv-client-soil-variant-tabs" role="tablist" aria-label="Variante Fast o Mat">
            {variants.map((vk) => (
              <button
                key={vk}
                type="button"
                role="tab"
                aria-selected={activeVariant === vk}
                className={activeVariant === vk ? "adv-client-soil-tab active" : "adv-client-soil-tab"}
                onClick={() => setActiveVariant(vk)}
                disabled={loading}
              >
                {vk === "matlab" ? "Mat (CV.m)" : "Fast"}
              </button>
            ))}
          </div>
        ) : null}
        {error ? (
          <p className="adv-soilplus-badge adv-soilplus-badge--err" role="alert">
            {error}
          </p>
        ) : null}
        {loading && !saved ? <p className="adv-smart-cluster-msg">Cargando resultados…</p> : null}
        {saved ? (
          <>
            <div className="adv-soilplus-window-scroll">
              <div className="adv-soilplus-top-row">
                <section className="adv-soilplus-card adv-soilplus-card--dem-top">
                  <h4>DEM de entrada (band_1.img)</h4>
                  <p className="adv-soilplus-dem-meta">
                    {`windowSize: ${ws} | Media DEM: ${Number(saved.dem_mean_snapshot || 0).toFixed(3)} | Std: — | Min: — | Max: — | CV mean: ${Number(
                      saved.cv_mean_snapshot || 0
                    ).toFixed(4)} ${
                      saved.roi_polygon_applied
                        ? `(ROI ${saved.roi_pixel_count ?? 0} px; DEM ROI μ ${Number(saved.dem_roi_mean_snapshot || 0).toFixed(3)})`
                        : "(toda la mascara DEM)"
                    }${
                      soilVars.f1 != null
                        ? ` | f1 ${Number(soilVars.f1).toFixed(4)} | f2 ${Number(soilVars.f2).toFixed(4)} | f3 ${Number(soilVars.f3).toFixed(4)}`
                        : ""
                    }`}
                  </p>
                  <div className="adv-soilplus-image-frame adv-soilplus-image-frame--dem-roi">
                    {imgs.dem ? (
                      <img src={imgs.dem} alt="DEM guardado" className="adv-soilplus-image" />
                    ) : (
                      <p className="adv-soilplus-image-empty">Sin DEM guardado.</p>
                    )}
                  </div>
                </section>
                <section className="adv-soilplus-card adv-soilplus-card--final-zoning">
                  <h4>Zonificación final — FCM sobre CV (K={nClusters})</h4>
                  <p className="adv-soilplus-dem-meta">
                    Clases difusas (exponente m=2) sobre CV normalizado; triángulos = muestras en píxeles del raster.
                    Ctrl + rueda para zoom; arrastre para desplazar.
                  </p>
                  <div className="adv-soilplus-zoom-tools">
                    <button
                      type="button"
                      onClick={() =>
                        setSoilClusterZoom((z) => {
                          const next = Math.max(1, Number((z - 0.25).toFixed(2)));
                          if (next === 1) setSoilClusterPan({ x: 0, y: 0 });
                          return next;
                        })
                      }
                      disabled={!imgs.fcm}
                    >
                      −
                    </button>
                    <input
                      type="range"
                      min={1}
                      max={4}
                      step={0.1}
                      value={soilClusterZoom}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        setSoilClusterZoom(next);
                        if (next === 1) setSoilClusterPan({ x: 0, y: 0 });
                      }}
                      disabled={!imgs.fcm}
                    />
                    <button
                      type="button"
                      onClick={() => setSoilClusterZoom((z) => Math.min(4, Number((z + 0.25).toFixed(2))))}
                      disabled={!imgs.fcm}
                    >
                      +
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSoilClusterZoom(1);
                        setSoilClusterPan({ x: 0, y: 0 });
                      }}
                      disabled={!imgs.fcm}
                    >
                      Reset
                    </button>
                    <span>{Math.round(soilClusterZoom * 100)}%</span>
                  </div>
                  <div
                    className={`adv-soilplus-image-frame adv-soilplus-image-frame--cluster adv-soilplus-cluster-scroll${soilClusterDragging ? " is-dragging" : ""}${soilClusterZoom > 1.01 ? " allow-pan-overflow" : ""}`}
                    onWheel={handleSoilClusterWheel}
                    onMouseDown={handleSoilClusterMouseDown}
                    onMouseMove={handleSoilClusterMouseMove}
                    onMouseUp={handleSoilClusterMouseUp}
                    onMouseLeave={handleSoilClusterMouseUp}
                  >
                    {imgs.fcm ? (
                      <div
                        className="adv-soilplus-cluster-zoom-inner"
                        style={{
                          transform: `translate(${soilClusterPan.x}px, ${soilClusterPan.y}px) scale(${soilClusterZoom})`,
                          transformOrigin: "center center",
                        }}
                      >
                        <div className="adv-soilplus-cluster-img-lock">
                          <img
                            src={imgs.fcm}
                            alt="Zonificación FCM sobre CV"
                            className={`adv-soilplus-image adv-soilplus-image--zoomable${soilClusterDragging ? " is-dragging" : ""}`}
                            draggable={false}
                            onLoad={(e) => {
                              const im = e.currentTarget;
                              setSoilClusterNaturalSize({ w: im.naturalWidth, h: im.naturalHeight });
                            }}
                          />
                          <SoilFcmSampleTriangles
                            points={soilSamplingPlan?.sample_points}
                            viewWidth={soilClusterViewW}
                            viewHeight={soilClusterViewH}
                          />
                        </div>
                      </div>
                    ) : (
                      <p className="adv-soilplus-image-empty">Sin imagen FCM.</p>
                    )}
                  </div>
                </section>
              </div>
              <div className="adv-soilplus-bottom-strip">
                <section className="adv-soilplus-card adv-soilplus-thumb">
                  <h4>
                    CV local ({cmap}) · {isMat ? "Mat" : "Fast"}
                  </h4>
                  <p className="adv-soilplus-dem-meta">Coef. variación (ventana {ws}).</p>
                  <div className="adv-soilplus-image-frame">
                    {imgs.cv ? (
                      <img src={imgs.cv} alt="CV local" className="adv-soilplus-image" />
                    ) : (
                      <p className="adv-soilplus-image-empty">Sin CV.</p>
                    )}
                  </div>
                </section>
                <section className="adv-soilplus-card adv-soilplus-thumb">
                  <h4>Aspecto (°)</h4>
                  <p className="adv-soilplus-dem-meta">Paleta HSV cíclica.</p>
                  <div className="adv-soilplus-image-frame">
                    {imgs.aspect ? (
                      <img src={imgs.aspect} alt="Aspecto terreno" className="adv-soilplus-image" />
                    ) : (
                      <p className="adv-soilplus-image-empty">Sin aspecto.</p>
                    )}
                  </div>
                </section>
                <section className="adv-soilplus-card adv-soilplus-thumb">
                  <h4>Pendiente (°)</h4>
                  <p className="adv-soilplus-dem-meta">Paleta inferno.</p>
                  <div className="adv-soilplus-image-frame">
                    {imgs.slope ? (
                      <img src={imgs.slope} alt="Pendiente terreno" className="adv-soilplus-image" />
                    ) : (
                      <p className="adv-soilplus-image-empty">Sin pendiente.</p>
                    )}
                  </div>
                </section>
                <section className="adv-soilplus-card adv-soilplus-thumb">
                  <h4>Muestras por cluster</h4>
                  <p className="adv-soilplus-dem-meta">
                    {soilSamplingPlan
                      ? `Colocadas ${soilSamplingPlan.total_samples_placed ?? soilSamplingPlan.total_samples}${
                          soilSamplingPlan.total_samples_placed !== soilSamplingPlan.total_samples
                            ? ` (objetivo ${soilSamplingPlan.total_samples})`
                            : ""
                        }`
                      : "—"}
                  </p>
                  {soilSamplingPlan?.samples_per_cluster ? (
                    <SoilClusterSampleBars
                      samples={soilSamplingPlan.samples_per_cluster}
                      totalSamples={
                        soilSamplingPlan.total_samples_placed ??
                        soilSamplingPlan.total_samples ??
                        (Number(saved?.total_samples) > 0 ? Number(saved.total_samples) : 1)
                      }
                      clusterCount={nClusters}
                      thumb
                    />
                  ) : (
                    <p className="adv-soilplus-image-empty">Sin datos de barras.</p>
                  )}
                </section>
                <section className="adv-soilplus-card adv-soilplus-thumb">
                  <h4>Paso 3 — curva Q (K = 2…11)</h4>
                  <p className="adv-soilplus-dem-meta">FCM sobre CV en ROI; Q = 1 − Σ n_k·var_k / (N·var total).</p>
                  <div className="adv-soilplus-image-frame adv-soilplus-image-frame--qchart">
                    <SoilQCurveChart data={soilQCurve} />
                  </div>
                </section>
              </div>
            </div>
          </>
        ) : !loading && !error ? (
          <p className="adv-smart-cluster-msg">No hay resultados Soil+ guardados para este proyecto.</p>
        ) : null}
      </div>
    </div>
  );
}
