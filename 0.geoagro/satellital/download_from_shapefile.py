#!/usr/bin/env python3
"""
Descarga Sentinel-1 y Sentinel-2 para el área de un shapefile y un año dado.

Vacía downloads_sentinel1 y downloads_sentinel2, luego descarga mes a mes
para el año indicado (por defecto 2025).

Uso:
  python download_from_shapefile.py /ruta/predio_vertices.shp
  python download_from_shapefile.py /ruta/predio_vertices.shp --year 2025
  python download_from_shapefile.py /ruta/predio_vertices.shp --year 2025 --no-clear  # no vaciar carpetas
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

import geopandas as gpd
from shapely import force_2d

# Directorios de descarga en el proyecto
PROJECT_ROOT = Path(__file__).resolve().parent
S1_DIR = PROJECT_ROOT / "downloads_sentinel1"
S2_DIR = PROJECT_ROOT / "downloads_sentinel2"


def wkt_from_shapefile(shp_path: Path) -> str:
    """Lee el shapefile y devuelve el polígono en WKT (WGS84)."""
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        raise ValueError("El shapefile no tiene CRS definido.")
    gdf = gdf.to_crs("EPSG:4326")
    if hasattr(gdf.geometry, "union_all"):
        geom = gdf.geometry.union_all()
    else:
        geom = gdf.geometry.unary_union
    if geom is None or geom.is_empty:
        raise ValueError("No hay geometría válida en el shapefile.")
    if geom.geom_type == "MultiPolygon" and len(geom.geoms) == 1:
        geom = geom.geoms[0]
    if geom.geom_type != "Polygon":
        raise ValueError(f"Se esperaba Polygon, se obtuvo {geom.geom_type}.")
    # Copernicus OData: WKT 2D (sin Z/M)
    geom = force_2d(geom)
    return geom.wkt


def clear_download_dirs():
    """Vacía downloads_sentinel1 y downloads_sentinel2 (solo contenido)."""
    for d in (S1_DIR, S2_DIR):
        if d.exists():
            for item in d.iterdir():
                if item.is_file():
                    item.unlink()
                else:
                    shutil.rmtree(item)
            print(f"  Vacío: {d}")
    S1_DIR.mkdir(parents=True, exist_ok=True)
    S2_DIR.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Descarga S1 y S2 para el área del shapefile (año indicado)."
    )
    parser.add_argument(
        "shapefile",
        type=Path,
        help="Ruta al .shp (o directorio con predio_vertices.shp).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Año a descargar (por defecto 2025).",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="No vaciar las carpetas de descarga antes de descargar.",
    )
    parser.add_argument(
        "--s2-only",
        action="store_true",
        help="Solo descargar Sentinel-2.",
    )
    parser.add_argument(
        "--s1-only",
        action="store_true",
        help="Solo descargar Sentinel-1.",
    )
    args = parser.parse_args()

    shp = Path(args.shapefile)
    if shp.is_dir():
        shp = shp / "predio_vertices.shp"
    if not shp.exists():
        print(f"Error: no existe {shp}")
        return 1

    print("Leyendo shapefile...")
    wkt = wkt_from_shapefile(shp)
    print(f"WKT (WGS84): {wkt[:80]}...")

    if not args.no_clear:
        print("Vaciando carpetas de descarga...")
        clear_download_dirs()
    else:
        S1_DIR.mkdir(parents=True, exist_ok=True)
        S2_DIR.mkdir(parents=True, exist_ok=True)

    start_date = date(args.year, 1, 1)
    end_date = date(args.year + 1, 1, 1)

    do_s2 = not args.s1_only
    do_s1 = not args.s2_only

    if do_s2:
        print("\n" + "=" * 60)
        print("DESCARGA SENTINEL-2 (año {})".format(args.year))
        print("=" * 60)
        import s2_test
        s2_test.search_and_download_monthly(wkt, start_date, end_date, str(S2_DIR))

    if do_s1:
        print("\n" + "=" * 60)
        print("DESCARGA SENTINEL-1 (año {})".format(args.year))
        print("=" * 60)
        import s1_test
        # s1_test usa search_and_download_monthly con (wkt, start, end, output_dir)
        s1_test.search_and_download_monthly(wkt, start_date, end_date, str(S1_DIR))

    print("\nFinalizado.")
    return 0


if __name__ == "__main__":
    exit(main())
