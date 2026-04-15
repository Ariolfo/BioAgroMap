import os
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping, box
import warnings

def recortar_tifs_por_poligonos(source_folder: str, shapefile_path: str, destination_folder: str):
    """
    Recorta todos los archivos .tif en source_folder usando cada polígono
    del shapefile y guarda los recortes en destination_folder/<fid>/RECORTES/.

    Parametros:
    - source_folder: ruta a la carpeta que contiene los TIFFs originales.
    - shapefile_path: ruta al shapefile con polígonos (campo 'fid' o 'id').
    - destination_folder: ruta base donde se crearán subcarpetas de salida.
    """
    src_folder = Path(source_folder)
    dest_base = Path(destination_folder)
    dest_base.mkdir(parents=True, exist_ok=True)

    # Validar que exista la carpeta fuente
    if not src_folder.exists():
        raise FileNotFoundError(f"❌ No se encontró la carpeta fuente: {source_folder}")
    
    # Validar que exista el shapefile
    if not Path(shapefile_path).exists():
        raise FileNotFoundError(f"❌ No se encontró el shapefile: {shapefile_path}")

    # Leer shapefile
    print(f"📂 Leyendo shapefile: {shapefile_path}")
    try:
        gdf = gpd.read_file(shapefile_path)
        print(f"✅ Shapefile cargado: {len(gdf)} polígonos encontrados")
    except Exception as e:
        raise ValueError(f"❌ Error al leer el shapefile: {e}")
    
    # Verificar que tenga geometrías
    if len(gdf) == 0:
        raise ValueError("❌ El shapefile no contiene polígonos")
    
    # Verificar CRS del shapefile
    if gdf.crs is None:
        print("⚠️  El shapefile no tiene CRS definido. Asumiendo EPSG:4326")
        gdf.set_crs(epsg=4326, inplace=True)
    
    # Contadores
    total_tifs = len(list(src_folder.glob("*.tif")))
    processed_polygons = 0
    total_clips = 0
    errors = []
    
    print(f"📊 Archivos TIF encontrados: {total_tifs}")
    print(f"📊 Polígonos a procesar: {len(gdf)}")
    
    # Mostrar información de los polígonos si hay múltiples
    if len(gdf) > 1:
        print(f"📋 IDs de polígonos encontrados:")
        polygon_ids = []
        for idx, row in gdf.iterrows():
            fid = row.get('id', row.get('fid', row.get('Id', row.get('FID', None))))
            if fid is not None:
                polygon_ids.append(str(fid))
        if polygon_ids:
            print(f"   {', '.join(polygon_ids)}")
        print(f"💡 Se crearán {len(polygon_ids)} carpetas de polígonos\n")
    else:
        print()
    
    # Procesar cada polígono
    for idx, row in gdf.iterrows():
        # Obtener ID del polígono
        fid = row.get('id', row.get('fid', row.get('Id', row.get('FID', None))))
        if fid is None:
            print(f"⚠️  Polígono en fila {idx}: No tiene campo 'id', 'fid', 'Id' o 'FID' - Saltando")
            continue
        
        geom = row.geometry
        if geom is None or geom.is_empty:
            print(f"⚠️  Polígono {fid}: Geometría vacía o inválida - Saltando")
            continue
        
        # Carpeta de destino para este polígono
        poly_folder = dest_base / str(fid) / "RECORTES"
        poly_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Procesando polígono {fid}...")
        polygon_clips = 0
        
        # Iterar TIFFs
        for tif in src_folder.glob("*.tif"):
            try:
                with rasterio.open(tif) as src:
                    # Obtener CRS del raster
                    raster_crs = src.crs
                    if raster_crs is None:
                        print(f"⚠️  {tif.name}: No tiene CRS definido - Saltando")
                        continue
                    
                    # Convertir geometría al CRS del raster si es necesario
                    if gdf.crs != raster_crs:
                        # Crear un GeoDataFrame temporal con una sola fila para reproyectar
                        temp_gdf = gpd.GeoDataFrame([row], crs=gdf.crs, geometry='geometry')
                        geom_reprojected = temp_gdf.to_crs(raster_crs).geometry.iloc[0]
                    else:
                        geom_reprojected = geom
                    
                    # Verificar intersección antes de recortar
                    raster_bounds = box(*src.bounds)
                    if not geom_reprojected.intersects(raster_bounds):
                        continue  # No hay intersección, saltar este TIF
                    
                    # Recortar
                    out_img, out_tf = mask(src, [mapping(geom_reprojected)], crop=True, all_touched=False)
                    
                    # Verificar que el recorte tenga datos
                    if out_img.size == 0 or out_img.shape[0] == 0:
                        continue
                    
                    # Actualizar metadata
                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_img.shape[1],
                        "width": out_img.shape[2],
                        "transform": out_tf,
                        "compress": "lzw"
                    })
                    
                    # Guardar recorte
                    out_path = poly_folder / tif.name
                    with rasterio.open(out_path, "w", **out_meta) as dst:
                        dst.write(out_img)
                    
                    polygon_clips += 1
                    total_clips += 1
                    
            except Exception as e:
                error_msg = f"Error recortando {tif.name} con polígono {fid}: {e}"
                errors.append(error_msg)
                print(f"❌ {error_msg}")
        
        if polygon_clips > 0:
            print(f"✅ Polígono {fid}: {polygon_clips} archivos recortados\n")
            processed_polygons += 1
        else:
            print(f"⚠️  Polígono {fid}: No se generaron recortes (sin intersección con rasters)\n")
    
    # Resumen
    print(f"\n{'='*60}")
    print(f"📊 Resumen de recorte:")
    print(f"   ✅ Polígonos procesados: {processed_polygons}/{len(gdf)}")
    print(f"   ✅ Archivos recortados: {total_clips}")
    if errors:
        print(f"   ❌ Errores: {len(errors)}")
    print(f"{'='*60}\n")
    
    if processed_polygons == 0:
        raise RuntimeError(
            f"❌ No se pudo procesar ningún polígono.\n"
            f"💡 Posibles causas:\n"
            f"   1. Los polígonos no intersectan con los rasters\n"
            f"   2. Los CRS del shapefile y los rasters no son compatibles\n"
            f"   3. Los polígonos están fuera del área de los rasters\n"
            f"   4. El shapefile no tiene el campo 'id' o 'fid' correcto"
        )
    
    if total_clips == 0:
        raise RuntimeError(
            f"❌ No se generaron archivos recortados.\n"
            f"💡 Verifica que los polígonos intersecten con los rasters."
        )

def main(
    source_folder: str,
    shape_file: str,
    destination_folder: str
) -> None:
    """
    Punto de entrada para integrar en pipeline.
    """
    recortar_tifs_por_poligonos(
        source_folder,
        shape_file,
        destination_folder
    )

source_folder = "/home/agrosavia/Documents/Geo_Agro/4.RASTER_CLEAN/CWC_C1"
shape_file = "/home/agrosavia/Documents/Geo_Agro/3.POLYGON_TOWN/CWC/EXP_1.shp" 
destination_folder = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/CWC_C1"
if __name__ == '__main__':
    main(
        source_folder,
        shape_file,
        destination_folder
    )
         
         # /home/agrosavia/Documents/Geo_Agro/4.RASTER_CLEAN/CWC_C1
         # /home/agrosavia/Documents/Geo_Agro/3.POLYGON_TOWN/CWC/EXP_1.shp
         # /home/agrosavia/Documents/Geo_Agro/5.RECORTES/CWC_C1