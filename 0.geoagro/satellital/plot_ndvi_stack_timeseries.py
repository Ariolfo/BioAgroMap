#!/usr/bin/env python3
"""
Gráfico de línea: media espacial del NDVI por fecha desde STACK_NDVI_3_YEAR.tif,
con banda sombreada entre media - 1·std y media + 1·std (std espacial por fecha).

Uso:
  python plot_ndvi_stack_timeseries.py
  python plot_ndvi_stack_timeseries.py -i recorte_3_year/NDVI/STACK_NDVI_3_YEAR.tif -o salida.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio


def main():
    parser = argparse.ArgumentParser()
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
        default=None,
        help="PNG de salida (por defecto: junto al .tif, _timeseries.png).",
    )
    args = parser.parse_args()

    stack_path = args.input.resolve()
    if not stack_path.exists():
        print(f"No existe: {stack_path}")
        return 1

    if args.out is None:
        out_png = stack_path.with_name(stack_path.stem + "_timeseries.png")
    else:
        out_png = args.out

    with rasterio.open(stack_path) as src:
        n = src.count
        means = []
        stds = []
        labels = []
        for b in range(1, n + 1):
            arr = src.read(b).astype(np.float32)
            valid = np.isfinite(arr)
            if not np.any(valid):
                means.append(np.nan)
                stds.append(np.nan)
            else:
                v = arr[valid]
                means.append(float(np.mean(v)))
                stds.append(float(np.std(v)))
            desc = src.descriptions[b - 1] or f"band_{b}"
            labels.append(desc.replace("NDVI_", "") if desc else str(b))

    means = np.array(means, dtype=np.float64)
    stds = np.array(stds, dtype=np.float64)
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(
        x,
        means - stds,
        means + stds,
        alpha=0.35,
        color="C0",
        label="Media ± 1 σ (espacial)",
    )
    ax.plot(x, means, "o-", color="C0", lw=2, markersize=6, label="Media NDVI")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    normalized = "normalized" in stack_path.name.lower()
    if normalized:
        ax.set_ylabel("NDVI normalizado [0, 1]")
        ax.set_title(
            "Serie temporal NDVI normalizado (min–max global; media ±1 σ espacial)"
        )
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(0, color="gray", ls="--", lw=0.8)
        ax.axhline(1, color="gray", ls="--", lw=0.8)
    else:
        ax.set_ylabel("NDVI")
        ax.set_title("Serie temporal NDVI (media espacial y ±1 desv. estándar espacial)")
        ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_path = out_png.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close()
    print(f"Guardado: {out_path}")
    return 0


if __name__ == "__main__":
    exit(main())
