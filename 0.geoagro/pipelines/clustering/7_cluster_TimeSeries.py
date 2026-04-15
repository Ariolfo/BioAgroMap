import pandas as pd
import numpy as np
from tslearn.clustering import TimeSeriesKMeans
from tslearn.preprocessing import TimeSeriesScalerMeanVariance
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
import matplotlib
matplotlib.use('Agg')

def cluster_time_series_tslearn(csv_path, n_clusters=3, output_folder=None):
    """
    Aplica clustering a series de tiempo utilizando tslearn con métrica euclidiana.
    Realiza el clustering tanto en datos crudos como en datos normalizados.

    Parámetros:
    -----------
    csv_path : str
        Ruta al archivo CSV con las columnas band_1, band_2, ... band_n.
    n_clusters : int
        Número de clusters para K-Means.
    
    Retorna:
    --------
    df_result_raw : pd.DataFrame
        DataFrame con las etiquetas de cluster asignadas (columna 'cluster_raw').
    df_result_norm : pd.DataFrame
        DataFrame con las etiquetas de cluster asignadas (columna 'cluster_norm').
    """
    # 1. Leer el CSV
    df = pd.read_csv(csv_path)

    # 2. Extraer las columnas que representan las series de tiempo (band_1, band_2, ...)
    band_columns = [col for col in df.columns if col.startswith('band_')]
    
    if not band_columns:
        print("No se encontraron columnas que empiecen con 'band_'. Verifica el CSV.")
        return None, None

    # 3. Construir la matriz de características X para el clustering
    #    Cada fila es una serie de tiempo correspondiente a un píxel o registro.
    X = df[band_columns].values  # shape: (n_samples, n_bands)

    print(f"Forma de X (datos crudos): {X.shape}")

    # --- CLUSTERING EN DATOS CRUDOS ---
    print("\n--- Clustering con datos crudos ---")
    kmeans_raw = TimeSeriesKMeans(n_clusters=n_clusters, metric="euclidean", random_state=42)
    labels_raw = kmeans_raw.fit_predict(X)
    
    # Agregamos la etiqueta de cluster al DataFrame original
    df_result_raw = df.copy()
    df_result_raw['cluster_raw'] = labels_raw

    # --- CLUSTERING EN DATOS NORMALIZADOS ---
    print("\n--- Clustering con datos normalizados ---")
    # Normalizar cada serie de tiempo (media 0, varianza 1) usando TimeSeriesScalerMeanVariance
    scaler = TimeSeriesScalerMeanVariance()
    X_norm = scaler.fit_transform(X)  # Devuelve un array 3D [n_samples, n_bands, 1] en tslearn
    
    # Para K-Means de tslearn, la forma [n_samples, n_timestamps] o [n_samples, n_timestamps, dim] es válida.
    # X_norm queda con shape: (n_samples, n_bands, 1)
    # Si queremos shape (n_samples, n_bands) para métrica euclidiana simple, aplanamos la última dimensión:
    X_norm_2D = X_norm.reshape(X_norm.shape[0], X_norm.shape[1])
    pca = PCA(n_components=3)
    X_pca_norm = pca.fit_transform(X_norm_2D)

    kmeans_norm = TimeSeriesKMeans(n_clusters=n_clusters, metric="euclidean", random_state=42)
    labels_norm = kmeans_norm.fit_predict(X_pca_norm)

    # Agregamos la etiqueta de cluster al DataFrame
    df_result_norm = df.copy()
    df_result_norm['cluster_norm'] = labels_norm

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    scatter = ax.scatter(
    X_pca_norm[:, 0],  # PC1
    X_pca_norm[:, 1],  # PC2
    X_pca_norm[:, 2],  # PC3
    c=labels_norm,     # color según la etiqueta de cluster
    cmap='viridis',  # paleta de colores
    alpha=0.6
)
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_zlabel("PC3")
    ax.set_title("Gráfico 3D con PCA")

    cbar = fig.colorbar(scatter, ax=ax, pad=0.1)
    cbar.set_label("Etiqueta de Cluster")

    plt.tight_layout()
    
    # Guardar gráfico si hay output_folder
    if output_folder:
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        plot_file = output_path / "clusters_3d_pca.png"
        fig.savefig(plot_file, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"✅ Gráfico 3D PCA guardado: {plot_file}")
    else:
        plt.show()
        plt.close(fig)

    print(f"Forma de X normalizado: {X_pca_norm.shape}")

    # Retornar ambos DataFrames con sus etiquetas de cluster
    return df_result_raw, df_result_norm

def main(csv_path: str, n_clusters: int = 3, output_folder: str = None):
    """
    Función main para integrar con el pipeline.
    
    Args:
        csv_path: Ruta al CSV con datos
        n_clusters: Número de clusters
        output_folder: Carpeta donde guardar resultados (opcional)
    """
    df_raw, df_norm = cluster_time_series_tslearn(csv_path, n_clusters, output_folder)
    
    if df_raw is not None and df_norm is not None and output_folder:
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        df_raw.to_csv(output_path / "clusters_raw.csv", index=False)
        df_norm.to_csv(output_path / "clusters_norm.csv", index=False)
        print(f"✅ Resultados guardados en {output_folder}")

if __name__ == "__main__":
    # Ejemplo de uso
    csv_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/8.CSV_ALL/seasonal_components.csv"  # <--- Ajusta la ruta
    
    # Número de clusters que deseas (puedes variar este valor)
    n_clusters = 5
    
    # Ejecutar la función
    df_raw, df_norm = cluster_time_series_tslearn(csv_path, n_clusters=n_clusters)
    
    if df_raw is not None and df_norm is not None:
        # Mostrar una parte de los resultados
        print("\nEjemplo de filas con cluster_raw:")
        print(df_raw[['polygon_fid'] + [col for col in df_raw.columns if col.startswith('band_')] + ['cluster_raw']].head())
        
        print("\nEjemplo de filas con cluster_norm:")
        print(df_norm[['polygon_fid'] + [col for col in df_norm.columns if col.startswith('band_')] + ['cluster_norm']].head())

        # (Opcional) Guardar a CSV
        # df_raw.to_csv("resultado_clustering_crudo.csv", index=False)
        # df_norm.to_csv("resultado_clustering_normalizado.csv", index=False)
        
        # 1) Plot: Datos normalizados
    band_columns = [col for col in df_norm.columns if col.startswith('band_')]
    for cluster_id in sorted(df_norm['cluster_norm'].unique()):
        subset = df_norm[df_norm['cluster_norm'] == cluster_id]
        mean_values = subset[band_columns].mean()
        #plt.plot(mean_values.values, label=f"Cluster Norm {cluster_id}")

    # 2) Plot: Datos crudos
    band_columns = [col for col in df_raw.columns if col.startswith('band_')]
    for cluster_id in sorted(df_raw['cluster_raw'].unique()):
        subset = df_raw[df_raw['cluster_raw'] == cluster_id]
        mean_values = subset[band_columns].mean()
        plt.plot(mean_values.values, '--', label=f"Cluster Raw {cluster_id}")

    plt.title("Comparación de NDVI por Cluster: Normalizado vs Crudo")
    plt.xlabel("Índice de banda")
    plt.ylabel("NDVI medio")
    plt.legend()
    plt.grid(True)
    plt.show()

