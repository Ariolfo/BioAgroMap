import re
import pandas as pd
import numpy as np
from pathlib import Path
from tslearn.clustering import TimeSeriesKMeans
import matplotlib.pyplot as plt
import geopandas as gpd
import requests
from typing import List, Optional, Tuple
import warnings
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')


def extract_date_from_tif(file_name: str) -> Optional[str]:
    """Extrae fecha en formato MM_YYYY del nombre del archivo TIF"""
    match = re.search(r"\d{2}_\d{4}", str(file_name))
    return match.group(0) if match else None


def extract_month_year(date_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """Convierte fecha MM_YYYY a tupla (year, month)"""
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None


def find_tif_files(base_folder: str, polygon_id: Optional[int] = None) -> List[Path]:
    """Encuentra archivos TIF en la estructura de carpetas"""
    base = Path(base_folder)
    if polygon_id is not None:
        folder = base / f"{polygon_id}.0" / "RECORTES"
        return sorted(folder.glob("*.tif")) if folder.exists() else []
    candidates = [p for p in base.iterdir() if p.is_dir() and p.name.endswith('.0')]
    if not candidates:
        return []
    rec = sorted(candidates)[0] / "RECORTES"
    return sorted(rec.glob("*.tif")) if rec.exists() else []


def extract_centroids_from_shp(shp_path: str) -> Optional[pd.DataFrame]:
    """Extrae centroides del shapefile para datos climáticos"""
    try:
        gdf = gpd.read_file(shp_path)
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf['centroid'] = gdf.geometry.centroid
        gdf['latitude'] = gdf.centroid.y
        gdf['longitude'] = gdf.centroid.x
        return gdf[['latitude', 'longitude']]
    except Exception:
        return None


def fetch_om_data(latitude: float, longitude: float, start_date: str, end_date: str, freq: str) -> Optional[pd.DataFrame]:
    """Obtiene datos climáticos de Open-Meteo API"""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation"],
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC"
    }
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json().get('hourly', {})
        df = pd.DataFrame({
            'date': pd.to_datetime(data.get('time', [])),
            'temperature_2m': data.get('temperature_2m', []),
            'relative_humidity_2m': data.get('relative_humidity_2m', []),
            'precipitation': data.get('precipitation', [])
        })
        if freq == 'daily':
            return df.resample('D', on='date').mean().reset_index()
        if freq == 'monthly':
            daily = df.resample('D', on='date').mean().reset_index()
            return daily.resample('M', on='date').mean().reset_index()
        return df
    except Exception:
        return None


