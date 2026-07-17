const RECOMMENDATIONS = [
  "Inspección fitosanitaria inmediata de los 5 focos de mortalidad identificados.",
  "Vuelo con dron multiespectral (<5 cm/px) para conteo individual de palmas muertas.",
  "Manejo diferenciado por zona: fertilización reforzada KCl + kieserita priorizando la zona sur.",
  "Coberturas vivas y mulch de tusas para retención hídrica.",
];

export default function LandingCriticalRecommendationsBox() {
  return (
    <aside className="landing-critical-recommendations-box" aria-label="Recomendaciones críticas">
      <h4 className="landing-critical-recommendations-title">Recomendaciones críticas</h4>
      <ol className="landing-critical-recommendations-list">
        {RECOMMENDATIONS.map((text) => (
          <li key={text.slice(0, 48)}>{text}</li>
        ))}
      </ol>
    </aside>
  );
}
