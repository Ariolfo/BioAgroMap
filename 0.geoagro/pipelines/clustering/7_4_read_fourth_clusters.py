#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt

def main(csv_path, polygon_fid):
    """
    Lee un CSV global con firmas de cluster (tanto filas individuales como medias) 
    para todos los polígonos, filtra los datos para un polygon_fid dado, y traza un gráfico separado para cada cluster.
    
    Each graph shows:
      - Las series de tiempo individuales (en azul claro)
      - La serie temporal media de ese clúster (En rojo)
    
    Parametros
    ----------
    csv_path : str
        Ruta del archivo CSV (e.g., "all_polygons_cluster_signatures.csv").
    polygon_fid : int or str
        El ID del poligono para filtrar (e.g., 1015).
    """
    # Read the CSV
    df = pd.read_csv(csv_path)
    
    # Filtra el DataFrame para el polygon_fid especificado
    df_poly = df[df["polygon_fid"] == polygon_fid]
    if df_poly.empty:
        print(f"No data found for polygon_fid={polygon_fid}")
        return
    
    # Identificar las columnas de banda (suponiendo que empiecen por «band_»)
    band_columns = [col for col in df_poly.columns if col.startswith("band_")]
    if not band_columns:
        print("No band columns found in the CSV.")
        return
    
    # Obtener los clusters únicos en este polígono
    unique_clusters = sorted(df_poly["cluster_label"].unique())
    
    for cluster in unique_clusters:
        df_cluster = df_poly[df_poly["cluster_label"] == cluster]
        # Separar las filas individuales y la fila media
        df_individual = df_cluster[df_cluster["type"] == "individual"]
        df_average = df_cluster[df_cluster["type"] == "cluster"]
        
        plt.figure(figsize=(8, 5))
        
        # Trazar cada serie temporal individual
        for _, row in df_individual.iterrows():
            y_values = row[band_columns].values
            plt.plot(range(len(band_columns)), y_values,
                     color='lightblue', alpha=0.5, linewidth=0.5)
        
        # Trazar la serie temporal mdel cluster
        if not df_average.empty:
            avg_row = df_average.iloc[0]
            y_avg = avg_row[band_columns].values
            plt.plot(range(len(band_columns)), y_avg,
                     color='red', linewidth=2, label="Average")
        
        plt.title(f"Polygon {polygon_fid} - Cluster {cluster}")
        plt.xlabel("Band index")
        plt.ylabel("NDVI")
        plt.legend()
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    csv_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/9_output/all_polygons_cluster_signatures.csv"
    polygon_fid = 1405  # Reemplaza con el ID del poligono que necesites
    
    main(csv_path, polygon_fid)
