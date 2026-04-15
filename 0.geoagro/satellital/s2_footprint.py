#!/usr/bin/env python3
"""
Extrae el polígono (footprint) de imágenes Sentinel-2.

Acepta un GeoTIFF combinado o una carpeta .SAFE; devuelve el bounding box
en WGS84 como polígono (WKT, GeoJSON o KML).

Uso:
  python s2_footprint.py imagen.tif
  python s2_footprint.py producto.SAFE
  python s2_footprint.py downloads_sentinel2 -o footprints.kml
  python s2_footprint.py downloads_sentinel2 --kml -o footprints.kml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import rasterio
from rasterio.warp import transform_geom
from shapely.geometry import box, mapping, shape


def get_raster_bounds(raster_path: Path) -> tuple[float, float, float, float, str]:
    """
    Lee bounds (left, bottom, right, top) y CRS de un raster.
    Devuelve (minx, miny, maxx, maxy, crs_wkt o epsg).
    """
    path = Path(raster_path)
    with rasterio.open(path) as src:
        bounds = src.bounds
        crs = src.crs
    return bounds.left, bounds.bottom, bounds.right, bounds.top, crs


def bounds_to_polygon_wgs84(
    left: float, bottom: float, right: float, top: float, crs
):
    """Crea un polígono rectangular en WGS84 a partir del bbox del raster."""
    geom = box(left, bottom, right, top)
    if crs is None or str(crs).upper() in ("EPSG:4326", "WGS84"):
        return geom
    geom_dict = mapping(geom)
    geom_wgs84 = transform_geom(crs, "EPSG:4326", geom_dict)
    return shape(geom_wgs84)


def footprint_from_raster(raster_path: Path) -> tuple[object, str]:
    """
    Obtiene el polígono (footprint) en WGS84 de un GeoTIFF o similar.
    Devuelve (geometría Shapely, WKT).
    """
    left, bottom, right, top, crs = get_raster_bounds(raster_path)
    geom = bounds_to_polygon_wgs84(left, bottom, right, top, crs)
    return geom, geom.wkt


def first_band_in_safe(safe_path: Path, res_m: int = 10) -> Path | None:
    """Devuelve la ruta al primer JP2 de banda en IMG_DATA/R10m (o res indicada)."""
    safe_path = Path(safe_path)
    res_folder = f"R{res_m}m"
    granules = safe_path / "GRANULE"
    if not granules.is_dir():
        return None
    for granule in sorted(granules.iterdir()):
        if not granule.is_dir():
            continue
        img_data = granule / "IMG_DATA" / res_folder
        if not img_data.is_dir():
            continue
        for f in sorted(img_data.iterdir()):
            if f.suffix.lower() == ".jp2" and "_B0" in f.name:
                return f
    return None


def footprint_from_safe(safe_path: Path, res_m: int = 10) -> tuple[object, str] | None:
    """Obtiene el footprint desde un producto .SAFE (usa la primera banda encontrada)."""
    band_path = first_band_in_safe(safe_path, res_m=res_m)
    if band_path is None:
        return None
    return footprint_from_raster(band_path)


def geom_to_kml_coordinates(geom) -> str:
    """Convierte geometría Shapely (polígono) a cadena <coordinates> para KML (lon,lat,0)."""
    from shapely.geometry import Polygon
    if isinstance(geom, Polygon):
        ring = geom.exterior
    else:
        ring = geom
    coords = list(ring.coords)
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return " ".join(f"{x},{y},0" for x, y in coords)


def write_kml(results: list[tuple[str, object, str]], out_path: Path) -> None:
    """Escribe un archivo KML con un Placemark por cada footprint."""
    placemarks = []
    for name, geom, _ in results:
        coords = geom_to_kml_coordinates(geom)
        name_esc = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        placemarks.append(
            f"""  <Placemark>
    <name>{name_esc}</name>
    <Polygon>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>{coords}</coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>"""
        )
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Sentinel-2 footprints</name>
{chr(10).join(placemarks)}
  </Document>
</kml>
"""
    out_path.write_text(kml, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Extrae el polígono (footprint) de imágenes S2 (GeoTIFF o .SAFE)."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="GeoTIFF, carpeta .SAFE, o directorio con varios.",
    )
    parser.add_argument(
        "-o", "--out",
        type=Path,
        default=None,
        help="Archivo de salida (.wkt o .geojson según formato).",
    )
    parser.add_argument(
        "--geojson",
        action="store_true",
        help="Salida en GeoJSON en lugar de WKT.",
    )
    parser.add_argument(
        "--kml",
        action="store_true",
        help="Salida en KML (también se detecta por -o archivo.kml).",
    )
    parser.add_argument(
        "--res",
        type=int,
        default=10,
        help="Resolución para buscar banda dentro de .SAFE (10, 20, 60).",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: no existe {input_path}")
        return 1

    results = []

    def process_one(path: Path, name: str):
        if path.suffix.lower() in (".tif", ".tiff"):
            geom, wkt = footprint_from_raster(path)
        elif path.is_dir() and path.name.endswith(".SAFE"):
            out = footprint_from_safe(path, res_m=args.res)
            if out is None:
                print(f"  {name}: no se encontró banda en .SAFE")
                return
            geom, wkt = out
        else:
            return
        results.append((name, geom, wkt))
        print(f"  {name}")
        print(f"    WKT: {wkt[:80]}...")

    if input_path.is_file():
        process_one(input_path, input_path.name)
    elif input_path.is_dir():
        if input_path.name.endswith(".SAFE"):
            process_one(input_path, input_path.name)
        else:
            for f in sorted(input_path.iterdir()):
                if f.suffix.lower() in (".tif", ".tiff"):
                    process_one(f, f.name)
                elif f.is_dir() and f.name.endswith(".SAFE"):
                    process_one(f, f.name)

    if not results:
        print("No se encontraron GeoTIFF ni carpetas .SAFE.")
        return 1

    out_path = args.out
    if args.kml and out_path is None:
        out_path = Path("footprints.kml")
    if out_path is not None:
        out_path = Path(out_path)
        use_kml = args.kml or (str(out_path).lower().endswith(".kml"))
        if use_kml:
            write_kml(results, out_path)
            print(f"\nGuardado: {out_path} (KML)")
        elif args.geojson:
            if len(results) == 1:
                geojson = {
                    "type": "Feature",
                    "properties": {"name": results[0][0]},
                    "geometry": mapping(results[0][1]),
                }
            else:
                geojson = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"name": name},
                            "geometry": mapping(geom),
                        }
                        for name, geom, _ in results
                    ],
                }
            out_path.write_text(json.dumps(geojson, indent=2), encoding="utf-8")
            print(f"\nGuardado: {out_path} (GeoJSON)")
        else:
            if len(results) == 1:
                out_path.write_text(results[0][2], encoding="utf-8")
            else:
                out_path.write_text(
                    "\n\n".join(f"# {name}\n{wkt}" for name, _, wkt in results),
                    encoding="utf-8",
                )
            print(f"\nGuardado: {out_path} (WKT)")

    return 0


if __name__ == "__main__":
    exit(main())
