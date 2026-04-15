#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np
from tslearn.clustering import TimeSeriesKMeans

def cluster_and_generate_signatures(df_polygon, band_columns, n_clusters=4):
    """
    Para un DataFrame filtrado a un polígono (df_polygon) y las columnas de bandas,
    realiza clustering en n_clusters y genera una lista de filas que incluyen:
      - Una fila por cada firma individual (con 'type' = "individual")
      - Una fila adicional por cada cluster con la firma promedio (con 'type' = "cluster")
      
    Se agregan las columnas 'pixel_x' y 'pixel_y' para conocer las coordenadas.
    Para las filas individuales se usan los valores originales y para la fila promedio
    se calculan las medias de las coordenadas.
    """
    # Construir la matriz de características
    X = df_polygon[band_columns].values  # shape: (n_samples, n_bands)
    
    # Ejecutar clustering con TimeSeriesKMeans
    kmeans = TimeSeriesKMeans(n_clusters=n_clusters, metric="euclidean", random_state=42)
    labels = kmeans.fit_predict(X)
    df_polygon = df_polygon.copy()
    df_polygon["cluster"] = labels
    
    signature_rows = []
    polygon_id = df_polygon["polygon_fid"].iloc[0]
    
    # Para cada cluster, agregar las firmas individuales y la firma promedio
    for cluster_label in sorted(df_polygon["cluster"].unique()):
        subset = df_polygon[df_polygon["cluster"] == cluster_label]
        # Firmas individuales: agregar pixel_x y pixel_y de cada fila
        for _, row in subset.iterrows():
            row_data = [
                polygon_id,
                row["pixel_x"],
                row["pixel_y"],
                "individual",
                cluster_label
            ] + list(row[band_columns].values)
            signature_rows.append(row_data)
        # Firma promedio del cluster: calcular la media de las bandas y de las coordenadas
        mean_series = subset[band_columns].mean()
        mean_pixel_x = subset["pixel_x"].mean()
        mean_pixel_y = subset["pixel_y"].mean()
        row_data = [
            polygon_id,
            mean_pixel_x,
            mean_pixel_y,
            "cluster",
            cluster_label
        ] + list(mean_series.values)
        signature_rows.append(row_data)
    
    return signature_rows

def main(csv_path, output_csv="all_polygons_cluster_signatures.csv", output_csv_clusters="all_polygons_clusters.csv", n_clusters=4):
    """
    Lee el CSV de entrada y para cada polígono realiza el clustering en n_clusters.
    Se genera un único CSV que incluye, para cada polígono, la información de sus clusters,
    diferenciando las firmas individuales de la firma promedio mediante la columna 'type'.
    
    Además, en cada fila se incluyen las columnas 'pixel_x' y 'pixel_y' para conocer las coordenadas.
    """
    df = pd.read_csv(csv_path)
    
    # Verificar que existan las columnas de coordenadas
    if "pixel_x" not in df.columns or "pixel_y" not in df.columns:
        print("No se encontraron las columnas 'pixel_x' y 'pixel_y' en el CSV.")
        return
    
    # Identificar las columnas de series de tiempo (band_1, band_2, …)
    band_columns = [col for col in df.columns if col.startswith("band_")]
    if not band_columns:
        print("No se encontraron columnas que comiencen con 'band_'. Revisa el CSV.")
        return
    
    all_signature_rows = []
    polygon_ids = df["polygon_fid"].unique()
    print(f"Se encontraron {len(polygon_ids)} polígonos en el CSV.")
    
    # Procesar cada polígono
    for pid in polygon_ids:
        print(f"Procesando polígono {pid}...")
        df_poly = df[df["polygon_fid"] == pid].copy()
        if df_poly.empty:
            print(f" - Polígono {pid} sin datos. Se omite.")
            continue
        
        signature_rows = cluster_and_generate_signatures(df_poly, band_columns, n_clusters=n_clusters)
        all_signature_rows.extend(signature_rows)
    
    # Crear un único DataFrame con todas las firmas
    signature_columns = ["polygon_fid", "pixel_x", "pixel_y", "type", "cluster_label"] + band_columns
    df_signatures = pd.DataFrame(all_signature_rows, columns=signature_columns)
    
    # Crear directorios de salida si no existen
    from pathlib import Path
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(output_csv_clusters).parent.mkdir(parents=True, exist_ok=True)
    
    # Guardar en un único CSV
    df_signatures.to_csv(output_csv, index=False)
    print(f"CSV global guardado en: {output_csv}")

    df_clusters = df_signatures[df_signatures["type"] == "cluster"].copy()
    df_clusters.to_csv(output_csv_clusters, index=False)
    print(f"CSV de clusters (solo firmas promedio) guardado en: {output_csv_clusters}")


if __name__ == "__main__":
    # Ajusta la ruta a tu CSV de entrada
    output_csv = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/9_output/all_polygons_cluster_signatures.csv"
    output_csv_clusters = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/9_output/all_polygons_clusters.csv"
    n_clusters = 4
    
    main(csv_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/8.CSV_ALL/669_chipata_all_polygons_clusters.csv", output_csv=output_csv, output_csv_clusters=output_csv_clusters, n_clusters=n_clusters)
