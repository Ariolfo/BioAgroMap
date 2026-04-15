#!/usr/bin/env python3
"""
Codo (inercia / WCSS) y coeficiente de silueta para elegir k en K-means (NDVI multibanda).

Uso:
  python ndvi_elbow_kmeans.py
  python ndvi_elbow_kmeans.py --recortes /ruta/RECORTES --max-k 12 --max-samples 200000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def load_pixel_matrix(
    tif_paths: list[Path],
    max_samples: int,
    seed: int,
) -> np.ndarray:
    if not tif_paths:
        raise ValueError("Sin rutas TIF")

    bands = []
    with rasterio.open(tif_paths[0]) as ref:
        shape = ref.shape
        for p in tif_paths:
            with rasterio.open(p) as src:
                if src.shape != shape:
                    raise ValueError(f"Shape distinto: {p.name} {src.shape} vs {shape}")
                bands.append(src.read(1).astype(np.float32))

    cube = np.stack(bands, axis=0)  # (n_bands, H, W)
    pixels = cube.reshape(cube.shape[0], -1).T  # (n_pix, n_bands)
    valid = np.all(np.isfinite(pixels), axis=1)
    pixels = pixels[valid]
    if pixels.size == 0:
        raise ValueError("No hay píxeles válidos (finitos en todas las bandas).")

    rng = np.random.default_rng(seed)
    n = pixels.shape[0]
    if n > max_samples:
        idx = rng.choice(n, size=max_samples, replace=False)
        pixels = pixels[idx]

    return pixels


def elbow_k_from_inertias(ks: list[int], inertias: list[float]) -> int:
    """Punto de codo: máxima distancia ortogonal a la recta (k1,I1)--(kK,IK)."""
    k_arr = np.array(ks, dtype=np.float64)
    y = np.array(inertias, dtype=np.float64)
    if len(k_arr) < 3:
        return int(ks[len(ks) // 2])

    p1 = np.array([k_arr[0], y[0]])
    p2 = np.array([k_arr[-1], y[-1]])
    line = p2 - p1
    line_len = np.linalg.norm(line)
    if line_len < 1e-12:
        return int(ks[0])

    distances = []
    for i in range(len(k_arr)):
        p = np.array([k_arr[i], y[i]])
        t = np.dot(p - p1, line) / (line_len**2)
        t = np.clip(t, 0.0, 1.0)
        proj = p1 + t * line
        distances.append(np.linalg.norm(p - proj))

    # No usar extremos como “codo” artificial
    inner = np.array(distances[1:-1])
    if inner.size == 0:
        return int(ks[1])
    best_local = int(np.argmax(inner) + 1)
    return int(ks[best_local])


def silhouette_on_fit(
    X: np.ndarray,
    labels: np.ndarray,
    subsample: int,
    seed: int,
) -> float:
    """Silueta media; si hay muchos puntos, submuestra (coste ~ O(n²))."""
    n = X.shape[0]
    if n < 2 or len(np.unique(labels)) < 2:
        return float("nan")
    if n <= subsample:
        return float(silhouette_score(X, labels, metric="euclidean"))
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=subsample, replace=False)
    return float(silhouette_score(X[idx], labels[idx], metric="euclidean"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Codo K-means sobre NDVI multibanda")
    parser.add_argument(
        "--recortes",
        type=Path,
        default=Path(
            "/home/agrosavia/Documents/PROJECTS/project_satellital/"
            "recorte_10_year/NDVI/_4_4_viz_input/satellital/RECORTES"
        ),
    )
    parser.add_argument(
        "--bands",
        nargs="+",
        default=[
            "NDVI_2025-01-06.tif",
            "NDVI_2025-10-05.tif",
            "NDVI_2025-11-04.tif",
            "NDVI_2025-12-04.tif",
        ],
    )
    parser.add_argument("--max-k", type=int, default=12)
    parser.add_argument("--max-samples", type=int, default=200_000)
    parser.add_argument(
        "--silhouette-subsample",
        type=int,
        default=15_000,
        help="Máx. píxeles para calcular silueta (el resto se submuestrea).",
    )
    parser.add_argument(
        "--no-silhouette",
        action="store_true",
        help="No calcular ni dibujar silueta.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="PNG del gráfico (por defecto junto a RECORTES/../cluster_elbow/)",
    )
    args = parser.parse_args()

    recortes = args.recortes.resolve()
    paths = [recortes / name for name in args.bands]
    for p in paths:
        if not p.is_file():
            print(f"No existe: {p}")
            return 1

    print(f"Píxeles: cargando {len(paths)} bandas desde {recortes}")
    X = load_pixel_matrix(paths, args.max_samples, args.seed)
    print(f"Muestra para K-means: {X.shape[0]} píxeles x {X.shape[1]} bandas")

    ks = list(range(1, args.max_k + 1))
    inertias: list[float] = []
    silhouettes: list[float] = []

    for k in ks:
        km = KMeans(n_clusters=k, random_state=args.seed, n_init=10)
        labels = km.fit_predict(X)
        inertias.append(float(km.inertia_))
        if args.no_silhouette or k < 2:
            silhouettes.append(float("nan"))
            sil_s = float("nan")
        else:
            sil_s = silhouette_on_fit(
                X, labels, args.silhouette_subsample, args.seed
            )
            silhouettes.append(sil_s)
        if args.no_silhouette or k < 2:
            print(f"  k={k:2d}  inertia={inertias[-1]:.2e}")
        else:
            print(
                f"  k={k:2d}  inertia={inertias[-1]:.2e}  silhouette={sil_s:.4f}"
            )

    k_elbow = elbow_k_from_inertias(ks, inertias)
    print(f"\nK sugerido (codo geométrico): {k_elbow}")

    k_sil: int | None = None
    if not args.no_silhouette:
        sil_ks = [(k, s) for k, s in zip(ks, silhouettes) if k >= 2 and np.isfinite(s)]
        if sil_ks:
            k_sil = max(sil_ks, key=lambda t: t[1])[0]
            print(f"K sugerido (silueta máxima): {k_sil}  (score={max(t[1] for t in sil_ks):.4f})")
        else:
            print("K sugerido (silueta): no disponible")

    if args.out is None:
        out_dir = recortes.parent / "cluster_elbow"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_png = out_dir / "elbow_silhouette_ndvi_4bandas.png"
    else:
        out_png = args.out.resolve()
        out_png.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2 if not args.no_silhouette else 1, figsize=(12, 5) if not args.no_silhouette else (8, 5))
    if args.no_silhouette:
        ax1 = axes
    else:
        ax1, ax2 = axes

    ax1.plot(ks, inertias, "o-", lw=2, ms=8, color="C0")
    ax1.axvline(
        k_elbow, color="C3", ls="--", lw=1.5, label=f"Codo: k={k_elbow}"
    )
    ax1.set_xlabel("Número de clusters (k)")
    ax1.set_ylabel("Inercia (WCSS)")
    ax1.set_title("Método del codo")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    if not args.no_silhouette:
        ks2 = [k for k in ks if k >= 2]
        sil_y = [silhouettes[ks.index(k)] for k in ks2]
        ax2.plot(ks2, sil_y, "s-", lw=2, ms=8, color="C2")
        if k_sil is not None:
            ax2.axvline(
                k_sil,
                color="C4",
                ls="--",
                lw=1.5,
                label=f"Silueta máx.: k={k_sil}",
            )
        ax2.set_xlabel("Número de clusters (k)")
        ax2.set_ylabel("Coeficiente de silueta (promedio)")
        ax2.set_title("Silueta (k ≥ 2)")
        ax2.grid(True, alpha=0.3)
        ax2.legend()

    fig.suptitle("K-means — 4 fechas NDVI", y=1.02)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close()
    print(f"\nGráfico guardado: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
