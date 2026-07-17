import { copyForIndex } from "../interpretations";

/**
 * Lectura teórica del índice activo (fuera del lienzo de miniaturas, dentro de la tarjeta).
 */
export default function LandingIndexTheoryBox({ indexKey }) {
  const copy = copyForIndex(indexKey);
  const label = String(indexKey || "").toUpperCase() || "Índice";

  return (
    <aside className="landing-index-theory" aria-live="polite">
      <h5 className="landing-index-theory-title">
        {copy.title || label}{" "}
        <strong className="landing-index-theory-badge">(Explicación teórica)</strong>
      </h5>
      {copy.legendLow || copy.legendHigh ? (
        <p className="landing-index-theory-legend">
          <span>
            <strong>Bajo:</strong> {copy.legendLow || "valores bajos"}
          </span>
          <span className="landing-index-theory-legend-sep" aria-hidden>
            ·
          </span>
          <span>
            <strong>Alto:</strong> {copy.legendHigh || "valores altos"}
          </span>
        </p>
      ) : null}
      <p className="landing-index-theory-body">{copy.theory || copy.interpretation}</p>
      {copy.howToRead ? (
        <p className="landing-index-theory-howto">
          <strong>Cómo leerlo:</strong> {copy.howToRead}
        </p>
      ) : null}
    </aside>
  );
}
