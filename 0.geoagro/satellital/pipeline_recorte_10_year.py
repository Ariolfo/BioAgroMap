#!/usr/bin/env python3
"""
Pipeline: recorte S2 → NDVI por fecha → stack → normalización → gráficos.

1. Recorta `downloads_sentinel2/*.tif` (YYYY-MM-DD.tif) con el shapefile.
2. NDVI en recorte_10_year/NDVI/NDVI_YYYY-MM-DD.tif y stack STACK_NDVI_10_YEAR.tif.
3. Normaliza el stack y genera PNG de serie temporal (crudo, normalizado y comparación 2 paneles).

Uso (desde la raíz del proyecto):
  python pipeline_recorte_10_year.py

Por defecto usa ``~/Downloads/palm_3_10_years/palm_10_years.shp``. Otro archivo:
  python pipeline_recorte_10_year.py --shape /ruta/al.shp
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SHAPE_10Y = Path.home() / "Downloads/palm_3_10_years/palm_10_years.shp"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode != 0:
        sys.exit(r.returncode)


def main() -> int:
    p = argparse.ArgumentParser(description="Pipeline NDVI 10 años → recorte_10_year")
    p.add_argument(
        "--shape",
        "-s",
        type=Path,
        default=DEFAULT_SHAPE_10Y,
        help=f"Ruta al .shp (por defecto: {DEFAULT_SHAPE_10Y})",
    )
    p.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "downloads_sentinel2",
        help="Carpeta con GeoTIFF S2 por fecha",
    )
    p.add_argument(
        "--out-dir",
        "-o",
        type=Path,
        default=ROOT / "recorte_10_year",
        help="Salida del recorte (NDVI queda en out-dir/NDVI)",
    )
    p.add_argument(
        "--skip-clip",
        action="store_true",
        help="No ejecutar recorte (solo NDVI, stack, norm y gráficos)",
    )
    args = p.parse_args()

    shape = args.shape.resolve()
    if not args.skip_clip:
        if not shape.is_file():
            print(f"No existe el shapefile: {shape}")
            print("Pase --shape con la ruta al .shp (p. ej. ~/Downloads/palm_3_10_years/palm_10_years.shp)")
            return 1
        run(
            [
                sys.executable,
                str(ROOT / "clip_rasters_by_shapefile.py"),
                "--shape",
                str(shape),
                "--input-dir",
                str(args.input_dir.resolve()),
                "--out-dir",
                str(args.out_dir.resolve()),
            ]
        )

    out_dir = args.out_dir.resolve()
    ndvi_dir = out_dir / "NDVI"
    stack = ndvi_dir / "STACK_NDVI_10_YEAR.tif"
    stack_norm = ndvi_dir / "STACK_NDVI_10_YEAR_normalized.tif"

    run(
        [
            sys.executable,
            str(ROOT / "compute_ndvi_stack.py"),
            "--input-dir",
            str(out_dir),
            "--stack-name",
            "STACK_NDVI_10_YEAR.tif",
        ]
    )

    run(
        [
            sys.executable,
            str(ROOT / "normalize_ndvi_stack.py"),
            "-i",
            str(stack),
            "-o",
            str(stack_norm),
        ]
    )

    run(
        [
            sys.executable,
            str(ROOT / "plot_ndvi_stack_timeseries.py"),
            "-i",
            str(stack),
        ]
    )
    run(
        [
            sys.executable,
            str(ROOT / "plot_ndvi_stack_timeseries.py"),
            "-i",
            str(stack_norm),
        ]
    )
    run(
        [
            sys.executable,
            str(ROOT / "plot_ndvi_stack_dual_timeseries.py"),
            "--raw",
            str(stack),
            "--normalized",
            str(stack_norm),
        ]
    )

    print("\nListo.")
    print(f"  Recorte: {out_dir}")
    print(f"  NDVI + stack: {ndvi_dir}")
    print(f"  Gráficos: {stack.with_name(stack.stem + '_timeseries.png')}, "
          f"{stack_norm.with_name(stack_norm.stem + '_timeseries.png')}, "
          f"{ndvi_dir / 'STACK_NDVI_10_YEAR_dual_timeseries.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
