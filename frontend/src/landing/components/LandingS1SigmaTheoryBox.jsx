const COPY = {
  vv: {
    title: "VV — polarización co-polar (σ⁰ dB)",
    legendLow: "superficie más lisa, agua abierta, suelo desnudo o vegetación rala",
    legendHigh: "superficie más rugosa, estructuras verticales o dosel denso / húmedo",
    theory:
      "La retrodispersión VV es el eco radar recibido en la misma polarización vertical en la que se emitió. En cultivos y pastos, valores altos suelen asociarse a mayor rugosidad o biomasa estructural; valores bajos, a coberturas más abiertas o superficies lisas. Comparar fechas del mismo lote: la escala de color es relativa a cada escena.",
    howToRead:
      "Azul/cian (bajo) → menos retorno VV; amarillo/rojo (alto) → más retorno VV en esa fecha.",
  },
  vh: {
    title: "VH — polarización cruzada (σ⁰ dB)",
    legendLow: "poca dispersión de volumen (suelo expuesto, cultivo joven o coberturas ralas)",
    legendHigh: "mayor dispersión de volumen (dosel más denso, biomasa o estructura foliar)",
    theory:
      "La retrodispersión VH (cruzada) es especialmente sensible a la dispersión de volumen en la vegetación. En contextos agrícolas, VH alto suele indicar más biomasa o dosel más desarrollado; VH bajo, menos volumen de vegetación o superficies más simples. Como en VV, interprete tendencias temporales más que un umbral absoluto fijo.",
    howToRead:
      "Azul/cian (bajo) → menos retorno VH; amarillo/rojo (alto) → más retorno VH en esa fecha.",
  },
};

/**
 * Lectura teórica de sigma0 VV/VH debajo del mosaico S1 en la landing.
 */
export default function LandingS1SigmaTheoryBox({ pol = "vv" }) {
  const key = String(pol).toLowerCase() === "vh" ? "vh" : "vv";
  const copy = COPY[key];

  return (
    <aside className="landing-index-theory" aria-live="polite">
      <h5 className="landing-index-theory-title">
        {copy.title}{" "}
        <strong className="landing-index-theory-badge">(Explicación teórica)</strong>
      </h5>
      <p className="landing-index-theory-legend">
        <span>
          <strong>Bajo:</strong> {copy.legendLow}
        </span>
        <span className="landing-index-theory-legend-sep" aria-hidden>
          ·
        </span>
        <span>
          <strong>Alto:</strong> {copy.legendHigh}
        </span>
      </p>
      <p className="landing-index-theory-body">{copy.theory}</p>
      <p className="landing-index-theory-howto">
        <strong>Cómo leerlo:</strong> {copy.howToRead}
      </p>
    </aside>
  );
}
