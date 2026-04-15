import os
import pandas as pd
import numpy as np
import rasterio
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

def plot_clusters_on_raster(csv_path, raster_path, cluster_filter=None, polygon_filter=None):
    """
    Lee un archivo CSV con las columnas:
        polygon_fid, pixel_x, pixel_y, cluster_label, type, band_1..band_n
    y un archivo raster (.tif).
    
    - Grafica el raster en escala de grises.
    - Superpone los clusters como una máscara coloreada, con transparencia parcial (alpha).
    - Re-mapea las etiquetas de los clusters a valores consecutivos 0..(n_clusters-1) para que el mapa de colores y la leyenda coincidan exactamente.
    - Si se proporciona polygon_filter, solo se utilizan las filas correspondientes a ese polygon_fid.
    - Si se proporciona cluster_filter, solo se muestran esos cluster_label(s).

    El CSV debe tener 'pixel_x' y 'pixel_y' para cada firma individual.
    """
    # --- 1) Leer el CSV ---
    df = pd.read_csv(csv_path)

    if polygon_filter is not None:
        df = df[df['polygon_fid'] == polygon_filter]
        if df.empty:
            print(f"No hay datos para polygon_fid={polygon_filter}.")
            return
    
    df = df[df['type'] == 'individual']
    if df.empty:
        print("No se encontraron firmas individuales en el CSV.")
        return

    if cluster_filter is not None:
        if isinstance(cluster_filter, (int, str)):
            cluster_filter = [int(cluster_filter)]
        else:
            cluster_filter = [int(c) for c in cluster_filter]
        df = df[df['cluster_label'].isin(cluster_filter)]
        if df.empty:
            print(f"No hay firmas individuales para los cluster(s): {cluster_filter}")
            return

    # --- 2) Abrir el raster en escala de grises ---
    with rasterio.open(raster_path) as src:
        img = src.read(1)  
        height, width = img.shape

    # --- 3) Preparar una máscara para almacenar los índices de los clusters ---
    mask = np.full((height, width), -1, dtype=np.int32)

    unique_clusters = sorted(df['cluster_label'].unique())
    n_clusters = len(unique_clusters)

    # Crear un mapeo de las etiquetas de los clusters -> índices consecutivos
    # Por ejemplo, si los clusters son [0, 3, 8], mapear 0->0, 3->1, 8->2
    cluster_to_index = {cl: i for i, cl in enumerate(unique_clusters)}

    # Llenar la máscara con los índices de los clusters
    for _, row in df.iterrows():
        x, y = int(row['pixel_x']), int(row['pixel_y'])
        cl = row['cluster_label']
        if 0 <= y < height and 0 <= x < width:
            mask[y, x] = cluster_to_index[cl]

    # --- 4) Crear un mapa de colores discreto con un color adicional para el fondo ---

    # Construir una paleta de colores para n_clusters
    base_cmap = cm.get_cmap('viridis', n_clusters)
    cluster_colors = [base_cmap(i) for i in range(n_clusters)]  # RGBA para cada cluster

    # Insertar un color para el fondo en el índice 0 si queremos un color, pero lo haremos completamente transparente.
    listed_cmap = ListedColormap(cluster_colors, name='ClusterMap')

    # --- 5) Enmascarar valores negativos para que muestren el fondo (transparente) ---
    mask_array = np.ma.masked_where(mask < 0, mask)  # enmascarar todos los negativos (fondo) => transparente

    # --- 6) Graficar todo ---
    plt.figure(figsize=(8, 8))

    # Mostrar el fondo en escala de grises
    plt.imshow(img, cmap='gray', alpha=1.0)  # fondo en escala de grises completamente opaco

    # Superponer la máscara de clusters
    plt.imshow(mask_array, cmap=listed_cmap, alpha=1)

    # Construir una leyenda manual que coincida con cluster_to_index
    from matplotlib.patches import Patch
    legend_patches = []
    for cl in unique_clusters:
        idx = cluster_to_index[cl]
        color = cluster_colors[idx]  # RGBA del mapa de colores
        legend_patches.append(Patch(facecolor=color, edgecolor='none', label=f"Cluster {cl}"))

    plt.legend(handles=legend_patches, loc='upper right', bbox_to_anchor=(1.3, 1.0))

    plt.title("Distribución espacial de firmas en el stack")
    plt.xlabel("Pixel X")
    plt.ylabel("Pixel Y")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # Ajusta las rutas a tu CSV y a la imagen de stack (.tif)
    csv_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/Geo_Agro/464_moniquira_CSV_ALL_Moni_20_cluster_output_RAW_None/clusters_and_signatures.csv"
    raster_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/464_moniquira/2013.0/STACK/stack_ndvi.tif"
    
    # Especifica cluster(s) a visualizar; por ejemplo, solo clusters 2 y 4
    cluster_filter =  None  # None # o [2, 4] por ejemplo para plotear clusters 
    # O, para visualizar todos, déjalo como None
    # cluster_filter = None
    
    # Opcional: filtrar por un polígono específico (ejemplo: 1405)
    polygon_filter = 2013.0  
    
    plot_clusters_on_raster(csv_path, raster_path, cluster_filter=cluster_filter, polygon_filter=polygon_filter)