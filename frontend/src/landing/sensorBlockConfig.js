/** Configuración de los tres bloques colapsables de la landing. */
export const LANDING_SENSOR_BLOCKS = [
  {
    id: "ps",
    title: "ALTA RESOLUCIÓN",
    defaultOpen: true,
  },
  {
    id: "s1",
    title: "SENTINEL 1",
    defaultOpen: false,
  },
  {
    id: "s2",
    title: "SENTINEL 2",
    defaultOpen: false,
  },
];

export function rgbGalleryModeForSensor(sensorKey) {
  if (sensorKey === "s1") return "s1-vv";
  return "rgb";
}

export function indexGalleryModeForSensor(sensorKey) {
  if (sensorKey === "s1") return "s1-sar-index";
  return "index";
}

export function pipelineVariantForSensor(sensorKey) {
  if (sensorKey === "ps") return "ps";
  if (sensorKey === "s1") return "s1";
  return "s2";
}
