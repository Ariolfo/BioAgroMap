import os
import tempfile
import zipfile
import logging
import geopandas as gpd
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt
import gradio as gr
from datetime import datetime, timedelta
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def extract_centroids_from_shp(shp_path):
    """Extrae centroides de un shapefile y retorna también el geodataframe completo"""
    try:
        logging.info(f"Leyendo shapefile: {shp_path}")
        gdf = gpd.read_file(shp_path)

        if gdf.crs is None:
            raise ValueError("El Shapefile no tiene un sistema de coordenadas definido.")

        if gdf.crs.to_epsg() != 4326:
            logging.info(f"Transformando CRS de {gdf.crs} a WGS84 (EPSG:4326).")
            gdf = gdf.to_crs(epsg=4326)

        # Para centroides precisos, proyectar a Mercator, calcular centroides y volver a 4326
        projected_crs = "EPSG:3857"
        gdf_projected = gdf.to_crs(projected_crs)
        gdf_projected["centroid_proj"] = gdf_projected.geometry.centroid
        gdf["centroid"] = gdf_projected["centroid_proj"].to_crs(epsg=4326)
        gdf["latitude"] = gdf["centroid"].y
        gdf["longitude"] = gdf["centroid"].x

        centroids_df = gdf[["latitude", "longitude", "centroid"]].copy()
        
        return gdf, centroids_df

    except Exception as e:
        logging.error(f"Error al procesar el archivo Shapefile: {e}")
        raise

def create_map_visualization(gdf_full, centroids):
    """Crea un mapa con el polígono y los centroides"""
    try:
        import plotly.graph_objects as go
        
        # Crear figura
        fig = go.Figure()
        
        # Agregar polígonos
        for idx, row in gdf_full.iterrows():
            geom = row.geometry
            
            if geom.geom_type == 'Polygon':
                x, y = geom.exterior.xy
                fig.add_trace(go.Scattermapbox(
                    lon=list(x),
                    lat=list(y),
                    mode='lines',
                    line=dict(width=2, color='blue'),
                    fill='toself',
                    fillcolor='rgba(0, 100, 255, 0.2)',
                    name=f'Polígono {idx}',
                    hoverinfo='name'
                ))
            elif geom.geom_type == 'MultiPolygon':
                for poly in geom.geoms:
                    x, y = poly.exterior.xy
                    fig.add_trace(go.Scattermapbox(
                        lon=list(x),
                        lat=list(y),
                        mode='lines',
                        line=dict(width=2, color='blue'),
                        fill='toself',
                        fillcolor='rgba(0, 100, 255, 0.2)',
                        name=f'Polígono {idx}',
                        hoverinfo='name',
                        showlegend=False
                    ))
        
        # Agregar centroides
        fig.add_trace(go.Scattermapbox(
            lon=centroids['longitude'],
            lat=centroids['latitude'],
            mode='markers',
            marker=dict(size=10, color='red', symbol='circle'),
            name='Centroides',
            hovertemplate='<b>Centroide</b><br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>'
        ))
        
        # Calcular centro del mapa
        center_lat = centroids['latitude'].mean()
        center_lon = centroids['longitude'].mean()
        
        # Calcular zoom apropiado basado en la extensión
        lat_range = centroids['latitude'].max() - centroids['latitude'].min()
        lon_range = centroids['longitude'].max() - centroids['longitude'].min()
        max_range = max(lat_range, lon_range)
        
        # Estimar zoom (aproximado)
        if max_range > 10:
            zoom = 5
        elif max_range > 5:
            zoom = 6
        elif max_range > 2:
            zoom = 7
        elif max_range > 1:
            zoom = 8
        elif max_range > 0.5:
            zoom = 9
        elif max_range > 0.1:
            zoom = 10
        else:
            zoom = 11
        
        # Configurar layout del mapa
        fig.update_layout(
            mapbox=dict(
                style='open-street-map',
                center=dict(lat=center_lat, lon=center_lon),
                zoom=zoom
            ),
            showlegend=True,
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)'),
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(text='Área de Estudio y Centroides', x=0.5, xanchor='center')
        )
        
        return fig
        
    except Exception as e:
        logging.error(f"Error al crear mapa: {e}")
        return None

