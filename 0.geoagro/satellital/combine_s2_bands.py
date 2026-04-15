#!/usr/bin/env python3
"""
Combina bandas de imágenes Sentinel-2 (productos .SAFE L1C/L2A) en un único GeoTIFF.

Uso:
  python combine_s2_bands.py <ruta_producto.SAFE> [--bands B04 B03 B02] [--res 10] [--out salida.tif]
  python combine_s2_bands.py downloads_sentinel2  # procesa todos los .SAFE del directorio

Presets: rgb, fcir (falso color infrarrojo), multiband (B02-B08A a 20m).
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject


# Presets de bandas: nombre -> (bandas en orden, resolución en metros)
PRESETS = {
    "rgb": (["B04", "B03", "B02"], 10),   # Rojo, Verde, Azul (color natural)
    "fcir": (["B08", "B04", "B03"], 10),  # NIR, R, G (falso color vegetación)
    "multiband": (["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A"], 20),
}

# Resoluciones típicas S2: 10m, 20m, 60m
RES_FOLDERS = {"10": "R10m", "20": "R20m", "60": "R60m"}


def parse_date_from_safe_name(name: str) -> str | None:
    """Extrae YYYY-MM-DD del nombre de producto (ej. S2A_MSIL1C_20250102T... -> 2025-01-02)."""
    match = re.search(r"(\d{4})(\d{2})(\d{2})T", name, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def find_img_data(safe_path: Path) -> Path | None:
    """Devuelve la ruta IMG_DATA del producto .SAFE (primer GRANULE)."""
    safe_path = Path(safe_path)
    if not safe_path.is_dir():
        return None
    granules = safe_path / "GRANULE"
    if not granules.is_dir():
        return None
    for granule in sorted(granules.iterdir()):
        if not granule.is_dir():
            continue
        img_data = granule / "IMG_DATA"
        if img_data.is_dir():
            return img_data
    return None


def find_band_files(img_data: Path, bands: list[str], res_m: int) -> dict[str, Path]:
    """
    Busca archivos JP2 para cada banda en la resolución dada.
    Soporta L2A (IMG_DATA/R10m con *_B04_10m.jp2) y L1C (IMG_DATA con *_B04.jp2).
    """
    res_folder = RES_FOLDERS.get(str(res_m))
    if not res_folder:
        res_folder = "R10m"
    band_dir = img_data / res_folder
    if band_dir.is_dir():
        return _find_band_files_in_dir(band_dir, bands, res_m)
    # L1C: bandas en IMG_DATA sin subcarpeta R10m, nombres *_B02.jp2
    if img_data.is_dir():
        return _find_band_files_in_dir_l1c(img_data, bands)
    return {}


def _find_band_files_in_dir(band_dir: Path, bands: list[str], res_m: int) -> dict[str, Path]:
    """Busca archivos *_BXX_Xm.jp2 (L2A) dentro de band_dir."""
    band_dir = Path(band_dir)
    if not band_dir.is_dir():
        return {}
    suffix = f"_{res_m}m.jp2"
    found = {}
    for f in band_dir.iterdir():
        if f.suffix.lower() != ".jp2":
            continue
        name = f.name
        for band in bands:
            if band in found:
                continue
            if f"_{band}_{res_m}m.jp2" in name or name.endswith(f"_{band}{suffix}"):
                found[band] = f
                break
    return found


def _find_band_files_in_dir_l1c(band_dir: Path, bands: list[str]) -> dict[str, Path]:
    """Busca archivos *_BXX.jp2 (L1C, sin sufijo _10m) en IMG_DATA."""
    band_dir = Path(band_dir)
    if not band_dir.is_dir():
        return {}
    found = {}
    for f in band_dir.iterdir():
        if f.suffix.lower() != ".jp2":
            continue
        name = f.name
        for band in bands:
            if band in found:
                continue
            if name.endswith(f"_{band}.jp2"):
                found[band] = f
                break
    return found


def read_band(path: Path) -> tuple[np.ndarray, dict]:
    """Lee una banda con rasterio; devuelve array y metadata (profile)."""
    with rasterio.open(path) as src:
        data = src.read()
        profile = src.profile.copy()
    return data, profile


def profile_for_geotiff(ref_profile: dict, count: int, dtype) -> dict:
    """Perfil para escribir GeoTIFF (no JP2)."""
    p = ref_profile.copy()
    p.update(
        driver="GTiff",
        count=count,
        dtype=dtype,
        compress="lzw",
        tiled=True,
        blockxsize=512,
        blockysize=512,
    )
    return p


def stack_bands_same_resolution(
    band_paths: list[Path], ref_profile: dict
) -> tuple[np.ndarray, dict]:
    """
    Apila varias bandas (misma resolución y tamaño) en un array (n_bands, H, W).
    ref_profile: metadata de la primera banda para el GeoTIFF de salida.
    """
    arrays = []
    for p in band_paths:
        arr, _ = read_band(p)
        arrays.append(arr)
    stack = np.concatenate(arrays, axis=0).astype(np.float32)
    out_profile = ref_profile.copy()
    out_profile.update(count=stack.shape[0], dtype=stack.dtype)
    return stack, out_profile


def resample_to_ref(
    src_path: Path, ref_profile: dict, ref_shape: tuple[int, int]
) -> np.ndarray:
    """Redimensiona una banda al grid de referencia (ref_shape)."""
    with rasterio.open(src_path) as src:
        data = src.read(
            out_shape=ref_shape,
            resampling=Resampling.bilinear,
        )
    return data.astype(np.float32)


def combine_bands_in_safe(
    safe_path: Path,
    bands: list[str],
    res_m: int,
    out_path: Path,
    scale: float = 1.0,
) -> Path:
    """
    Combina las bandas indicadas de un producto .SAFE en un GeoTIFF.
    scale: factor para valores (ej. 1/10000 para reflectance 0-1).
    """
    img_data = find_img_data(safe_path)
    if not img_data:
        raise FileNotFoundError(f"No se encontró IMG_DATA en {safe_path}")

    band_files = find_band_files(img_data, bands, res_m)
    missing = [b for b in bands if b not in band_files]
    if missing:
        raise FileNotFoundError(
            f"Bandas no encontradas en {img_data}: {missing}. "
            f"Disponibles en R{res_m}m: listar {img_data / RES_FOLDERS[str(res_m)]}"
        )

    paths_ordered = [band_files[b] for b in bands]
    stack, ref_profile = stack_bands_same_resolution(paths_ordered, read_band(paths_ordered[0])[1])

    if scale != 1.0:
        stack = (stack * scale).astype(np.float32)
    else:
        stack = stack.astype(np.float32)  # GTiff acepta float32

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile = profile_for_geotiff(ref_profile, count=len(bands), dtype=stack.dtype)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(stack)

    return out_path


def process_safe(
    safe_path: Path,
    preset: str | None,
    bands: list[str] | None,
    res_m: int,
    out_dir: Path,
    scale: float,
    name_by_date: bool = False,
) -> Path:
    """Procesa un producto .SAFE y escribe el GeoTIFF en out_dir."""
    safe_path = Path(safe_path)
    if preset and preset.lower() in PRESETS:
        bands_list, res_default = PRESETS[preset.lower()]
        bands = bands or bands_list
        res_m = res_m or res_default
    else:
        bands = bands or ["B04", "B03", "B02"]
        res_m = res_m or 10

    if name_by_date:
        date_str = parse_date_from_safe_name(safe_path.name)
        out_name = f"{date_str}.tif" if date_str else f"{safe_path.stem}_bands.tif"
    else:
        safe_name = safe_path.name.replace(".SAFE", "")
        out_name = f"{safe_name}_bands_{'_'.join(bands)}_R{res_m}m.tif"
    out_path = out_dir / out_name

    return combine_bands_in_safe(safe_path, bands, res_m, out_path, scale=scale)


def combine_bands_from_folder(
    band_dir: Path,
    bands: list[str],
    out_path: Path,
    res_m: int = 10,
    scale: float = 1.0,
) -> Path:
    """
    Combina bandas desde una carpeta que contiene los JP2 (ej. IMG_DATA/R10m).
    band_dir: ruta a R10m (o R20m/R60m) con archivos *_B02_10m.jp2, etc.
    """
    band_dir = Path(band_dir)
    band_files = _find_band_files_in_dir(band_dir, bands, res_m)
    missing = [b for b in bands if b not in band_files]
    if missing:
        raise FileNotFoundError(f"En {band_dir} no se encontraron: {missing}")

    paths_ordered = [band_files[b] for b in bands]
    stack, ref_profile = stack_bands_same_resolution(paths_ordered, read_band(paths_ordered[0])[1])

    if scale != 1.0:
        stack = (stack * scale).astype(np.float32)
    else:
        stack = stack.astype(np.float32)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile = profile_for_geotiff(ref_profile, count=len(bands), dtype=stack.dtype)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(stack)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Combina bandas de productos Sentinel-2 (.SAFE) en un GeoTIFF."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Ruta a un .SAFE o al directorio con varios .SAFE (ej. downloads_sentinel2)",
    )
    parser.add_argument(
        "--bands", "-b",
        nargs="+",
        default=None,
        help="Bandas en orden, ej: B04 B03 B02. Por defecto RGB.",
    )
    parser.add_argument(
        "--preset", "-p",
        choices=list(PRESETS),
        default=None,
        help="Preset: rgb, fcir o multiband.",
    )
    parser.add_argument(
        "--res", "-r",
        type=int,
        default=None,
        choices=[10, 20, 60],
        help="Resolución en metros (10, 20 o 60).",
    )
    parser.add_argument(
        "--out", "-o",
        type=Path,
        default=None,
        help="Archivo o directorio de salida. Por defecto: mismo dir que el .SAFE.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Factor de escala (ej. 0.0001 para reflectance 0-1). Por defecto 1 (valores 0-10000).",
    )
    parser.add_argument(
        "--name-by-date", "-d",
        action="store_true",
        help="Nombrar salida por fecha de adquisición (YYYY-MM-DD.tif).",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: la ruta no existe: {input_path}")
        print("Uso: python combine_s2_bands.py <carpeta .SAFE o IMG_DATA/R10m> [--bands B02 B03 B04 B08] [-o salida.tif]")
        return 1
    if not input_path.is_dir():
        print(f"Error: debe ser una carpeta: {input_path}")
        print("Indique la ruta a un .SAFE o a la carpeta de bandas (ej. .../IMG_DATA/R10m).")
        return 1

    bands = args.bands or (PRESETS.get((args.preset or "").lower(), [["B04", "B03", "B02"], 10])[0])
    res_m = args.res or 10

    # ¿Es una carpeta de bandas directa (ej. .../IMG_DATA/R10m)?
    if not (input_path / "GRANULE").is_dir():
        jp2s = [f for f in input_path.iterdir() if f.suffix.lower() == ".jp2"]
        if jp2s:
            # En R10m sin --bands usar B02 B03 B04 B08 por defecto
            if not (args.bands or args.preset):
                bands = ["B02", "B03", "B04", "B08"]
            # Inferir resolución del nombre de carpeta (R10m -> 10)
            if "R10m" in input_path.name:
                res_m = 10
            elif "R20m" in input_path.name:
                res_m = 20
            elif "R60m" in input_path.name:
                res_m = 60
            out_path = Path(args.out) if args.out else (input_path / f"combined_{'_'.join(bands)}_R{res_m}m.tif")
            if args.out and out_path.is_dir():
                out_path = out_path / f"combined_{'_'.join(bands)}_R{res_m}m.tif"
            try:
                out_file = combine_bands_from_folder(input_path, bands, out_path, res_m=res_m, scale=args.scale)
                print(f"OK: {out_file}")
                return 0
            except Exception as e:
                print(f"Error: {e}")
                return 1

    safe_list = []
    if not input_path.name.endswith(".SAFE"):
        # Directorio con varios .SAFE
        for item in sorted(input_path.iterdir()):
            if item.is_dir() and item.name.endswith(".SAFE"):
                safe_list.append(item)
        if not safe_list:
            print(f"No se encontraron carpetas .SAFE en {input_path}")
            return 1
        out_dir = Path(args.out) if args.out else input_path
        if out_dir.suffix.lower() == ".tif":
            out_dir = out_dir.parent
    else:
        # Una sola carpeta .SAFE
        safe_list = [input_path]
        out_dir = (Path(args.out).parent if args.out and str(args.out).lower().endswith(".tif") else input_path.parent)

    out_dir = Path(out_dir)
    for i, safe in enumerate(safe_list):
        try:
            # Si es un solo .SAFE y --out es un .tif, usar esa ruta exacta
            if len(safe_list) == 1 and args.out and str(args.out).lower().endswith(".tif"):
                out_path = Path(args.out)
                bands_list = args.bands or (PRESETS.get((args.preset or "").lower(), [["B04", "B03", "B02"], 10])[0])
                res_m = args.res or (PRESETS.get((args.preset or "").lower(), [None, 10])[1]) or 10
                combine_bands_in_safe(safe, bands_list, res_m, out_path, scale=args.scale)
                out_file = out_path
            else:
                out_file = process_safe(
                    safe,
                    preset=args.preset,
                    bands=args.bands,
                    res_m=args.res or 10,
                    out_dir=out_dir,
                    scale=args.scale,
                    name_by_date=args.name_by_date,
                )
            print(f"OK: {out_file}")
        except Exception as e:
            print(f"Error procesando {safe.name}: {e}")

    return 0


if __name__ == "__main__":
    exit(main())
