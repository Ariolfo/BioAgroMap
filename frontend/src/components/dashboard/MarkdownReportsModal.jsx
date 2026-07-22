import { useCallback, useEffect, useRef, useState } from "react";
import api, { formatApiErrorDetail, setAuthToken } from "../../api";

const SENSOR_LABELS = { PS: "Alta resolución (PS)", S1: "Sentinel 1", S2: "Sentinel 2" };

export default function MarkdownReportsModal({ open, onClose, token, projectId, projectName }) {
  const [files, setFiles] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const loadFiles = useCallback(async () => {
    if (!token || !projectId) return;
    setLoadingList(true);
    try {
      setAuthToken(token);
      const res = await api.get(`/preprocess/landing-markdown-files/${projectId}`);
      setFiles(res.data?.files ?? []);
    } catch (error) {
      setErrorMsg(`Error listando Markdown: ${formatApiErrorDetail(error)}`);
    } finally {
      setLoadingList(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    if (open) {
      setErrorMsg("");
      setStatusMsg("");
      void loadFiles();
    }
    return stopPolling;
  }, [open, loadFiles]);

  async function runUpdate() {
    if (!token || !projectId || generating) return;
    setGenerating(true);
    setErrorMsg("");
    setStatusMsg("Generando los 3 Markdown (PS, S1, S2)…");
    try {
      setAuthToken(token);
      const res = await api.post(`/preprocess/landing-markdown-generate/${projectId}`);
      const taskId = res.data?.task_id;
      if (!taskId) throw new Error("Sin task_id");
      pollRef.current = setInterval(async () => {
        try {
          const st = await api.get(`/preprocess/task-status/${taskId}`);
          const { state, ready, result, error } = st.data || {};
          if (!ready) {
            setStatusMsg(`Generando… (${state})`);
            return;
          }
          stopPolling();
          setGenerating(false);
          if (state === "SUCCESS" && result?.ok) {
            setStatusMsg("Markdown actualizados.");
            void loadFiles();
          } else {
            setStatusMsg("");
            setErrorMsg(result?.message || error || "La generación falló.");
          }
        } catch (pollErr) {
          stopPolling();
          setGenerating(false);
          setStatusMsg("");
          setErrorMsg(`Error consultando estado: ${formatApiErrorDetail(pollErr)}`);
        }
      }, 3000);
    } catch (error) {
      setGenerating(false);
      setStatusMsg("");
      setErrorMsg(`Error: ${formatApiErrorDetail(error)}`);
    }
  }

  async function downloadFile(sensor, name) {
    try {
      setAuthToken(token);
      const res = await api.get(
        `/preprocess/landing-markdown-download/${projectId}?sensor=${encodeURIComponent(sensor)}`,
        { responseType: "blob" }
      );
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setErrorMsg(`Error descargando ${name}: ${formatApiErrorDetail(error)}`);
    }
  }

  if (!open) return null;

  return (
    <div
      className="index-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="markdown-reports-title"
      onClick={() => onClose?.()}
    >
      <div className="index-modal" onClick={(e) => e.stopPropagation()}>
        <div className="index-modal-header">
          <h3 id="markdown-reports-title">
            Markdown narrativos{projectName ? ` — ${projectName}` : ""}
          </h3>
          <button type="button" className="index-modal-close" onClick={() => onClose?.()} aria-label="Cerrar">
            ×
          </button>
        </div>
        <div className="index-modal-body">
          <p className="cluster-meta">
            Exporta la landing narrativa a 3 archivos Markdown autocontenidos (PS, S1 y S2), con
            imágenes embebidas grandes (aprovechando hasta <strong>4.9 MB</strong> por archivo).
          </p>
          <div className="cluster-flow-toolbar">
            <button
              type="button"
              className="indices-run-btn"
              onClick={() => void runUpdate()}
              disabled={generating || !projectId}
            >
              {generating ? "Actualizando…" : "Actualizar"}
            </button>
            <button
              type="button"
              className="rgb-gallery-btn-secondary"
              onClick={() => void loadFiles()}
              disabled={loadingList}
            >
              Recargar lista
            </button>
          </div>
          {statusMsg ? <p className="cluster-meta">{statusMsg}</p> : null}
          {errorMsg ? <p className="cluster-meta" style={{ color: "#c0392b" }}>{errorMsg}</p> : null}
          {files.length ? (
            <table className="markdown-files-table" style={{ width: "100%", marginTop: 12 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>Sensor</th>
                  <th style={{ textAlign: "left" }}>Archivo</th>
                  <th style={{ textAlign: "right" }}>Tamaño</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.name}>
                    <td>{SENSOR_LABELS[f.sensor] || f.sensor}</td>
                    <td>
                      <code>{f.name}</code>
                    </td>
                    <td style={{ textAlign: "right" }}>{f.size_mb} MB</td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        type="button"
                        className="rgb-gallery-btn-secondary"
                        onClick={() => void downloadFile(f.sensor, f.name)}
                      >
                        Descargar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="cluster-meta" style={{ marginTop: 12 }}>
              {loadingList ? "Cargando…" : "Aún no hay Markdown generados. Pulsa «Actualizar»."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
