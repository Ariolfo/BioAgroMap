import { useEffect, useState } from "react";
import api, { setAuthToken } from "../api";

const ACTION_LABELS = {
  user_created: "Usuario creado",
  user_deactivated: "Usuario inactivado",
  user_reactivated: "Usuario reactivado",
  user_deleted: "Usuario eliminado",
  role_changed: "Rol modificado",
};

function formatAction(a) {
  return ACTION_LABELS[a] || a;
}

export default function UserManagementModal({
  open,
  token,
  onClose,
  onStatusMessage,
}) {
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingLog, setLoadingLog] = useState(false);
  const [savingUserId, setSavingUserId] = useState(null);
  const [error, setError] = useState("");
  const [createName, setCreateName] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createRole, setCreateRole] = useState("cliente");
  const [creating, setCreating] = useState(false);
  const [createSuccess, setCreateSuccess] = useState(null);

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      setAuthToken(token);
      const res = await api.get("/auth/users");
      setUsers(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Error al cargar usuarios");
    } finally {
      setLoading(false);
    }
  }

  async function loadAuditLog() {
    setLoadingLog(true);
    setError("");
    try {
      setAuthToken(token);
      const res = await api.get("/auth/users/audit-log");
      setAuditLog(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Error al cargar el log");
    } finally {
      setLoadingLog(false);
    }
  }

  useEffect(() => {
    if (!open || !token) return;
    let cancelled = false;
    (async () => {
      if (!cancelled) await loadUsers();
    })();
    return () => {
      cancelled = true;
    };
  }, [open, token]);

  useEffect(() => {
    if (!open || !token || tab !== "log") return;
    let cancelled = false;
    (async () => {
      if (!cancelled) await loadAuditLog();
    })();
    return () => {
      cancelled = true;
    };
  }, [open, token, tab]);

  async function updateRole(userId, role) {
    setSavingUserId(userId);
    setError("");
    try {
      setAuthToken(token);
      const res = await api.patch(`/auth/users/${userId}/role`, { role });
      const newRole = String(res.data?.role || role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
      onStatusMessage?.(`Rol actualizado: usuario #${userId} -> ${newRole}`);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "No se pudo actualizar el rol");
    } finally {
      setSavingUserId(null);
    }
  }

  async function setUserActive(userId, isActive) {
    setSavingUserId(userId);
    setError("");
    try {
      setAuthToken(token);
      await api.patch(`/auth/users/${userId}/active`, { is_active: isActive });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_active: isActive } : u)),
      );
      onStatusMessage?.(isActive ? "Usuario reactivado" : "Usuario inactivado");
      if (tab === "log") await loadAuditLog();
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "No se pudo cambiar el estado");
    } finally {
      setSavingUserId(null);
    }
  }

  async function deleteUser(userId, email) {
    if (!window.confirm(`Eliminar definitivamente a ${email}? Esta acción queda registrada en el log.`)) {
      return;
    }
    setSavingUserId(userId);
    setError("");
    try {
      setAuthToken(token);
      await api.delete(`/auth/users/${userId}`);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
      onStatusMessage?.("Usuario eliminado");
      if (tab === "log") await loadAuditLog();
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "No se pudo eliminar");
    } finally {
      setSavingUserId(null);
    }
  }

  async function handleCreateUser(e) {
    e.preventDefault();
    const name = createName.trim();
    const email = createEmail.trim();
    if (!name || !email) {
      setError("Nombre y correo son obligatorios");
      return;
    }
    setCreating(true);
    setError("");
    setCreateSuccess(null);
    try {
      setAuthToken(token);
      const res = await api.post("/auth/users", {
        full_name: name,
        email,
        role: createRole,
      });
      const data = res.data || {};
      setCreateSuccess({
        email: data.email,
        temporary_password: data.temporary_password,
      });
      setCreateName("");
      setCreateEmail("");
      setCreateRole("cliente");
      await loadUsers();
      if (tab === "log") await loadAuditLog();
      onStatusMessage?.("Usuario creado (revise la contraseña temporal mostrada abajo)");
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : err?.message || "No se pudo crear el usuario");
    } finally {
      setCreating(false);
    }
  }

  if (!open) return null;

  return (
    <div className="index-modal-overlay" role="dialog" aria-modal="true">
      <div className="rgb-gallery-backdrop" onClick={onClose} />
      <div className="index-modal user-mgmt-modal">
        <div className="index-modal-header">
          <h3>Gestión de usuarios</h3>
          <button type="button" className="index-modal-close" onClick={onClose} aria-label="Cerrar">
            &times;
          </button>
        </div>
        <div className="user-mgmt-tabs">
          <button
            type="button"
            className={tab === "users" ? "user-mgmt-tab active" : "user-mgmt-tab"}
            onClick={() => setTab("users")}
          >
            Usuarios
          </button>
          <button
            type="button"
            className={tab === "log" ? "user-mgmt-tab active" : "user-mgmt-tab"}
            onClick={() => setTab("log")}
          >
            Log de auditoría
          </button>
        </div>
        <div className="index-modal-body user-mgmt-body">
          {error ? <p className="status-msg">{error}</p> : null}

          {tab === "users" ? (
            <>
              <form className="user-mgmt-create" onSubmit={handleCreateUser}>
                <div className="user-mgmt-create-title">Crear usuario (admin o cliente)</div>
                <div className="user-mgmt-create-grid">
                  <label>
                    Nombre
                    <input
                      type="text"
                      value={createName}
                      onChange={(ev) => setCreateName(ev.target.value)}
                      placeholder="Nombre completo"
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    Correo
                    <input
                      type="email"
                      value={createEmail}
                      onChange={(ev) => setCreateEmail(ev.target.value)}
                      placeholder="correo@ejemplo.com"
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    Rol
                    <select value={createRole} onChange={(ev) => setCreateRole(ev.target.value)}>
                      <option value="cliente">cliente</option>
                      <option value="admin">admin</option>
                    </select>
                  </label>
                </div>
                <button type="submit" className="user-mgmt-create-submit" disabled={creating}>
                  {creating ? "Creando…" : "Crear usuario"}
                </button>
              </form>
              {createSuccess ? (
                <div className="user-mgmt-temp-pw">
                  <strong>Contraseña temporal</strong> (cópiela ahora; no se volverá a mostrar):{" "}
                  <code>{createSuccess.temporary_password}</code>
                  <div className="user-mgmt-temp-pw-email">Correo: {createSuccess.email}</div>
                </div>
              ) : null}

              {loading ? <p className="projects-empty">Cargando usuarios...</p> : null}
              {!loading && users.length === 0 ? <p className="projects-empty">No hay usuarios para mostrar.</p> : null}
              {!loading && users.length > 0 ? (
                <ul className="user-mgmt-list">
                  {users.map((u) => (
                    <li key={u.id} className="user-mgmt-item">
                      <div className="user-mgmt-item-main">
                        <div className="user-mgmt-name">{u.full_name || "—"}</div>
                        <div className="user-mgmt-email">{u.email}</div>
                        <div className="user-mgmt-meta">
                          ID {u.id} · tenant {u.tenant_id}
                          {u.created_at ? ` · creado ${u.created_at}` : ""}
                          <span className={u.is_active ? "user-mgmt-badge active" : "user-mgmt-badge inactive"}>
                            {u.is_active ? "activo" : "inactivo"}
                          </span>
                        </div>
                      </div>
                      <div className="user-mgmt-item-actions">
                        <select
                          value={u.role || "cliente"}
                          disabled={savingUserId === u.id}
                          onChange={(e) => updateRole(u.id, e.target.value)}
                        >
                          <option value="cliente">cliente</option>
                          <option value="admin">admin</option>
                        </select>
                        {u.is_active ? (
                          <button
                            type="button"
                            className="user-mgmt-btn secondary"
                            disabled={savingUserId === u.id}
                            onClick={() => setUserActive(u.id, false)}
                          >
                            Inactivar
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="user-mgmt-btn secondary"
                            disabled={savingUserId === u.id}
                            onClick={() => setUserActive(u.id, true)}
                          >
                            Reactivar
                          </button>
                        )}
                        <button
                          type="button"
                          className="user-mgmt-btn danger"
                          disabled={savingUserId === u.id}
                          onClick={() => deleteUser(u.id, u.email)}
                        >
                          Eliminar
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <>
              <div className="user-mgmt-log-toolbar">
                <button type="button" className="user-mgmt-btn secondary" onClick={loadAuditLog} disabled={loadingLog}>
                  {loadingLog ? "Actualizando…" : "Actualizar log"}
                </button>
              </div>
              {loadingLog ? <p className="projects-empty">Cargando log…</p> : null}
              {!loadingLog && auditLog.length === 0 ? (
                <p className="projects-empty">Aún no hay entradas en el log.</p>
              ) : null}
              {!loadingLog && auditLog.length > 0 ? (
                <ul className="user-mgmt-audit-list">
                  {auditLog.map((row) => (
                    <li key={row.id} className="user-mgmt-audit-item">
                      <div className="user-mgmt-audit-when">{row.created_at}</div>
                      <div className="user-mgmt-audit-action">{formatAction(row.action)}</div>
                      <div className="user-mgmt-audit-meta">
                        actor #{row.actor_user_id ?? "—"} · objetivo #{row.target_user_id ?? "—"}
                      </div>
                      {row.details && Object.keys(row.details).length > 0 ? (
                        <pre className="user-mgmt-audit-details">{JSON.stringify(row.details, null, 2)}</pre>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
