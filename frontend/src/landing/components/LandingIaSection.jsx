import { useEffect, useMemo } from "react";
import DashboardIaAnalysisModal from "../../components/dashboard/DashboardIaAnalysisModal";
import useDashboardIaReport from "../../components/dashboard/useDashboardIaReport";
import { buildLandingIaContext } from "../buildIaContext";
import { sectionKey as narrativeSectionKey } from "../landingSectionKeys";
import LandingSectionNarrative from "./LandingSectionNarrative";

/**
 * Sección 1.7 — Informe técnico.
 * - Admin (editMode): el markdown auto se carga como borrador editable (texto + imágenes).
 * - Cliente / vista publicada: si hay narrativa publicada se muestra; si no, el informe auto.
 */
export default function LandingIaSection({
  projectId,
  projectName,
  adapted,
  extras,
  sensorKey,
  hideTitle = false,
  editMode = false,
  narrative = null,
  token = "",
}) {
  const sectionKey = narrativeSectionKey(sensorKey, "ia");
  const iaContext = useMemo(
    () =>
      buildLandingIaContext({
        projectId,
        projectName,
        adapted,
        extras,
        sensorKey,
      }),
    [projectId, projectName, adapted, extras, sensorKey]
  );

  const { fullReport, reportReady, reportLoading, customError, integralError, isCustom } =
    useDashboardIaReport(iaContext, { enabled: true });

  const draftBody = narrative?.byKey?.[sectionKey]?.draft_body ?? "";
  const displayBody = narrative?.bodyForDisplay?.(sectionKey) ?? "";
  const hasDraft = Boolean(String(draftBody || "").trim());

  useEffect(() => {
    if (!editMode || !narrative?.seedDraftIfEmpty) return;
    if (!reportReady) return;
    if (hasDraft) return;
    narrative.seedDraftIfEmpty(sectionKey, fullReport);
  }, [editMode, narrative, sectionKey, reportReady, fullReport, hasDraft]);

  if (editMode) {
    return (
      <div className="landing-subsection landing-subsection--ia">
        {!hideTitle ? <h3 className="landing-subsection-title">Informe técnico</h3> : null}
        {!hasDraft && reportLoading ? (
          <p className="landing-hint">Generando texto por defecto del informe técnico…</p>
        ) : null}
        {!hasDraft && !reportLoading && !reportReady ? (
          <p className="landing-hint">
            No hay texto automático disponible aún. Puede escribir el informe manualmente abajo.
          </p>
        ) : null}
        {customError || integralError ? (
          <p className="landing-error">
            {customError ||
              (integralError
                ? `Aviso: el análisis multi-escena no se completó (${integralError}). Puede editar el texto base.`
                : null)}
          </p>
        ) : null}
        {hasDraft || (!reportLoading && !reportReady) ? (
          <LandingSectionNarrative
            sectionKey={sectionKey}
            editMode
            draftValue={draftBody}
            onDraftChange={(v) => narrative?.setDraft?.(sectionKey, v)}
            displayBody=""
            disabled={narrative?.saving}
            allowImages
            projectId={projectId}
            token={token}
            label={
              isCustom
                ? "Informe agronómico — texto e imágenes (Markdown)"
                : "Informe técnico (ingeniería agronómica) — texto editable (Markdown)"
            }
          />
        ) : null}
        <p className="landing-hint" style={{ marginTop: 8 }}>
          Este texto se genera automáticamente a partir de los datos del proyecto. Puede editarlo,
          subir o pegar imágenes, y luego guardar/publicar desde el panel de Contenido.
        </p>
      </div>
    );
  }

  // Vista cliente / publicada: narrativa guardada tiene prioridad.
  if (String(displayBody || "").trim()) {
    return (
      <div className="landing-subsection landing-subsection--ia">
        {!hideTitle ? (
          <h3 className="landing-subsection-title">Informe técnico (ingeniería agronómica)</h3>
        ) : null}
        <LandingSectionNarrative
          sectionKey={sectionKey}
          editMode={false}
          displayBody={displayBody}
          token={token}
        />
      </div>
    );
  }

  return (
    <div className="landing-subsection landing-subsection--ia">
      {!hideTitle ? <h3 className="landing-subsection-title">Informe de IA</h3> : null}
      <DashboardIaAnalysisModal open embedded onClose={() => {}} iaContext={iaContext} />
    </div>
  );
}
