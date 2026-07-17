import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, {
  formatApiErrorDetail,
  loadStoredAuth,
  persistAuthTokens,
} from "../api";
import {
  buildLandingMeta,
  isProjectPublished,
  resolveProjectFromParam,
} from "./dataAdapter";
import useLandingProjectData from "./hooks/useLandingProjectData";
import useLandingTexts from "./hooks/useLandingTexts";
import LandingHero from "./components/LandingHero";
import LandingCollapsibleBlock from "./components/LandingCollapsibleBlock";
import LandingTableOfContents from "./components/LandingTableOfContents";
import LandingSensorBlock from "./sections/LandingSensorBlock";
import { LANDING_SENSOR_BLOCKS } from "./sensorBlockConfig";
import { blockAnchor, buildLandingToc, sensorKeyFromAnchor } from "./landingNavConfig";
import { shouldHideIaForClient } from "./landingSectionKeys";
import {
  buildRecorteRgbEndpoint,
  fetchPreviewDataUrl,
  findRecortePathForSceneDate,
  SENSOR_META,
} from "./previewUtils";
import "./landing.css";

function normalizeUserRole(role) {
  const v = String(role || "").trim().toLowerCase();
  if (v === "client") return "cliente";
  return v;
}

/**
 * @param {"client"|"admin-edit"|"admin-preview"} mode
 */
