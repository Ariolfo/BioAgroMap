#!/usr/bin/env python3
"""
Normaliza un stack NDVI (min–max global sobre valores finitos) a rango [0, 1].

Uso:
  python normalize_ndvi_stack.py
  python normalize_ndvi_stack.py -i recorte_3_year/NDVI/STACK_NDVI_3_YEAR.tif \\
 -o recorte_3_year/NDVI/STACK_NDVI_3_YEAR_normalized.tif
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio


def main():
    parser = argparse.ArgumentParser(description="Min–max [0,1] sobre stack NDVI.")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("recorte_3_year/NDVI/STACK_NDVI_3_YEAR.tif"),
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("recorte_3_year/NDVI/STACK_NDVI_3_YEAR_normalized.tif"),
    )
    args = parser.parse_args()

    src_path = args.input.resolve()
    if not src_path.exists():
        print(f"No existe: {src_path}")
        return 1

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_path) as src:
        cube = src.read().astype(np.float32)
        valid = np.isfinite(cube)
        if not np.any(valid):
            print("Sin valores finitos.")
            return 1
        vmin = float(np.min(cube[valid]))
        vmax = float(np.max(cube[valid]))
        if vmax <= vmin:
            norm = np.zeros_like(cube, dtype=np.float32)
            norm[valid] = 0.5
        else:
            norm = np.full_like(cube, np.nan, dtype=np.float32)
            norm[valid] = (cube[valid] - vmin) / (vmax - vmin)

        meta = src.meta.copy()
        meta.update(dtype="float32", nodata=None)
        with rasterio.open(out_path, "w", **meta) as dst:
            dst.write(norm)
            for b in range(1, src.count + 1):
                desc = src.descriptions[b - 1]
                if desc:
                    dst.set_band_description(b, desc)
        print(f"Min={vmin:.6f}  Max={vmax:.6f}")
        print(f"Guardado: {out_path}")
    return 0


if __name__ == "__main__":
    exit(main())
