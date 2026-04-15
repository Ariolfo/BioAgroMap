#!/usr/bin/env python3
"""
Recorta rasters GeoTIFF con un polígono de un shapefile.

Uso:
  python clip_rasters_by_shapefile.py \\
    --shape palm_3_years.shp \\
    --input-dir downloads_sentinel2 \\
    --out-dir recorte_3_year

  python clip_rasters_by_shapefile.py \\
    --shape palm_10_years.shp \\
    --out-dir recorte_10_year

Por defecto solo procesa archivos con nombre YYYY-MM-DD.tif.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import mapping
from shapely import force_2d

DATE_TIF = re.compile(r"^\d{4}-\d{2}-\d{2}\.tif$", re.IGNORECASE)


def clip_raster(
    raster_path: Path,
    gdf_wgs84: gpd.GeoDataFrame,
    out_path: Path,
) -> None:
    with rasterio.open(raster_path) as src:
        gdf = gdf_wgs84.to_crs(src.crs)
        geoms = [mapping(force_2d(geom)) for geom in gdf.geometry]
        out_image, out_transform = rio_mask(src, geoms, crop=True, nodata=np.nan)
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "compress": "lzw",
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
            }
        )
        # float si hay nodata nan
        if np.isnan(out_image).any():
            out_meta["dtype"] = "float32"
            out_image = out_image.astype(np.float32)
        else:
            out_meta["dtype"] = out_image.dtype

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(out_image)


def main():
    parser = argparse.ArgumentParser(description="Recorta GeoTIFF con un shapefile.")
    parser.add_argument("--shape", "-s", type=Path, required=True, help="Ruta al .shp")
    parser.add_argument(
        "--input-dir", "-i", type=Path, default=Path("downloads_sentinel2")
    )
    parser.add_argument("--out-dir", "-o", type=Path, required=True)
    parser.add_argument(
        "--all-tifs",
        action="store_true",
        help="Procesar todos los .tif del directorio (no solo YYYY-MM-DD.tif).",
    )
    args = parser.parse_args()

    shp = Path(args.shape).resolve()
    if not shp.exists():
        print(f"No existe el shapefile: {shp}")
        return 1

    in_dir = Path(args.input_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not in_dir.is_dir():
        print(f"No existe el directorio de entrada: {in_dir}")
        return 1

    gdf = gpd.read_file(shp)
    if gdf.crs is None:
        print("El shapefile no tiene CRS.")
        return 1
    gdf_wgs84 = gdf.to_crs("EPSG:4326")

    tifs = sorted(in_dir.glob("*.tif"))
    if not args.all_tifs:
        tifs = [p for p in tifs if DATE_TIF.match(p.name)]

    if not tifs:
        print(f"No hay .tif que procesar en {in_dir}")
        return 1

    print(f"Shapefile: {shp}")
    print(f"Salida: {out_dir}  ({len(tifs)} archivos)")
    for tif in tifs:
        out_path = out_dir / tif.name
        try:
            clip_raster(tif, gdf_wgs84, out_path)
            print(f"  OK: {out_path.name}")
        except Exception as e:
            print(f"  Error {tif.name}: {e}")
    return 0


if __name__ == "__main__":
    exit(main())
