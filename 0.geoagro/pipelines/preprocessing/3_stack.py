import os
import re
import numpy as np
from osgeo import gdal
from pathlib import Path
from typing import Optional

def extract_date(file_name):
    """
    Extrae la fecha en formato 'MM_YYYY' del nombre del archivo.
    """
    match = re.search(r'\d{2}_\d{4}', str(file_name))
    return match.group(0) if match else None

# Función para extraer el mes y el año como enteros
def extract_month_year(date_str):
    """
    Extrae el año y el mes como enteros a partir de una cadena 'MM_YYYY'.
    """
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None

def describe_bands(ds, tif_path: Path, prefix: Optional[str] = None) -> None:
    """
    Muestra por consola las bandas disponibles en el raster para facilitar la verificación manual.
    """
    band_count = ds.RasterCount
    header = f"{tif_path.name}: {band_count} bandas detectadas"
    if prefix:
        header = f"{prefix} {header}"
    print(header)
    for idx in range(1, band_count + 1):
        band = ds.GetRasterBand(idx)
        meta = band.GetMetadata() or {}
        descriptor = (
            meta.get("BandName")
            or meta.get("BANDNAME")
            or meta.get("Description")
            or meta.get("DESCRIPTION")
            or band.GetDescription()
            or "sin descripción"
        )
        wavelength = meta.get("wavelength") or meta.get("WAVELENGTH")
        extra = f" | λ={wavelength}" if wavelength else ""
        print(f"  - Banda {idx}: {descriptor}{extra}")


def _dataset_bounds(gt, width, height):
    x_min = gt[0]
    y_max = gt[3]
    x_max = x_min + gt[1] * width
    y_min = y_max + gt[5] * height
    return (x_min, y_min, x_max, y_max)


def _open_aligned(ds, ref_proj, ref_gt, ref_width, ref_height):
    """
    Devuelve un dataset en memoria alineado al grid de referencia si es necesario.
    """
    same_size = (ds.RasterXSize == ref_width and ds.RasterYSize == ref_height)
    same_proj = (ds.GetProjection() == ref_proj)
    same_gt = (ds.GetGeoTransform() == ref_gt)
    if same_size and same_proj and same_gt:
        return ds

    bounds = _dataset_bounds(ref_gt, ref_width, ref_height)
    warped = gdal.Warp(
        "",
        ds,
        format="MEM",
        dstSRS=ref_proj,
        outputBounds=bounds,
        width=ref_width,
        height=ref_height,
        resampleAlg=gdal.GRA_Bilinear,
        multithread=True,
    )
    return warped


