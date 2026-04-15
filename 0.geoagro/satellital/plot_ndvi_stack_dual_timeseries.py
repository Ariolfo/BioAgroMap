#!/usr/bin/env python3
"""
Una figura con dos paneles: serie temporal NDVI crudo y normalizado (media ±1 σ espacial).

Uso:
  python plot_ndvi_stack_dual_timeseries.py \\
    --raw recorte_10_year/NDVI/STACK_NDVI_10_YEAR.tif \\
    --normalized recorte_10_year/NDVI/STACK_NDVI_10_YEAR_normalized.tif
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio


def band_stats(src: rasterio.io.DatasetReader) -> tuple[np.ndarray, np.ndarray, list[str]]:
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
    return (
        np.array(means, dtype=np.float64),
        np.array(stds, dtype=np.float64),
        labels,
    )


def plot_panel(
    ax,
    means: np.ndarray,
    stds: np.ndarray,
    labels: list[str],
    ylabel: str,
    title: str,
    ylim: tuple[float, float] | None,
    ref_lines: tuple[float, ...],
) -> None:
    n = len(means)
    x = np.arange(n)
    ax.fill_between(
        x,
        means - stds,
        means + stds,
        alpha=0.35,
        color="C0",
        label="Media ± 1 σ (espacial)",
    )
    ax.plot(x, means, "o-", color="C0", lw=2, markersize=5, label="Media NDVI")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    for y in ref_lines:
        ax.axhline(y, color="gray", ls="--", lw=0.8)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", "-r", type=Path, required=True)
    parser.add_argument("--normalized", "-n", type=Path, required=True)
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="PNG (por defecto: junto al stack crudo, sufijo _dual_timeseries.png)",
    )
    args = parser.parse_args()

    raw_path = args.raw.resolve()
    norm_path = args.normalized.resolve()
    for path in (raw_path, norm_path):
        if not path.exists():
            print(f"No existe: {path}")
            return 1

    if args.out is None:
        out_png = raw_path.with_name(raw_path.stem + "_dual_timeseries.png")
    else:
        out_png = args.out

    with rasterio.open(raw_path) as src_r, rasterio.open(norm_path) as src_n:
        if src_r.count != src_n.count:
            print(
                f"Distinto número de bandas: raw={src_r.count} vs norm={src_n.count}"
            )
            return 1
        m_r, s_r, labels = band_stats(src_r)
        m_n, s_n, labels_n = band_stats(src_n)
        if labels != labels_n:
            labels = labels  # preferir etiquetas del crudo

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(14, 5), sharex=True)
    plot_panel(
        ax0,
        m_r,
        s_r,
        labels,
        "NDVI",
        "NDVI (media espacial ±1 σ)",
        ylim=None,
        ref_lines=(0,),
    )
    plot_panel(
        ax1,
        m_n,
        s_n,
        labels,
        "NDVI normalizado [0, 1]",
        "NDVI normalizado (min–max global; media ±1 σ)",
        ylim=(-0.05, 1.05),
        ref_lines=(0, 1),
    )
    fig.tight_layout()
    out_path = out_png.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close()
    print(f"Guardado: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
