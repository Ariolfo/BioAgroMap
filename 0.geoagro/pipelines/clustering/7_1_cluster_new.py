# 7_cluster_TimeSeries.py
import pandas as pd
import numpy as np
from tslearn.clustering import TimeSeriesKMeans
from tslearn.preprocessing import TimeSeriesScalerMeanVariance
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import matplotlib.cm as cm

def main(
    input_csv: str,
    n_clusters: int,
    output_plot_raw: str,
    output_plot_norm: str
):
    """
    Aplica clustering KMeans a series temporales desde un CSV,
    guarda resultados y genera gráficos.

    Parámetros:
    - input_csv: ruta al CSV con columnas band_1, band_2, ..., band_n
    - n_clusters: número de clusters
    - output_csv_raw: CSV de salida con etiquetas 'cluster_raw'
    - output_csv_norm: CSV de salida con etiquetas 'cluster_norm'
    - output_plot_raw: Ruta para guardar el gráfico de datos crudos
    - output_plot_norm: Ruta para guardar el gráfico de datos normalizados
    """
    # 1. Leer datos
    df = pd.read_csv(input_csv)
    band_columns = [col for col in df.columns if col.startswith('band_')]
    if not band_columns:
        raise ValueError("No se encontraron columnas 'band_' en el CSV")

    # Matriz de series: (n_samples, n_timesteps)
    X = df[band_columns].values
    print(f"[7_cluster_TimeSeries] Datos crudos X.shape = {X.shape}")

    # --- Clustering en datos crudos ---
    kmeans_raw = TimeSeriesKMeans(
        n_clusters=n_clusters,
        metric="euclidean",
        random_state=42
    )
    labels_raw = kmeans_raw.fit_predict(X)
    df['cluster_raw'] = labels_raw

    # Crear directorios de salida si no existen
    from pathlib import Path
    Path(output_plot_raw).parent.mkdir(parents=True, exist_ok=True)
    Path(output_plot_norm).parent.mkdir(parents=True, exist_ok=True)
    
    # --- Gráfico de datos crudos ---
    plt.figure(figsize=(12, 8))
    unique_raw = np.unique(labels_raw)
    cmap_raw = cm.get_cmap('tab10', len(unique_raw))
    for cluster in unique_raw:
        subset = df[df['cluster_raw'] == cluster]
        series = subset[band_columns].values
        # Series individuales
        for row in series:
            plt.plot(range(len(band_columns)), row, color=cmap_raw(cluster), alpha=0.3)
        # Serie promedio
        mean_series = series.mean(axis=0)
        plt.plot(
            range(len(band_columns)),
            mean_series,
            color=cmap_raw(cluster),
            linewidth=3,
            label=f"Cluster {cluster}"
        )
    plt.title("Series de tiempo - Datos Crudos con Clusters")
    plt.xlabel("Índice de banda")
    plt.ylabel("Valor")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_plot_raw, dpi=150)
    plt.close()
    print(f"[7_cluster_TimeSeries] Gráfico crudo guardado en {output_plot_raw}")

    # --- Clustering en datos normalizados ---
    scaler = TimeSeriesScalerMeanVariance()
    X_norm = scaler.fit_transform(X)  # (n_samples, n_timesteps, 1)
    X_norm_2D = X_norm.reshape(X_norm.shape[0], X_norm.shape[1])
    print(f"[7_cluster_TimeSeries] Datos normalizados X_norm_2D.shape = {X_norm_2D.shape}")

    # PCA para reducir dimensionalidad
    n_components = min(3, X_norm_2D.shape[1])
    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_norm_2D)
    print(f"[7_cluster_TimeSeries] Datos PCA X_pca.shape = {X_pca.shape}")

    kmeans_norm = TimeSeriesKMeans(
        n_clusters=n_clusters,
        metric="euclidean",
        random_state=42
    )
    labels_norm = kmeans_norm.fit_predict(X_pca)
    df['cluster_norm'] = labels_norm

    # --- Gráfico de datos normalizados ---
    plt.figure(figsize=(12, 8))
    unique_norm = np.unique(labels_norm)
    cmap_norm = cm.get_cmap('tab10', len(unique_norm))
    for cluster in unique_norm:
        subset = df[df['cluster_norm'] == cluster]
        series = subset[band_columns].values
        for row in series:
            plt.plot(range(len(band_columns)), row, color=cmap_norm(cluster), alpha=0.3)
        mean_series = series.mean(axis=0)
        plt.plot(
            range(len(band_columns)),
            mean_series,
            color=cmap_norm(cluster),
            linewidth=3,
            label=f"Cluster {cluster}"
        )
    plt.title("Series de tiempo - Datos Normalizados con Clusters")
    plt.xlabel("Índice de banda")
    plt.ylabel("Valor")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_plot_norm, dpi=150)
    plt.close()
    print(f"[7_cluster_TimeSeries] Gráfico normalizado guardado en {output_plot_norm}")
