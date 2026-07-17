import RgbTimeSeriesGallery from "../../components/RgbTimeSeriesGallery";
import { INDEX_CATALOG, INDEX_CATALOG_PS } from "../../components/PreprocessPanel";

export default function LandingEmbeddedGallery({
  projectId,
  token,
  projectName,
  galleryVisualMode,
  pipelineVariant,
  allowedIndexKeys = null,
  initialIndexKey = null,
  sectionTitle = null,
  onActiveIndexChange = null,
  fixedS1Pol = null,
  fixedS1Palette = null,
}) {
  const indexCatalog = pipelineVariant === "ps" ? INDEX_CATALOG_PS : INDEX_CATALOG;

  return (
    <div className="landing-subsection landing-subsection--gallery">
      {sectionTitle ? <h3 className="landing-subsection-title">{sectionTitle}</h3> : null}
      <RgbTimeSeriesGallery
        open
        embedded
        mode="view"
        galleryVisualMode={galleryVisualMode}
        indexCatalog={indexCatalog}
        selectedIndices={[]}
        onSelectedIndicesChange={() => {}}
        onClose={() => {}}
        canEstimate={false}
        projectId={projectId}
        token={token}
        pipelineVariant={pipelineVariant === "s1" ? "s2" : pipelineVariant}
        projectName={projectName}
        allowedIndexKeys={allowedIndexKeys}
        initialIndexKey={initialIndexKey}
        onActiveIndexChange={onActiveIndexChange}
        fixedS1Pol={fixedS1Pol}
        fixedS1Palette={fixedS1Palette}
      />
    </div>
  );
}