export default function ClientLandingPage({ mode: modeProp }) {
  const { proyectoParam } = useParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(() => loadStoredAuth().access || "");
  const [userRole, setUserRole] = useState("");
  const [projects, setProjects] = useState([]);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [heroSrc, setHeroSrc] = useState("");
  const [openBlocks, setOpenBlocks] = useState({ ps: true, s1: false, s2: false });
  const [tocExpanded, setTocExpanded] = useState(true);
  const [adminViewAsClient, setAdminViewAsClient] = useState(false);

  const isAdminRoute = modeProp === "admin-edit" || modeProp === "admin-preview";
  const roleNorm = normalizeUserRole(userRole);
  const isAdminUser = roleNorm === "admin";

  const editMode = isAdminRoute && isAdminUser && !adminViewAsClient;
  const narrativeView = editMode ? "draft" : "published";

  const project = useMemo(
    () => resolveProjectFromParam(projects, proyectoParam),
    [projects, proyectoParam]
  );
  const projectId = project?.id;

  /** Proyecto 14/palm: sin IA solo en vista cliente. */
  const hideIaSection =
    (!editMode || adminViewAsClient) && shouldHideIaForClient(project);

  const landingToc = useMemo(() => {
    const toc = buildLandingToc();
    if (!hideIaSection) return toc;
    return toc.map((block) => ({
      ...block,
      subsections: (block.subsections || []).filter(
        (s) => !String(s.id || "").endsWith("-ia")
      ),
    }));
  }, [hideIaSection]);

  const { loading, error, adapted, aoiGeojson, extras, getCachedPreview } =
    useLandingProjectData(projectId, token);

  const narrative = useLandingTexts(projectId, token, narrativeView);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      setAuthLoading(true);
      setAuthError("");
      const stored = loadStoredAuth();
      if (!stored.access) {
        setAuthLoading(false);
        setAuthError("Inicie sesión para ver los resultados de su proyecto.");
        return;
      }
      persistAuthTokens(stored.access, stored.refresh);
      setToken(stored.access);
      try {
        const [me, projRes] = await Promise.all([api.get("/auth/me"), api.get("/projects")]);
        if (cancelled) return;
        const role = normalizeUserRole(me.data?.role);
        setUserRole(role);
        setProjects(projRes.data || []);
        if (isAdminRoute && role !== "admin") {
          setAuthError("Solo administradores pueden editar el informe narrativo.");
        }
      } catch (e) {
        if (!cancelled) setAuthError(formatApiErrorDetail(e));
      } finally {
        if (!cancelled) setAuthLoading(false);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [isAdminRoute]);

  const landingMeta = useMemo(() => {
    if (!project) return null;
    if (!adapted) return { ...project, projectName: project.name };
    return buildLandingMeta(project, adapted);
  }, [project, adapted]);

  const blocked =
    !isAdminRoute &&
    normalizeUserRole(userRole) === "cliente" &&
    project &&
    !isProjectPublished(project);

  useEffect(() => {
    if (!projectId || blocked || !adapted) return undefined;
    const psFrames =
      adapted?.sensorData?.ps?.framesByIndex?.NDVI ||
      Object.values(adapted?.sensorData?.ps?.framesByIndex || {})[0];
    const s2Frames =
      adapted?.sensorData?.s2?.framesByIndex?.NDVI ||
      Object.values(adapted?.sensorData?.s2?.framesByIndex || {})[0];
    const frame = psFrames?.[psFrames.length - 1] || s2Frames?.[s2Frames.length - 1];
    if (!frame) return undefined;

    const sensorKey = adapted?.recorteInventory?.ps?.length ? "ps" : "s2";
    const recItems = adapted?.recorteInventory?.[sensorKey] || [];
    const rel = findRecortePathForSceneDate(recItems, frame.date);
    if (!rel) return undefined;

    let cancelled = false;
    (async () => {
      try {
        const pv = SENSOR_META[sensorKey].variant;
        const key = `${projectId}|hero|${pv}|${rel}`;
        const rgb = await getCachedPreview(key, () =>
          fetchPreviewDataUrl(buildRecorteRgbEndpoint(projectId, rel, pv), token)
        );
        if (!cancelled && rgb) setHeroSrc(rgb);
      } catch {
        /* hero optional */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, adapted, blocked, getCachedPreview, token]);

  const kpis = useMemo(() => {
    if (!landingMeta) return [];
    return [
      { label: "Escenas S1", value: landingMeta.sceneCounts?.s1 ?? 0 },
      { label: "Escenas S2", value: landingMeta.sceneCounts?.s2 ?? 0 },
      { label: "Alta resolución", value: landingMeta.sceneCounts?.ps ?? 0 },
      { label: "Periodo", value: landingMeta.dateRangeLabel || "—" },
    ];
  }, [landingMeta]);

  const handleTocNavigate = useCallback((anchorId) => {
    const sensorKey = sensorKeyFromAnchor(anchorId);
    if (sensorKey) {
      setOpenBlocks((prev) => ({ ...prev, [sensorKey]: true }));
    }
    window.setTimeout(() => {
      const el = document.getElementById(anchorId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 120);
  }, []);

  if (authLoading) {
    return (
      <div className="landing-page landing-page--center">
        <p>Cargando su informe…</p>
      </div>
    );
  }

  if (authError || !token) {
    return (
      <div className="landing-page landing-page--center">
        <p>{authError || "Sesión requerida."}</p>
        <Link to="/" className="landing-cta">
          Ir a iniciar sesión
        </Link>
      </div>
    );
  }

  if (isAdminRoute && !isAdminUser) {
    return (
      <div className="landing-page landing-page--center">
        <p>Acceso restringido a administradores.</p>
        <Link to="/" className="landing-cta">
          Volver
        </Link>
      </div>
    );
  }

  if (!authLoading && projects.length && !project) {
    return (
      <div className="landing-page landing-page--center">
        <p>No encontramos el proyecto «{proyectoParam}» en su cuenta.</p>
        <Link to="/" className="landing-cta">
          Volver al inicio
        </Link>
      </div>
    );
  }

  if (blocked) {
    return (
      <div className="landing-page landing-page--center">
        <h1>{project?.name}</h1>
        <p>
          Los resultados aún no están publicados. Cuando el equipo BioAgro los apruebe, podrá verlos
          aquí.
        </p>
        <Link to="/" className="landing-cta">
          Volver
        </Link>
      </div>
    );
  }

  return (
    <div className={`landing-page${editMode ? " landing-page--admin-edit" : ""}`}>
      <div className="landing-content">
        <div className="landing-logo-bar">
          <div className="landing-logo-brand">
            <img src="/logo-bioagro.png" alt="BioAgro" className="landing-logo-img" />
            <p className="landing-logo-tagline">Agricultura más Inteligente con BioAgro</p>
          </div>
          <button
            type="button"
            className="landing-link-btn"
            onClick={() =>
              navigate("/app", {
                state: projectId ? { restoreProjectId: projectId } : undefined,
              })
            }
          >
            Vista técnica
          </button>
        </div>

        {isAdminRoute && isAdminUser ? (
          <div className="landing-admin-banner" role="region" aria-label="Controles de edición narrativa">
            <div className="landing-admin-banner-main">
              <strong>{editMode ? "Edición admin — borradores" : "Vista previa como cliente (textos publicados)"}</strong>
              <span className="landing-admin-banner-hint">
                {narrative.hasUnpublishedDrafts
                  ? "Hay cambios de borrador sin publicar."
                  : "Borrador y publicado coinciden (o no hay textos)."}
              </span>
              {narrative.saveMsg ? <span className="landing-admin-banner-ok">{narrative.saveMsg}</span> : null}
              {narrative.error ? <span className="landing-admin-banner-err">{narrative.error}</span> : null}
            </div>
            <div className="landing-admin-banner-actions">
              <button
                type="button"
                className="landing-admin-btn"
                disabled={narrative.saving}
                onClick={() => setAdminViewAsClient((v) => !v)}
              >
                {adminViewAsClient ? "Volver a editar" : "Ver como cliente"}
              </button>
              {editMode ? (
                <>
                  <button
                    type="button"
                    className="landing-admin-btn landing-admin-btn--primary"
                    disabled={narrative.saving}
                    onClick={() => void narrative.saveDrafts()}
                  >
                    {narrative.saving ? "Guardando…" : "Guardar borradores"}
                  </button>
                  <button
                    type="button"
                    className="landing-admin-btn landing-admin-btn--publish"
                    disabled={narrative.saving}
                    onClick={() => void narrative.publishDrafts()}
                  >
                    Publicar narrativa
                  </button>
                </>
              ) : null}
            </div>
          </div>
        ) : null}

        <LandingHero meta={landingMeta} heroImageSrc={heroSrc} kpis={kpis} />

        {(loading || error) && (
          <div className="landing-status">
            {loading ? <p>Cargando resultados del proyecto…</p> : null}
            {error ? <p className="landing-error">{error}</p> : null}
          </div>
        )}

        {!loading && adapted ? (
          <div className={`landing-body-layout${tocExpanded ? "" : " landing-body-layout--toc-collapsed"}`}>
            <LandingTableOfContents
              toc={landingToc}
              onNavigate={handleTocNavigate}
              expanded={tocExpanded}
              onExpandedChange={setTocExpanded}
            />
            <main className="landing-main">
              {LANDING_SENSOR_BLOCKS.map((block, idx) => (
                <LandingCollapsibleBlock
                  key={block.id}
                  anchorId={blockAnchor(block.id)}
                  blockNum={String(idx + 1)}
                  title={landingToc[idx]?.title || block.title}
                  open={openBlocks[block.id]}
                  onOpenChange={(next) =>
                    setOpenBlocks((prev) => ({ ...prev, [block.id]: next }))
                  }
                >
                  <LandingSensorBlock
                    sensorKey={block.id}
                    projectId={projectId}
                    token={token}
                    projectName={landingMeta?.projectName || project?.name}
                    adapted={adapted}
                    extras={extras}
                    getCachedPreview={getCachedPreview}
                    editMode={editMode}
                    hideIaSection={hideIaSection}
                    narrative={narrative}
                  />
                </LandingCollapsibleBlock>
              ))}
            </main>
          </div>
        ) : null}

        <footer className="landing-footer">
          <p>Agricultura más inteligente con BioAgro</p>
          {aoiGeojson ? (
            <p className="landing-footer-note">
              Polígono del lote cargado desde sus datos de proyecto.
            </p>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
