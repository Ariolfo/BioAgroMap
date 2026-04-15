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
    generate_plots: bool = True
) -> None:
    """
    Genera 3 clusters por polígono y extrae solo las firmas del cluster dominante.
    Opcionalmente genera visualizaciones con overlay de temperatura.
    
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
                'pixel_x': row['pixel_x'],
                'pixel_y': row['pixel_y'],
                'cluster_label': dominant_cluster,
                'signature_type': 'individual'
            }
            # Agregar valores de bandas
            for band_col in band_cols:
                signature[band_col] = row[band_col]
            
            all_signatures.append(signature)
        
        # Calcular y agregar firma promedio del cluster dominante
        mean_signature = {
            'polygon_fid': poly_id,
            'pixel_x': None,
            'pixel_y': None,
            'cluster_label': dominant_cluster,
            'signature_type': 'cluster_mean'
        }
        
        # Calcular promedio por banda
        for band_col in band_cols:
            mean_signature[band_col] = dominant_data[band_col].mean()
        
        all_signatures.append(mean_signature)
        
        # Generar gráfico del cluster dominante (si está habilitado)
        if generate_plots:
            try:
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # Plotear firmas individuales del cluster dominante
                for _, row in dominant_data.iterrows():
                    ax.plot(range(n_bands), row[band_cols].values, color='lightblue', alpha=0.3)
                
                # Plotear promedio del cluster dominante
                mean_values = [mean_signature[band_col] for band_col in band_cols]
                ax.plot(range(n_bands), mean_values, color='red', linewidth=3, 
                       label=f'Promedio cluster {dominant_cluster}', zorder=3)
                ax.legend(loc='upper left')
                
                # Líneas verticales para separar períodos temporales
                for m in range(n_bands):
                    ax.axvline(x=m, color='gray', linestyle='--', linewidth=0.8, alpha=0.7)
                
                # Overlay de temperatura (si hay datos climáticos)
                if climate_df is not None:
                    x_climate = np.linspace(0, n_bands-1, len(climate_df))
                    ax2 = ax.twinx()
                    ax2.plot(x_climate, climate_df['temperature_2m'], marker='o', color='orange', 
                            linestyle='-', linewidth=2, alpha=0.7, label='Temperatura', zorder=1)
                    ax2.set_ylabel('Temperatura (°C)', color='orange')
                    ax2.tick_params(axis='y', labelcolor='orange')
                    ax2.legend(loc="upper right")
                
                # Configurar ejes y etiquetas
                ax.set_xlabel('Período temporal')
                ax.set_ylabel('Índice de vegetación')
                ax.set_title(f"Cluster dominante - Polígono {poly_id}")
                
                # Etiquetas del eje X (fechas si están disponibles)
                if fdates_fmt:
                    ax.set_xticks(range(n_bands))
                    ax.set_xticklabels(fdates_fmt, rotation=45, ha='right', fontsize=8)
                else:
                    ax.set_xticks(range(n_bands))
                    ax.set_xticklabels([f'B{i+1}' for i in range(n_bands)], rotation=45, ha='right', fontsize=8)
                
                # Información del cluster
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
        
        # Estadísticas de resumen
        summary_stats.append({
            'polygon_fid': poly_id,
            'total_pixels': n_pixels,
            'dominant_cluster': dominant_cluster,
            'dominant_cluster_size': dominant_count,
            'dominant_cluster_percentage': round(dominant_count/n_pixels*100, 2),
            'cluster_distribution': str(dict(cluster_counts))
        })
    
    # Guardar resultados
    if all_signatures:
        # CSV con todas las firmas dominantes
        signatures_df = pd.DataFrame(all_signatures)
        signatures_path = out_dir / 'dominant_cluster_signatures.csv'
        signatures_df.to_csv(signatures_path, index=False)
        print(f"\n✅ Firmas guardadas en: {signatures_path}")
        print(f"   Total firmas individuales: {len(signatures_df[signatures_df['signature_type']=='individual'])}")
        print(f"   Total firmas promedio: {len(signatures_df[signatures_df['signature_type']=='cluster_mean'])}")
        
        # CSV con estadísticas de resumen
        summary_df = pd.DataFrame(summary_stats)
        summary_path = out_dir / 'clustering_summary.csv'
        summary_df.to_csv(summary_path, index=False)
        print(f"✅ Resumen guardado en: {summary_path}")
        
        # Mostrar estadísticas finales
        print(f"\n📊 RESUMEN FINAL:")
        print(f"   Polígonos procesados: {len(summary_stats)}")
        print(f"   Total píxeles dominantes: {signatures_df[signatures_df['signature_type']=='individual'].shape[0]}")
        print(f"   Promedio píxeles dominantes por polígono: {signatures_df[signatures_df['signature_type']=='individual'].shape[0]/len(summary_stats):.1f}")
        
    else:
        print("\n❌ No se generaron firmas. Verificar datos de entrada.")


def main(
    csv_path: str,
    output_folder: str,
    base_tif_folder: Optional[str] = None,
    climate_shp: Optional[str] = None,
    climate_start_date: Optional[str] = None,
    climate_end_date: Optional[str] = None,
    climate_freq: str = 'monthly',
    polygon_id: Optional[int] = None,
    generate_plots: bool = True
):
    """
    Función principal para extracción de clusters dominantes.
    
    Args:
        csv_path: Ruta al CSV con datos de series temporales
        output_folder: Carpeta donde guardar resultados
        base_tif_folder: Carpeta base con archivos TIF (opcional)
        climate_shp: Ruta al shapefile para datos climáticos (opcional)
        climate_start_date: Fecha inicio para datos climáticos (opcional)
        climate_end_date: Fecha fin para datos climáticos (opcional)
        climate_freq: Frecuencia de datos climáticos ('daily' o 'monthly')
        polygon_id: ID del polígono a procesar (None = todos)
        generate_plots: Si generar gráficos
    """
    config = {
        "csv_path": csv_path,
        "output_folder": output_folder,
        "base_tif_folder": base_tif_folder,
        "climate_shp": climate_shp,
        "climate_start_date": climate_start_date,
        "climate_end_date": climate_end_date,
        "climate_freq": climate_freq,
        "polygon_id": polygon_id,
        "generate_plots": generate_plots
    }
    
    print("📋 Configuración:")
    print(f"   📁 CSV de entrada: {csv_path}")
    print(f"   📁 Carpeta de salida: {output_folder}")
    if base_tif_folder:
        print(f"   📁 Carpeta TIF: {base_tif_folder}")
    if climate_shp:
        print(f"   🗺️  Shapefile clima: {climate_shp}")
    if climate_start_date and climate_end_date:
        print(f"   📅 Período clima: {climate_start_date} a {climate_end_date}")
    print(f"   🎯 Polígonos: {'Todos' if polygon_id is None else polygon_id}")
    print(f"   📊 Generar gráficos: {generate_plots}")
    
    # Ejecutar extracción
    extract_dominant_cluster_signatures(**config)


if __name__ == "__main__":
    # Ejecutar configuración principal
    print("🚀 Iniciando extracción de clusters dominantes...")
    main()
    print("✨ Proceso completado!")
                 # True para generar gráficos
