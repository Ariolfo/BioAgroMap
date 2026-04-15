export default function PreprocessPanel({
  token,
  projectId,
  loading,
  targetRasterId,
  indiceType,
  setIndiceType,
  stackMode,
  setStackMode,
  onCrop,
  onIndices,
  onStack,
  onCluster,
}) {
  return (
    <>
      <button
        onClick={onCrop}
        disabled={loading || !projectId || !token || !targetRasterId}
      >
        1) Recorte
      </button>

      <label>
        2) Indices
        <select
          value={indiceType}
          onChange={(e) => setIndiceType(e.target.value)}
        >
          <option value="NDVI">NDVI</option>
          <option value="EVI">EVI</option>
          <option value="NDWI">NDWI</option>
        </select>
      </label>
      <button
        onClick={onIndices}
        disabled={loading || !projectId || !token || !targetRasterId}
      >
        Calcular indice
      </button>

      <label>
        3) Stack
        <select
          value={stackMode}
          onChange={(e) => setStackMode(e.target.value)}
        >
          <option value="visualizar">Visualizar</option>
          <option value="gif">Gif</option>
        </select>
      </label>
      <button
        onClick={onStack}
        disabled={loading || !projectId || !token}
      >
        Procesar stack
      </button>

      <button
        onClick={onCluster}
        disabled={loading || !projectId || !token || !targetRasterId}
      >
        4) Cluster
      </button>
    </>
  );
}
