const SMART_SLOTS = [
  {
    slot: 1,
    title: "Smart cluster 1",
    emptyMsg: "Sin mapa smart1. Ejecute el análisis espacio-temporal en el dashboard técnico.",
  },
  {
    slot: 2,
    title: "Smart cluster 2",
    emptyMsg: "Sin mapa smart2. Ejecute el análisis espacio-temporal en el dashboard técnico.",
  },
  {
    slot: 3,
    title: "Smart cluster 3",
    emptyMsg: "Sin mapa smart3. Ejecute el análisis espacio-temporal en el dashboard técnico.",
  },
];

export default function LandingSmartClusterSection({ sensorKey, psStClusters, hideTitle = false }) {
  const isPs = sensorKey === "ps";

  return (
    <div className="landing-subsection landing-subsection--smart">
      {!hideTitle ? <h3 className="landing-subsection-title">Clusters Smart</h3> : null}
      {!isPs ? (
        <p className="landing-hint">
          Los clusters espacio-temporales Smart están disponibles en el bloque de alta resolución (PlanetScope).
        </p>
      ) : (
        <div className="adv-smart-clusters-grid landing-smart-grid">
          {SMART_SLOTS.map((c) => {
            const st = psStClusters?.[c.slot] || {};
            return (
              <div key={c.slot} className="adv-smart-cluster-cell">
                <h4 className="adv-smart-cluster-heading">{c.title}</h4>
                <div className="adv-smart-cluster-frame">
                  {st.error ? (
                    <p className="adv-smart-cluster-msg adv-smart-cluster-msg--err">{st.error}</p>
                  ) : null}
                  {st.busy ? <p className="adv-smart-cluster-msg">Calculando cluster…</p> : null}
                  {!st.busy && st.preview ? (
                    <img className="adv-smart-cluster-map" src={st.preview} alt={c.title} />
                  ) : null}
                  {!st.busy && !st.preview && !st.error ? (
                    <p className="adv-smart-cluster-msg">{c.emptyMsg}</p>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
