import { useEffect, useRef, useState } from "react";
import api, { API_URL, formatApiErrorDetail, loadStoredAuth, setAuthToken } from "../../api";

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

export default function SmartClusterModal({ open, onClose, token, projectId, projectName = "" }) {
  const [busyByPreset, setBusyByPreset] = useState({ smart1: false, smart2: false, smart3: false });
  const [errByPreset, setErrByPreset] = useState({ smart1: "", smart2: "", smart3: "" });
  const [previewByPreset, setPreviewByPreset] = useState({ smart1: "", smart2: "", smart3: "" });
  const [zoomByPreset, setZoomByPreset] = useState({ smart1: 1, smart2: 1, smart3: 1 });
  const [panByPreset, setPanByPreset] = useState({
    smart1: { x: 0, y: 0 },
    smart2: { x: 0, y: 0 },
    smart3: { x: 0, y: 0 },
  });
  const [draggingPreset, setDraggingPreset] = useState("");
  const dragRef = useRef({
    preset: "",
    startX: 0,
    startY: 0,
    panX: 0,
    panY: 0,
  });

  const effectiveToken = token || loadStoredAuth().access || "";

  const loadPreviews = async () => {
    if (!projectId || !effectiveToken) return;
    const base = API_URL.replace(/\/$/, "");
    for (const preset of ["smart1", "smart2", "smart3"]) {
      setBusyByPreset((p) => ({ ...p, [preset]: true }));
      setErrByPreset((p) => ({ ...p, [preset]: "" }));
      try {
        const src = await fetchPreviewObjectUrl(
          `${base}/preprocess/ps-spatiotemporal-cluster-preview/${projectId}?preset=${encodeURIComponent(preset)}`,
          effectiveToken
        );
        setPreviewByPreset((p) => ({ ...p, [preset]: src }));
      } catch {
        setPreviewByPreset((p) => ({ ...p, [preset]: "" }));
      } finally {
        setBusyByPreset((p) => ({ ...p, [preset]: false }));
      }
    }
  };

  const runSmartClusters = async () => {
    if (!projectId || !effectiveToken) return;
    const base = API_URL.replace(/\/$/, "");
    for (const preset of ["smart1", "smart2", "smart3"]) {
      setBusyByPreset((p) => ({ ...p, [preset]: true }));
      setErrByPreset((p) => ({ ...p, [preset]: "" }));
      try {
        if (effectiveToken) setAuthToken(effectiveToken);
        await api.post(
          `/preprocess/ps-spatiotemporal-cluster/${projectId}`,
          { n_clusters: 4, random_state: 42 },
          { params: { preset } }
        );
        const src = await fetchPreviewObjectUrl(
          `${base}/preprocess/ps-spatiotemporal-cluster-preview/${projectId}?preset=${encodeURIComponent(preset)}`,
          effectiveToken
        );
        setPreviewByPreset((p) => ({ ...p, [preset]: src }));
      } catch (e) {
        setErrByPreset((p) => ({ ...p, [preset]: formatApiErrorDetail(e) }));
      } finally {
        setBusyByPreset((p) => ({ ...p, [preset]: false }));
      }
    }
  };

  useEffect(() => {
    if (!open) return;
    void loadPreviews();
  }, [open, projectId, effectiveToken]);

  const beginPan = (preset, e) => {
    if ((zoomByPreset[preset] || 1) <= 1) return;
    dragRef.current = {
      preset,
      startX: e.clientX,
      startY: e.clientY,
      panX: panByPreset[preset]?.x || 0,
      panY: panByPreset[preset]?.y || 0,
    };
    setDraggingPreset(preset);
  };

  const movePan = (e) => {
    const activePreset = dragRef.current.preset;
    if (!activePreset) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    setPanByPreset((prev) => ({
      ...prev,
      [activePreset]: {
        x: dragRef.current.panX + dx,
        y: dragRef.current.panY + dy,
      },
    }));
  };

  const endPan = () => {
    dragRef.current.preset = "";
    setDraggingPreset("");
  };

  if (!open) return null;

  const someBusy = busyByPreset.smart1 || busyByPreset.smart2 || busyByPreset.smart3;

  return (
    <div className="adv-dashboard-overlay" role="dialog" aria-modal="true" aria-label="Smart Cluster">
      <div className="adv-dashboard-backdrop" onClick={onClose} />
      <div className="adv-dashboard-window">
        <div className="adv-dashboard-header">
          <h2>Smart Cluster - {projectName || `Proyecto ${projectId}`}</h2>
          <div className="adv-dashboard-header-actions">
            <button type="button" onClick={() => void loadPreviews()} disabled={someBusy}>
              Recargar
            </button>
            <button type="button" onClick={() => void runSmartClusters()} disabled={someBusy}>
              {someBusy ? "Generando..." : "Generar clusters Smart"}
            </button>
            <button type="button" className="adv-close-btn" onClick={onClose} aria-label="Cerrar">
              x
            </button>
          </div>
        </div>
        <section className="adv-smart-clusters-panel smart-clusters-modal-panel" aria-label="Clusters Smart">
          <div className="adv-smart-clusters-grid smart-clusters-modal-grid">
            {[
              ["smart1", "cluster Smart 1", "Mapa clusters PS preset NDVI, NDRE, NDWI, VARI"],
              ["smart2", "cluster Smart 2", "Mapa clusters PS preset EVI, NDRE, NDWI, VARI"],
              ["smart3", "cluster Smart 3", "Mapa clusters PS preset KNDVI, MCARI, NDWI, VARI"],
            ].map(([preset, title, alt]) => (
              <div key={preset} className="adv-smart-cluster-cell">
                <h4 className="adv-smart-cluster-heading">{title}</h4>
                <div className="smart-cluster-zoom-tools">
                  <button
                    type="button"
                    onClick={() =>
                      setZoomByPreset((p) => ({
                        ...p,
                        [preset]: Math.max(1, Number((p[preset] - 0.25).toFixed(2))),
                      }))
                    }
                    disabled={!previewByPreset[preset]}
                  >
                    -
                  </button>
                  <input
                    type="range"
                    min={1}
                    max={4}
                    step={0.1}
                    value={zoomByPreset[preset]}
                    onChange={(e) =>
                      setZoomByPreset((p) => ({
                        ...p,
                        [preset]: Number(e.target.value),
                      }))
                    }
                    disabled={!previewByPreset[preset]}
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setZoomByPreset((p) => ({
                        ...p,
                        [preset]: Math.min(4, Number((p[preset] + 0.25).toFixed(2))),
                      }))
                    }
                    disabled={!previewByPreset[preset]}
                  >
                    +
                  </button>
                  <button
                    type="button"
                    onClick={() => setZoomByPreset((p) => ({ ...p, [preset]: 1 }))}
                    disabled={!previewByPreset[preset]}
                  >
                    Reset
                  </button>
                  <span>{Math.round((zoomByPreset[preset] || 1) * 100)}%</span>
                </div>
                <div className="adv-smart-cluster-frame">
                  {errByPreset[preset] ? (
                    <p className="adv-smart-cluster-msg adv-smart-cluster-msg--err">{errByPreset[preset]}</p>
                  ) : null}
                  {busyByPreset[preset] ? (
                    <p className="adv-smart-cluster-msg">Calculando cluster...</p>
                  ) : previewByPreset[preset] ? (
                    <div
                      className={`smart-cluster-pan-surface${draggingPreset === preset ? " is-dragging" : ""}`}
                      onMouseDown={(e) => beginPan(preset, e)}
                      onMouseMove={movePan}
                      onMouseUp={endPan}
                      onMouseLeave={endPan}
                    >
                      <img
                        className="adv-smart-cluster-map smart-cluster-map-zoomable"
                        src={previewByPreset[preset]}
                        alt={alt}
                        style={{
                          transform: `translate(${panByPreset[preset]?.x || 0}px, ${panByPreset[preset]?.y || 0}px) scale(${zoomByPreset[preset] || 1})`,
                        }}
                        draggable={false}
                      />
                    </div>
                  ) : (
                    <p className="adv-smart-cluster-msg">Sin mapa disponible.</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
