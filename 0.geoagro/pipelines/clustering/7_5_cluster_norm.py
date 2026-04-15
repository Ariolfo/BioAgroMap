# 8_cluster_norm_pipeline.py
import re
import os
import numpy as np
import pandas as pd
import requests
import geopandas as gpd
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Tuple
from tslearn.clustering import TimeSeriesKMeans
from tslearn.preprocessing import TimeSeriesScalerMeanVariance
from sklearn.decomposition import PCA
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm


def extract_date_from_tif(file_name: str) -> Optional[str]:
    match = re.search(r"\d{2}_\d{4}", str(file_name))
    return match.group(0) if match else None


def extract_month_year(date_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None


def find_tif_files(base_folder: str, polygon_id: Optional[int] = None) -> List[Path]:
    base = Path(base_folder)
    if polygon_id is not None:
        folder = base / f"{polygon_id}.0" / "RECORTES" # si los poligonos tienen numeracion decimal
        return sorted(folder.glob("*.tif")) if folder.exists() else []
    candidates = [p for p in base.iterdir() if p.is_dir() and p.name.endswith('.0')] # si los poligonos tienen numeracion decimal
    if not candidates:
        return []
    rec = sorted(candidates)[0] / "RECORTES"
    return sorted(rec.glob("*.tif")) if rec.exists() else []

def compute_inertia(k: int, X: np.ndarray, metric: str) -> float:
    model = TimeSeriesKMeans(n_clusters=k, metric=metric, random_state=42, n_jobs = -1)
    model.fit(X)
    return model.inertia_


def compute_inertia_args(args):
    k, X, metric = args
    return compute_inertia(k, X, metric)


def elbow_method_time_series(X: np.ndarray, max_k: int = 40, metric: str = "euclidean") -> Tuple[List[int], List[float]]:
    ks = list(range(1, max_k + 1))
    args = [(k, X, metric) for k in ks]
    with concurrent.futures.ProcessPoolExecutor(max_workers = os.cpu_count()) as executor:
        inertias = list(executor.map(compute_inertia_args, args))
    return ks, inertias


def find_elbow(ks: List[int], inertias: List[float]) -> int:
    if len(inertias) < 2:
        return ks[0]
    diffs = [inertias[i] - inertias[i+1] for i in range(len(inertias)-1)]
    return ks[int(np.argmax(diffs)) + 1]


def extract_centroids_from_shp(shp_path: str) -> Optional[pd.DataFrame]:
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


def plot_single_cluster(cl, df, band_cols, num_bands, climate_df, out_dir, polygon_id):
    plt.figure(figsize=(10,6))
    subset = df[df['cluster_norm']==cl]
    for _, row in subset.iterrows():
        plt.plot(range(num_bands), row[band_cols].values, color='lightgreen', alpha=0.3)
    mean_series = subset[band_cols].mean()
    plt.plot(range(num_bands), mean_series.values, color='blue', linewidth=3, label=f'Avg cluster {cl}')
    if climate_df is not None and not climate_df.empty:
        y = climate_df['temperature_2m'].values
        x = np.linspace(0, num_bands-1, len(y))
        ax = plt.gca()
        ax2 = ax.twinx()
        ax2.plot(x, y, color='orange', linewidth=2, label='Temp')
        ax2.set_ylabel('Temp (°C)', color='orange')
        ax2.tick_params(axis='y', labelcolor='orange')
        ax2.legend(loc='upper right')
    plt.title(f'Cluster NORMALIZED {polygon_id if polygon_id is not None else "all"}')
    plt.xlabel('Time')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)
    plt.savefig(out_dir/f'cluster_norm_{cl}.png', dpi=150)
    plt.close()


def main(
    csv_path: str,
    base_tif_folder: str,
    output_folder: str,
    climate_shp: str,
    climate_start_date: str,
    climate_end_date: str,
    climate_freq: str = 'monthly',
    max_k: int = 40,
    polygon_id: Optional[int] = None
) -> None:
    out_dir = Path(output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Leer firmas y TIFs
    tifs = find_tif_files(base_tif_folder, polygon_id)
    dates = [extract_date_from_tif(t.name) for t in tifs]
    pairs = [(t, d) for t, d in zip(tifs, dates) if d]
    pairs.sort(key=lambda x: extract_month_year(x[1]))
    num_bands = len(pairs)
    fdates = [d for (_, d) in pairs]
    fdates_dt = pd.to_datetime([f"01_{d}" for d in fdates], format="%d_%m_%Y")
    fdates_fmt = [dt.strftime("%m-%Y") for dt in fdates_dt]

    df_full = pd.read_csv(csv_path)
    df = df_full[df_full['polygon_fid']==polygon_id].copy() if polygon_id else df_full.copy()
    if df.empty: 
        print(f"[ERROR] No samples found for polygon_id{polygon_id}. Exiting")
        return
    band_cols = [c for c in df.columns if c.startswith('band_')]
    if not band_cols:
        raise ValueError("No band_* columns present in the CSV for clustering")
    X = df[band_cols].values

    # Normalización y elbow
    X_norm = TimeSeriesScalerMeanVariance().fit_transform(X).reshape(X.shape)
    ks, inertias = elbow_method_time_series(X_norm, max_k)
    plt.figure(); plt.plot(ks, inertias, marker='o')
    plt.title('Elbow - NORMALIZED'); plt.xlabel('k'); plt.ylabel('Inertia'); plt.grid(True)
    plt.savefig(out_dir/'elbow_norm.png', dpi=150); plt.close()
    k_norm = find_elbow(ks, inertias)

    # PCA + clustering
    X_pca = PCA(n_components=min(3, X_norm.shape[1])).fit_transform(X_norm)
    labels = TimeSeriesKMeans(n_clusters=k_norm, random_state=42).fit_predict(X_pca)
    df['cluster_norm'] = labels
    df.to_csv(out_dir/'clusters_norm.csv', index=False)

    # Datos climáticos
    centroids = extract_centroids_from_shp(climate_shp)
    climate_df = None
    if centroids is not None:
        avg_lat, avg_lon = centroids['latitude'].mean(), centroids['longitude'].mean()
        climate_df = fetch_om_data(avg_lat, avg_lon, climate_start_date, climate_end_date, climate_freq)

    # Graficar clusters en paralelo
    cluster_labels = sorted(df['cluster_norm'].unique())
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(
            lambda cl: plot_single_cluster(
                cl, df, band_cols, num_bands, climate_df, out_dir, polygon_id
            ),
            cluster_labels
        )

    # Signatures medios
    sig_rows = [['norm', cl] + list(df[df['cluster_norm']==cl][band_cols].mean())
                for cl in cluster_labels]
    sig_df = pd.DataFrame(sig_rows, columns=['type','cluster']+band_cols)
    sig_df.to_csv(out_dir/'signatures_norm.csv', index=False)

    print(f"Normalized clustering outputs saved in {out_dir}")
