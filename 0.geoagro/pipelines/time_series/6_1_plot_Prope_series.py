import numpy as np
import matplotlib.pyplot as plt
from osgeo import gdal
from pathlib import Path
import re
from statsmodels.tsa.seasonal import seasonal_decompose
import pandas as pd
import requests
import geopandas as gpd

# ---------------------------
# Funciones para el clima (API OpenMeteo)
# ---------------------------

def extract_centroids_from_shp(shp_path):
    try:
        gdf = gpd.read_file(shp_path)
        if gdf.crs is None:
            raise ValueError("El Shapefile no tiene un sistema de coordenadas definido.")
        if gdf.crs.to_epsg() != 4326:
            print(f"Transformando CRS de {gdf.crs} a WGS84 (EPSG:4326).")
            gdf = gdf.to_crs(epsg=4326)
        projected_crs = "EPSG:3857"  # Web Mercator Projection
        gdf_projected = gdf.to_crs(projected_crs)
        gdf_projected['centroid'] = gdf_projected.geometry.centroid
        gdf['centroid'] = gdf_projected['centroid'].to_crs(epsg=4326)
        gdf['latitude'] = gdf['centroid'].y
        gdf['longitude'] = gdf['centroid'].x
        return gdf[['latitude', 'longitude', 'centroid']]
    except Exception as e:
        print(f"Error al procesar el archivo Shapefile: {e}")
        return None

def fetch_om_data(latitude, longitude, start_date, end_date, freq):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["weather_code", "temperature_2m", "relative_humidity_2m", "precipitation"],
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "America/Chicago"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Verificar si la solicitud fue exitosa
        data = response.json()["hourly"]
        dataframe = pd.DataFrame({
            "date": pd.to_datetime(data["time"]),
            "weather_code": data["weather_code"],
            "temperature_2m": data["temperature_2m"],
            "relative_humidity_2m": data["relative_humidity_2m"],
            "precipitation": data["precipitation"]
        })
        if freq == "daily":
            daily_dataframe = dataframe.resample('D', on='date').mean().reset_index()
            return daily_dataframe
        elif freq == "monthly":
            daily_dataframe = dataframe.resample('D', on='date').mean().reset_index()
            monthly_dataframe = daily_dataframe.resample('M', on='date').mean().reset_index()
            return monthly_dataframe
        else:
            return dataframe
    except Exception as e:
        print(f"Failed to fetch data from OpenMeteo: {e}")
        return None

def fetch_weather_data_for_average_centroid(centroids, start_date, end_date, freq):
    # Calcular el centroide promedio de todos los centroides
    avg_latitude = centroids['latitude'].mean()
    avg_longitude = centroids['longitude'].mean()
    print(f"Calculando el centroide promedio: {avg_latitude}, {avg_longitude}")
    # Realizar una sola solicitud a la API para este centroide promedio
    df = fetch_om_data(avg_latitude, avg_longitude, start_date, end_date, freq)
    return df

# ---------------------------
# Funciones para las series NDVI
# ---------------------------

def extract_date(file_name):
    """Extrae la fecha en formato 'MM_YYYY' del nombre del archivo."""
    match = re.search(r'\d{2}_\d{4}', str(file_name))
    return match.group(0) if match else None

def extract_month_year(date_str):
    """Extrae el año y el mes como enteros a partir de una cadena 'MM_YYYY'."""
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None

# ---------------------------
# Función para plotear firmas NDVI y temperatura en ejes separados
# ---------------------------

