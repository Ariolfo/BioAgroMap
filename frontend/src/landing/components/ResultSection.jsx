export default function ResultSection({
  title,
  subtitle,
  badge,
  visual,
  interpretation,
  howToRead,
  action,
  id,
  className = "",
}) {
  return (
    <section className={`landing-result-section ${className}`.trim()} id={id}>
      <header className="landing-result-header">
        <div>
          {badge ? <span className="landing-result-badge">{badge}</span> : null}
          <h2 className="landing-result-title">{title}</h2>
          {subtitle ? <p className="landing-result-subtitle">{subtitle}</p> : null}
        </div>
      </header>
      {visual ? <div className="landing-result-visual">{visual}</div> : null}
      <div className="landing-result-copy">
        {interpretation ? (
          <div className="landing-result-block">
            <h3>¿Qué significa esto?</h3>
            <p>{interpretation}</p>
          </div>
        ) : null}
        {howToRead ? (
          <div className="landing-result-block landing-result-how">
            <h3>Cómo leer los colores</h3>
            <p>{howToRead}</p>
          </div>
        ) : null}
        {action ? (
          <div className="landing-result-block landing-result-action">
            <h3>¿Qué hacer?</h3>
            <p>{action}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
