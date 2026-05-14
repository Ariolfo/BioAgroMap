import { useCallback, useLayoutEffect, useRef, useState } from "react";

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function clientToRaster(clientX, clientY, img) {
  if (!img?.naturalWidth) return null;
  const rect = img.getBoundingClientRect();
  const nw = img.naturalWidth;
  const nh = img.naturalHeight;
  const rw = rect.width;
  const rh = rect.height;
  const s = Math.min(rw / nw, rh / nh);
  const cw = nw * s;
  const ch = nh * s;
  const padX = rect.left + (rw - cw) / 2;
  const padY = rect.top + (rh - ch) / 2;
  if (clientX < padX || clientX > padX + cw || clientY < padY || clientY > padY + ch) return null;
  const x = ((clientX - padX) / cw) * nw;
  const y = ((clientY - padY) / ch) * nh;
  return [clamp(x, 0, nw - 1), clamp(y, 0, nh - 1)];
}

export function soilRoiToQueryParam(roi) {
  if (!roi || !roi.closed || !Array.isArray(roi.points) || roi.points.length < 3) return null;
  return JSON.stringify(roi.points.map((p) => [Number(p[0]), Number(p[1])]));
}

const defaultRoi = () => ({ points: [], closed: false });

/**
 * Dibuja un polígono sobre la vista previa DEM; coordenadas en píxeles del raster (columna, fila).
 */
export default function DemRoiEditor({ imageUrl, disabled, value, onChange }) {
  const imgRef = useRef(null);
  const [dims, setDims] = useState(null);

  const recomputeDims = useCallback(() => {
    const img = imgRef.current;
    if (!img?.naturalWidth) {
      setDims(null);
      return;
    }
    const rect = img.getBoundingClientRect();
    const nw = img.naturalWidth;
    const nh = img.naturalHeight;
    const rw = rect.width;
    const rh = rect.height;
    const s = Math.min(rw / nw, rh / nh);
    const cw = nw * s;
    const ch = nh * s;
    const padX = (rw - cw) / 2;
    const padY = (rh - ch) / 2;
    setDims({ nw, nh, padX, padY, cw, ch, rw, rh });
  }, []);

  useLayoutEffect(() => {
    recomputeDims();
    const img = imgRef.current;
    if (!img) return undefined;
    const ro = new ResizeObserver(() => recomputeDims());
    ro.observe(img);
    return () => ro.disconnect();
  }, [imageUrl, recomputeDims]);

  const handleSvgClick = (e) => {
    if (disabled || !imgRef.current) return;
    const p = clientToRaster(e.clientX, e.clientY, imgRef.current);
    if (!p) return;
    const cur = value || defaultRoi();
    if (cur.closed) {
      onChange({ points: [p], closed: false });
      return;
    }
    onChange({ points: [...cur.points, p], closed: false });
  };

  const closePolygon = () => {
    const cur = value || defaultRoi();
    if (cur.points.length < 3) return;
    onChange({ ...cur, closed: true });
  };

  const clearPolygon = () => {
    onChange(defaultRoi());
  };

  const cur = value || defaultRoi();
  /* Grosor y radios en coords del viewBox (píxeles raster): límites para que no se vean enormes en DEM grandes */
  const sw = dims ? Math.max(0.6, Math.min(1.8, dims.nw / 1200)) : 1;
  const pr = dims ? Math.max(1, Math.min(2.8, dims.nw / 650)) : 1.5;

  if (!imageUrl) {
    return <p className="adv-soilplus-image-empty">Sin imagen. Cargando DEM…</p>;
  }

  return (
    <div className="adv-soilplus-dem-roi-stack">
      <div className="adv-soilplus-dem-roi-inner">
        <img
          ref={imgRef}
          src={imageUrl}
          alt="DEM para ROI"
          className="adv-soilplus-dem-roi-img"
          onLoad={recomputeDims}
        />
        {dims ? (
          <svg
            className="adv-soilplus-dem-roi-svg"
            role="presentation"
            style={{ left: dims.padX, top: dims.padY, width: dims.cw, height: dims.ch }}
            viewBox={`0 0 ${dims.nw} ${dims.nh}`}
            preserveAspectRatio="none"
            onClick={handleSvgClick}
          >
            <rect x={0} y={0} width={dims.nw} height={dims.nh} fill="rgba(0,0,0,0.001)" />
            {cur.closed && cur.points.length >= 3 ? (
              <polygon
                points={cur.points.map(([x, y]) => `${x},${y}`).join(" ")}
                fill="rgba(14,165,233,0.15)"
                stroke="#0ea5e9"
                strokeWidth={sw}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ) : cur.points.length > 0 ? (
              <polyline
                points={cur.points.map(([x, y]) => `${x},${y}`).join(" ")}
                fill="none"
                stroke="#0ea5e9"
                strokeWidth={sw}
                strokeDasharray="5 4"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ) : null}
            {cur.points.map(([x, y], i) => (
              <circle key={`dem-roi-v-${i}`} cx={x} cy={y} r={pr} fill="#ef4444" stroke="#fff" strokeWidth={Math.max(0.25, sw * 0.2)} />
            ))}
          </svg>
        ) : null}
      </div>
      <div className="adv-soilplus-dem-roi-tools">
        <button type="button" className="adv-soilplus-roi-btn" onClick={closePolygon} disabled={disabled || cur.points.length < 3 || cur.closed}>
          Cerrar polígono
        </button>
        <button type="button" className="adv-soilplus-roi-btn" onClick={clearPolygon} disabled={disabled || (cur.points.length === 0 && !cur.closed)}>
          Limpiar
        </button>
        <span className="adv-soilplus-roi-hint">
          {cur.closed
            ? "ROI lista. Clic de nuevo para dibujar otra."
            : "Clic en la imagen: añadir vértices. Mínimo 3, luego Cerrar polígono."}
        </span>
      </div>
    </div>
  );
}

export { defaultRoi };
