import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import os
import re
import numpy as np
from pathlib import Path
from PIL import Image
from osgeo import gdal
import rasterio
import argparse

# Funciones para extraer y ordenar fechas
def extract_date(file_name):
    """
    Extrae la fecha en formato 'MM_YYYY' del nombre del archivo.
    Soporta formatos: MM_YYYY (01_2023) y YYYY-MM (2023-01)
    """
    # Intentar formato MM_YYYY (ej: 01_2023)
    match = re.search(r'(\d{2})_(\d{4})', str(file_name))
    if match:
        return match.group(0)
    # Intentar formato YYYY-MM (ej: 2023-01)
    match = re.search(r'(\d{4})-(\d{2})', str(file_name))
    if match:
        # Convertir YYYY-MM a MM_YYYY
        year, month = match.groups()
        return f"{month}_{year}"
    return None

def extract_month_year(date_str):
    """
    Extrae el año y el mes como enteros a partir de una cadena 'MM_YYYY'.
    """
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None

def sort_tif_files(tif_files):
    """
    Ordena los archivos .tif basado en la fecha extraída del nombre.
    Si no hay fecha, usa (0, 0) para no fallar.
    """
    def sort_key(x):
        my = extract_month_year(extract_date(x.name))
        return (my[0] or 0, my[1] or 0)
    return sorted(tif_files, key=sort_key)

