import LandingEmbeddedGallery from "../components/LandingEmbeddedGallery";
import LandingIndexGroupGallery from "../components/LandingIndexGroupGallery";
import LandingTimelapseSeriesPanel from "../components/LandingTimelapseSeriesPanel";
import LandingClusterSection from "../components/LandingClusterSection";
import LandingSmartClusterSection from "../components/LandingSmartClusterSection";
import LandingSoilSection from "../components/LandingSoilSection";
import LandingIaSection from "../components/LandingIaSection";
import LandingS1SigmaTheoryBox from "../components/LandingS1SigmaTheoryBox";
import LandingSectionCard from "../components/LandingSectionCard";
import LandingSectionNarrative from "../components/LandingSectionNarrative";
import { indexKeysForLandingGroup, LANDING_INDEX_GROUPS } from "../interpretations";
import {
  getSectionMeta,
  interactiveSectionSubtitle,
  rgbSectionSubtitle,
  sectionAnchor,
  sensorShowsAgrogeofisica,
  sensorShowsIa,
  sensorShowsSmartClusters,
} from "../landingNavConfig";
import { sectionKey as narrativeSectionKey } from "../landingSectionKeys";
import {
  indexGalleryModeForSensor,
  pipelineVariantForSensor,
  rgbGalleryModeForSensor,
} from "../sensorBlockConfig";

const INDEX_VARIANTS = ["leaf", "sage", "mint", "fern"];

function NarrativeSlot({
  sensorKey,
  suffix,
  editMode,
  narrative,
  projectId = null,
  token = "",
  label,
}) {
  const key = narrativeSectionKey(sensorKey, suffix);
  return (
    <LandingSectionNarrative
      sectionKey={key}
      editMode={editMode}
      draftValue={narrative?.byKey?.[key]?.draft_body ?? ""}
      onDraftChange={(v) => narrative?.setDraft?.(key, v)}
      displayBody={narrative?.bodyForDisplay?.(key) ?? ""}
      disabled={narrative?.saving}
      allowImages={Boolean(editMode)}
      projectId={projectId}
      token={token}
      label={label}
    />
  );
}

