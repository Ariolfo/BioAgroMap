import { LANDING_SENSOR_BLOCKS } from "./sensorBlockConfig";
import { LANDING_INDEX_GROUPS } from "./interpretations";

export function blockAnchor(sensorKey) {
  return `landing-block-${sensorKey}`;
}

export function sectionAnchor(sensorKey, suffix) {
  return `landing-${sensorKey}-${suffix}`;
}

/** Subsecciones visibles por sensor (S1/S2 no incluyen Smart ni AgroGeoFísica). */
export function subsectionDefsForSensor(sensorKey) {
  const rgbTitle =
    sensorKey === "s1"
      ? "Vista temporal de datos de RADAR (Polarización VV y VH - sigma0 dB)"
      : "Vista temporal visible";
  const base = [
    { suffix: "interactive", title: "Vista interactiva temporal" },
    { suffix: "rgb", title: rgbTitle },
    {
      suffix: "indices",
      title: "Índices de vegetación",
      indexChildren: true,
    },
    { suffix: "clusters", title: "Clusters generales" },
  ];
  if (sensorKey === "ps") {
    base.push(
      { suffix: "smart-clusters", title: "Clusters inteligentes" },
      { suffix: "agrogeofisica", title: "Agrogeofísica" },
      { suffix: "ia", title: "Informe inteligente" }
    );
  }
  return base.map((def, i) => ({ ...def, subNum: i + 1 }));
}

/** Subtítulo de la tarjeta RGB / radar según sensor. */
export function rgbSectionSubtitle(sensorKey) {
  if (sensorKey === "s1") {
    return "Galerías temporales de retrodispersión sigma0 (dB) en polarizaciones VV y VH.";
  }
  return "Galería de escenas en color natural (RGB) a lo largo del tiempo.";
}

export function sensorShowsSmartClusters(sensorKey) {
  return sensorKey === "ps";
}

export function sensorShowsAgrogeofisica(sensorKey) {
  return sensorKey === "ps";
}

export function sensorShowsIa(sensorKey) {
  return sensorKey === "ps";
}

const BLOCK_TITLES = {
  ps: "Alta resolución",
  s1: "Sentinel 1",
  s2: "Sentinel 2",
};

/** Subtítulo de la tarjeta 2.1 / vista interactiva según sensor. */
export function interactiveSectionSubtitle(sensorKey) {
  if (sensorKey === "s1") {
    return (
      "El análisis de la agricultura con radar (especialmente tecnología SAR - Radar de Apertura Sintética) " +
      "utiliza microondas activas para medir la estructura física, biomasa y humedad del suelo y las plantas. " +
      "A diferencia de las imágenes ópticas, los datos de radar penetran la nubosidad, la lluvia y la oscuridad, " +
      "operando eficazmente las 24 horas. Algo importante en países ubicados en el trópico, como Colombia."
    );
  }
  return "Compare índice y RGB, explore el timelapse y las series de clima.";
}

/**
 * Título del bloque en la vista narrativa (no TOC).
 * Para S1 añade la etiqueta Radar/SAR y el eslogan en negrita.
 */
export function narrativeBlockTitle(sensorKey) {
  if (sensorKey === "s1") {
    return {
      plain: "Sentinel 1 - Radar (SAR - Radar de Apertura Sintética)",
      emphasis: "OBSERVANDO TU FINCA A TRAVÉS DE LAS NUBES",
    };
  }
  return { plain: BLOCK_TITLES[sensorKey] || sensorKey, emphasis: null };
}

/** Entradas de tabla de contenidos para los tres bloques sensor. */
export function buildLandingToc() {
  return LANDING_SENSOR_BLOCKS.map((block, blockIdx) => {
    const blockNum = blockIdx + 1;
    const sensorKey = block.id;
    const subsections = subsectionDefsForSensor(sensorKey).map((def) => {
      const num = `${blockNum}.${def.subNum}`;
      const entry = {
        id: sectionAnchor(sensorKey, def.suffix),
        num,
        title: def.title,
        level: 2,
      };
      if (def.indexChildren) {
        entry.children = LANDING_INDEX_GROUPS.map((g, gi) => ({
          id: sectionAnchor(sensorKey, g.id),
          num: `${blockNum}.${def.subNum}.${gi + 1}`,
          title: g.title,
          level: 3,
        }));
      }
      return entry;
    });

    return {
      sensorKey,
      id: blockAnchor(sensorKey),
      num: String(blockNum),
      title: BLOCK_TITLES[sensorKey] || block.title,
      level: 1,
      subsections,
    };
  });
}

export function getSectionMeta(sensorKey, suffix) {
  const toc = buildLandingToc();
  const block = toc.find((b) => b.sensorKey === sensorKey);
  if (!block) return null;
  for (const sub of block.subsections) {
    if (sub.id === sectionAnchor(sensorKey, suffix)) return sub;
    if (sub.children) {
      const child = sub.children.find((c) => c.id === sectionAnchor(sensorKey, suffix));
      if (child) return child;
    }
  }
  return null;
}

export function sensorKeyFromAnchor(anchorId) {
  const m = String(anchorId || "").match(/^landing-(?:block-)?(ps|s1|s2)/);
  return m ? m[1] : null;
}
