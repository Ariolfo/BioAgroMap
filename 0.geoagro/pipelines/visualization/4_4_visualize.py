import os
import re
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import rasterio


def extract_date(file_name: str) -> str:
    """
    Extrae la fecha en formato 'MM_YYYY' del nombre del archivo.
    Soporta formatos: MM_YYYY (01_2023) y YYYY-MM (2023-01)
    """
    # Intentar formato MM_YYYY (ej: 01_2023)
    match = re.search(r"(\d{2})_(\d{4})", str(file_name))
    if match:
        return match.group(0)
    # Intentar formato YYYY-MM (ej: 2023-01)
    match = re.search(r"(\d{4})-(\d{2})", str(file_name))
    if match:
        # Convertir YYYY-MM a MM_YYYY
        year, month = match.groups()
        return f"{month}_{year}"
    return None


def extract_month_year(date_str: str) -> tuple[int,int]:
    """
    Convierte 'MM_YYYY' en (año, mes).
    """
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None


def visualize_timelapse_for_polygon(
    polygon_dir: Path,
    stack_type: str
):
    """
    Genera y guarda un timelapse (PNG) para un único polígono y tipo de stack dentro de su carpeta TIMELAPSE.

    :param polygon_dir: Path a la carpeta del polígono (p.ej. '1.0').
    :param stack_type: nombre del archivo apilado ('stack_ndvi.tif' o 'stack_evi.tif').
    """
    polygon_id = polygon_dir.name
    stack_path = polygon_dir / "STACK" / stack_type
    if not stack_path.exists():
        print(f"⚠️  No existe stack {stack_path}, saltando.")
        return

    tif_dir = polygon_dir / "RECORTES"
    tif_files = sorted(
        tif_dir.glob("*.tif"),
        key=lambda p: extract_month_year(extract_date(p.name))
    )

    # Leer apilado: (bands, h, w) → (h, w, bands)
    with rasterio.open(stack_path) as src:
        arr = src.read()
    arr = np.moveaxis(arr, 0, -1)

    bands = arr.shape[2]
    if bands != len(tif_files):
        print(f"⚠️  Mismatch {bands} bandas vs {len(tif_files)} TIF en {polygon_id}/{stack_type}, saltando.")
        return

    # Layout: 8 columnas
    cols = 8
    rows = int(np.ceil(bands / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(14, rows * 2))
    axes = axes.flatten()

    for i in range(bands):
        ax = axes[i]
        img = arr[:, :, i]
        ax.imshow(img, cmap='RdYlGn', vmin=0, vmax=1)
        title = extract_date(tif_files[i].name) or tif_files[i].stem
        ax.set_title(title, fontsize=10)
        ax.axis('off')

    # Ocultar ejes sobrantes
    for ax in axes[bands:]:
        ax.axis('off')

    plt.tight_layout()

    # Guardar en carpeta TIMELAPSE dentro del polígono
    out_dir = polygon_dir / "TIMELAPSE" / stack_type.replace('stack_', '').replace('.tif', '')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / f"timelapse_{polygon_id}.png"
    fig.savefig(str(out_png), dpi=150)
    plt.close(fig)
    print(f"✅ Timelapse guardado: {out_png}")


def main(
    recortes_root: str
):
    """
    Itera sobre cada carpeta de polígono en recortes_root y genera timelapses NDVI y EVI.

    :param recortes_root: ruta a carpeta con subdirectorios de polígonos.
    """
    base = Path(recortes_root)
    for polygon_dir in sorted(base.iterdir()):
        if not polygon_dir.is_dir():
            continue
        # NDVI
        visualize_timelapse_for_polygon(polygon_dir, 'stack_ndvi.tif')
        # EVI
        visualize_timelapse_for_polygon(polygon_dir, 'stack_evi.tif')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--recortes_root', required=True,
        help='Ruta a carpeta con subdirs de polígonos'
    )
    args = parser.parse_args()
    main(args.recortes_root)
