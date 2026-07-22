/** Grupos funcionales para la landing (lenguaje del agricultor). */
export const FUNCTIONAL_GROUPS = [
  {
    id: "vigor",
    title: "Vigor y biomasa",
    indices: ["NDVI", "EVI", "KNDVI", "MSAVI2", "MTVI2"],
    meaning:
      "Indican qué tan activa y productiva está la vegetación. Valores altos suelen corresponder a buen vigor; valores bajos alertan sobre estrés o baja fotosíntesis.",
    action: "Compare zonas verdes intensas con parches amarillentos o grises: ahí conviene inspección en campo.",
  },
  {
    id: "clorofila",
    title: "Clorofila y nutrición",
    indices: ["CIre", "MCARI", "NDRE", "TGI"],
    meaning:
      "Reflejan el contenido de clorofila y posibles deficiencias (nitrógeno, magnesio, hierro). Caídas sostenidas sugieren nutrición limitada, no solo falta de agua.",
    action: "Si solo este grupo está bajo en una zona, priorice análisis foliar antes de fertilizar todo el lote.",
  },
  {
    id: "verdor",
    title: "Verdor visible",
    indices: ["GIYI", "VARI"],
    meaning:
      "Describen el color foliar que ve el ojo: verde intenso, amarillamiento o pálido. Útil para detectar cambios visibles antes de que el estrés sea severo.",
    action: "Cruce con fotos de campo o vuelo dron en las fechas donde el color cambió.",
  },
  {
    id: "estructura",
    title: "Estructura del dosel",
    indices: ["RSTRUCTURE", "R_structure"],
    meaning:
      "Mide la uniformidad del dosel: plantas faltantes, huecos o copas desbalanceadas. Valores bajos pueden indicar vacíos, mortalidad incipiente o plantas jóvenes con cobertura incompleta.",
    action: "Priorice recorrido en zonas con estructura baja repetida en varias fechas.",
  },
];

/** Sub-bloques de índices en la landing (Vigor, Nutrición, Agua, Estructura). */
export const LANDING_INDEX_GROUPS = [
  {
    id: "vigor",
    title: "Vigor",
    keysOptical: ["NDVI", "EVI", "KNDVI", "MSAVI2", "MTVI2"],
    keysSar: ["RVI", "RFDI"],
    meaning:
      "Indican qué tan activa y productiva está la vegetación. Valores altos suelen corresponder a buen vigor.",
  },
  {
    id: "nutricion",
    title: "Nutrición",
    keysOptical: ["CIre", "MCARI", "NDRE", "TGI"],
    keysSar: ["VV_VH", "VH_VV"],
    meaning:
      "Reflejan clorofila y posibles deficiencias nutricionales. Caídas sostenidas sugieren nutrición limitada.",
  },
  {
    id: "agua",
    title: "Agua",
    keysOptical: ["NDWI"],
    keysSar: ["NRPB"],
    meaning: "Contenido hídrico foliar y estrés por sequía o riego insuficiente.",
  },
  {
    id: "estructura",
    title: "Estructura",
    keysOptical: ["VARI", "GIYI", "RSTRUCTURE"],
    keysSar: [],
    meaning: "Uniformidad del dosel: huecos, plantas faltantes o copas desbalanceadas.",
  },
];

/** Índices ópticos reales por sensor (alineado a catálogos de estimación / galería). */
const OPTICAL_KEYS_BY_SENSOR = {
  ps: new Set([
    "NDVI",
    "EVI",
    "NDWI",
    "MSAVI2",
    "MTVI2",
    "VARI",
    "TGI",
    "KNDVI",
    "GIYI",
    "MCARI",
    "NDRE",
    "RSTRUCTURE",
  ]),
  // CIre = (B8/B5)−1 es Sentinel-2; no se calcula en PlanetScope.
  s2: new Set(["NDVI", "EVI", "NDWI", "CIre", "MCARI"]),
};

export function indexKeysForLandingGroup(groupId, sensorKey) {
  const g = LANDING_INDEX_GROUPS.find((x) => x.id === groupId);
  if (!g) return [];
  if (sensorKey === "s1") return [...g.keysSar];
  const allow = OPTICAL_KEYS_BY_SENSOR[sensorKey] || OPTICAL_KEYS_BY_SENSOR.s2;
  const allowUpper = new Set([...allow].map((x) => String(x).toUpperCase()));
  return g.keysOptical.filter((k) => allowUpper.has(String(k).toUpperCase()));
}

