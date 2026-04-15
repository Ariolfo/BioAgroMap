import geopandas as gpd
import pandas as pd
import requests
import plotly.graph_objects as go

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

def fetch_om_data(latitude, longitude, start_date, end_datmeteoe, freq):
    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["weather_code", "temperature_2m", "relative_humidity_2m", "precipitation"],
        "start_date": start_date,
        "end_date": end_datmeteoe,
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

def fetch_weather_data_for_all_centroids(centroids, start_date, end_date, freq):
    data_list = []
    for _, row in centroids.iterrows():
        df = fetch_om_data(row['latitude'], row['longitude'], start_date, end_date, freq)
        if df is not None:
            data_list.append(df)
    if not data_list:
        return None
    # Combinar los datos de todos los centroides y calcular el promedio para cada fecha
    all_data = pd.concat(data_list, axis=0)
    avg_data = all_data.groupby("date").mean().reset_index()
    return avg_data

def main():
    # Obtener la ruta del archivo shapefile y las fechas de inicio y fin desde la entrada del usuario
    shp_path = input("Introduce la ruta del archivo Shapefile: ")
    start_date = input("Introduce la fecha de inicio (YYYY-MM-DD): ")
    end_date = input("Introduce la fecha de fin (YYYY-MM-DD): ")
    freq = input("Introduce la frecuencia (hourly, daily, monthly): ").lower()

    # Extraer los centroides
    centroids = extract_centroids_from_shp(shp_path)
    if centroids is not None:
        print("Centroids extracted:")
        print(centroids[['latitude', 'longitude']])

        avg_df = fetch_weather_data_for_all_centroids(centroids, start_date, end_date, freq)
        if avg_df is None:
           print("No se pudieron obtener datos meteorológicos.")
           return
        
        fig = go.Figure()
        for variable in ["weather_code", "temperature_2m", "relative_humidity_2m", "precipitation"]:
            fig.add_trace(go.Scatter(x=avg_df['date'], y=avg_df[variable], mode='lines', name=variable))

        fig.update_layout(
            title=f"Average weather variables over Time ({freq.capitalize()})",
            xaxis_title="Time",
            yaxis_title="Values"
        )
        fig.show()
    else:
        print("No se pudieron extraer los centroides.")

if __name__ == "__main__":
    main()