export default function LandingSensorBlock({
  sensorKey,
  projectId,
  token,
  projectName,
  adapted,
  extras,
  getCachedPreview,
  editMode = false,
  hideIaSection = false,
  narrative = null,
}) {
  const pipelineVariant = pipelineVariantForSensor(sensorKey);
  const rgbMode = rgbGalleryModeForSensor(sensorKey);
  const indexMode = indexGalleryModeForSensor(sensorKey);

  const meta = (suffix) => getSectionMeta(sensorKey, suffix);
  const showIa = !hideIaSection && sensorShowsIa(sensorKey);
  const showSmart = sensorShowsSmartClusters(sensorKey);
  const showAgro = sensorShowsAgrogeofisica(sensorKey);

  return (
    <div className="landing-sensor-sections">
      <LandingSectionCard
        id={sectionAnchor(sensorKey, "interactive")}
        num={meta("interactive")?.num}
        title={meta("interactive")?.title}
        subtitle={interactiveSectionSubtitle(sensorKey)}
        variant="mint"
        headingLevel={3}
      >
        <LandingTimelapseSeriesPanel
          sensorKey={sensorKey}
          projectId={projectId}
          token={token}
          adapted={adapted}
          extras={extras}
          getCachedPreview={getCachedPreview}
          onReloadSeries={(selection) => extras?.reloadSeries?.(selection)}
          hideTitle
        />
        <NarrativeSlot
          sensorKey={sensorKey}
          suffix="interactive"
          editMode={editMode}
          narrative={narrative}
          projectId={projectId}
          token={token}
        />
      </LandingSectionCard>

      <LandingSectionCard
        id={sectionAnchor(sensorKey, "rgb")}
        num={meta("rgb")?.num}
        title={meta("rgb")?.title}
        subtitle={rgbSectionSubtitle(sensorKey)}
        variant="sage"
        headingLevel={3}
      >
        {sensorKey === "s1" ? (
          <div className="landing-s1-sigma-galleries">
            <div className="landing-s1-sigma-block">
              <LandingEmbeddedGallery
                projectId={projectId}
                token={token}
                projectName={projectName}
                galleryVisualMode="s1-vv"
                pipelineVariant={pipelineVariant}
                fixedS1Pol="vv"
                fixedS1Palette="jet"
              />
              <LandingS1SigmaTheoryBox pol="vv" />
              <NarrativeSlot
                sensorKey={sensorKey}
                suffix="rgb-vv"
                editMode={editMode}
                narrative={narrative}
                projectId={projectId}
                token={token}
                label="Narrativa Visual VV (Markdown)"
              />
            </div>
            <div className="landing-s1-sigma-block">
              <LandingEmbeddedGallery
                projectId={projectId}
                token={token}
                projectName={projectName}
                galleryVisualMode="s1-vv"
                pipelineVariant={pipelineVariant}
                fixedS1Pol="vh"
                fixedS1Palette="jet"
              />
              <LandingS1SigmaTheoryBox pol="vh" />
              <NarrativeSlot
                sensorKey={sensorKey}
                suffix="rgb-vh"
                editMode={editMode}
                narrative={narrative}
                projectId={projectId}
                token={token}
                label="Narrativa Visual VH (Markdown)"
              />
            </div>
          </div>
        ) : (
          <>
            <LandingEmbeddedGallery
              projectId={projectId}
              token={token}
              projectName={projectName}
              galleryVisualMode={rgbMode}
              pipelineVariant={pipelineVariant}
            />
            <NarrativeSlot
              sensorKey={sensorKey}
              suffix="rgb"
              editMode={editMode}
              narrative={narrative}
              projectId={projectId}
              token={token}
            />
          </>
        )}
      </LandingSectionCard>

      <LandingSectionCard
        id={sectionAnchor(sensorKey, "indices")}
        num={meta("indices")?.num}
        title={meta("indices")?.title}
        subtitle="Índices agrupados por función agronómica."
        variant="fern"
        headingLevel={3}
      >
        <div className="landing-index-groups">
          {LANDING_INDEX_GROUPS.map((group, gi) => {
            const keys = indexKeysForLandingGroup(group.id, sensorKey);
            if (!keys.length) return null;
            const groupMeta = getSectionMeta(sensorKey, group.id);
            return (
              <LandingSectionCard
                key={group.id}
                id={sectionAnchor(sensorKey, group.id)}
                num={groupMeta?.num}
                title={group.title}
                subtitle={group.meaning}
                variant={INDEX_VARIANTS[gi % INDEX_VARIANTS.length]}
                headingLevel={4}
              >
                <LandingIndexGroupGallery
                  sensorKey={sensorKey}
                  projectId={projectId}
                  token={token}
                  projectName={projectName}
                  galleryVisualMode={indexMode}
                  pipelineVariant={pipelineVariant}
                  allowedIndexKeys={keys}
                  initialIndexKey={keys[0]}
                  editMode={editMode}
                  narrative={narrative}
                />
              </LandingSectionCard>
            );
          })}
        </div>
      </LandingSectionCard>

      <LandingSectionCard
        id={sectionAnchor(sensorKey, "clusters")}
        num={meta("clusters")?.num}
        title={meta("clusters")?.title}
        variant="sage"
        headingLevel={3}
      >
        <LandingClusterSection
          sensorKey={sensorKey}
          clusterData={extras?.clusterBySensor?.[sensorKey]}
          loading={extras?.clustersLoading}
          error={extras?.clustersError}
          hideTitle
        />
        <NarrativeSlot
          sensorKey={sensorKey}
          suffix="clusters"
          editMode={editMode}
          narrative={narrative}
          projectId={projectId}
          token={token}
        />
      </LandingSectionCard>

      {showSmart ? (
        <LandingSectionCard
          id={sectionAnchor(sensorKey, "smart-clusters")}
          num={meta("smart-clusters")?.num}
          title={meta("smart-clusters")?.title}
          variant="mint"
          headingLevel={3}
        >
          <LandingSmartClusterSection
            sensorKey={sensorKey}
            psStClusters={extras?.psStClusters}
            hideTitle
          />
          <NarrativeSlot
            sensorKey={sensorKey}
            suffix="smart-clusters"
            editMode={editMode}
            narrative={narrative}
            projectId={projectId}
            token={token}
          />
        </LandingSectionCard>
      ) : null}

      {showAgro ? (
        <LandingSectionCard
          id={sectionAnchor(sensorKey, "agrogeofisica")}
          num={meta("agrogeofisica")?.num}
          title={meta("agrogeofisica")?.title}
          variant="leaf"
          headingLevel={3}
        >
          <LandingSoilSection
            projectId={projectId}
            token={token}
            clientSoilSummary={extras?.clientSoilSummary}
            clientSoilImgUrls={extras?.clientSoilImgUrls}
            loading={extras?.soilLoading}
            error={extras?.soilError}
            hideTitle
          />
          <NarrativeSlot
            sensorKey={sensorKey}
            suffix="agrogeofisica"
            editMode={editMode}
            narrative={narrative}
            projectId={projectId}
            token={token}
          />
        </LandingSectionCard>
      ) : null}

      {showIa ? (
        <LandingSectionCard
          id={sectionAnchor(sensorKey, "ia")}
          num={meta("ia")?.num}
          title={`${meta("ia")?.title || "Informe inteligente"} basado en tus datos y comportamiento de tu lote o finca`}
          variant="fern"
          headingLevel={3}
        >
          <LandingIaSection
            projectId={projectId}
            projectName={projectName}
            adapted={adapted}
            extras={extras}
            sensorKey={sensorKey}
            hideTitle
            editMode={editMode}
            narrative={narrative}
            token={token}
          />
        </LandingSectionCard>
      ) : null}
    </div>
  );
}