def extract_dominant_cluster_signatures(
    csv_path: str,
    output_folder: str,
    base_tif_folder: Optional[str] = None,
    climate_shp: Optional[str] = None,
    climate_start_date: Optional[str] = None,
    climate_end_date: Optional[str] = None,
    climate_freq: str = 'monthly',
    polygon_id: Optional[int] = None,
    generate_plots: bool = True,
    final_n_clusters: int = 4,   # <- número de clusters finales (segundo nivel)
    scale_final_features: bool = True  # <- escalar o no las firmas promedio antes del KMeans final
) -> None:
    """
    Genera 3 clusters por polígono y extrae solo las firmas del cluster dominante.
    Luego, realiza un clustering adicional (KMeans) sobre las firmas promedio dominantes
    para agruparlas en 'final_n_clusters' y genera estadísticas de procedencia.

    Args:
        csv_path: Ruta al CSV con la estructura band_1...band_N
        output_folder: Carpeta donde guardar los resultados
        base_tif_folder: Carpeta base con archivos TIF para extraer fechas (opcional)
        climate_shp: Ruta al shapefile para obtener centroides climáticos (opcional)
        climate_start_date: Fecha inicio para datos climáticos (YYYY-MM-DD)
        climate_end_date: Fecha fin para datos climáticos (YYYY-MM-DD)
        climate_freq: Frecuencia datos climáticos ('daily' o 'monthly')
        polygon_id: Si se especifica, procesa solo ese polígono. Si es None, procesa todos.
        generate_plots: Si generar gráficos de clusters con temperatura
        final_n_clusters: número de clusters finales sobre las firmas promedio dominantes
        scale_final_features: si True, estandariza las bandas antes del KMeans final
    """
    # Crear directorio de salida
    out_dir = Path(output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cargar datos
    print(f"Cargando datos desde: {csv_path}")
    df_full = pd.read_csv(csv_path)

    # Identificar columnas de bandas
    band_cols = [c for c in df_full.columns if c.startswith('band_')]
    n_bands = len(band_cols)
    print(f"Detectadas {n_bands} bandas temporales: {band_cols[0]} a {band_cols[-1]}")

    # Extraer información temporal de TIFs (si se proporciona)
    fdates_fmt = None
    if base_tif_folder and generate_plots:
        print("Extrayendo información temporal de archivos TIF...")
        tifs = find_tif_files(base_tif_folder, polygon_id)
        if tifs:
            dates = [extract_date_from_tif(t.name) for t in tifs]
            pairs = [(t, d) for t, d in zip(tifs, dates) if d]
            pairs.sort(key=lambda x: extract_month_year(x[1]))
            fdates = [d for (_, d) in pairs]
            fdates_dt = pd.to_datetime([f"01_{d}" for d in fdates], format="%d_%m_%Y")
            fdates_fmt = [dt.strftime("%m-%Y") for dt in fdates_dt]
            print(f"  📅 Fechas encontradas: {len(fdates_fmt)} períodos")
        else:
            print("  ⚠️  No se encontraron archivos TIF")

    # Obtener datos climáticos (si se proporciona configuración)
    climate_df = None
    if climate_shp and climate_start_date and climate_end_date and generate_plots:
        print("Obteniendo datos climáticos...")
        centroids = extract_centroids_from_shp(climate_shp)
        if centroids is not None:
            avg_lat, avg_lon = centroids['latitude'].mean(), centroids['longitude'].mean()
            print(f"  🌍 Centroide promedio: {avg_lat:.4f}, {avg_lon:.4f}")
            climate_df = fetch_om_data(avg_lat, avg_lon, climate_start_date, climate_end_date, climate_freq)
            if climate_df is not None:
                print(f"  🌡️  Datos climáticos obtenidos: {len(climate_df)} registros")
            else:
                print("  ⚠️  Error obteniendo datos climáticos")
        else:
            print("  ⚠️  Error procesando shapefile climático")

    # Determinar polígonos a procesar
    if polygon_id is not None:
        polygon_ids = [polygon_id]
        print(f"Procesando solo polígono: {polygon_id}")
    else:
        polygon_ids = sorted(df_full['polygon_fid'].unique())
        print(f"Procesando {len(polygon_ids)} polígonos: {polygon_ids}")

    # Resultados para consolidar
    all_signatures = []
    summary_stats = []

    # Procesar cada polígono
    for poly_id in polygon_ids:
        print(f"\n--- Procesando polígono {poly_id} ---")

        # Filtrar datos del polígono
        df_poly = df_full[df_full['polygon_fid'] == poly_id].copy()
        n_pixels = len(df_poly)

        if n_pixels < 3:
            print(f"  ⚠️  Polígono {poly_id} tiene solo {n_pixels} píxeles. Saltando...")
            continue

        print(f"  📊 {n_pixels} píxeles encontrados")

        # Extraer series temporales
        X = df_poly[band_cols].values

        # Clustering con k=3
        try:
            kmeans = TimeSeriesKMeans(n_clusters=3, random_state=42, verbose=False)
            cluster_labels = kmeans.fit_predict(X)
            df_poly['cluster'] = cluster_labels

        except Exception as e:
            print(f"  ❌ Error en clustering para polígono {poly_id}: {e}")
            continue

        # Contar elementos por cluster
        cluster_counts = pd.Series(cluster_labels).value_counts().sort_values(ascending=False)
        dominant_cluster = cluster_counts.index[0]
        dominant_count = cluster_counts.iloc[0]

        print(f"  🎯 Cluster dominante: {dominant_cluster} con {dominant_count}/{n_pixels} píxeles ({dominant_count/n_pixels*100:.1f}%)")
        print(f"  📈 Distribución clusters: {dict(cluster_counts)}")

        # Extraer firmas del cluster dominante
        dominant_data = df_poly[df_poly['cluster'] == dominant_cluster].copy()

        # Agregar firmas individuales
        for _, row in dominant_data.iterrows():
            signature = {
                'polygon_fid': poly_id,
                'pixel_x': row.get('pixel_x', None),
                'pixel_y': row.get('pixel_y', None),
                'cluster_label': dominant_cluster,         # etiqueta del cluster dominante (0,1,2) del nivel 1
                'signature_type': 'individual'
            }
            for band_col in band_cols:
                signature[band_col] = row[band_col]
            all_signatures.append(signature)

        # Calcular y agregar firma promedio del cluster dominante
        mean_signature = {
            'polygon_fid': poly_id,
            'pixel_x': None,
            'pixel_y': None,
            'cluster_label': dominant_cluster,             # de cuál cluster dominante proviene
            'signature_type': 'cluster_mean'
        }
        for band_col in band_cols:
            mean_signature[band_col] = dominant_data[band_col].mean()
        all_signatures.append(mean_signature)

        # Gráfico del cluster dominante
        if generate_plots:
            try:
                fig, ax = plt.subplots(figsize=(12, 6))

                # Firmas individuales del cluster dominante
                for _, row in dominant_data.iterrows():
                    ax.plot(range(n_bands), row[band_cols].values, color='lightblue', alpha=0.3)

                # Promedio del cluster dominante
                mean_values = [mean_signature[band_col] for band_col in band_cols]
                ax.plot(range(n_bands), mean_values, color='red', linewidth=3,
                        label=f'Promedio cluster {dominant_cluster}', zorder=3)
                ax.legend(loc='upper left')

                # Líneas verticales por período
                for m in range(n_bands):
                    ax.axvline(x=m, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)

                # Overlay clima
                if climate_df is not None:
                    x_climate = np.linspace(0, n_bands - 1, len(climate_df))
                    ax2 = ax.twinx()
                    ax2.plot(x_climate, climate_df['temperature_2m'], marker='o', color='orange',
                             linestyle='-', linewidth=2, alpha=0.7, label='Temperatura', zorder=1)
                    ax2.set_ylabel('Temperatura (°C)', color='orange')
                    ax2.tick_params(axis='y', labelcolor='orange')
                    ax2.legend(loc="upper right")

                # Ejes y etiquetas
                ax.set_xlabel('Período temporal')
                ax.set_ylabel('Índice de vegetación')
                ax.set_title(f"Cluster dominante - Polígono {poly_id}")

                # Etiquetas del eje X
                ax.set_xticks(range(n_bands))
                if fdates_fmt and len(fdates_fmt) == n_bands:
                    ax.set_xticklabels(fdates_fmt, rotation=45, ha='right', fontsize=8)
                else:
                    ax.set_xticklabels([f'B{i+1}' for i in range(n_bands)], rotation=45, ha='right', fontsize=8)

                # Info del cluster
                ax.text(0.99, 0.90, f"Cluster: {dominant_cluster}\n# firmas: {dominant_count}",
                        transform=ax.transAxes, ha='right', va='top',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray"))

                ax.grid(True, alpha=0.3)
                plt.tight_layout()

                # Guardar gráfico
                plot_path = out_dir / f'dominant_cluster_polygon_{poly_id}.png'
                plt.savefig(plot_path, dpi=150, bbox_inches='tight')
                plt.close()

                print(f"  📊 Gráfico guardado: {plot_path.name}")

            except Exception as e:
                print(f"  ❌ Error generando gráfico para polígono {poly_id}: {e}")
                plt.close()

        # Estadísticas de resumen por polígono
        summary_stats.append({
            'polygon_fid': poly_id,
            'total_pixels': n_pixels,
            'dominant_cluster': dominant_cluster,
            'dominant_cluster_size': dominant_count,
            'dominant_cluster_percentage': round(dominant_count / n_pixels * 100, 2),
            'cluster_distribution': str(dict(cluster_counts))
        })

    # ===== Consolidación y Clustering Final sobre Firmas Promedio Dominantes =====
    if not all_signatures:
        print("\n❌ No se generaron firmas. Verificar datos de entrada.")
        return

    # DataFrame con todas las firmas (individuales y promedio)
    signatures_df = pd.DataFrame(all_signatures)

    # Filtrar solo firmas promedio dominantes (una por polígono)
    dominant_means = signatures_df[signatures_df['signature_type'] == 'cluster_mean'].copy()
    if dominant_means.empty:
        print("\n❌ No se encontraron firmas promedio para el clustering final.")
        return

    # Preparar matriz de características (bandas)
    X_means = dominant_means[band_cols].values

    # Ajustar número de clusters finales si hay pocos polígonos
    n_samples = X_means.shape[0]
    n_final = min(max(1, final_n_clusters), n_samples)
    if n_samples < final_n_clusters:
        print(f"\n⚠️  Solo hay {n_samples} firmas promedio. Se ajusta final_n_clusters a {n_final}.")

    # (Opcional) Escalado de bandas antes del KMeans final
    X_fit = X_means
    scaler = None
    if scale_final_features:
        scaler = StandardScaler()
        X_fit = scaler.fit_transform(X_means)

    print("\n🔄 Clustering adicional de clusters dominantes (nivel 2)...")
    kmeans_final = KMeans(n_clusters=n_final, random_state=42, n_init="auto")
    final_labels = kmeans_final.fit_predict(X_fit)

    dominant_means['final_cluster'] = final_labels

    # Mapear final_cluster por polígono y anexarlo a todas las firmas
    poly_to_final = dict(zip(dominant_means['polygon_fid'], dominant_means['final_cluster']))
    signatures_df['final_cluster'] = signatures_df['polygon_fid'].map(poly_to_final)

    # ===== Estadísticos: procedencia del cluster final =====
    # Tabla de contingencia: final_cluster vs cluster_label (de qué cluster dominante viene)
    ct_counts = pd.crosstab(dominant_means['final_cluster'], dominant_means['cluster_label'])
    ct_perc = ct_counts.div(ct_counts.sum(axis=1), axis=0).round(4) * 100.0

    # Preparar tabla combinada de conteos y porcentajes
    combined = ct_counts.copy()
    # añadir columnas con sufijo _pct
    for col in ct_perc.columns:
        combined[f"{col}_pct"] = ct_perc[col]

    # columna auxiliar: fuente dominante más común por cada cluster final
    most_common_source = ct_counts.idxmax(axis=1)
    most_common_pct = ct_perc.max(axis=1).round(2)
    combined['most_common_dominant_cluster'] = most_common_source
    combined['most_common_pct'] = most_common_pct

    # Añadir lista de polígonos por cluster final
    polys_by_final = (
        dominant_means.groupby('final_cluster')['polygon_fid']
        .apply(lambda s: sorted(list(map(int, s))))
    )
    combined['polygons'] = polys_by_final

    # ===== Guardados =====
    out_dir.mkdir(parents=True, exist_ok=True)

    signatures_path = out_dir / 'dominant_cluster_signatures_with_final.csv'
    signatures_df.to_csv(signatures_path, index=False)
    print(f"\n✅ Firmas (con final_cluster) guardadas en: {signatures_path}")
    print(f"   Totales -> individuales: {len(signatures_df[signatures_df['signature_type']=='individual'])}, "
          f"promedios: {len(signatures_df[signatures_df['signature_type']=='cluster_mean'])}")

    summary_df = pd.DataFrame(summary_stats)
    summary_path = out_dir / 'clustering_summary.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"✅ Resumen por polígono guardado en: {summary_path}")

    final_means_path = out_dir / "final_clusters_means.csv"
    dominant_means.to_csv(final_means_path, index=False)
    print(f"✅ Firmas promedio dominantes con etiqueta final guardadas en: {final_means_path}")

    final_stats_path = out_dir / "final_clusters_stats.csv"
    combined.reset_index().rename(columns={'index': 'final_cluster'}).to_csv(final_stats_path, index=False)
    print(f"📊 Estadísticas de procedencia guardadas en: {final_stats_path}")

    # ===== Gráfico resumen de curvas promedio por cluster final =====
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        for fcl in sorted(dominant_means['final_cluster'].unique()):
            mean_curve = dominant_means[dominant_means['final_cluster'] == fcl][band_cols].mean(axis=0).values
            ax.plot(range(n_bands), mean_curve, linewidth=3, label=f'Final {fcl}')
        ax.set_xlabel('Período temporal')
        ax.set_ylabel('Índice de vegetación (promedio)')
        ax.set_title('Curvas promedio por cluster final (nivel 2)')
        ax.set_xticks(range(n_bands))
        if fdates_fmt and len(fdates_fmt) == n_bands:
            ax.set_xticklabels(fdates_fmt, rotation=45, ha='right', fontsize=8)
        else:
            ax.set_xticklabels([f'B{i+1}' for i in range(n_bands)], rotation=45, ha='right', fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left')
        plt.tight_layout()
        overview_path = out_dir / 'final_clusters_overview.png'
        plt.savefig(overview_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"🖼️  Gráfico resumen guardado: {overview_path.name}")
    except Exception as e:
        print(f"⚠️  No se pudo generar el gráfico resumen de clusters finales: {e}")

    # ===== Resumen final en consola =====
    print(f"\n📊 RESUMEN FINAL:")
    print(f"   Polígonos procesados: {len(summary_stats)}")
    print(f"   Total píxeles dominantes (nivel 1): {signatures_df[signatures_df['signature_type']=='individual'].shape[0]}")
    print(f"   Clusters finales (nivel 2): {n_final}")
    print("   Procedencia por cluster final (conteos):")
    print(ct_counts)
    print("   Procedencia por cluster final (%):")
    print(ct_perc.round(2))


def main():
    """Función principal con configuración personalizada"""
    # Configuración con parámetros solicitados
    CSV_PATH = "/home/agrosavia/Documents/Geo_Agro/8.CSV_ALL/nadia_sub_villap/ndvi/serie/datos_sin_outliers_IQR.csv"
    OUTPUT_DIR = "/home/agrosavia/Documents/Geo_Agro/test"

    # NOTA: base_tif_folder debe ser una carpeta con archivos TIF, no un CSV
    # Si no tienes archivos TIF, puedes poner None para deshabilitar extracción de fechas
    BASE_TIF_FOLDER = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/nadia_sub_villap/RECORTES"  # Ajusta esta ruta

    # Ruta completa al shapefile climático
    CLIMATE_SHP = "/home/agrosavia/Documents/Geo_Agro/3.POLYGON_TOWN/nadia/nadia_22_24/Fechas_Siembra_Villapinzon2.shp"

    config = {
        "csv_path": CSV_PATH,
        "output_folder": OUTPUT_DIR,
        "base_tif_folder": BASE_TIF_FOLDER,   # Si no tienes TIFs, cambia a None
        "climate_shp": CLIMATE_SHP,
        "climate_start_date": "2023-01-01",
        "climate_end_date": "2024-12-01",
        "climate_freq": "monthly",
        "polygon_id": None,                   # None para procesar todos los polígonos
        "generate_plots": True,
        "final_n_clusters": 4,                # <- requerido
        "scale_final_features": True          # <- recomendable
    }

    print("📋 Configuración:")
    print(f"   📁 CSV de entrada: {CSV_PATH}")
    print(f"   📁 Carpeta de salida: {OUTPUT_DIR}")
    print(f"   📁 Carpeta TIF: {BASE_TIF_FOLDER}")
    print(f"   🗺️  Shapefile clima: {CLIMATE_SHP}")
    print(f"   📅 Período clima: {config['climate_start_date']} a {config['climate_end_date']}")
    print(f"   🎯 Polígonos: {'Todos' if config['polygon_id'] is None else config['polygon_id']}")
    print(f"   📊 Generar gráficos: {config['generate_plots']}")
    print(f"   🔢 Clusters finales: {config['final_n_clusters']}")
    print(f"   🧪 Estandarizar firmas para clustering final: {config['scale_final_features']}")

    # Ejecutar extracción + clustering final
    extract_dominant_cluster_signatures(**config)


if __name__ == "__main__":
    print("🚀 Iniciando extracción de clusters dominantes y clustering final...")
    main()
    print("✨ Proceso completado!")
