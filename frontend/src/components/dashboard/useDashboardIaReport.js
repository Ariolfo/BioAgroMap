import { useEffect, useMemo, useState } from "react";
import api, { formatApiErrorDetail } from "../../api";
import { appendPlanetIntegralAppendix, buildDashboardIaTechnicalReport } from "./dashboardIaAnalysis";
import { getCustomIaReportUrl } from "./customIaReports";

/**
 * Markdown del informe técnico (auto o personalizado Palma) + apéndice Planet.
 * Usado por el modal del dashboard y por la sección 1.7 de la landing (editable).
 */
export default function useDashboardIaReport(iaContext, { enabled = true } = {}) {
  const [planetIntegral, setPlanetIntegral] = useState(null);
  const [integralLoading, setIntegralLoading] = useState(false);
  const [integralError, setIntegralError] = useState("");
  const [customMarkdown, setCustomMarkdown] = useState("");
  const [customLoading, setCustomLoading] = useState(false);
  const [customError, setCustomError] = useState("");

  const customReportUrl = useMemo(
    () =>
      iaContext
        ? getCustomIaReportUrl({
            projectId: iaContext.projectId,
            projectName: iaContext.projectName,
          })
        : null,
    [iaContext?.projectId, iaContext?.projectName]
  );

  const base = useMemo(() => {
    if (!iaContext || customReportUrl) return { report: "", disclaimer: "" };
    return buildDashboardIaTechnicalReport(iaContext);
  }, [iaContext, customReportUrl]);

  useEffect(() => {
    if (!enabled || !iaContext?.projectId || customReportUrl) {
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
  }, [enabled, iaContext?.projectId, customReportUrl]);

  useEffect(() => {
    if (!enabled || !customReportUrl) {
      setCustomMarkdown("");
      setCustomError("");
      setCustomLoading(false);
      return undefined;
    }
    let cancelled = false;
    setCustomLoading(true);
    setCustomError("");
    (async () => {
      try {
        const res = await fetch(`${customReportUrl}?v=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`No se pudo cargar el informe (${res.status})`);
        const text = await res.text();
        if (!cancelled) setCustomMarkdown(text);
      } catch (e) {
        if (!cancelled) setCustomError(e?.message || "Error al cargar el informe");
      } finally {
        if (!cancelled) setCustomLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled, customReportUrl]);

  const fullReport = useMemo(() => {
    if (customReportUrl) return customMarkdown;
    let r = base.report;
    if (planetIntegral) r = appendPlanetIntegralAppendix(r, planetIntegral);
    return r;
  }, [customReportUrl, customMarkdown, base.report, planetIntegral]);

  const isCustom = !!customReportUrl;
  const reportLoading = customLoading || (!isCustom && integralLoading);
  const reportReady = Boolean(String(fullReport || "").trim()) && !reportLoading && !customError;

  return {
    fullReport,
    base,
    isCustom,
    customReportUrl,
    reportLoading,
    reportReady,
    integralLoading,
    integralError,
    customLoading,
    customError,
    planetIntegral,
  };
}
