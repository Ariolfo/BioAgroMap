#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import rasterio
import matplotlib.cm as cm
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def main(csv_path, base_raster_dir, output_folder):
    """
    Para cada polígono en el CSV:
      - Carga el raster completo (base_raster_dir/<polygon_id>/STACK/stack_ndvi.tif).
      - Filtra las firmas individuales para ese polígono.
      - Crea una matriz (uint8) del tamaño total del raster, inicializada en 0 (fondo).
      - Para cada cluster_label, asigna un índice (1..n) en vez de su valor real.
      - Genera una paleta (colormap) con n_global_clusters colores usando 'jet' de matplotlib.
      - Crea una imagen RGBA aplicando la paleta y la guarda en PNG.
      
    Advertencia:
      - El número de clusters por polígono debe ser <= 255.
    """
    from pathlib import Path
    
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

    # 1) Leer el CSV y filtrar solo 'individual'
    print(f"📄 Leyendo CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   Total filas: {len(df)}")
    print(f"   Columnas: {list(df.columns)}")
    
    # Verificar que tiene las columnas necesarias
    required_cols = ['type', 'cluster_label', 'polygon_fid', 'pixel_x', 'pixel_y']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Error: El CSV no tiene las columnas requeridas: {missing_cols}")
        print(f"   Columnas disponibles: {list(df.columns)}")
        print(f"💡 Asegúrate de ejecutar primero el módulo '7_3_fourth_clusters' para generar el CSV correcto.")
        return
    
    # Normalizar polygon_fid: NaN -> "nan" para coincidir con carpeta nan/ (no eliminar filas)
    df = df.copy()
    mask_na = df['polygon_fid'].isna()
    if mask_na.any():
        print("⚠️ polygon_fid vacíos se asignan a 'nan' para coincidir con carpeta nan/.")
        df.loc[mask_na, 'polygon_fid'] = 'nan'
    df['polygon_fid'] = df['polygon_fid'].astype(str)
    df.loc[df['polygon_fid'] == 'nan', 'polygon_fid'] = 'nan'
    
    df = df[df['type'] == 'individual']
    if df.empty:
        print("⚠️ No se encontraron firmas individuales en el CSV.")
        print(f"   Tipos disponibles: {df['type'].unique() if 'type' in df.columns else 'N/A'}")
        return
    
    print(f"✅ Encontradas {len(df)} firmas individuales")

    global_clusters = sorted(df['cluster_label'].unique())
    n_global_clusters = len(global_clusters)
    # Diccionario global (0 se reserva para fondo, índices empiezan en 1)
    global_cluster_to_index = {cl: i+1 for i, cl in enumerate(global_clusters)}
    
    # 2) Obtener polygon_fid únicos
    polygon_ids = sorted(df['polygon_fid'].unique())
    print(f"Se encontraron {len(polygon_ids)} polígonos en el CSV.")

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
                    found_dirs.append((subdir.name, str(stack_path)))
        
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
                (f"{pid}.0", os.path.join(base_raster_dir, f"{pid}.0", "STACK", "stack_ndvi.tif")),
                (str(int(float(pid))), os.path.join(base_raster_dir, str(int(float(pid))), "STACK", "stack_ndvi.tif")),
                (str(pid), os.path.join(base_raster_dir, str(pid), "STACK", "stack_ndvi.tif")),
                ("nan", os.path.join(base_raster_dir, "nan", "STACK", "stack_ndvi.tif")),
            ]
            
            for name, path in raster_paths_to_try:
                if os.path.exists(path):
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

        # Abrir raster para obtener dimensiones
        with rasterio.open(raster_path) as src:
            height, width = src.height, src.width

        # Crear matriz de índices (uint8) con 0 (fondo)
        mask = np.zeros((height, width), dtype=np.uint8)

        # Llenar la máscara usando el mapeo global de clusters
        for _, row in df_poly.iterrows():
            x = int(row['pixel_x'])
            y = int(row['pixel_y'])
            cl = row['cluster_label']
            if 0 <= y < height and 0 <= x < width:
                mask[y, x] = global_cluster_to_index[cl]

        # Generar paleta: lista de 256 colores RGBA (0 reservado para fondo)
        palette = [(0, 0, 0, 255)] * 256
        base_cmap = cm.get_cmap('jet', n_global_clusters)
        for i in range(n_global_clusters):
            r, g, b, a = base_cmap(i)
            palette[i+1] = (int(r*255), int(g*255), int(b*255), 255)

        # Crear imagen RGBA aplicando la paleta a la máscara
        palette_array = np.array(palette, dtype=np.uint8) 
        img_rgba = palette_array[mask]  
        fig, ax = plt.subplots(figsize=(12, 12)) 
        ax.imshow(img_rgba)
        ax.axis('off')

        unique_clusters_poly = sorted(df_poly['cluster_label'].unique())
        legend_handles = []
        for cl in unique_clusters_poly:
            index = global_cluster_to_index[cl]
            r, g, b, a = palette[index]
            # Normalizar colores para matplotlib (0 a 1)
            color = (r/255, g/255, b/255, a/255)
            patch = mpatches.Patch(color=color, label=f"Cluster {cl}")
            legend_handles.append(patch)
        ax.legend(handles=legend_handles, loc='lower right', frameon=True)

        # Convertir a imagen y guardar como PNG usando PIL
        out_png_path = os.path.join(output_folder, f"polygon_{pid}_clusters.png")
        try:
            plt.savefig(out_png_path, bbox_inches='tight', pad_inches=0.1, dpi=150)
            plt.close(fig)
            print(f"✅ Guardado PNG con paleta para polígono {pid}: {out_png_path}")
        except Exception as e:
            print(f"❌ Error guardando PNG para polígono {pid}: {e}")
            plt.close(fig)
            continue

if __name__ == "__main__":
    # Ruta al CSV con la información de firmas y clusters
    csv_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/9_output/2023_2024/Santana606_1057/ndvi/seasonal/rst_stationary/clusters_and_signatures.csv"
    # Directorio base que contiene las carpetas de polígonos (cada una con su raster)
    base_raster_dir = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/2023_2024/Santana606_1057/RECORTES"
    # Carpeta donde se guardarán los PNG de salida
    output_folder = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/9_output/2023_2024/Santana606_1057/ndvi/seasonal/rst_stationary/png_clusters_poligonos"
    
    # Ejecutar para todos los polígonos en el CSV
    main(csv_path, base_raster_dir, output_folder)
