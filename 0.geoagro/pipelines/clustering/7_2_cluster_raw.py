# 8_cluster_advanced.py
import re
import pandas as pd
import numpy as np
from pathlib import Path
from tslearn.clustering import TimeSeriesKMeans
from tslearn.preprocessing import TimeSeriesScalerMeanVariance
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import geopandas as gpd
import requests
import concurrent.futures
from typing import List, Optional, Tuple


def extract_date_from_tif(file_name: str) -> Optional[str]:
    # Intentar formato MM_YYYY (ej: 01_2023)
    match = re.search(r"(\d{2})_(\d{4})", str(file_name))
    if match:
        return match.group(0)
    # Intentar formato YYYY-MM (ej: 2023-01)
    match = re.search(r"(\d{4})-(\d{2})", str(file_name))
    if match:
        # Convertir YYYY-MM a MM_YYYY
        year, month = match.groups()
        return f"{month}_{year}"
    return None


def extract_month_year(date_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None

def find_tif_files(base_folder: str, polygon_id: Optional[int] = None) -> List[Path]:
    base = Path(base_folder)
    if polygon_id is not None:
        folder = base / f"{polygon_id}" / "RECORTES"
        #folder = base / f"{polygon_id}.0" / "RECORTES"
        return sorted(folder.glob("*.tif")) if folder.exists() else []
    #candidates = [p for p in base.iterdir() if p.is_dir() and p.name.endswith('.0')]
    candidates = [p for p in base.iterdir() if p.is_dir() and p.name.endswith('')]
    if not candidates:
        return []
    rec = sorted(candidates)[0] / "RECORTES"
    return sorted(rec.glob("*.tif")) if rec.exists() else []

def compute_inertia(k: int, X: np.ndarray, metric: str = "euclidean") -> float:
    model = TimeSeriesKMeans(n_clusters=k, metric=metric, random_state=42)
    model.fit(X)
    return model.inertia_

def elbow_method_time_series(
        X: np.ndarray,
        max_k: int,
        metric: str = "euclidean"
) -> Tuple[List[int], List[float]]:
    ks = list(range(1, max_k + 1))
    args = [(k, X, metric) for k in ks]
    with concurrent.futures.ProcessPoolExecutor() as exe:
        inertias = list(exe.map(lambda a: compute_inertia(*a), args))
    return ks, inertias


def find_elbow(ks: List[int], inertias: List[float]) -> int:
    if len(inertias) < 2:
        return ks[0]
    diffs = [inertias[i] - inertias[i+1] for i in range(len(inertias)-1)]
    return ks[int(np.argmax(diffs))+1]


def extract_centroids_from_shp(shp_path: str) -> Optional[pd.DataFrame]:
    try:
        gdf = gpd.read_file(shp_path)
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        # Proyectar a CRS proyectado para calcular centroides precisos
        if gdf.crs.to_epsg() == 4326:
            gdf_projected = gdf.to_crs(epsg=3857)  # Web Mercator
            gdf_projected['centroid_proj'] = gdf_projected.geometry.centroid
            gdf['centroid'] = gdf_projected['centroid_proj'].to_crs(epsg=4326)
        else:
            gdf['centroid'] = gdf.geometry.centroid
        gdf['latitude'] = gdf.centroid.y
        gdf['longitude'] = gdf.centroid.x
        return gdf[['latitude', 'longitude']]
    except Exception:
        return None


def fetch_om_data(latitude: float, longitude: float, start_date: str, end_date: str, freq: str) -> Optional[pd.DataFrame]:
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
        if len(df) == 0:
            return None
        if freq == 'daily':
            result = df.resample('D', on='date').mean().reset_index()
            return result if len(result) > 0 else None
        if freq == 'monthly':
            daily = df.resample('D', on='date').mean().reset_index()
            if len(daily) == 0:
                return None
            # Usar 'ME' en lugar de 'M' para pandas >= 2.0
            try:
                result = daily.resample('ME', on='date').mean().reset_index()
            except ValueError:
                # Fallback para versiones antiguas de pandas
                result = daily.resample('M', on='date').mean().reset_index()
            return result if len(result) > 0 else None
        return df if len(df) > 0 else None
    except Exception:
        return None


def main(
    csv_path: str,
    base_tif_folder: str,
    output_folder: str,
    climate_shp: str,
    climate_start_date: str,
    climate_end_date: str,
    climate_freq: str = 'monthly',
    max_k: int = 20,
    n_clusters: Optional[int] = None,
    polygon_id: Optional[int] = None
) -> None:
    """
    1. Encuentra TIFs y extrae fechas.
    2. Carga y filtra CSV.
    3. Elbow method e inertia plot.
    4. Clustering con k sugerido.
    5. Fetch clima usando centroide promedio.
    6. Plotea clusters con overlay de temperatura.
    7. Exporta CSVs y gráficos en output_folder.

    :param n_cluster: Numero de clusters a usar; si None, se usa el elbow method.
    """
    out_dir = Path(output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    # TIF files
    tifs = find_tif_files(base_tif_folder, polygon_id)
    dates = [extract_date_from_tif(t.name) for t in tifs]
    pairs = [(t, d) for t, d in zip(tifs, dates) if d]
    pairs.sort(key=lambda x: extract_month_year(x[1]))
    num_bands = len(pairs)
    fdates = [d for (_, d) in pairs]
    fdates_dt = pd.to_datetime([f"01_{d}" for d in fdates], format="%d_%m_%Y")
    fdates_fmt = [dt.strftime("%m-%Y") for dt in fdates_dt]

    # Load CSV
    df_full = pd.read_csv(csv_path)
    
    # Limpiar polygon_fid si está vacío
    if 'polygon_fid' not in df_full.columns or df_full['polygon_fid'].isna().all():
        print("⚠️ polygon_fid está vacío o no existe. Asignando ID por defecto...")
        if 'polygon_fid' not in df_full.columns:
            df_full['polygon_fid'] = 1
        else:
            df_full['polygon_fid'] = df_full['polygon_fid'].fillna(1)
    
    # Si polygon_id es None, usar el primer ID disponible
    if polygon_id is None:
        available_ids = df_full['polygon_fid'].dropna().unique()
        if len(available_ids) > 0:
            polygon_id = available_ids[0]
            print(f"📊 Usando polygon_id={polygon_id} (primer disponible)")
        else:
            polygon_id = 1
            print(f"📊 Usando polygon_id=1 (por defecto)")
    
    df = df_full[df_full['polygon_fid']==polygon_id].copy()

    if len(df) == 0:
        print(f"❌ Error: No se encontraron datos para polygon_id={polygon_id}")
        print(f"   Polígonos disponibles: {df_full['polygon_fid'].unique()}")
        return

    band_cols = [c for c in df.columns if c.startswith('band_')]
    if not band_cols:
        print("❌ Error: No se encontraron columnas 'band_' en el CSV")
        return
    
    X = df[band_cols].values
    
    if len(X) == 0:
        print(f"❌ Error: Array vacío (0 muestras). No hay datos para procesar.")
        return                                                   

    if n_clusters is None:
        # Elbow
        ks, inertias = elbow_method_time_series(X, max_k)
        plt.figure()
        plt.plot(ks, inertias, marker='o')
        plt.title('Elbow - RAW')
        plt.xlabel('k'); plt.ylabel('Inertia'); plt.grid(True)
        plt.savefig(out_dir/'elbow_raw.png', dpi=150)
        plt.close() 
        k_to_use = find_elbow(ks, inertias)
        print(f"EL metodo Elbow sugiere k={k_to_use}")
    else:
        k_to_use = n_clusters
        print(f"Usando numero definido de clusters: {k_to_use}")

    # Clustering
    km = TimeSeriesKMeans(n_clusters=k_to_use, random_state=42)
    labels = km.fit_predict(X)
    df['cluster_raw'] = labels
    df.to_csv(out_dir/'clusters_raw.csv', index=False)

    # Climate data
    centroids = extract_centroids_from_shp(climate_shp)
    climate_df = None
    if centroids is not None:
        avg_lat, avg_lon = centroids['latitude'].mean(), centroids['longitude'].mean()
        climate_df = fetch_om_data(avg_lat, avg_lon, climate_start_date, climate_end_date, climate_freq)

    # Plot clusters
    for cl in sorted(df['cluster_raw'].unique()):
        fig, ax = plt.subplots(figsize=(12, 6))
        sub = df[df['cluster_raw']==cl]
        n_signatures = len(sub)

        for _, row in sub.iterrows():
            ax.plot(range(num_bands), row[band_cols].values, color='lightblue', alpha=0.3)

        mean_series = sub[band_cols].mean()
        ax.plot(range(num_bands), mean_series.values, color='red', linewidth=3, label=f'Avg cluster {cl}', zorder=3)
        ax.legend(loc='upper left')
        
        for m in range(num_bands):
            ax.axvline(x=m, color='gray', linestyle='--',  linewidth=0.8, alpha=0.7)

        # Solo graficar datos climáticos si están disponibles y tienen el tamaño correcto
        # Deshabilitado temporalmente para evitar errores - el análisis de series temporales funciona sin esto
        try:
            if climate_df is not None and len(climate_df) > 0 and 'temperature_2m' in climate_df.columns:
                temp_values = climate_df['temperature_2m'].values
                # Solo graficar si las dimensiones coinciden exactamente
                if len(temp_values) == num_bands and len(climate_df) == num_bands:
                    x = np.linspace(0, num_bands-1, num_bands)
                    if len(x) == len(temp_values) and len(x) > 0:
                        ax2 = ax.twinx()
                        ax2.plot(x, temp_values, marker='o', color='orange', linestyle='-', linewidth=2, alpha=0.7, label='Temp', zorder=1)
                        ax2.set_ylabel('Temp (°C)', color='orange')
                        ax2.tick_params(axis='y', labelcolor='orange')
                        ax2.legend(loc="upper right")
        except Exception as e:
            # Si hay cualquier error con los datos climáticos, simplemente continuar sin graficarlos
            pass
        plt.title(f"Cluster RAW {polygon_id or 'all'}")
        ax.set_xticks(range(num_bands))
        ax.set_xticklabels(fdates_fmt, ha = 'right')
        ax.text(0.99, 0.90, f"# signatures={n_signatures}",
                transform=ax.transAxes,
                ha='right', va='top', bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray"))
        ax.tick_params(axis='x', rotation=45, labelsize=8)
        ax.grid(True)
        plt.tight_layout()
        plt.savefig(out_dir/f'cluster_{cl}.png', dpi=150)
        plt.close()

    # Signatures
    rows = []
    for cl in sorted(df['cluster_raw'].unique()):
        sub = df[df['cluster_raw']==cl]
        for _, r in sub.iterrows():
            rows.append([r.get('polygon_fid'), r.get('pixel_x'), r.get('pixel_y'), cl, 'individual'] + list(r[band_cols]))
        mean_r = sub[band_cols].mean()
        rows.append([polygon_id, None, None, cl, 'cluster'] + list(mean_r))
    cols = ['polygon_fid','pixel_x','pixel_y','cluster_label','type'] + band_cols
    pd.DataFrame(rows, columns=cols).to_csv(out_dir/'signatures.csv', index=False)

    print(f"Outputs saved in {out_dir}")

 
if __name__ == "__main__":
    BASE = Path("/home/agrosavia/Documents/Geo_Agro")            
    RASTER_CLEAN = BASE / "4.RASTER_CLEAN"
    POLYGON_TOWN = BASE / "3.POLYGON_TOWN"
    RECORTES = BASE / "5.RECORTES" 
    CSV_ALL = BASE / "8.CSV_ALL" 
    OUTPUT = BASE / "9.OUTPUT" 
    PROJECT = "nadia_sub_villap"

    from pathlib import Path
    config={
        "7_2_cluster_raw": {
        # NDVI SERIE
        "csv_path": str(CSV_ALL / PROJECT / "ndvi/serie/CSV_ALL.csv"),
        "base_tif_folder": str(RECORTES  / PROJECT / "RECORTES"),
        "output_folder": str(OUTPUT  / PROJECT / "ndvi/serie/rst_raw"),
        "climate_shp": str(POLYGON_TOWN / "nadia" / "subsetvillap"/ "subsetvillap.shp"),
        "climate_start_date": "2023-01-01",
        "climate_end_date": "2024-12-01",
        "climate_freq": "monthly",
        "max_k": 20,
        "n_clusters": 10,
        "polygon_id": None,
    },
}
    
    for name, params in config.items():
        print(f"\n===Ejecutando configuracion '{name}' === ")
        main(**params)
        print(f"=== Terminado '{name}' === ") 