/**
 * Textos de lectura para el agricultor / landing.
 * ``theory`` + ``legendLow``/``legendHigh`` se usan en la caja bajo la galería.
 */
export const INDEX_FARMER_COPY = {
  NDVI: {
    title: "NDVI — salud general del cultivo",
    howToRead: "Verde intenso = dosel denso y activo. Amarillo/naranja = estrés o baja cobertura. Rojo/marrón = suelo desnudo o vegetación muy débil.",
    interpretation:
      "Es el índice más conocido: resume cuánta biomasa verde hay y qué tan sana parece. Caídas bruscas entre fechas pueden anticipar mortalidad, estrés o fallas de riego.",
    theory:
      "Índice de vegetación de diferencia normalizada (NIR−rojo)/(NIR+rojo). Resume biomasa verde y actividad fotosintética. Rango típico ≈ −1 a +1. Los colores de la galería son relativos a cada escena (percentiles): compare el mismo índice entre fechas.",
    legendLow: "suelo expuesto / vegetación débil",
    legendHigh: "dosel denso / mayor vigor",
  },
  EVI: {
    title: "EVI — vigor en dosel denso",
    howToRead: "Similar al NDVI, pero más sensible cuando el dosel es muy cerrado.",
    interpretation: "Ayuda a distinguir vegetación productiva de áreas con fotosíntesis reducida en lotes con cobertura ya formada.",
    theory:
      "Índice de vegetación mejorado: reduce saturación del NDVI en doseles densos y atenúa efectos de suelo/atmósfera. Útil cuando la cobertura foliar es cerrada. Colores relativos a cada escena.",
    legendLow: "baja biomasa / suelo visible",
    legendHigh: "dosel activo y estructurado",
  },
  KNDVI: {
    title: "KNDVI — vigor fino del dosel",
    howToRead: "Valores altos = vegetación vigorosa; bajos = estrés o baja actividad foliar.",
    interpretation: "Complementa al NDVI para ver variaciones sutiles de vigor dentro del mismo lote.",
    theory:
      "Kernel NDVI: transforma el NDVI con un kernel (p. ej. tanh) para resaltar contrastes finos de vigor. Complementa al NDVI cuando las diferencias dentro del lote son sutiles. Colores relativos a cada escena.",
    legendLow: "baja actividad foliar",
    legendHigh: "vegetación vigorosa",
  },
  MSAVI2: {
    title: "MSAVI2 — vigor en etapas tempranas",
    howToRead: "Funciona bien cuando hay suelo visible entre plantas jóvenes.",
    interpretation: "Útil si hay replantes o zonas con cobertura parcial.",
    theory:
      "MSAVI2 (Qi et al., 1994): índice ajustado al suelo sin factor L manual. Reduce el ruido del suelo cuando hay mucha superficie desnuda (emergencia, replantes, dosel incompleto). Orientativo: −1…0,2 suelo; 0,2…0,4 plántulas; 0,4…0,6 cobertura moderada; >0,6 dosel más denso (entonces NDVI suele aportar más). Colores relativos a cada escena.",
    legendLow: "suelo desnudo / plántulas dispersas",
    legendHigh: "mayor cobertura verde temprana",
  },
  MTVI2: {
    title: "MTVI2 — biomasa y estructura",
    howToRead: "Valores altos indican mayor desarrollo de biomasa verde.",
    interpretation: "Permite comparar bloques con distinta edad o manejo.",
    theory:
      "MTVI2 (Haboudane et al., 2004): índice triangular modificado que estima biomasa verde / LAI con corrección de fondo. Útil para comparar bloques de distinta edad o manejo. Colores relativos a cada escena.",
    legendLow: "poca biomasa / dosel abierto",
    legendHigh: "mayor biomasa y estructura foliar",
  },
  NDRE: {
    title: "NDRE — clorofila y nutrición",
    howToRead: "Tonos altos = buen contenido de clorofila; bajos = posible deficiencia nutricional.",
    interpretation: "Caídas localizadas pueden señalar falta de nitrógeno u otros nutrientes antes de síntomas visibles claros.",
    theory:
      "Normalized Difference Red Edge (NIR−borde rojo)/(NIR+borde rojo). Sensible a clorofila y nitrógeno foliar; suele detectar deficiencias antes que el NDVI en doseles medios–altos. Colores relativos a cada escena.",
    legendLow: "menor clorofila / posible déficit nutricional",
    legendHigh: "mayor clorofila / mejor nutrición",
  },
  CIre: {
    title: "CIre — clorofila en borde rojo",
    howToRead: "Sensibles a variaciones de clorofila en hojas.",
    interpretation: "Zonas persistentemente bajas merecen muestreo foliar o de suelo.",
    theory:
      "Chlorophyll Index – red edge: (NIR/borde rojo)−1 (Gitelson et al.). Proxy de clorofila y estado nutricional. Zonas bajas de forma sostenida conviene contrastar con muestreo foliar. Colores relativos a cada escena.",
    legendLow: "menor clorofila / posible deficiencia",
    legendHigh: "mayor clorofila / mejor estado nutricional",
  },
  MCARI: {
    title: "MCARI — absorción de clorofila",
    howToRead: "Resalta diferencias de clorofila entre plantas vecinas.",
    interpretation: "Ideal para detectar manchas nutricionales heterogéneas.",
    theory:
      "Modified Chlorophyll Absorption Ratio Index (Daughtry et al.): resalta absorción de clorofila con corrección de fondo. Útil para manchas nutricionales heterogéneas dentro del lote. Colores relativos a cada escena.",
    legendLow: "menor absorción de clorofila",
    legendHigh: "mayor absorción de clorofila",
  },
  TGI: {
    title: "TGI — triángulo verde (clorofila)",
    howToRead: "Relacionado con el amarillamiento por falta de clorofila.",
    interpretation: "Incrementos pueden anticipar clorosis o estrés nutricional.",
    theory:
      "Triangular Greenness Index (Hunt et al.): usa bandas visibles (azul, verde, rojo) para estimar clorofila y amarillamiento. Valores bajos anticipan clorosis o estrés nutricional visible. Colores relativos a cada escena.",
    legendLow: "tendencia a amarillamiento / menos clorofila",
    legendHigh: "mayor verdor / más clorofila",
  },
  GIYI: {
    title: "GIYI — verdor amarillento",
    howToRead: "Contrasta verde vs. amarillo en el follaje.",
    interpretation: "Cambios bruscos pueden indicar estrés hídrico o nutricional visible.",
    theory:
      "Índice verde–amarillo (producto): contrasta bandas de verdor y amarillo del sensor. Cambios bruscos pueden indicar estrés hídrico, nutricional o senescencia visible. Colores relativos a cada escena.",
    legendLow: "predominio amarillento",
    legendHigh: "predominio verde",
  },
  VARI: {
    title: "VARI — color visible del follaje",
    howToRead: "Verde = follaje sano; tonos pálidos = posible estrés.",
    interpretation: "Complementa índices de vigor con la apariencia visual de las copas.",
    theory:
      "Visible Atmospherically Resistant Index (Gitelson et al.): verdor visible con cierta resistencia a atmósfera. Complementa índices NIR con la apariencia del follaje. Colores relativos a cada escena.",
    legendLow: "follaje pálido / poco verde",
    legendHigh: "follaje más verde y vigoroso",
  },
  RSTRUCTURE: {
    title: "R_structure — uniformidad del dosel",
    howToRead: "Valores altos = dosel uniforme; bajos = huecos, plantas faltantes o estrés estructural.",
    interpretation: "Caídas en el tiempo pueden señalar mortalidad o fallas de establecimiento.",
    theory:
      "Cociente NDRE/NDVI (índice de producto): proxy de uniformidad/estructura relativa del dosel. Valores bajos pueden indicar huecos, plantas faltantes o estrés estructural. Interpretar comparando fechas del mismo lote. Colores relativos a cada escena.",
    legendLow: "dosel menos uniforme / posibles huecos",
    legendHigh: "dosel más uniforme y estructurado",
  },
  NDWI: {
    title: "NDWI — agua en la vegetación",
    howToRead: "Valores bajos = menor contenido hídrico foliar (sequía o riego insuficiente).",
    interpretation: "Se analiza en detalle en la sección de Análisis Hídrico.",
    theory:
      "Índice de diferencia normalizada de agua. En Sentinel-2 (Gao) usa NIR–SWIR y prioriza agua en el dosel; en PlanetScope (McFeeters) usa verde–NIR y responde también a humedad superficial. Valores bajos sugieren menor agua disponible o estrés hídrico. Colores relativos a cada escena.",
    legendLow: "menor agua / posible estrés hídrico",
    legendHigh: "mayor contenido hídrico",
  },
  RVI: {
    title: "RVI — radar de volumen (Sentinel-1)",
    howToRead: "Valores altos = mayor dispersión del radar, asociada a biomasa y estructura.",
    interpretation: "Observa el cultivo a través de nubes; útil cuando la óptica no está disponible.",
    theory:
      "Radar Vegetation Index: 4×VH/(VH+VV) en potencia lineal. Proxies de biomasa y estructura del dosel a través de nubes. Colores relativos a cada escena.",
    legendLow: "menor respuesta de vegetación",
    legendHigh: "mayor biomasa / estructura radar",
  },
  RFDI: {
    title: "RFDI — contraste polarimétrico (Sentinel-1)",
    howToRead: "Valores altos = mayor contraste VV–VH; bajos = menor contraste estructural.",
    interpretation: "Complementa al RVI para detectar cambios de estructura del cultivo con radar.",
    theory:
      "Radar Forest Degradation Index: (VV−VH)/(VV+VH) en lineal. Resalta contraste polarimétrico asociado a estructura. Interpretar cambios en el tiempo, no valores absolutos aislados. Colores relativos a cada escena.",
    legendLow: "menor contraste polarimétrico",
    legendHigh: "mayor contraste estructural",
  },
  VV_VH: {
    title: "VV/VH — cociente polarimétrico (Sentinel-1)",
    howToRead: "Valores altos = mayor cociente VV respecto a VH en esta escena.",
    interpretation: "Compare fechas del mismo lote: cambios pueden indicar variación de estructura o humedad.",
    theory:
      "Cociente VV/VH en potencia lineal. Describe la relación entre polarizaciones; no es un índice de «vigor» óptico. Interpretar tendencias temporales. Colores relativos a cada escena.",
    legendLow: "cociente polarimétrico bajo",
    legendHigh: "cociente polarimétrico alto",
  },
  VH_VV: {
    title: "VH/VV — cociente polarimétrico (Sentinel-1)",
    howToRead: "Valores altos = mayor cociente VH respecto a VV en esta escena.",
    interpretation: "Complementa VV/VH; útil para seguir cambios de estructura con radar bajo nubes.",
    theory:
      "Cociente VH/VV en potencia lineal. Relación polarimétrica complementaria a VV/VH. Preferir comparación entre fechas del mismo lote. Colores relativos a cada escena.",
    legendLow: "cociente polarimétrico bajo",
    legendHigh: "cociente polarimétrico alto",
  },
  NRPB: {
    title: "NRPB — índice polarimétrico normalizado (Sentinel-1)",
    howToRead: "Valores altos = mayor contraste VH−VV normalizado; bajos = menor contraste.",
    interpretation: "Útil cuando la óptica falla por nubes; seguir cambios de humedad/estructura en el tiempo.",
    theory:
      "Normalized Ratio Procedure between Bands: (VH−VV)/(VH+VV) en lineal. Índice polarimétrico ligado a humedad y estructura según el contexto del lote. Colores relativos a cada escena.",
    legendLow: "señal polarimétrica más baja",
    legendHigh: "señal polarimétrica más alta",
  },
};

export function copyForIndex(indexKey) {
  const k = String(indexKey || "").toUpperCase();
  for (const [id, copy] of Object.entries(INDEX_FARMER_COPY)) {
    if (id.toUpperCase() === k) return copy;
  }
  return {
    title: indexKey || "Índice",
    howToRead: "Colores cálidos (rojo/naranja) suelen indicar menor vigor; verdes altos indican vegetación activa.",
    interpretation: "Compare esta capa entre fechas para ver si el problema es puntual o se repite en el tiempo.",
  };
}

export function groupForIndex(indexKey) {
  const k = String(indexKey || "").toUpperCase();
  return (
    FUNCTIONAL_GROUPS.find((g) =>
      g.indices.some((i) => String(i).toUpperCase() === k)
    ) || null
  );
}
