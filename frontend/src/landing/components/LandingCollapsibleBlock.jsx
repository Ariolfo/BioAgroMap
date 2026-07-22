import { useState } from "react";

export default function LandingCollapsibleBlock({
  title,
  titleEmphasis = null,
  blockNum,
  anchorId,
  defaultOpen = true,
  open: controlledOpen,
  onOpenChange,
  children,
}) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;

  const setOpen = (next) => {
    if (onOpenChange) onOpenChange(next);
    else setInternalOpen(next);
  };

  return (
    <section id={anchorId} className="landing-sensor-block landing-theme-block">
      <div className="landing-sensor-block-header landing-theme-block-header">
        <button
          type="button"
          className="landing-sensor-block-toggle"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-label={open ? "Contraer sección" : "Expandir sección"}
        >
          <span className={`landing-sensor-block-chevron${open ? " is-open" : ""}`} aria-hidden>
            ▶
          </span>
        </button>
        <div className="landing-sensor-block-title-wrap">
          {blockNum ? <span className="landing-block-num">{blockNum}</span> : null}
          <h2 className="landing-sensor-block-title">
            {title}
            {titleEmphasis ? (
              <strong className="landing-sensor-block-title-emphasis">{titleEmphasis}</strong>
            ) : null}
          </h2>
        </div>
      </div>
      {open ? <div className="landing-sensor-block-body">{children}</div> : null}
    </section>
  );
}