def plot_signatures_and_climate(stack_path, tif_files, shp_path, start_date, end_date, freq, plot_type='both', decompose=None):
    """
    Genera un gráfico en el que:
      - Se plotean las firmas NDVI (por píxel o la media) en el eje y primario.
      - Se plotea la temperatura (datos climáticos) en el eje y secundario.
    
    Parámetros:
      - stack_path: Ruta al archivo GeoTIFF con el stack NDVI.
      - tif_files: Lista de archivos TIFF para extraer las fechas.
      - shp_path: Ruta al Shapefile para extraer los centroides y obtener datos climáticos.
      - start_date, end_date: Fechas para solicitar datos climáticos.
      - freq: Frecuencia de los datos climáticos ('hourly', 'daily' o 'monthly').
      - plot_type: Tipo de gráfico ('both', 'media' o 'series').
      - decompose: Componente a descomponer ('trend', 'seasonal', 'residual') o None.
    """
    # Cargar el stack NDVI
    ds = gdal.Open(str(stack_path))
    if ds is None:
        raise ValueError(f"No se pudo abrir el archivo: {stack_path}")
    stacked_ndvi_array = np.stack([ds.GetRasterBand(i+1).ReadAsArray() for i in range(ds.RasterCount)], axis=-1)
    
    # Detectar píxeles sin información (valor 0)
    zero_pixels = np.all(stacked_ndvi_array == 0, axis=2)
    if np.any(zero_pixels):
        print("Advertencia: Se detectaron píxeles sin información (valor 0).")
    
    # Extraer fechas a partir de los nombres de los TIFF
    dates = [extract_date(f.name) for f in tif_files]
    num_bands = len(dates)
    try:
        dates_dt = [pd.to_datetime(date, format='%m_%Y') for date in dates]
    except Exception as e:
        print("Error al convertir fechas, usando índices numéricos.", e)
        dates_dt = list(range(num_bands))
    
    # Crear figura con dos ejes: ax1 para NDVI y ax2 para temperatura
    fig, ax1 = plt.subplots(figsize=(14, 8))
    ax1.set_ylabel('NDVI')
    ax1.set_xlabel('Fecha')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # Graficar las series NDVI según el tipo seleccionado
    series_count = 0
    all_series = []
    if plot_type in ['both', 'series']:
        for i in range(stacked_ndvi_array.shape[0]):
            for j in range(stacked_ndvi_array.shape[1]):
                if not zero_pixels[i, j]:
                    series = stacked_ndvi_array[i, j, :]
                    if decompose:
                        decomposition = seasonal_decompose(series, model='additive', period=12)
                        if decompose == 'trend':
                            series = decomposition.trend
                        elif decompose == 'seasonal':
                            series = decomposition.seasonal
                        elif decompose == 'residual':
                            series = decomposition.resid
                    all_series.append(series)
                    ax1.plot(dates_dt, series, color='blue', alpha=0.3, linewidth=0.5)
                    series_count += 1
        if all_series:
            all_series = np.array(all_series)
            y_min = np.nanmin(all_series)
            y_max = np.nanmax(all_series)
            ax1.set_ylim(y_min - 0.1 * abs(y_min), y_max + 0.1 * abs(y_max))
    
    if plot_type in ['both', 'media']:
        reshaped = stacked_ndvi_array.reshape(-1, num_bands)
        valid_rows = np.array([not np.all(row == 0) for row in reshaped])
        valid_series = reshaped[valid_rows]
        if valid_series.size > 0:
            mean_values = np.nanmean(valid_series, axis=0)
            std_values = np.nanstd(valid_series, axis=0)
            if decompose:
                decomposition = seasonal_decompose(mean_values, model='additive', period=12)
                if decompose == 'trend':
                    mean_values = decomposition.trend
                elif decompose == 'seasonal':
                    mean_values = decomposition.seasonal
                elif decompose == 'residual':
                    mean_values = decomposition.resid
                std_values = np.zeros_like(mean_values)
            ax1.plot(dates_dt, mean_values, color='red', linewidth=2.5, label='Media NDVI')
            ax1.fill_between(dates_dt,
                             mean_values - std_values,
                             mean_values + std_values,
                             color='red', alpha=0.2, label='Desv. Estándar NDVI')
    
    ax1.set_xticks(dates_dt)
    ax1.set_xticklabels([date.strftime('%m_%Y') for date in dates_dt], rotation=45, ha='right')
    
    # Eje secundario para datos climáticos: temperatura
    centroids = extract_centroids_from_shp(shp_path)
    if centroids is None:
        print("No se pudieron extraer centroides desde el shapefile para datos climáticos.")
    else:
        climate_df = fetch_weather_data_for_average_centroid(centroids, start_date, end_date, freq)
        if climate_df is not None and not climate_df.empty:
            ax2 = ax1.twinx()
            ax2.set_ylabel('Temperatura (°C)', color='orange')
            ax2.tick_params(axis='y', labelcolor='orange')
            ax2.plot(climate_df['date'], climate_df['temperature_2m'], color='orange', linewidth=2, label='Temperatura')
            ax2.legend(loc='upper right')
    
    # Título y leyendas
    if plot_type in ['both', 'series']:
        ax1.set_title(f'Firmas NDVI y Datos Climáticos ({series_count} series NDVI)')
    else:
        ax1.set_title('Firmas NDVI y Datos Climáticos')
    
    ax1.legend(loc='upper left')
    fig.tight_layout()
    return fig  # Retornar figura en lugar de mostrar

