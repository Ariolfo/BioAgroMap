import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { bboxFromGeojson, buildBaseStyle } from "../utils/geo";

export default function OrderPreviewMap({ geojson }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: buildBaseStyle("vectorial"),
      center: [-74.2973, 4.5709],
      zoom: 5.5,
    });
    mapRef.current = map;

    function paint() {
      if (!geojson) return;
      try {
        if (map.getLayer("order_geom_line")) map.removeLayer("order_geom_line");
        if (map.getLayer("order_geom_fill")) map.removeLayer("order_geom_fill");
        if (map.getSource("order_geom")) map.removeSource("order_geom");
      } catch (_) {}
      map.addSource("order_geom", { type: "geojson", data: geojson });
      map.addLayer({
        id: "order_geom_fill",
        type: "fill",
        source: "order_geom",
        paint: { "fill-color": "#22c55e", "fill-opacity": 0.38 },
      });
      map.addLayer({
        id: "order_geom_line",
        type: "line",
        source: "order_geom",
        paint: { "line-color": "#166534", "line-width": 2 },
      });
      const b = bboxFromGeojson(geojson);
      if (b) map.fitBounds(b, { padding: 40, maxZoom: 16 });
    }

    map.on("load", paint);
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [geojson]);

  return <div className="order-preview-map" ref={containerRef} />;
}