def calculate_index(tif_path, ref_grid=None):
    ds = gdal.Open(str(tif_path))
    if ds.RasterCount >= 6:
        # [1: blue, 2: green, 3: thermal, 4: nir, 5: red edge, 6: red]
        band_roles = {"blue": 1, "green": 2, "lwir": 3, "nir": 4, "rededge": 5, "red": 6}
    elif ds.RasterCount == 5:
        # [1: blue, 2: green, 3: nir, 4: red edge, 5: red]
        band_roles = {"blue": 1, "green": 2, "nir": 3, "rededge": 4, "red": 5}
    elif ds.RasterCount >= 4:
        # [1: blue, 2: green, 3: red, 4: nir]
        band_roles = {"blue": 1, "green": 2, "red": 3, "nir": 4}
    else:
        raise ValueError(
            f"Se encontraron {ds.RasterCount} bandas en {tif_path}. "
            "Se requieren al menos 4 para calcular NDVI/EVI (Blue, Red, NIR)."
        )

    missing = [role for role in ("blue", "red", "nir") if role not in band_roles]
    if missing:
        raise ValueError(
            f"No se pudieron mapear las bandas {missing} en {tif_path}. "
            "Revisa la configuración de band_roles."
        )

    # Alinear al grid de referencia si se proporciona
    if ref_grid is not None:
        ref_proj, ref_gt, ref_w, ref_h = ref_grid
        ds_aligned = _open_aligned(ds, ref_proj, ref_gt, ref_w, ref_h)
    else:
        ds_aligned = ds

    blue = ds_aligned.GetRasterBand(band_roles["blue"]).ReadAsArray().astype(np.float32)
    red = ds_aligned.GetRasterBand(band_roles["red"]).ReadAsArray().astype(np.float32)
    nir = ds_aligned.GetRasterBand(band_roles["nir"]).ReadAsArray().astype(np.float32)
    """ red_edge = (
        ds.GetRasterBand(band_roles["rededge"]).ReadAsArray().astype(np.float32)
        if "rededge" in band_roles else None
    ) """

    ds = None

    valid_mask = (blue != 0.0) & (red != 0.0) & (nir != 0.0)

    ndvi = np.full_like(nir, np.nan)
    evi  = np.full_like(nir, np.nan)
    evi2 = np.full_like(nir, np.nan)
    """ ndre = np.full_like(nir, np.nan) if red_edge is not None else None """

    # NDVI
    ndvi[valid_mask] = (nir[valid_mask] - red[valid_mask]) / (nir[valid_mask] + red[valid_mask] + 1e-9)
    ndvi_min = np.nanmin(ndvi)
    ndvi_max = np.nanmax(ndvi)
    ndvi_norm = (ndvi - ndvi_min) / (ndvi_max - ndvi_min + 1e-9)
    ndvi_norm = np.nan_to_num(ndvi_norm, nan=0.0)

    # EVI
    evi[valid_mask] = 2.5 * (nir[valid_mask] - red[valid_mask]) / (nir[valid_mask] + 6.0 * red[valid_mask] - 7.5 * blue[valid_mask] + 1.0 + 1e-9)
    evi_min = np.nanmin(evi)
    evi_max = np.nanmax(evi)
    evi_norm = (evi - evi_min) / (evi_max - evi_min + 1e-9)
    evi_norm = np.nan_to_num(evi_norm, nan=0.0)

    # EVI2
    evi2[valid_mask] = 2.5 * (nir[valid_mask] - red[valid_mask]) / (nir[valid_mask] + 2.4 * red[valid_mask] + 1.0 + 1e-9)
    evi2_min = np.nanmin(evi2)
    evi2_max = np.nanmax(evi2)
    evi2_norm = (evi2 - evi2_min) / (evi2_max - evi2_min + 1e-9)
    evi2_norm = np.nan_to_num(evi2_norm, nan=0.0)

    """ ndre_norm = None
    if ndre is not None:
        valid_mask_ndre = valid_mask & (red_edge != 0.0)
        ndre[valid_mask_ndre] = (
            (nir[valid_mask_ndre] - red_edge[valid_mask_ndre])
            / (nir[valid_mask_ndre] + red_edge[valid_mask_ndre] + 1e-9)
        )
        if np.any(~np.isnan(ndre)):
            ndre_min = np.nanmin(ndre)
            ndre_max = np.nanmax(ndre)
            ndre_norm = (ndre - ndre_min) / (ndre_max - ndre_min + 1e-9)
            ndre_norm = np.nan_to_num(ndre_norm, nan=0.0) """

    return ndvi_norm, evi_norm, evi2_norm

