import { useEffect, useMemo, useState } from "react";
import api, { formatApiErrorDetail } from "../../api";
import { appendPlanetIntegralAppendix, buildDashboardIaTechnicalReport } from "./dashboardIaAnalysis";

export function DigitalBrainIcon({ className, size = 22 }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M12 3.5c-1.2 0-2.2.55-2.85 1.4-.25-.08-.52-.12-.8-.12-1.1 0-2 .75-2.25 1.75-.85.25-1.45 1-1.45 1.9 0 .45.15.85.4 1.2-.15.35-.25.75-.25 1.15 0 .95.55 1.75 1.35 2.15v.85c0 1.15.9 2.1 2.05 2.1h.15c.55.95 1.55 1.6 2.7 1.6s2.2-.65 2.75-1.6h.2c1.1 0 2-.95 2-2.1v-.85c.85-.4 1.4-1.2 1.4-2.15 0-.4-.1-.8-.25-1.15.25-.35.4-.75.4-1.2 0-.9-.6-1.65-1.45-1.9-.25-1-1.15-1.75-2.25-1.75-.28 0-.55.04-.8.12C14.2 4.05 13.2 3.5 12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinejoin="round"
      />
      <circle cx="9" cy="10" r="0.9" fill="currentColor" />
      <circle cx="15" cy="10" r="0.9" fill="currentColor" />
      <path d="M12 12.2v2.2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path
        d="M6.5 8.5h-1M17.5 8.5h1M7 14.5H6M18 14.5h-1M12 5.5V4"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.85"
      />
    </svg>
  );
}

/** `**negrita**` y `` `código` `` sin asteriscos/backticks sueltos (evita fallos con `**texto:**` etc.). */
function renderReportInline(text, keyPrefix) {
  const s = String(text);
  const out = [];
  let i = 0;
  let part = 0;
  const pushPlain = (from, to) => {
    if (from < to) out.push(<span key={`${keyPrefix}-p-${part++}`}>{s.slice(from, to)}</span>);
  };
  while (i < s.length) {
    if (s.slice(i, i + 2) === "**") {
      const j = s.indexOf("**", i + 2);
      if (j === -1) {
        pushPlain(i, s.length);
        break;
      }
      out.push(
        <strong key={`${keyPrefix}-b-${part++}`} className="adv-ia-strong">
          {s.slice(i + 2, j)}
        </strong>,
      );
      i = j + 2;
      continue;
    }
    if (s[i] === "`") {
      const j = s.indexOf("`", i + 1);
      if (j === -1) {
        pushPlain(i, s.length);
        break;
      }
      out.push(
        <code key={`${keyPrefix}-c-${part++}`} className="adv-ia-code">
          {s.slice(i + 1, j)}
        </code>,
      );
      i = j + 1;
      continue;
    }
    const ns = s.indexOf("**", i);
    const nb = s.indexOf("`", i);
    let next = s.length;
    if (ns >= 0) next = Math.min(next, ns);
    if (nb >= 0) next = Math.min(next, nb);
    pushPlain(i, next);
    i = next;
  }
  return out;
}

function formatBlocks(text) {
  const lines = String(text || "").split("\n");
  const blocks = [];
  let buf = [];
  const flush = () => {
    if (buf.length) {
      blocks.push(buf.join("\n"));
      buf = [];
    }
  };
  for (const line of lines) {
    if (line.startsWith("## ")) {
      flush();
      blocks.push({ type: "h", text: line.slice(3).trim() });
    } else if (line.startsWith("### ")) {
      flush();
      blocks.push({ type: "h3", text: line.slice(4).trim() });
    } else if (line.trim() === "") {
      flush();
    } else {
      buf.push(line);
    }
  }
  flush();
  return blocks;
}

export default function DashboardIaAnalysisModal({ open, onClose, iaContext }) {
  const [planetIntegral, setPlanetIntegral] = useState(null);
  const [integralLoading, setIntegralLoading] = useState(false);
  const [integralError, setIntegralError] = useState("");

  const base = useMemo(() => {
    if (!iaContext) return { report: "", disclaimer: "" };
    return buildDashboardIaTechnicalReport(iaContext);
  }, [iaContext]);

  useEffect(() => {
    if (!open || !iaContext?.projectId) {
      setPlanetIntegral(null);
      setIntegralError("");
      setIntegralLoading(false);
      return undefined;
    }
    let cancelled = false;
    setIntegralLoading(true);
    setIntegralError("");
    setPlanetIntegral(null);
    (async () => {
      try {
        const { data } = await api.get(`/preprocess/dashboard-ia-planet-integral/${iaContext.projectId}`, {
          params: { max_scenes: 48 },
        });
        if (!cancelled) setPlanetIntegral(data);
      } catch (e) {
        if (!cancelled) setIntegralError(formatApiErrorDetail(e));
      } finally {
        if (!cancelled) setIntegralLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, iaContext?.projectId]);

  const fullReport = useMemo(() => {
    let r = base.report;
    if (planetIntegral) r = appendPlanetIntegralAppendix(r, planetIntegral);
    return r;
  }, [base.report, planetIntegral]);

  if (!open) return null;

  const blocks = formatBlocks(fullReport);

  return (
    <div className="adv-ia-overlay" role="dialog" aria-modal="true" aria-labelledby="adv-ia-report-title">
      <div className="adv-ia-backdrop" onClick={onClose} />
      <div className="adv-ia-window adv-ia-window--report">
        <div className="adv-ia-header adv-ia-header--report">
          <div className="adv-ia-header-title">
            <DigitalBrainIcon className="adv-ia-header-icon" size={24} />
            <h3 id="adv-ia-report-title">Informe técnico (ingeniería agronómica)</h3>
          </div>
          <button type="button" className="adv-close-btn" onClick={onClose} aria-label="Cerrar ventana">
            ×
          </button>
        </div>
        <p className="adv-ia-sub adv-ia-sub--report">
          {iaContext?.projectName ? `Proyecto: ${String(iaContext.projectName).trim()}` : null}
        </p>
        <div className="adv-ia-body adv-ia-body--report" role="document">
          {integralLoading ? (
            <p className="adv-ia-integral-status">Analizando todas las escenas Planet en servidor (NDVI, RGB, textura)…</p>
          ) : null}
          {integralError ? (
            <p className="adv-ia-integral-status adv-ia-integral-status--err">
              No se pudo completar el análisis multi-escena: {integralError}
            </p>
          ) : null}
          {blocks.map((b, i) => {
            if (typeof b === "object" && b?.type === "h") {
              return (
                <h4 key={`h-${i}`} className="adv-ia-section-title">
                  {renderReportInline(b.text, `h-${i}`)}
                </h4>
              );
            }
            if (typeof b === "object" && b?.type === "h3") {
              return (
                <h5 key={`h3-${i}`} className="adv-ia-subsection-title">
                  {renderReportInline(b.text, `h3-${i}`)}
                </h5>
              );
            }
            return (
              <p key={`p-${i}`} className="adv-ia-paragraph">
                {String(b).split("\n").map((line, j) => (
                  <span key={j}>
                    {renderReportInline(line, `p-${i}-${j}`)}
                    {j < String(b).split("\n").length - 1 ? <br /> : null}
                  </span>
                ))}
              </p>
            );
          })}
        </div>
      </div>
    </div>
  );
}
