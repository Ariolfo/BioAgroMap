import { useMemo, useState } from "react";

function isoDateFromClusterResult(row) {
  const haystack = [row?.output_basename, row?.source_basename, row?.label, row?.key]
    .filter(Boolean)
    .join(" ");
  const isoLike = haystack.match(/(\d{4})[-_]?(\d{2})[-_]?(\d{2})/);
  if (isoLike) {
    const [, y, m, d] = isoLike;
    return `${y}-${m}-${d}`;
  }
  const shortLike = haystack.match(/(\d{2})[-/](\d{2})[-/](\d{2})/);
  if (shortLike) {
    const [, d, m, yy] = shortLike;
    return `20${yy}-${m}-${d}`;
  }
  return null;
}

function formatIsoToDdMmYyyy(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function clusterMultibandTitle(row, sensor) {
  const base = row?.output_basename ?? row?.key ?? "—";
  if (sensor !== "s2") return base;
  const iso = isoDateFromClusterResult(row);
  const ddmmyyyy = formatIsoToDdMmYyyy(iso);
  return ddmmyyyy ? `${base} · ${ddmmyyyy}` : base;
}

function sortClusterResultsByDate(rows) {
  return [...rows].sort((a, b) => {
    const da = isoDateFromClusterResult(a);
    const db = isoDateFromClusterResult(b);
    if (da && db) {
      const c = da.localeCompare(db);
      if (c !== 0) return c;
    } else if (da) return -1;
    else if (db) return 1;
    return String(a?.output_basename || a?.key || "").localeCompare(
      String(b?.output_basename || b?.key || "")
    );
  });
}

export default function LandingClusterSection({ sensorKey, clusterData, loading, error, hideTitle = false }) {
  const [clusterZoom, setClusterZoom] = useState(100);

  const gmmIndexResults = useMemo(
    () => clusterData?.results?.filter((r) => r.kind === "index") ?? [],
    [clusterData]
  );
  const gmmMultibandResults = useMemo(() => {
    const raw = clusterData?.results?.filter((r) => r.kind === "multiband") ?? [];
    return sensorKey === "s2" ? sortClusterResultsByDate(raw) : raw;
  }, [clusterData, sensorKey]);

  const hasResults = gmmIndexResults.length > 0 || gmmMultibandResults.length > 0;

  return (
    <div className="landing-subsection landing-subsection--cluster">
      {!hideTitle ? <h3 className="landing-subsection-title">Clusters GMM</h3> : null}
      {loading ? <p className="landing-hint">Cargando clusters…</p> : null}
      {error ? <p className="landing-error">{error}</p> : null}
      {!loading && !error && !hasResults ? (
        <p className="landing-hint">No hay resultados GMM para este sensor en el proyecto.</p>
      ) : null}
      {hasResults ? (
        <>
          <div
            className="cluster-zoom-toolbar cluster-zoom-toolbar--single-line landing-cluster-toolbar"
            role="group"
            aria-label="Zoom de las vistas"
          >
            <span className="cluster-zoom-label">Zoom</span>
            <button
              type="button"
              className="cluster-zoom-btn"
              aria-label="Reducir zoom"
              onClick={() => setClusterZoom((z) => Math.max(50, z - 10))}
            >
              −
            </button>
            <input
              className="cluster-zoom-range"
              type="range"
              min={50}
              max={200}
              step={5}
              value={clusterZoom}
              onChange={(e) => setClusterZoom(Number(e.target.value))}
            />
            <span className="cluster-zoom-pct">{clusterZoom}%</span>
            <button
              type="button"
              className="cluster-zoom-reset"
              onClick={() => setClusterZoom(100)}
            >
              100%
            </button>
          </div>
          <div className="landing-cluster-embed">
            <div className="cluster-results-zoom-inner" style={{ zoom: clusterZoom / 100 }}>
              {gmmIndexResults.length ? (
                <>
                  <h4 className="cluster-results-section-title">Índices espectrales</h4>
                  <div className="cluster-gmm-grid cluster-gmm-grid--row1">
                    {gmmIndexResults.map((r) => (
                      <div key={r.key} className="cluster-gmm-tile">
                        <h5 className="cluster-gmm-tile-title">
                          <code>{clusterMultibandTitle(r, sensorKey)}</code>
                          <span className="cluster-gmm-k"> · K={r.k_used ?? "—"}</span>
                        </h5>
                        <p className="cluster-meta">{r.label}</p>
                        {r.preview_png_base64 ? (
                          <img
                            className="cluster-elbow-img"
                            alt={`Clusters ${r.key}`}
                            src={`data:image/png;base64,${r.preview_png_base64}`}
                          />
                        ) : null}
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
              {gmmMultibandResults.length ? (
                <>
                  <h4 className="cluster-results-section-title">
                    {sensorKey === "s2"
                      ? "Recortes multibanda (4 bandas originales)"
                      : "Recortes multibanda (6+ bandas)"}
                  </h4>
                  <div className="cluster-gmm-grid">
                    {gmmMultibandResults.map((r) => (
                      <div key={r.key} className="cluster-gmm-tile">
                        <h5 className="cluster-gmm-tile-title">
                          <code>{r.output_basename ?? r.key}</code>
                          <span className="cluster-gmm-k"> · K={r.k_used ?? "—"}</span>
                        </h5>
                        {r.preview_png_base64 ? (
                          <img
                            className="cluster-elbow-img"
                            alt={`Clusters ${r.key}`}
                            src={`data:image/png;base64,${r.preview_png_base64}`}
                          />
                        ) : null}
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