def create_stacks(polygon_folder):
    
    recortes_folder = Path(polygon_folder) / "RECORTES"
    if not recortes_folder.exists():
        raise FileNotFoundError(
            f"❌ No se encontró la carpeta RECORTES en {polygon_folder}\n"
            f"💡 Solución: Ejecuta primero el módulo '2_all_clipp' para generar los recortes por polígono."
        )

    stack_folder = Path(polygon_folder) / "STACK"
    stack_folder.mkdir(parents=True, exist_ok=True)  

    tif_files = list(recortes_folder.glob("*.tif"))
    if not tif_files:
        raise ValueError(
            f"❌ No hay archivos .tif en {recortes_folder}\n"
            f"💡 Solución: Ejecuta primero el módulo '2_all_clipp' para recortar las imágenes por polígonos.\n"
            f"📋 El módulo '2_all_clipp' requiere:\n"
            f"   - Archivos TIF en 4.RASTER_CLEAN/[proyecto]/\n"
            f"   - Shapefile con los polígonos\n"
            f"   - Genera archivos TIF recortados en 5.RECORTES/[proyecto]/[polígono]/RECORTES/"
        )

    tif_files.sort(key=lambda x: extract_month_year(extract_date(x.name)))

    ordered_labels = []
    for tif in tif_files:
        label = extract_date(tif.name)
        ordered_labels.append(label if label else tif.name)
    if ordered_labels:
        print(f"[INFO] Orden temporal {Path(polygon_folder).name}: {', '.join(ordered_labels)}")

    ndvi_list = []
    evi_list = []
    evi2_list = []
    """ ndre_list = []
    ndre_expected = None """

    # Definir grid de referencia con el primer TIF
    ref_ds = gdal.Open(str(tif_files[0]))
    ref_proj = ref_ds.GetProjection()
    ref_gt = ref_ds.GetGeoTransform()
    ref_w, ref_h = ref_ds.RasterXSize, ref_ds.RasterYSize
    ref_grid = (ref_proj, ref_gt, ref_w, ref_h)
    ref_ds = None

    for tif_path in tif_files:
        ndvi_norm, evi_norm, evi2_norm = calculate_index(tif_path, ref_grid=ref_grid)
        ndvi_list.append(ndvi_norm)
        evi_list.append(evi_norm)
        evi2_list.append(evi2_norm)
        """ if ndre_expected is None:
            ndre_expected = ndre_norm is not None
        if ndre_expected:
            if ndre_norm is None:
                raise ValueError(
                    f"No se pudo calcular NDRE para {tif_path}, pero otras escenas sí lo permiten."
                )
            ndre_list.append(ndre_norm) """

    ndvi_stack = np.stack(ndvi_list, axis=0)
    evi_stack  = np.stack(evi_list,  axis=0)
    evi2_stack = np.stack(evi2_list, axis=0)

    save_geotiff(ndvi_stack, tif_files[0], stack_folder / "stack_ndvi.tif")
    save_geotiff(evi_stack,  tif_files[0], stack_folder / "stack_evi.tif")
    save_geotiff(evi2_stack, tif_files[0], stack_folder / "stack_evi2.tif")
    """ if ndre_expected:
        ndre_stack = np.stack(ndre_list, axis=0)
        save_geotiff(ndre_stack, tif_files[0], stack_folder / "stack_ndre.tif")
 """
def save_geotiff(data, reference_tif, output_path, nodata_value=0.0):
    
    ds = gdal.Open(str(reference_tif))
    if ds is None:
        raise ValueError(f"No se pudo abrir el archivo de referencia: {reference_tif}")

    # Obtener la información geográfica
    rows, cols = data.shape[1], data.shape[2]
    bands = data.shape[0]
    geotransform = ds.GetGeoTransform()
    projection = ds.GetProjection()
    ds=None

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(output_path), cols, rows, bands, gdal.GDT_Float32)

    out_ds.SetGeoTransform(geotransform)
    out_ds.SetProjection(projection)

    for i in range(bands):
        band = out_ds.GetRasterBand(i + 1)
        band.WriteArray(data[i])
        band.SetNoDataValue(nodata_value)

    out_ds.FlushCache()
    out_ds = None

