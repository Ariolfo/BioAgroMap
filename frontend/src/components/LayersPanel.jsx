import { useMemo } from "react";

export default function LayersPanel({
  mapLayers,
  onToggleVisibility,
  onZoomToLayer,
  onHideLayer,
}) {
  const vectorLayers = useMemo(
    () => mapLayers.filter((l) => l.kind === "vector"),
    [mapLayers]
  );

  return (
    <div className="layers-panel">
      <div className="layers-panel-header">
        <span>Capas ({vectorLayers.length})</span>
      </div>
      <ul className="layers-list">
        {vectorLayers.length === 0 ? (
          <li className="layers-empty">Sin capas cargadas</li>
        ) : (
          vectorLayers.map((l) => {
            const label = l.displayName || l.name;
            return (
            <li key={l.id} className="layers-item">
              <input
                type="checkbox"
                checked={l.visible}
                onChange={() => onToggleVisibility(l.id)}
                aria-label={`Mostrar/ocultar ${label}`}
              />
              <span className={`layers-badge ${l.kind}`}>
                {l.kind === "vector" ? "V" : "R"}
              </span>
              <span className="layers-name" title={label}>
                {label}
              </span>
              <button
                className="layers-zoom"
                title="Zoom a capa"
                onClick={() => onZoomToLayer(l.id)}
              >
                &#8982;
              </button>
              <button
                type="button"
                className="layers-remove"
                title="Ocultar en el mapa (la capa sigue en el proyecto)"
                onClick={() => onHideLayer(l.id)}
              >
                &times;
              </button>
            </li>
            );
          })
        )}
      </ul>
    </div>
  );
}
