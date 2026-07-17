import { useMemo } from "react";
import DashboardIaAnalysisModal from "../../components/dashboard/DashboardIaAnalysisModal";
import { buildLandingIaContext } from "../buildIaContext";

export default function LandingIaSection({
  projectId,
  projectName,
  adapted,
  extras,
  sensorKey,
  hideTitle = false,
}) {
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

  return (
    <div className="landing-subsection landing-subsection--ia">
      {!hideTitle ? <h3 className="landing-subsection-title">Informe de IA</h3> : null}
      <DashboardIaAnalysisModal
        open
        embedded
        onClose={() => {}}
        iaContext={iaContext}
      />
    </div>
  );
}