def fetch_om_data(latitude, longitude, start_date, end_date, freq):
    """Obtiene datos meteorológicos de Open-Meteo Archive API"""
    url = "https://archive-api.open-meteo.com/v1/archive"

    # SIEMPRE usar daily para reducir carga en la API
    daily_vars = [
        "temperature_2m_mean",
        "relative_humidity_2m_mean", 
        "precipitation_sum", 
        "et0_fao_evapotranspiration"
    ]
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(daily_vars),  # ← Aquí debe decir "daily"
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if "daily" not in payload:
            logging.error(f"Respuesta de Open-Meteo no contiene 'daily': {payload.get('reason', payload)}")
            return None

        data = payload["daily"]

        dataframe = pd.DataFrame({
            "date": pd.to_datetime(data.get("time", [])),
            "temperature_2m": data.get("temperature_2m_mean", []),
            "relative_humidity_2m": data.get("relative_humidity_2m_mean", []),
            "precipitation": data.get("precipitation_sum", []),
            "evapotranspiration": data.get("et0_fao_evapotranspiration", [])
        })

        if dataframe.empty:
            return None

        # Si pidieron monthly, hacer resample
        if freq == "monthly":
            monthly_dataframe = dataframe.resample("M", on="date").mean().reset_index()
            return monthly_dataframe
        
        return dataframe

    except requests.exceptions.HTTPError as e:
        raise  # Re-lanzar para manejar en nivel superior
    except Exception as e:
        logging.error(f"Failed to fetch data from Open-Meteo: {e}")
        return None

