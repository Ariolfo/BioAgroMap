export default function LandingSectionCard({
  id,
  num,
  title,
  subtitle,
  variant = "mint",
  headingLevel = 3,
  children,
}) {
  const Heading = headingLevel === 2 ? "h2" : headingLevel === 3 ? "h3" : "h4";

  return (
    <article
      id={id}
      className={`landing-theme-card landing-theme-card--${variant}`}
      aria-labelledby={title ? `${id}-title` : undefined}
    >
      {title ? (
        <header className="landing-theme-card-head">
          <div className="landing-section-title-row">
            {num ? <span className="landing-section-num">{num}</span> : null}
            <Heading id={`${id}-title`} className="landing-section-heading">
              {title}
            </Heading>
          </div>
          {subtitle ? <p className="landing-section-subtitle">{subtitle}</p> : null}
        </header>
      ) : null}
      <div className="landing-theme-card-body">{children}</div>
    </article>
  );
}
