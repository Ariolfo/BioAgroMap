import { useEffect, useState } from "react";
import api, { setAuthToken } from "../api";
import OrderPreviewMap from "./OrderPreviewMap";

const STATUS_OPTS = [
  { value: "pendiente", label: "Pendiente" },
  { value: "en proceso", label: "En proceso" },
  { value: "completado", label: "Completado" },
];

export default function AdminStudyOrdersModal({ open, token, onClose, onStatusMessage }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState(null);
  const [saving, setSaving] = useState(false);

  async function loadList() {
    setLoading(true);
    setError("");
    try {
      setAuthToken(token);
      const res = await api.get("/study-orders");
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Error al cargar órdenes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open || !token) return;
    loadList();
  }, [open, token]);

  async function openDetail(id) {
    setError("");
    try {
      setAuthToken(token);
      const res = await api.get(`/study-orders/${id}`);
      setDetail(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Error al cargar detalle");
    }
  }

  async function saveStatus(newStatus) {
    if (!detail) return;
    setSaving(true);
    setError("");
    try {
      setAuthToken(token);
      const res = await api.patch(`/study-orders/${detail.id}`, { status: newStatus });
      setDetail(res.data);
      setRows((prev) => prev.map((r) => (r.id === detail.id ? { ...r, status: newStatus } : r)));
      onStatusMessage?.(`Estado actualizado: orden #${detail.id}`);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "No se pudo guardar");
    } finally {
      setSaving(false);
    }
  }

  async function approvePublish() {
    if (!detail?.project_id) return;
    setSaving(true);
    setError("");
    try {
      setAuthToken(token);
      await api.patch(`/projects/${detail.project_id}/status`, { status: "publicado" });
      onStatusMessage?.(`Proyecto #${detail.project_id} publicado`);
      await openDetail(detail.id);
      await loadList();
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "No se pudo publicar");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <div className="index-modal-overlay" role="dialog" aria-modal="true">
      <div className="rgb-gallery-backdrop" onClick={onClose} />
      <div className="index-modal user-mgmt-modal orders-modal">
        <div className="index-modal-header">
          <h3>{detail ? `Orden #${detail.id}` : "Órdenes AgroGeoFísico"}</h3>
          <button type="button" className="index-modal-close" onClick={onClose} aria-label="Cerrar">
            &times;
          </button>
        </div>
        <div className="index-modal-body user-mgmt-body">
          {error ? <p className="status-msg">{error}</p> : null}

          {!detail ? (
            <>
              <div className="orders-toolbar">
                <button type="button" className="user-mgmt-btn secondary" onClick={loadList} disabled={loading}>
                  {loading ? "Cargando…" : "Actualizar"}
                </button>
              </div>
              {loading && rows.length === 0 ? <p className="projects-empty">Cargando…</p> : null}
              {!loading && rows.length === 0 ? <p className="projects-empty">No hay solicitudes.</p> : null}
              {rows.length > 0 ? (
                <ul className="orders-list">
                  {rows.map((r) => (
                    <li key={r.id} className="orders-row">
                      <div>
                        <div className="orders-email">{r.user_email}</div>
                        <div className="orders-meta">
                          #{r.id} · proyecto: {r.project_name || r.project_id || "—"} · {r.created_at} · cultivo: {r.crop || "—"} ·{" "}
                          <span className="orders-status">{r.status}</span>
                        </div>
                      </div>
                      <button type="button" className="user-mgmt-btn secondary" onClick={() => openDetail(r.id)}>
                        Ver detalle
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <div className="order-detail">
              <button type="button" className="user-mgmt-btn secondary order-back" onClick={() => setDetail(null)}>
                ← Lista
              </button>
              <div className="order-detail-grid">
                <div className="order-detail-mapwrap">
                  <OrderPreviewMap key={detail.id} geojson={detail.geometry} />
                </div>
                <div className="order-detail-fields">
                  <p>
                    <strong>Correo usuario:</strong> {detail.user_email}
                  </p>
                  <p>
                    <strong>Proyecto:</strong> {detail.project_name || detail.project_id || "—"}
                  </p>
                  <p>
                    <strong>Nombre:</strong> {detail.applicant_name}
                  </p>
                  <p>
                    <strong>Celular:</strong> {detail.applicant_phone}
                  </p>
                  <p>
                    <strong>Empresa:</strong> {detail.company || "—"}
                  </p>
                  <p>
                    <strong>Fechas estudio:</strong> {detail.study_date_start} → {detail.study_date_end}
                  </p>
                  <p>
                    <strong>Cultivo:</strong> {detail.crop || "—"}
                  </p>
                  <p>
                    <strong>Edad:</strong> {detail.age_years != null ? detail.age_years : "—"}
                  </p>
                  <p>
                    <strong>Meteorológicos:</strong> {detail.has_weather_data ? "Sí" : "No"}
                  </p>
                  <p>
                    <strong>Suelo:</strong> {detail.has_soil_data ? "Sí" : "No"}
                  </p>
                  <p>
                    <strong>Notas:</strong> {detail.extra_notes || "—"}
                  </p>
                  <p>
                    <strong>Solicitud:</strong> {detail.created_at}
                  </p>
                  <label className="order-status-edit">
                    Estado
                    <select
                      value={detail.status}
                      disabled={saving}
                      onChange={(ev) => saveStatus(ev.target.value)}
                    >
                      {STATUS_OPTS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="user-mgmt-btn secondary"
                    disabled={saving || !detail.project_id}
                    onClick={approvePublish}
                    title="Aprobar para publicar resultados al cliente"
                  >
                    Aprobar para publicar
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