def fetch_weather_data_for_all_centroids(centroids, start_date, end_date, freq):
    """Obtiene datos meteorológicos para todos los centroides y los promedia"""
    data_list = []
    max_retries = 3
    retry_delay = 5  # segundos
    
    for idx, row in centroids.iterrows():
        logging.info(f"Procesando centroid {idx}: ({row['latitude']}, {row['longitude']})")
        
        # Intentar con reintentos
        for attempt in range(max_retries):
            try:
                df = fetch_om_data(row["latitude"], row["longitude"], start_date, end_date, freq)
                
                if df is not None:
                    df["source_idx"] = idx
                    data_list.append(df)
                    logging.info(f"✅ Centroid {idx} procesado exitosamente")
                else:
                    logging.warning(f"⚠️ Centroid {idx}: No se obtuvieron datos")
                
                # Delay entre peticiones exitosas para respetar rate limit
                time.sleep(1.5)  # 1.5 segundos entre peticiones
                break  # Salir del loop de reintentos si fue exitoso
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Backoff exponencial
                        logging.warning(f"⏳ Rate limit alcanzado en centroid {idx}. Esperando {wait_time}s antes de reintentar...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"❌ Centroid {idx}: Falló después de {max_retries} intentos")
                        break
                else:
                    logging.error(f"❌ Error HTTP {e.response.status_code} en centroid {idx}: {e}")
                    break
            except Exception as e:
                logging.error(f"❌ Error inesperado en centroid {idx}: {e}")
                break

    if not data_list:
        logging.error("No se pudieron obtener datos de ningún centroide")
        return None

    all_data = pd.concat(data_list, axis=0)
    avg_data = all_data.groupby("date").mean().reset_index()
    return avg_data

def create_plotly_subplots(avg_df, freq):
    """Crea gráficos con subplots para cada variable meteorológica"""
    
    variables_info = [
        ("temperature_2m", "Temperature (2m)", "°C", "lines"),
        ("relative_humidity_2m", "Relative Humidity (2m)", "%", "lines"),
        ("precipitation", "Precipitation", "mm", "bars"),
        ("evapotranspiration", "Evapotranspiration (FAO)", "mm", "lines")
    ]
    
    available_vars = [(var, title, unit, chart_type) for var, title, unit, chart_type in variables_info if var in avg_df.columns]
    
    if not available_vars:
        return None
    
    n_vars = len(available_vars)
    
    fig = make_subplots(
        rows=n_vars, 
        cols=1,
        subplot_titles=[title for var, title, unit, chart_type in available_vars],
        vertical_spacing=0.12,
        shared_xaxes=True
    )
    
    for idx, (var, title, unit, chart_type) in enumerate(available_vars, start=1):
        if chart_type == "bars":
            # Gráfico de barras para precipitación
            fig.add_trace(
                go.Bar(
                    x=avg_df["date"], 
                    y=avg_df[var], 
                    name=title,
                    marker=dict(color='steelblue'),
                    showlegend=False
                ),
                row=idx, 
                col=1
            )
        else:
            # Gráfico de líneas para otras variables
            fig.add_trace(
                go.Scatter(
                    x=avg_df["date"], 
                    y=avg_df[var], 
                    mode="lines",
                    name=title,
                    line=dict(width=1.5),
                    showlegend=False
                ),
                row=idx, 
                col=1
            )
        
        fig.update_yaxes(title_text=unit, row=idx, col=1, title_font=dict(size=10))
    
    fig.update_xaxes(title_text="Time", row=n_vars, col=1, title_font=dict(size=10))
    
    fig.update_layout(
        title_text=f"Weather Variables ({freq.capitalize()})",
        title_font=dict(size=14),
        height=180 * n_vars,  # Reducido de 300 a 180
        showlegend=False,
        hovermode='x unified',
        margin=dict(l=50, r=30, t=50, b=40)
    )
    
    return fig

def create_matplotlib_subplots(avg_df, freq, output_path):
    """Crea gráficos con subplots usando matplotlib"""
    
    variables_info = [
        ("temperature_2m", "Temperature (2m)", "°C", "line"),
        ("relative_humidity_2m", "Relative Humidity (2m)", "%", "line"),
        ("precipitation", "Precipitation", "mm", "bar"),
        ("evapotranspiration", "Evapotranspiration (FAO)", "mm", "line")
    ]
    
    available_vars = [(var, title, unit, chart_type) for var, title, unit, chart_type in variables_info if var in avg_df.columns]
    
    if not available_vars:
        return False
    
    n_vars = len(available_vars)
    
    # Tamaño reducido para mejor visualización
    fig, axes = plt.subplots(n_vars, 1, figsize=(10, 2.2 * n_vars), sharex=True)
    
    if n_vars == 1:
        axes = [axes]
    
    for idx, (var, title, unit, chart_type) in enumerate(available_vars):
        if chart_type == "bar":
            # Gráfico de barras para precipitación
            axes[idx].bar(avg_df["date"], avg_df[var], width=1.0, color='steelblue', edgecolor='none')
        else:
            # Gráfico de líneas para otras variables
            axes[idx].plot(avg_df["date"], avg_df[var], linewidth=1.5, color=f'C{idx}')
        
        axes[idx].set_ylabel(unit, fontsize=9)
        axes[idx].set_title(title, fontsize=10, fontweight='bold')
        axes[idx].grid(True, alpha=0.3)
        axes[idx].tick_params(axis='both', which='major', labelsize=8)
    
    axes[-1].set_xlabel("Time", fontsize=9)
    
    fig.suptitle(f"Weather Variables ({freq.capitalize()})", 
                 fontsize=12, fontweight='bold', y=0.995)
    
    plt.tight_layout()
    
    try:
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
        plt.close()
        return True
    except Exception as e:
        logging.error(f"Error al guardar PNG: {e}")
        return False

def extract_shapefile_from_zip(zip_file):
    """Extrae archivos de un ZIP y encuentra el .shp"""
    temp_dir = tempfile.mkdtemp()
    
    try:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Buscar archivo .shp
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.shp'):
                    return os.path.join(root, file)
        
        raise ValueError("No se encontró archivo .shp en el ZIP")
    
    except Exception as e:
        logging.error(f"Error al extraer shapefile: {e}")
        raise

def process_weather_data(shapefile_zip, start_date, end_date, frequency):
    """Función principal para procesar datos desde Gradio"""
    
    try:
        # Validar fechas
        if not start_date or not end_date:
            return None, None, None, None, "❌ Por favor ingresa fechas válidas", None, None
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt >= end_dt:
            return None, None, None, None, "❌ La fecha de inicio debe ser anterior a la fecha de fin", None, None
        
        if end_dt > datetime.now():
            return None, None, None, None, "❌ La fecha de fin no puede ser futura (solo datos históricos)", None, None
        
        # Extraer shapefile del ZIP
        if shapefile_zip is None:
            return None, None, None, None, "❌ Por favor carga un archivo ZIP con el shapefile", None, None
        
        shp_path = extract_shapefile_from_zip(shapefile_zip)
        
        # Extraer centroides y geodataframe completo
        status_msg = "📍 Extrayendo centroides del shapefile..."
        gdf_full, centroids = extract_centroids_from_shp(shp_path)
        
        if centroids is None or centroids.empty:
            return None, None, None, None, "❌ No se pudieron extraer centroides del shapefile", None, None
        
        status_msg += f"\n✅ {len(centroids)} centroides extraídos"
        
        # Crear mapa de visualización
        status_msg += "\n🗺️ Generando mapa..."
        map_fig = create_map_visualization(gdf_full, centroids)
        
        # Obtener datos meteorológicos
        status_msg += f"\n🌦️ Obteniendo datos meteorológicos ({frequency})..."
        avg_df = fetch_weather_data_for_all_centroids(centroids, start_date, end_date, frequency)
        
        if avg_df is None or avg_df.empty:
            return map_fig, None, None, None, f"{status_msg}\n❌ No se pudieron obtener datos meteorológicos", None, None
        
        status_msg += f"\n✅ {len(avg_df)} registros obtenidos"
        
        # Crear gráfico interactivo
        status_msg += "\n📊 Generando visualizaciones..."
        fig = create_plotly_subplots(avg_df, frequency)
        
        if fig is None:
            return map_fig, None, None, None, f"{status_msg}\n❌ Error al crear gráfico", None, None
        
        # Crear gráfico estático (PNG)
        png_path = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
        success = create_matplotlib_subplots(avg_df, frequency, png_path)
        
        if not success:
            png_path = None
        
        # Guardar datos en CSV
        csv_path = tempfile.NamedTemporaryFile(delete=False, suffix='.csv').name
        try:
            avg_df.to_csv(csv_path, index=True)
            status_msg += "\n✅ Datos exportados a CSV"
        except Exception as e:
            logging.error(f"Error al guardar CSV: {e}")
            csv_path = None
        
        status_msg += "\n✅ Visualización completada"
        
        # Crear resumen estadístico
        summary = f"""
**Período:** {start_date} → {end_date}  
**Registros:** {len(avg_df)} ({frequency})  
**Centroides:** {len(centroids)}

**Promedios:**
- 🌡️ Temp: {avg_df['temperature_2m'].mean():.1f}°C ({avg_df['temperature_2m'].min():.1f}-{avg_df['temperature_2m'].max():.1f}°C)
- 💧 Humedad: {avg_df['relative_humidity_2m'].mean():.1f}%
- 🌧️ Precip. total: {avg_df['precipitation'].sum():.1f} mm
- 🌱 ET total: {avg_df['evapotranspiration'].sum():.1f} mm
"""
        
        # Preparar DataFrame para visualización en la interfaz
        display_df = avg_df.copy()
        
        # Imprimir en consola para verificación
        print("\nDataFrame generado:")
        print(display_df)
        
        return map_fig, fig, png_path, csv_path, status_msg, summary, display_df
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        logging.error(error_msg)
        return None, None, None, None, error_msg, None, None

# Crear interfaz Gradio
def create_gradio_interface():
    """Crea la interfaz Gradio"""
    
    with gr.Blocks(theme=gr.themes.Soft(), title="Weather Data Analyzer") as demo:
        gr.Markdown("""
        # 🌤️ Weather Data Analyzer
        Análisis de datos meteorológicos históricos para agricultura
        """)
        
        with gr.Row():
            # COLUMNA IZQUIERDA: Inputs y Controles
            with gr.Column(scale=1):
                gr.Markdown("### 📁 Datos de entrada")
                
                shapefile_input = gr.File(
                    label="📦 Shapefile (.zip)",
                    file_types=[".zip"],
                    type="filepath"
                )
                
                gr.Markdown("""
                💡 Comprime .shp, .shx, .dbf, .prj en un .zip
                """)
                
                start_date_input = gr.Textbox(
                    label="📅 Fecha inicio",
                    value=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                    placeholder="2024-01-01"
                )
                
                end_date_input = gr.Textbox(
                    label="📅 Fecha fin",
                    value=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                    placeholder="2024-12-31"
                )
                
                frequency_input = gr.Dropdown(
                    label="⏱️ Frecuencia",
                    choices=["hourly", "daily", "monthly"],
                    value="daily"
                )
                
                process_btn = gr.Button("🚀 Procesar", variant="primary", size="lg")
                
                status_output = gr.Textbox(
                    label="📋 Estado",
                    lines=6,
                    interactive=False
                )
                
                summary_output = gr.Markdown(label="📊 Resumen")
                
                png_output = gr.File(label="⬇️ Descargar PNG")
                
                csv_output = gr.File(label="⬇️ Descargar CSV")
            
            # COLUMNA DERECHA: Mapa y Gráficos
            with gr.Column(scale=2):
                gr.Markdown("### 🗺️ Área de Estudio")
                
                map_output = gr.Plot(label="Mapa del polígono", show_label=False)
                
                gr.Markdown("### 📊 Visualización de datos")
                
                plot_output = gr.Plot(label="Gráfico interactivo", show_label=False)
                
                gr.Markdown("### 📋 Tabla de datos")
                
                table_output = gr.Dataframe(
                    label="Datos meteorológicos completos",
                    show_label=False,
                    wrap=True,
                    interactive=False
                )
        
        # Conectar botón con función de procesamiento
        process_btn.click(
            fn=process_weather_data,
            inputs=[shapefile_input, start_date_input, end_date_input, frequency_input],
            outputs=[map_output, plot_output, png_output, csv_output, status_output, summary_output, table_output]
        )
        
        gr.Markdown("""
        ---
        **Fuente:** Open-Meteo Archive API | **Variables:** Temperatura, Humedad, Precipitación, Evapotranspiración (FAO)
        """)
    
    return demo

# Ejecutar aplicación
if __name__ == "__main__":
    demo = create_gradio_interface()
    # Gradio encontrará automáticamente un puerto disponible
    demo.launch(share=False, server_name="0.0.0.0")