import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { buildBaseStyle } from "../utils/geo";

function rectangleFeatureCollection(c1, c2) {
  const w = Math.min(c1[0], c2[0]);
  const e = Math.max(c1[0], c2[0]);
  const s = Math.min(c1[1], c2[1]);
  const n = Math.max(c1[1], c2[1]);
  const ring = [
    [w, s],
    [e, s],
    [e, n],
    [w, n],
    [w, s],
  ];
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: { type: "Polygon", coordinates: [ring] },
      },
    ],
  };
}

function polygonFromRing(pts) {
  if (pts.length < 3) return null;
  const ring = [...pts, pts[0]];
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: { type: "Polygon", coordinates: [ring] },
      },
    ],
  };
}

const TMP_SRC = "_study_draw_tmp_src";
const TMP_LINE = "_study_draw_tmp_line";

export default function MapView({
  mapRef,
  mapLayers,
  mapLayersRef,
  projectId,
  token,
  baseStyle,
  setBaseStyle,
  studyDraw = null,
}) {
  const containerRef = useRef(null);
  const [showBaseOptions, setShowBaseOptions] = useState(false);
  const rasterBlobUrlsRef = useRef(new Map());
  const rasterFetchInFlightRef = useRef(new Set());
  const polygonPtsRef = useRef([]);
  const rectCornerRef = useRef(null);
  const drawCompleteRef = useRef(null);
  const drawTooFewRef = useRef(null);

  useEffect(() => {
    drawCompleteRef.current = studyDraw?.onComplete;
    drawTooFewRef.current = studyDraw?.onPolygonTooFew;
  }, [studyDraw?.onComplete, studyDraw?.onPolygonTooFew]);

  function removeStudyTemp(map) {
    try {
      if (map.getLayer(TMP_LINE)) map.removeLayer(TMP_LINE);
    } catch (_) {}
    try {
      if (map.getSource(TMP_SRC)) map.removeSource(TMP_SRC);
    } catch (_) {}
  }

  function paintTempLine(map, pts) {
    removeStudyTemp(map);
    if (pts.length < 2) return;
    const geo = {
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: pts },
    };
    if (!map.isStyleLoaded()) return;
    map.addSource(TMP_SRC, { type: "geojson", data: geo });
    map.addLayer({
      id: TMP_LINE,
      type: "line",
      source: TMP_SRC,
      paint: { "line-color": "#e11d48", "line-width": 2 },
    });
  }

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: buildBaseStyle("vectorial"),
      center: [-74.2973, 4.5709],
      zoom: 5.5,
    });
    mapRef.current.addControl(new maplibregl.NavigationControl(), "top-right");
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    for (const [, url] of rasterBlobUrlsRef.current.entries()) {
      URL.revokeObjectURL(url);
    }
    rasterBlobUrlsRef.current.clear();
    try {
      mapLayersRef.current.forEach((l) => {
        if (l.kind !== "raster") return;
        if (map.getLayer(l.id)) map.removeLayer(l.id);
        if (map.getSource(l.id)) map.removeSource(l.id);
      });
    } catch (_) {
      /* style may be invalid mid-switch */
    }

    map.setStyle(buildBaseStyle(baseStyle));
    const repaint = () => {
      mapLayersRef.current.forEach((l) => {
        if (!l.geojsonData) return;
        if (map.getSource(l.id)) {
          try {
            map.removeLayer(l.id + "_outline");
          } catch (_) {}
          try {
            map.removeLayer(l.id);
          } catch (_) {}
          map.removeSource(l.id);
        }
        map.addSource(l.id, { type: "geojson", data: l.geojsonData });
        map.addLayer({
          id: l.id,
          type: "fill",
          source: l.id,
          paint: { "fill-color": "#2d6cdf", "fill-opacity": 0.35 },
          layout: { visibility: l.visible ? "visible" : "none" },
        });
        map.addLayer({
          id: l.id + "_outline",
          type: "line",
          source: l.id,
          paint: { "line-color": "#1a3f8c", "line-width": 2 },
          layout: { visibility: l.visible ? "visible" : "none" },
        });
      });
    };
    map.once("load", repaint);
  }, [baseStyle]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !projectId || !token) return;

    const removeRastersFromMap = () => {
      if (!map.isStyleLoaded()) return;
      const rasterIds = mapLayersRef.current
        .filter((l) => l.kind === "raster")
        .map((l) => l.id);
      for (const id of rasterIds) {
        const url = rasterBlobUrlsRef.current.get(id);
        if (url) {
          URL.revokeObjectURL(url);
          rasterBlobUrlsRef.current.delete(id);
        }
        rasterFetchInFlightRef.current.delete(id);
        try {
          if (map.getLayer(id)) map.removeLayer(id);
          if (map.getSource(id)) map.removeSource(id);
        } catch (_) {}
      }
    };

    const run = () => {
      if (map.isStyleLoaded()) removeRastersFromMap();
      else map.once("load", removeRastersFromMap);
    };
    run();
  }, [mapLayers, projectId, token, baseStyle]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !studyDraw?.active) {
      polygonPtsRef.current = [];
      rectCornerRef.current = null;
      if (map && map.isStyleLoaded()) removeStudyTemp(map);
      if (map) {
        try {
          map.doubleClickZoom.enable();
        } catch (_) {}
      }
      return undefined;
    }

    polygonPtsRef.current = [];
    rectCornerRef.current = null;
    const onStyle = () => {
      try {
        map.doubleClickZoom.disable();
      } catch (_) {}
    };
    if (map.isStyleLoaded()) onStyle();
    else map.once("load", onStyle);

    const onClick = (e) => {
      const lng = e.lngLat.lng;
      const lat = e.lngLat.lat;
      if (studyDraw.mode === "polygon") {
        polygonPtsRef.current = [...polygonPtsRef.current, [lng, lat]];
        paintTempLine(map, polygonPtsRef.current);
      } else if (studyDraw.mode === "rectangle") {
        if (!rectCornerRef.current) {
          rectCornerRef.current = [lng, lat];
        } else {
          const gj = rectangleFeatureCollection(rectCornerRef.current, [lng, lat]);
          removeStudyTemp(map);
          rectCornerRef.current = null;
          polygonPtsRef.current = [];
          try {
            map.doubleClickZoom.enable();
          } catch (_) {}
          drawCompleteRef.current?.(gj);
        }
      }
    };

    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
      removeStudyTemp(map);
      polygonPtsRef.current = [];
      rectCornerRef.current = null;
      try {
        map.doubleClickZoom.enable();
      } catch (_) {}
    };
  }, [studyDraw?.active, studyDraw?.mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !studyDraw?.active || studyDraw.mode !== "polygon") return;
    const key = studyDraw.finalizePolygonKey ?? 0;
    if (key <= 0) return;
    const pts = polygonPtsRef.current;
    if (pts.length < 3) {
      drawTooFewRef.current?.();
      return;
    }
    const gj = polygonFromRing(pts);
    if (!gj) return;
    removeStudyTemp(map);
    polygonPtsRef.current = [];
    try {
      map.doubleClickZoom.enable();
    } catch (_) {}
    drawCompleteRef.current?.(gj);
  }, [studyDraw?.finalizePolygonKey, studyDraw?.active, studyDraw?.mode]);

  return (
    <main className="map-container">
      <div className="map-base-control">
        <button
          className="layers-toggle"
          type="button"
          onClick={() => setShowBaseOptions((prev) => !prev)}
          aria-label="Cambiar mapa base"
          title="Capas de mapa"
        >
          <span className="layers-icon" />
        </button>
        {showBaseOptions ? (
          <div className="layers-menu">
            <button
              type="button"
              className={baseStyle === "vectorial" ? "active" : ""}
              onClick={() => {
                setBaseStyle("vectorial");
                setShowBaseOptions(false);
              }}
            >
              Vectorial
            </button>
            <button
              type="button"
              className={baseStyle === "satelital" ? "active" : ""}
              onClick={() => {
                setBaseStyle("satelital");
                setShowBaseOptions(false);
              }}
            >
              Satelital
            </button>
            <button
              type="button"
              className={baseStyle === "hibrido" ? "active" : ""}
              onClick={() => {
                setBaseStyle("hibrido");
                setShowBaseOptions(false);
              }}
            >
              Hibrido
            </button>
          </div>
        ) : null}
      </div>
      <div className="map" ref={containerRef} />
    </main>
  );
}