def main(csv_path: str = None, output_folder: str = None, root_folder: str = None, 
         shp_path: str = None, start_date: str = "2021-01-01", end_date: str = "2023-12-31", 
         freq: str = "monthly", plot_type: str = 'both', decompose: str = None):
    """
    Función principal para generar gráficos de propiedades de series temporales.
    
    Args:
        csv_path: Ruta al CSV (opcional, se usa para encontrar polígonos)
        output_folder: Carpeta donde guardar gráficos (opcional)
        root_folder: Carpeta raíz con polígonos (requerido si no se proporciona csv_path)
        shp_path: Ruta al shapefile para datos climáticos
        start_date: Fecha inicio para datos climáticos
        end_date: Fecha fin para datos climáticos
        freq: Frecuencia de datos climáticos ('hourly', 'daily', 'monthly')
        plot_type: Tipo de gráfico ('both', 'media', 'series')
        decompose: Componente a descomponer ('trend', 'seasonal', 'residual') o None
    """
    from pathlib import Path
    import matplotlib
    matplotlib.use('Agg')  # Usar backend no interactivo para guardar archivos
    
    if root_folder is None:
        raise ValueError("Se requiere 'root_folder' para procesar polígonos")
    
    root_path = Path(root_folder)
    if not root_path.exists():
        raise FileNotFoundError(f"La carpeta raíz no existe: {root_folder}")
    
    # Procesar cada carpeta de polígono
    polygon_folders = [d for d in root_path.iterdir() if d.is_dir()]
    
    if not polygon_folders:
        raise ValueError(f"No se encontraron carpetas de polígonos en {root_folder}")
    
    print(f"📁 Procesando {len(polygon_folders)} polígono(s) en {root_folder}")
    
    for polygon_folder in polygon_folders:
        try:
            stack_path = polygon_folder / "STACK" / "stack_ndvi.tif"
            recortes_folder = polygon_folder / "RECORTES"
            
            if not stack_path.exists():
                print(f"⚠️ No se encontró stack en {polygon_folder.name}, omitiendo...")
                continue
            
            if not recortes_folder.exists():
                print(f"⚠️ No se encontró carpeta RECORTES en {polygon_folder.name}, omitiendo...")
                continue
            
            tif_files = sorted(recortes_folder.glob("*.tif"), 
                             key=lambda x: extract_month_year(extract_date(x.name)))
            
            if not tif_files:
                print(f"⚠️ No se encontraron archivos TIF en {polygon_folder.name}, omitiendo...")
                continue
            
            print(f"🔄 Procesando polígono: {polygon_folder.name}")
            
            if shp_path:
                fig = plot_signatures_and_climate(stack_path, tif_files, shp_path, start_date, end_date, 
                                          freq, plot_type, decompose)
                
                # Guardar gráfico si se especifica output_folder
                if output_folder:
                    output_path = Path(output_folder)
                    output_path.mkdir(parents=True, exist_ok=True)
                    output_file = output_path / f"properties_{polygon_folder.name}.png"
                    fig.savefig(output_file, dpi=150, bbox_inches='tight')
                    plt.close(fig)
                    print(f"✅ Gráfico guardado: {output_file}")
                else:
                    plt.show()
                    plt.close(fig)
            else:
                print(f"⚠️ No se proporcionó shp_path, omitiendo datos climáticos")
            
            print(f"✅ Polígono {polygon_folder.name} procesado exitosamente")
        except Exception as e:
            print(f"❌ Error procesando polígono {polygon_folder.name}: {str(e)}")
            continue

if __name__ == "__main__":
    # Ejemplo de uso (solo para pruebas)
    polygon_folder = Path("/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/464_moniquira/1640.0")
    if polygon_folder.exists():
        stack_path = polygon_folder / "STACK" / "stack_ndvi.tif"
        tif_files = sorted((polygon_folder / "RECORTES").glob("*.tif"), 
                          key=lambda x: extract_month_year(extract_date(x.name)))
        
        shp_path = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/3.POLYGON_TOWN/469Moniquira/469_moniquira.shp"
        start_date = "2020-09-01"
        end_date = "2025-01-01"
        freq = "monthly"
        plot_type = 'both'
        decompose = None
        
        plot_signatures_and_climate(stack_path, tif_files, shp_path, start_date, end_date, freq, plot_type, decompose)
    else:
        print("⚠️ Carpeta no encontrada. Ejecuta desde la aplicación Streamlit con parámetros correctos.")
