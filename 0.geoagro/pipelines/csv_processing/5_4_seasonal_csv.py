# 5_4_seasonal_components.py
import os
import rasterio
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose
from pathlib import Path

def vectorize_seasonal_components(
    base_dir: str,
    stack_type: str,
    csv_path: str = None,
    append: bool = False,
    period: int = 12
) -> str:
    """
    Vectoriza los componentes estacionales de los stacks de NDVI en base_dir,
    guardándolos en csv_path (append opcional). Devuelve la ruta csv_path.
    """
    all_data = []
    for polygon_dir in os.listdir(base_dir):
        try:
            polygon_fid = float(polygon_dir)
            stack_path = os.path.join(base_dir, polygon_dir, "STACK", stack_type)
            if not os.path.exists(stack_path):
                continue

            print(f"Procesando polígono {polygon_fid}...")
            with rasterio.open(stack_path) as src:
                stack_data = src.read()  # shape: (bands, h, w)
            num_bands, h, w = stack_data.shape
            mask = np.any(stack_data != 0, axis=0)

            píxeles = 0
            for y in range(h):
                for x in range(w):
                    if not mask[y, x]:
                        continue
                    vec = stack_data[:, y, x]
                    sea = np.full_like(vec, np.nan)
                    if len(vec) >= 2 * period:
                        try:
                            sea = seasonal_decompose(vec, model="additive", period=period).seasonal
                        except Exception:
                            pass
                    row = {
                        "polygon_fid": polygon_fid,
                        "pixel_x": x,
                        "pixel_y": y,
                        **{f"band_{i+1}": sea[i] for i in range(num_bands)}
                    }
                    all_data.append(row)
                    píxeles += 1

            print(f"  → {píxeles} píxeles procesados")
        except ValueError:
            continue

    df = pd.DataFrame(all_data)

    if df.empty:
        print("No se encontraron datos válidos para procesar.")
        return None
    if csv_path is None:
        csv_path = os.path.join(base_dir, "seasonal_components.csv")
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and os.path.exists(csv_path) else "w"
    df.to_csv(csv_path, index=False, header=(mode == "w"), mode=mode)
    print(f"Guardado: {csv_path} ({'append' if mode=='a' else 'write'})")
    return csv_path

def main(
    base_dirs: list,
    stack_type: str,
    output_csv: str,
    append: bool = False,
    period: int = 12
):
    """
    Ejecuta vectorize_seasonal_components para cada carpeta en base_dirs.
    """
    for i, bd in enumerate(base_dirs):
        vectorize_seasonal_components(
            bd,
            stack_type=stack_type,
            csv_path=output_csv,
            append=(append and i > 0),
            period=period
        )

if __name__ == "__main__":
    # solo para pruebas independientes
    DIRS = ["/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/2023_2024/Santana606_1057/RECORTES"]
    OUT = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/8.CSV_ALL/2023_2024/Santana606_1057/evi/seasonal/CSV_ALL.csv"
    main(DIRS, OUT, append=False, period=12)
