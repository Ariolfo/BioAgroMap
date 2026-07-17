export default function LandingHero({ meta, heroImageSrc, kpis = [] }) {
  return (
    <header className="landing-hero">
      <div className="landing-hero-grid">
        <div className="landing-hero-copy">
          <h1 className="landing-hero-title">{meta?.projectName || "Su lote"}</h1>
          <p className="landing-hero-lead">
            Resultados satelitales de su cultivo, explicados en lenguaje claro para decidir dónde actuar.
          </p>
          {kpis.length ? (
            <div className="landing-kpi-row">
              {kpis.map((k) => (
                <div key={k.label} className="landing-kpi-card">
                  <span className="landing-kpi-value">{k.value}</span>
                  <span className="landing-kpi-label">{k.label}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="landing-hero-visual">
          {heroImageSrc ? (
            <img src={heroImageSrc} alt="Vista satelital reciente del lote" className="landing-hero-image" />
          ) : (
            <div className="landing-hero-placeholder">Vista satelital del lote</div>
          )}
        </div>
      </div>
    </header>
  );
}