def main(root_folder):
    """
    Genera stacks de NDVI, EVI y EVI2 para cada polígono.
    
    Args:
        root_folder: Ruta a la carpeta raíz del proyecto (ej: 5.RECORTES/[proyecto])
    
    Requiere:
        - Archivos TIF recortados en [polígono]/RECORTES/*.tif (generados por 2_all_clipp)
    
    Genera:
        - stack_ndvi.tif en [polígono]/STACK/
        - stack_evi.tif en [polígono]/STACK/
        - stack_evi2.tif en [polígono]/STACK/
    """
    root_path = Path(root_folder)
    if not root_path.exists():
        raise FileNotFoundError(f"❌ El directorio raíz no existe: {root_folder}")

    # Verificar si hay carpetas de polígonos
    polygon_folders = [f for f in root_path.iterdir() if f.is_dir()]
    if not polygon_folders:
        raise ValueError(
            f"❌ No se encontraron carpetas de polígonos en {root_folder}\n"
            f"💡 Solución: Ejecuta primero el módulo '2_all_clipp' para generar los recortes por polígono."
        )

    # Procesar cada carpeta de polígono
    processed_count = 0
    error_count = 0
    
    for polygon_folder in polygon_folders:
        # Saltar carpetas especiales como .git, __pycache__, etc.
        if polygon_folder.name.startswith('.'):
            continue
        
        # Verificar si tiene carpeta RECORTES antes de procesar
        recortes_folder = polygon_folder / "RECORTES"
        if not recortes_folder.exists():
            print(f"⚠️  Polígono '{polygon_folder.name}': No tiene carpeta RECORTES/ - Saltando")
            error_count += 1
            continue
        
        tif_count = len(list(recortes_folder.glob("*.tif")))
        if tif_count == 0:
            print(f"⚠️  Polígono '{polygon_folder.name}': RECORTES/ está vacío (0 archivos TIF) - Saltando")
            print(f"   💡 Ejecuta '2_all_clipp' para generar los recortes para este polígono\n")
            error_count += 1
            continue
            
        try:
            print(f"📁 Procesando polígono: {polygon_folder.name} ({tif_count} archivos TIF encontrados)")
            create_stacks(polygon_folder)
            print(f"✅ Stack de NDVI, EVI y EVI2 generados para {polygon_folder.name}\n")
            processed_count += 1
        except Exception as e:
            print(f"❌ Error procesando {polygon_folder.name}: {str(e)}\n")
            error_count += 1
    
    # Resumen
    print(f"\n{'='*60}")
    print(f"📊 Resumen:")
    print(f"   ✅ Polígonos procesados: {processed_count}")
    if error_count > 0:
        print(f"   ❌ Polígonos con errores: {error_count}")
    print(f"{'='*60}")
    
    if processed_count == 0:
        # Diagnosticar el problema
        empty_folders = []
        missing_folders = []
        for polygon_folder in polygon_folders:
            if polygon_folder.name.startswith('.'):
                continue
            recortes_folder = polygon_folder / "RECORTES"
            if not recortes_folder.exists():
                missing_folders.append(polygon_folder.name)
            elif len(list(recortes_folder.glob("*.tif"))) == 0:
                empty_folders.append(polygon_folder.name)
        
        error_msg = f"❌ No se pudo procesar ningún polígono.\n\n"
        error_msg += f"📋 Diagnóstico:\n"
        
        if missing_folders:
            error_msg += f"   ⚠️  Polígonos sin carpeta RECORTES/: {', '.join(missing_folders)}\n"
        if empty_folders:
            error_msg += f"   ⚠️  Polígonos con RECORTES/ vacío: {', '.join(empty_folders)}\n"
        
        error_msg += f"\n💡 Solución:\n"
        error_msg += f"   1. Ejecuta el módulo '2_all_clipp' (Recorte de imágenes por polígonos)\n"
        error_msg += f"      - Requiere: Shapefile cargado y archivos TIF en 4.RASTER_CLEAN/[proyecto]/\n"
        error_msg += f"      - Genera: Archivos TIF recortados en 5.RECORTES/[proyecto]/[polígono]/RECORTES/\n"
        error_msg += f"   2. Verifica que el shapefile tenga el campo 'fid' o 'id' con los IDs de polígonos\n"
        error_msg += f"   3. Después de ejecutar '2_all_clipp', vuelve a ejecutar '3_stack'\n"
        
        raise RuntimeError(error_msg)

# Ruta de la carpeta raíz
root_folder = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/CWC_C1"  

if __name__ == "__main__":
    main(root_folder)
