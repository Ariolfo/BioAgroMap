import { useEffect, useState } from "react";

export default function AuthPanel({
  email,
  setEmail,
  password,
  setPassword,
  loading,
  authStep,
  otpDebug,
  onContinueEmail,
  onVerifyOtp,
  onLogin,
  onResetEmailStep,
}) {
  const [otpLocal, setOtpLocal] = useState("");
  useEffect(() => {
    if (authStep !== "otp") setOtpLocal("");
  }, [authStep]);

  return (
    <div className="auth-simplified">
      <p className="auth-step-hint" role="status" aria-live="polite">
        {loading
          ? "Procesando…"
          : authStep === "email"
            ? "Paso 1: indique su correo. Si es admin, se pedirá contraseña; usuarios cliente usan código."
            : authStep === "password"
              ? "Este correo ya está registrado. Ingrese su contraseña."
              : "Paso 2: introduzca el código de verificación (simulación actual: 12345678)."}
      </p>
      <label>
        Correo electrónico
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="correo@ejemplo.com"
          disabled={loading || authStep === "otp"}
          autoComplete="username"
        />
      </label>

      {authStep === "email" ? (
        <div className="auth-buttons">
          <button type="button" onClick={onContinueEmail} disabled={loading}>
            {loading ? "Comprobando…" : "Continuar"}
          </button>
        </div>
      ) : null}

      {authStep === "password" ? (
        <>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              autoComplete="current-password"
            />
          </label>
          <div className="auth-buttons">
            <button type="button" onClick={onLogin} disabled={loading}>
              Iniciar sesión
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={loading}
              onClick={() => {
                setPassword("");
                onResetEmailStep?.();
              }}
            >
              Cambiar correo
            </button>
          </div>
        </>
      ) : null}

      {authStep === "otp" ? (
        <>
          <p className="auth-otp-hint">Mientras se integra el correo, use el código de verificación: 12345678.</p>
          {otpDebug ? (
            <p className="auth-otp-debug">
              <strong>Modo prueba:</strong> código <code>{otpDebug}</code> (variable LOG_OTP=1 en el servidor)
            </p>
          ) : null}
          <label>
            Código de verificación
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="Código (ej. 12345678)"
              value={otpLocal}
              onChange={(e) => setOtpLocal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && otpLocal.trim()) onVerifyOtp?.(otpLocal.trim());
              }}
            />
          </label>
          <div className="auth-buttons">
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                const v = otpLocal.trim();
                if (v) onVerifyOtp?.(v);
              }}
            >
              {loading ? "Verificando…" : "Verificar código"}
            </button>
            <button type="button" className="btn-secondary" disabled={loading} onClick={() => onResetEmailStep?.()}>
              Cambiar correo
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
