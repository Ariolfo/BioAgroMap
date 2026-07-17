const FINDINGS = [
  "Ciclo estacional marcado: máximo vigor junio-julio (precipitación ~18-24 mm, T ~28°C), mínimo enero-marzo (precipitación <2 mm, T >30°C, máxima radiación).",
  "Se confirman vacíos permanentes en el dosel (palmas muertas) mediante cruce temporal: puntos rojos en RSTRUCTURE que persisten tanto en pico seco como en pico húmedo.",
  "Los vacíos muestran expansión progresiva entre enero 2025 y marzo 2026 con patrón radial, sugiriendo causa fitosanitaria (Pudrición de Cogollo o Marchitez Letal).",
  "El NDWI revela déficit hídrico estructural incluso en lluvias, consistente con suelos arenosos de la altillanura.",
  "El NDRE confirma zonificación norte-sur permanente: la mitad norte tiene mejor contenido de clorofila que la mitad sur en todas las fechas.",
  "La comparación interanual (ene-mar 2025 vs ene-mar 2026) muestra mayor área estresada y vacíos expandidos en el segundo ciclo.",
];

export default function LandingKeyFindingsBox() {
  return (
    <aside className="landing-key-findings-box" aria-label="Hallazgos principales">
      <h4 className="landing-key-findings-title">Hallazgos principales</h4>
      <ol className="landing-key-findings-list">
        {FINDINGS.map((text) => (
          <li key={text.slice(0, 48)}>{text}</li>
        ))}
      </ol>
    </aside>
  );
}
