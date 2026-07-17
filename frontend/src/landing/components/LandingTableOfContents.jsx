import { useCallback, useEffect, useState } from "react";

function TocLinkButton({ entry, activeId, onNavigate }) {
  const isActive = activeId === entry.id;
  const levelClass =
    entry.level === 1
      ? "landing-toc-link--l1"
      : entry.level === 2
        ? "landing-toc-link--l2"
        : "landing-toc-link--l3";

  return (
    <button
      type="button"
      className={`landing-toc-link ${levelClass}${isActive ? " is-active" : ""}`}
      onClick={() => onNavigate(entry.id)}
    >
      {entry.num ? <span className="landing-toc-num">{entry.num}</span> : null}
      <span className="landing-toc-label">{entry.title}</span>
    </button>
  );
}

function TocLink({ entry, activeId, onNavigate }) {
  return (
    <li className={`landing-toc-item landing-toc-item--l${entry.level}`}>
      <TocLinkButton entry={entry} activeId={activeId} onNavigate={onNavigate} />
      {entry.children?.length ? (
        <ul className="landing-toc-sublist">
          {entry.children.map((child) => (
            <TocLink key={child.id} entry={child} activeId={activeId} onNavigate={onNavigate} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function TocBlockSection({ block, activeId, onNavigate, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <li className="landing-toc-block">
      <div className="landing-toc-block-row">
        <button
          type="button"
          className="landing-toc-block-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? "Contraer sección del menú" : "Expandir sección del menú"}
        >
          <span className={`landing-toc-block-chevron${open ? " is-open" : ""}`} aria-hidden>
            ▶
          </span>
        </button>
        <TocLinkButton entry={block} activeId={activeId} onNavigate={onNavigate} />
      </div>
      {open ? (
        <ul className="landing-toc-sublist landing-toc-sublist--sections">
          {block.subsections.map((sub) => (
            <TocLink key={sub.id} entry={sub} activeId={activeId} onNavigate={onNavigate} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export default function LandingTableOfContents({ toc, onNavigate, expanded, onExpandedChange }) {
  const [activeId, setActiveId] = useState("");
  const [internalExpanded, setInternalExpanded] = useState(true);
  const isExpanded = expanded !== undefined ? expanded : internalExpanded;

  const setExpanded = useCallback(
    (next) => {
      if (onExpandedChange) onExpandedChange(next);
      else setInternalExpanded(next);
    },
    [onExpandedChange]
  );

  const handleNavigate = useCallback(
    (id) => {
      onNavigate?.(id);
      setActiveId(id);
      if (!isExpanded) setExpanded(true);
    },
    [onNavigate, isExpanded, setExpanded]
  );

  useEffect(() => {
    const ids = [];
    for (const block of toc) {
      ids.push(block.id);
      for (const sub of block.subsections) {
        ids.push(sub.id);
        if (sub.children) ids.push(...sub.children.map((c) => c.id));
      }
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]?.target?.id) setActiveId(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0, 0.15, 0.4] }
    );

    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [toc]);

  return (
    <nav
      className={`landing-toc${isExpanded ? "" : " landing-toc--collapsed"}`}
      aria-label="Tabla de contenidos del informe"
    >
      <div className="landing-toc-card">
        <div className="landing-toc-card-head">
          {isExpanded ? <h2 className="landing-toc-heading">Contenido</h2> : null}
          <button
            type="button"
            className="landing-toc-panel-toggle"
            onClick={() => setExpanded(!isExpanded)}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? "Contraer menú de contenido" : "Expandir menú de contenido"}
            title={isExpanded ? "Contraer menú" : "Expandir menú"}
          >
            <span className={`landing-toc-panel-chevron${isExpanded ? " is-open" : ""}`} aria-hidden>
              {isExpanded ? "◀" : "▶"}
            </span>
            {!isExpanded ? <span className="landing-toc-collapsed-label">Menú</span> : null}
          </button>
        </div>
        {isExpanded ? (
          <ul className="landing-toc-list">
            {toc.map((block, idx) => (
              <TocBlockSection
                key={block.id}
                block={block}
                activeId={activeId}
                onNavigate={handleNavigate}
                defaultOpen={idx === 0}
              />
            ))}
          </ul>
        ) : null}
      </div>
    </nav>
  );
}
