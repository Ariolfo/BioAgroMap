# 8_2_tif_clustered.py
import os
import numpy as np
import pandas as pd
import rasterio
import matplotlib.cm as cm
from matplotlib.colors import ListedColormap
from pathlib import Path

def plot_and_save_cluster_tif(
    csv_path: str,
    base_raster_dir: str,
    output_folder: str
) -> None:
    """
    Para cada polígono en el CSV:
      - Carga stack_ndvi.tif
      - Crea máscara indexada por cluster y escribe TIFF con paleta.
    """
    # Verificar que el CSV existe, si no, buscar alternativas
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"⚠️ No se encontró el archivo CSV: {csv_path}")
        print(f"🔍 Buscando archivos alternativos...")
        
        # Buscar archivos de signatures en la estructura del proyecto
        base_path = csv_file.parent.parent.parent if csv_file.parent else Path(csv_path).parent
        possible_files = [
            base_path / "clustering" / "fourth_clusters_signatures.csv",
            base_path / "clustering" / "signatures.csv",
            base_path.rglob("signatures.csv"),
            base_path.rglob("fourth_clusters_signatures.csv"),
        ]
        
        found_file = None
        for pattern in possible_files:
            if isinstance(pattern, Path) and pattern.exists():
                found_file = pattern
                break
            elif hasattr(pattern, '__iter__'):
                for f in pattern:
                    if f.exists():
                        found_file = f
                        break
                if found_file:
                    break
        
        if found_file:
            print(f"✅ Archivo encontrado: {found_file}")
            csv_path = str(found_file)
        else:
            print(f"❌ Error: No se encontró ningún archivo CSV de signatures.")
            print(f"💡 Asegúrate de ejecutar primero:")
            print(f"   - '7_3_fourth_clusters' para generar fourth_clusters_signatures.csv, o")
            print(f"   - '7_2_cluster_raw' para generar signatures.csv")
            return
    
    os.makedirs(output_folder, exist_ok=True)

    df = pd.read_csv(csv_path)
    
    # Verificar que tiene las columnas necesarias
    required_cols = ['type', 'cluster_label', 'polygon_fid', 'pixel_x', 'pixel_y']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Error: El CSV no tiene las columnas requeridas: {missing_cols}")
        print(f"💡 Asegúrate de ejecutar primero el módulo '7_3_fourth_clusters' para generar el CSV correcto.")
        return
    
    df = df[df['type'] == 'individual']
    if df.empty:
        print("⚠️ No se encontraron firmas individuales en el CSV.")
        print(f"   Columnas disponibles: {list(df.columns)}")
        return

    global_clusters = sorted(df['cluster_label'].unique())
    n_global_clusters = len(global_clusters)
    global_cluster_to_index = {cl: i+1 for i, cl in enumerate(global_clusters)}

    polygon_ids = sorted(df['polygon_fid'].unique())
    print(f"Se encontraron {len(polygon_ids)} polígonos en el CSV.")

    # Generar paleta global una vez
    palette = [(0,0,0,255)] * 256
    base_cmap = cm.get_cmap('jet', n_global_clusters)
    for i, cl in enumerate(global_clusters):
        r, g, b, _ = base_cmap(i)
        palette[i+1] = (int(r*255), int(g*255), int(b*255), 255)
    colormap_dict = {i: palette[i] for i in range(len(palette))}

    for pid in polygon_ids:
        df_poly = df[df['polygon_fid'] == pid]
        if df_poly.empty:
            print(f"⚠️ No hay datos para polygon_fid={pid}. Se omite.")
            continue

        print(f"📊 Procesando polígono {pid} ({len(df_poly)} píxeles)...")

        # Buscar raster en todas las subcarpetas disponibles
        base_path = Path(base_raster_dir)
        raster_path = None
        
        if not base_path.exists():
            print(f"❌ La carpeta base no existe: {base_raster_dir}")
            continue
        
        # Buscar en todas las subcarpetas
        found_dirs = []
        for subdir in base_path.iterdir():
            if subdir.is_dir():
                stack_path = subdir / "STACK" / "stack_ndvi.tif"
                if stack_path.exists():
                    found_dirs.append((subdir.name, stack_path))
        
        if not found_dirs:
            print(f"❌ No se encontraron rasters en ninguna subcarpeta de {base_raster_dir}")
            continue
        
        # Si solo hay una carpeta, usarla (caso común: carpeta "nan")
        if len(found_dirs) == 1:
            raster_path = found_dirs[0][1]
            print(f"✅ Raster encontrado en carpeta '{found_dirs[0][0]}': {raster_path}")
        else:
            # Intentar coincidir por nombre de carpeta
            raster_paths_to_try = [
                (f"{pid}.0", base_path / f"{pid}.0" / "STACK" / "stack_ndvi.tif"),
                (str(int(float(pid))), base_path / str(int(float(pid))) / "STACK" / "stack_ndvi.tif"),
                (str(pid), base_path / str(pid) / "STACK" / "stack_ndvi.tif"),
                ("nan", base_path / "nan" / "STACK" / "stack_ndvi.tif"),
            ]
            
            for name, path in raster_paths_to_try:
                if path.exists():
                    raster_path = path
                    print(f"✅ Raster encontrado en carpeta '{name}': {raster_path}")
                    break
            
            # Si no se encontró por nombre, usar el primero disponible
            if raster_path is None:
                raster_path = found_dirs[0][1]
                print(f"⚠️ Usando primera carpeta disponible '{found_dirs[0][0]}': {raster_path}")
        
        if raster_path is None:
            print(f"❌ No se pudo determinar el raster para polígono {pid}")
            continue

        with rasterio.open(raster_path) as src:
            profile = src.profile.copy()
            height, width = profile['height'], profile['width']

        mask = np.zeros((height, width), dtype=np.uint8)

        for _, row in df_poly.iterrows():
            x = int(row['pixel_x'])
            y = int(row['pixel_y'])
            cl = row['cluster_label']
            idx = global_cluster_to_index.get(cl, 0)
            if 0 <= y < height and 0 <= x < width:
                mask[y, x] = idx

        profile.update({
            'count': 1,
            'dtype': 'uint8',
            'photometric': 'PALETTE',
            'nodata': 0,
        })

        out_tif_path = Path(output_folder) / f"polygon_{pid}_clusters.tif"
        with rasterio.open(out_tif_path, 'w', **profile) as dst:
            dst.write(mask, 1)
            dst.write_colormap(1, colormap_dict)

        print(f"Guardado TIFF para polígono {pid}: {out_tif_path}")


def main(
    csv_path: str,
    base_raster_dir: str,
    output_folder: str
) -> None:
    """
    Función de entrada para pipeline.
    """
    plot_and_save_cluster_tif(
        csv_path,
        base_raster_dir,
        output_folder
    )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_path')
    parser.add_argument('base_raster_dir')
    parser.add_argument('output_folder')
    args = parser.parse_args()
    main(
        args.csv_path,
        args.base_raster_dir,
        args.output_folder
    )