def create_titled_image(data, title, is_ndvi=False):
    """
    Crea una imagen con título a partir de datos numpy.
    
    Parámetros:
    - data: Array numpy con los datos de la imagen
    - title: Título de la imagen
    - is_ndvi: Si es True, usa colormap RdYlGn y rango 0-1
    
    Retorna:
    - Objeto PIL.Image con la imagen generada
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Configurar visualización
    cmap = 'RdYlGn' if is_ndvi else None
    vmin = 0 if is_ndvi else None
    vmax = 1 if is_ndvi else None
    
    if is_ndvi:
        im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
    else:
        im = ax.imshow(data)
    
    # Configurar título y estilo
    ax.set_title(title, fontsize=12, pad=20)
    ax.axis('off')
    fig.tight_layout()
    
    # Convertir a imagen Pillow
    fig.canvas.draw()
    buf = fig.canvas.buffer_rgba()
    width, height = fig.canvas.get_width_height()
    img = Image.frombytes('RGBA', (width, height), buf).convert('RGB')
    
    plt.close(fig)
    return img

def create_polygon_gif(polygon_folder, duration=1000):
    """
    Crea un GIF timelapse para un polígono.
    
    Parámetros:
    - polygon_folder: Ruta a la carpeta del polígono
    - duration: Duración de cada frame en milisegundos
    
    Retorna:
    - Ruta al archivo GIF creado o None si hubo error
    """
    # Configurar rutas
    polygon_path = Path(polygon_folder)
    recortes_folder = polygon_path / "RECORTES"
    gif_folder = polygon_path / "GIF"
    gif_folder.mkdir(parents=True, exist_ok=True)
    output_gif = gif_folder / f"{polygon_path.name}_timelapse.gif"

    # Validar estructura
    if not recortes_folder.exists():
        raise FileNotFoundError(f"No existe carpeta RECORTES en {polygon_path}")
    
    # Obtener y ordenar archivos .tif por fecha
    tif_files = list(recortes_folder.glob("*.tif"))
    tif_files = sort_tif_files(tif_files)  # Ordenar por fecha
    
    if not tif_files:
        raise ValueError(f"No hay archivos TIFF en {recortes_folder}")

    # Procesar imágenes
    image_frames = []
    
    for idx, tif_path in enumerate(tif_files):
        try:
            ds = gdal.Open(str(tif_path))
            if ds is None:
                print(f"  ⚠️ No se pudo abrir {tif_path.name}, se omite.")
                continue
            nbands = ds.RasterCount
            date_tag = extract_date(tif_path.name) or "frame"
            title_base = date_tag.replace("_", "/") if "_" in str(date_tag) else date_tag

            # RGB: bandas 1,2,3 (B,G,R) o 3,2,1 para R,G,B
            if nbands >= 3:
                from skimage import exposure

                with rasterio.open(tif_path) as src:
                    rgb = np.dstack([src.read(3), src.read(2), src.read(1)])
                rgb = np.clip(rgb.astype(np.float32) / (np.nanpercentile(rgb, 98) + 1e-9), 0, 1)
                rgb_norm = exposure.equalize_adapthist(rgb, clip_limit=0.03)
                img_rgb = create_titled_image(rgb_norm, f"{title_base}\nRGB")
            else:
                # Una banda: NDVI (nombre NDVI_*) en [0,1] o escala de grises renormalizada
                b1 = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                if tif_path.name.upper().startswith("NDVI_"):
                    b1_disp = np.clip(np.nan_to_num(b1, nan=0.0), 0.0, 1.0)
                    img_rgb = create_titled_image(
                        b1_disp, f"{title_base}\nNDVI", is_ndvi=True
                    )
                else:
                    b1_norm = (b1 - np.nanmin(b1)) / (
                        np.nanmax(b1) - np.nanmin(b1) + 1e-9
                    )
                    img_rgb = create_titled_image(
                        np.stack([b1_norm] * 3, axis=-1), f"{title_base}\nRGB"
                    )

            # NDVI solo si hay al menos 4 bandas (asumir 3=Red, 4=NIR)
            if nbands >= 4:
                red = ds.GetRasterBand(3).ReadAsArray().astype(np.float32)
                nir = ds.GetRasterBand(4).ReadAsArray().astype(np.float32)
                ndvi = np.nan_to_num((nir - red) / (nir + red + 1e-9), nan=0.0)
                ndvi_norm = (ndvi - ndvi.min()) / (ndvi.max() - ndvi.min() + 1e-9)
                img_ndvi = create_titled_image(ndvi_norm, f"{title_base}\nNDVI", is_ndvi=True)
                combined = Image.new('RGB', (img_rgb.width + img_ndvi.width, img_rgb.height))
                combined.paste(img_rgb, (0, 0))
                combined.paste(img_ndvi, (img_rgb.width, 0))
            else:
                combined = img_rgb
            image_frames.append(combined)
            ds = None
        except Exception as e:
            print(f"  ⚠️ Error en {tif_path.name}: {str(e)}")
            continue

    # Guardar GIF
    if image_frames:
        image_frames[0].save(
            output_gif,
            save_all=True,
            append_images=image_frames[1:],
            duration=duration,
            loop=0,
            optimize=True,
            quality=85
        )
        return output_gif
    print(f"  ⚠️ No se generó ningún frame en {recortes_folder}. Comprueba que los TIF tengan al menos 1 banda (o 3 para RGB, 4 para RGB+NDVI).")
    return None

def process_all_polygons(root_folder, duration=1000):
    """
    Procesa todas las carpetas de polígonos dentro de un directorio raíz.
    
    Parámetros:
    - root_folder: Ruta contenedora de todas las carpetas de polígonos
    - duration: Duración de cada frame en milisegundos
    """
    root_path = Path(root_folder)
    
    if not root_path.exists():
        raise FileNotFoundError(f"El directorio raíz no existe: {root_folder}")
    
    processed = 0
    errors = 0
    
    for polygon_folder in sorted(root_path.iterdir()):
        if polygon_folder.is_dir() and not polygon_folder.name.startswith("."):
            try:
                print(f"\n{'='*50}")
                print(f"Procesando polígono: {polygon_folder.name}")
                
                # Crear GIF para el polígono
                gif_path = create_polygon_gif(polygon_folder, duration)
                
                if gif_path:
                    print(f"GIF generado con éxito: {gif_path}")
                    processed += 1
                else:
                    errors += 1
                    
            except Exception as e:
                print(f"Error procesando {polygon_folder.name}: {str(e)}")
                errors += 1
                continue

    print(f"\n{'='*50}")
    print(f"Proceso completado")
    print(f"Polígonos procesados: {processed}")
    print(f"Errores: {errors}")
    print(f"Total carpetas: {processed + errors}")
    
def main (root_folder: str, duration: int = 1000):
    process_all_polygons(root_folder, duration)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generar GIFs temporales para múltiples polígonos')
    parser.add_argument('--root_folder', type=str, help='Carpeta raíz conteniendo todas las carpetas de polígonos')
    parser.add_argument('--duration', type=int, default=1000, help='Duración por frame en milisegundos')
    args = parser.parse_args()
    
    if args.root_folder:
        main(args.root_folder, args.duration)
    else:
        print("Error: Se requiere --root_folder")
        print("Ejemplo: python 4_3_gif.py --root_folder /path/to/recortes")

        

