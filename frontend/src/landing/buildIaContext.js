export function buildLandingIaContext({
  projectId,
  projectName,
  adapted,
  extras,
  sensorKey,
}) {
  const sd = adapted?.sensorData?.[sensorKey];
  const idxKey = sd?.indices?.[0] || (sensorKey === "s1" ? "RVI" : "NDVI");
  const frames = sd?.framesByIndex?.[idxKey] || [];
  const af = frames[frames.length - 1] || null;
  return {
    projectId,
    projectName,
    sensorData: adapted?.sensorData || { s1: null, s2: null, ps: null },
    indexBySensor: {
      s1: adapted?.sensorData?.s1?.indices?.[0] || "RVI",
      s2: adapted?.sensorData?.s2?.indices?.[0] || "NDVI",
      ps: adapted?.sensorData?.ps?.indices?.[0] || "NDVI",
    },
    seriesBySensor: extras?.seriesBySensor || { s1: [], s2: [], ps: [] },
    climateBySensor: extras?.climateBySensor || { s1: [], s2: [], ps: [] },
    clusterBySensor: {
      s1: extras?.clusterBySensor?.s1?.results || [],
      s2: extras?.clusterBySensor?.s2?.results || [],
      ps: extras?.clusterBySensor?.ps?.results || [],
    },
    psStClusters: {
      1: {
        preview: !!extras?.psStClusters?.[1]?.preview,
        busy: extras?.psStClusters?.[1]?.busy,
        error: extras?.psStClusters?.[1]?.error,
      },
      2: {
        preview: !!extras?.psStClusters?.[2]?.preview,
        busy: extras?.psStClusters?.[2]?.busy,
        error: extras?.psStClusters?.[2]?.error,
      },
      3: {
        preview: !!extras?.psStClusters?.[3]?.preview,
        busy: extras?.psStClusters?.[3]?.busy,
        error: extras?.psStClusters?.[3]?.error,
      },
    },
    clientSoilSummary: extras?.clientSoilSummary || null,
    hasGeofisica: extras?.hasGeofisica || false,
    soilDemInfo: extras?.soilDemInfo || null,
    activeSceneDate: af?.date ?? null,
    activeSensorKey: sensorKey,
    activeIndexKey: idxKey,
  };
}
