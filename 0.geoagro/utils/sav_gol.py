import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
from scipy.signal import savgol_filter

def plot_ndvi_by_polygon(file_path, polygon_id, window_length=7, polyorder=2):
    """
    Lee un archivo CSV que contiene datos de series temporales de NDVI, filtra los datos para un polígono específico y 
    crea dos gráficos: uno con las firmas de NDVI sin procesar y otro con las firmas de NDVI suavizadas.
    
    
    Parámetros:
        file_path (str): Ruta al archivo CSV.
        polygon_id (int o str): El polygon_fid para filtrar los datos.
        longitud_ventana (int): La longitud de la ventana para el filtro Savitzky-Golay (debe ser impar y <= número de puntos temporales).
        polyorder (int): El orden polinómico para el filtro Savitzky-Golay.
    """
    df = pd.read_csv(file_path)
    
    df_polygon = df[df['polygon_fid'] == polygon_id].copy()
    
    ndvi_cols = [col for col in df.columns if col.startswith('band_')]
    
    df_polygon['pixel_id'] = df_polygon['polygon_fid'].astype(str) + "_" + df_polygon['pixel_x'].astype(str) + "_" + df_polygon['pixel_y'].astype(str)
    
    time_points = np.arange(1, len(ndvi_cols) + 1)
    
    fig_raw = go.Figure()
    fig_smooth = go.Figure()
    
    for idx, row in df_polygon.iterrows():
        ndvi_series = row[ndvi_cols].values
        smoothed_series = savgol_filter(ndvi_series, window_length, polyorder)
        pixel_id = row['pixel_id']
        
        fig_raw.add_trace(go.Scatter(
            x=time_points,
            y=ndvi_series,
            mode='lines',
            name=f'Pixel {pixel_id}',
            opacity=0.7
        ))
        
        fig_smooth.add_trace(go.Scatter(
            x=time_points,
            y=smoothed_series,
            mode='lines',
            name=f'Pixel {pixel_id}',
            opacity=0.7
        ))
    
    fig_raw.update_layout(
        title=f'Polygon {polygon_id} NDVI Signatures - Raw',
        xaxis_title='Time (Band)',
        yaxis_title='NDVI',
        template='plotly_white'
    )
    
    fig_smooth.update_layout(
        title=f'Polygon {polygon_id} NDVI Signatures - Smoothed',
        xaxis_title='Time (Band)',
        yaxis_title='NDVI',
        template='plotly_white'
    )
    
    fig_raw.show()
    fig_smooth.show()

file_path = '/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/8.CSV_ALL/464_moniquira_CSV_ALL.csv'
polygon_id = 1897  
plot_ndvi_by_polygon(file_path, polygon_id)
