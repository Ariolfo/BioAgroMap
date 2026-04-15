import os
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask

def recortar_rasters_con_shapefile(shapefile_path, source_folder, destination_folder):
    # Crear la carpeta de destino si no existe
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Leer el shapefile usando Geopandas
    shape = gpd.read_file(shapefile_path)

    # Convertir las geometrías del shapefile a coordenadas adecuadas
    geometries = [feature["geometry"] for feature in shape.__geo_interface__["features"]]

    # Recorrer los archivos TIFF en la carpeta de origen
    for file_name in os.listdir(source_folder):
        if file_name.endswith('.tif'):
            raster_path = os.path.join(source_folder, file_name)

            with rasterio.open(raster_path) as src:
                # Recortar el raster usando el shapefile
                out_image, out_transform = mask(src, geometries, crop=True)
                out_meta = src.meta.copy()

                # Actualizar la metadata del raster recortado
                out_meta.update({
                    "driver": "GTiff",
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform
                })

                # Ruta del archivo recortado
                clipped_raster_path = os.path.join(destination_folder, file_name)

                # Guardar el raster recortado en la carpeta de destino
                with rasterio.open(clipped_raster_path, "w", **out_meta) as dest:
                    dest.write(out_image)

                print(f"Archivo recortado y guardado: {clipped_raster_path}")

shapefile_path = Path('/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/RASTER/poligono_muni/669_chipata/669_chipata.shp')
source_folder = Path('/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/4.RASTER_CLEAN/669_chipata')
destination_folder = Path('/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/669_chipata')

recortar_rasters_con_shapefile(shapefile_path, source_folder, destination_folder)