#!/usr/bin/env python3
"""
Calcula NDVI por fecha desde recortes S2 (4 bandas: B02,B03,B04,B08).
Guarda NDVI_YYYY-MM-DD.tif en <recorte>/NDVI/ y un stack multibanda (nombre configurable).

NDVI = (NIR - Red) / (NIR + Red)  →  banda 3 = B04, banda 4 = B08.

Uso:
  python compute_ndvi_stack.py --input-dir recorte_3_year
  python compute_ndvi_stack.py --input-dir recorte_10_year --stack-name STACK_NDVI_10_YEAR.tif
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import rasterio

DATE_TIF = re.compile(r"^(\d{4}-\d{2}-\d{2})\.tif$", re.IGNORECASE)


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    red = red.astype(np.float32)
    nir = nir.astype(np.float32)
    denom = nir + red
    num = nir - red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(denom > 0, num / denom, np.nan)
    return ndvi.astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description="NDVI por fecha + stack multibanda.")
    parser.add_argument(
        "--input-dir",
        "-i",
        type=Path,
        default=Path("recorte_3_year"),
        help="Carpeta con YYYY-MM-DD.tif (4 bandas S2).",
    )
    parser.add_argument(
        "--ndvi-subdir",
        type=str,
        default="NDVI",
        help="Subcarpeta donde guardar NDVI individuales (relativa a input-dir).",
    )
    parser.add_argument(
        "--stack-name",
        type=str,
        default="STACK_NDVI_3_YEAR.tif",
        help="Nombre del GeoTIFF stack (dentro de la subcarpeta NDVI).",
    )
    args = parser.parse_args()

    in_dir = Path(args.input_dir).resolve()
    if not in_dir.is_dir():
        print(f"No existe: {in_dir}")
        return 1

    ndvi_dir = in_dir / args.ndvi_subdir
    ndvi_dir.mkdir(parents=True, exist_ok=True)

    pairs: list[tuple[str, Path]] = []
    for p in sorted(in_dir.glob("*.tif")):
        m = DATE_TIF.match(p.name)
        if m:
            pairs.append((m.group(1), p))

    if not pairs:
        print(f"No hay archivos YYYY-MM-DD.tif en {in_dir}")
        return 1

    stack_arrays: list[np.ndarray] = []
    stack_dates: list[str] = []
    ref_profile = None
    ref_shape = None

    for date_str, src_path in pairs:
        with rasterio.open(src_path) as src:
            if src.count < 4:
                print(f"  Omitido {src_path.name}: necesita 4 bandas (tiene {src.count}).")
                continue
            red = src.read(3)
            nir = src.read(4)
            ndvi = compute_ndvi(red, nir)
            profile = src.profile.copy()
            profile.update(count=1, dtype="float32", nodata=None, compress="lzw")
            # Evitar tiled si el raster es pequeño (bloques deben ser múltiplos de 16)
            h, w = ndvi.shape
            bx = min(256, (w // 16) * 16)
            by = min(256, (h // 16) * 16)
            if bx >= 16 and by >= 16:
                profile.update(tiled=True, blockxsize=bx, blockysize=by)
            out_path = ndvi_dir / f"NDVI_{date_str}.tif"
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(ndvi, 1)
            print(f"  OK: {out_path.name}")

            if ref_shape is None:
                ref_shape = ndvi.shape
                ref_profile = profile
            elif ndvi.shape != ref_shape:
                print(
                    f"  Aviso: {date_str} tiene shape {ndvi.shape} != {ref_shape}; "
                    "no se incluirá en el stack."
                )
                continue

            stack_arrays.append(ndvi)
            stack_dates.append(date_str)

    if not stack_arrays:
        print("No se pudo construir el stack.")
        return 1

    stack_path = ndvi_dir / args.stack_name
    n = len(stack_arrays)
    cube = np.stack(stack_arrays, axis=0)
    stack_profile = ref_profile.copy()
    stack_profile.update(count=n, height=cube.shape[1], width=cube.shape[2])
    with rasterio.open(stack_path, "w", **stack_profile) as dst:
        dst.write(cube)
        for i, date_str in enumerate(stack_dates):
            dst.set_band_description(i + 1, f"NDVI_{date_str}")

    print(f"\nStack: {stack_path}  ({n} fechas)")
    return 0


if __name__ == "__main__":
    exit(main())
