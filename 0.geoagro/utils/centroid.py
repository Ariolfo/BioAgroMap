import geopandas as gpd

def extract_single_centroid(shp_path, target_crs="EPSG:4326"):
    """
    Carga el shapefile, lo transforma al CRS deseado (por defecto EPSG:4326),
    unifica todas las geometrías en una sola y devuelve las coordenadas
    (longitud, latitud) del centroide del recorte territorial completo.
    
    Parámetros:
      shp_path (str): Ruta al shapefile.
      target_crs (str): CRS al que se transformará el shapefile (por defecto 'EPSG:4326').

    Retorna:
      tuple: (centroid_x, centroid_y)
    """
    # Cargar el shapefile
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        raise ValueError("El shapefile no tiene definido un sistema de coordenadas.")
    
    # Transformar al CRS deseado
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    # Unificar todas las geometrías en una sola
    unified_geom = gdf.unary_union
    
    # Calcular el centroide de la geometría unificada
    centroid = unified_geom.centroid
    
    return centroid.x, centroid.y

# Ejemplo de uso:
# Cambia 'ruta/al/shapefile.shp' por la ruta de tu shapefile
centroid_x, centroid_y = extract_single_centroid("/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/3.POLYGON_TOWN/469Moniquira/469_moniquira.shp")
print("Coordenadas del centroide:", centroid_x, centroid_y)
