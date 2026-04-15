import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from osgeo import gdal
import rasterio
from matplotlib.gridspec import GridSpec
from mpl_toolkits.axes_grid1 import make_axes_locatable
from statsmodels.tsa.seasonal import seasonal_decompose
from skimage import exposure
import re
import warnings
warnings.filterwarnings('ignore')

# Función para extraer la fecha del nombre del archivo
def extract_date(file_name):
    match = re.search(r'\d{2}_\d{4}', str(file_name))
    return match.group(0) if match else None

# Función para extraer el mes y el año como enteros
def extract_month_year(date_str):
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None

def calculate_mean_time_series(stacked_array):
    """
    Calcula la serie temporal media de un stack de imágenes.
    """
    return np.mean(stacked_array, axis=(0, 1))

def plot_mean_time_series_decomposition(normalized_array, stacked_array, rgb_image, axs, tif_files_sorted):
    """
    Grafica la descomposición estacional de la serie temporal media.
    """
    mean_time_series = calculate_mean_time_series(stacked_array)
    bands = np.arange(1, len(mean_time_series) + 1)

    # Ajustar el periodo según el número de bandas
    period = max(2, len(bands) // 2)

    try:
        result = seasonal_decompose(mean_time_series, period=period, model='additive', extrapolate_trend='freq')
    except ValueError as e:
        print(f"Error in seasonal decomposition: {e}")
        return

    # Usamos tif_files_sorted para las etiquetas
    labels = [tif_file.stem for tif_file in tif_files_sorted]

    # Gráfico de la imagen original
    axs[0].clear()
    axs[0].imshow(normalized_array[:, :, 0], cmap="RdYlGn")
    axs[0].set_title('Original Image')

    # Gráfico de la imagen RGB
    axs[1].clear()
    axs[1].imshow(rgb_image)
    axs[1].set_title('RGB Image')

    # Gráfico de la serie temporal media y sus componentes
    axs[2].plot(bands, mean_time_series, marker='o', label='Mean Time Series')
    axs[2].plot(bands, result.trend, color='red', label='Trend')
    axs[2].plot(bands, result.seasonal, color='green', label='Seasonal')
    axs[2].plot(bands, result.resid, color='blue', linestyle='--', label='Residual')
    axs[2].set_title('All Components')
    axs[2].set_ylabel('Value')
    axs[2].legend()
    axs[2].grid(True)
    axs[2].set_xticks(bands)
    axs[2].set_xticklabels(labels, rotation=90, ha='right')

    # Gráfico de la serie temporal media
    axs[3].plot(bands, mean_time_series, marker='o', label='Mean Time Series')
    axs[3].set_title('Mean Time Series')
    axs[3].set_ylabel('Value')
    axs[3].legend()
    axs[3].grid(True)
    axs[3].set_xticks(bands)
    axs[3].set_xticklabels(labels, rotation=90, ha='right')
    axs[3].set_ylim(-0.02, 1)

    # Gráfico de la tendencia
    axs[4].plot(bands, result.trend, color='red', label='Trend')
    axs[4].set_title('Trend')
    axs[4].set_ylabel('Value')
    axs[4].legend()
    axs[4].grid(True)
    axs[4].set_xticks(bands)
    axs[4].set_xticklabels(labels, rotation=90, ha='right')

    # Gráfico de la estacionalidad
    axs[5].plot(bands, result.seasonal, color='green', label='Seasonal')
    axs[5].set_title('Seasonal')
    axs[5].set_ylabel('Value')
    axs[5].legend()
    axs[5].grid(True)
    axs[5].set_xticks(bands)
    axs[5].set_xticklabels(labels, rotation=90, ha='right')

    # Gráfico de los residuales
    axs[6].plot(bands, result.resid, color='blue', linestyle='--', label='Residual')
    axs[6].set_title('Residual')
    axs[6].set_ylabel('Value')
    axs[6].legend()
    axs[6].grid(True)
    axs[6].set_xticks(bands)
    axs[6].set_xticklabels(labels, rotation=90, ha='right')

def process_polygon_folder(polygon_folder, output_folder=None):
    """
    Procesa una carpeta de polígono con imágenes recortadas y genera visualización de la serie temporal media.
    
    Parámetros:
    - polygon_folder: Ruta a la carpeta del polígono (debe contener subcarpeta RECORTES)
    """
    # Convertir a Path object
    polygon_path = Path(polygon_folder)
    
    # Verificar estructura de carpetas
    recortes_folder = polygon_path / "RECORTES"
    stack_folder = polygon_path / "STACK"
    
    if not recortes_folder.exists():
        raise ValueError(f"No existe la carpeta RECORTES en {polygon_path}")
        
    # Obtener lista de archivos TIFF y ordenarlos por fecha
    tif_files = list(recortes_folder.glob("*.tif"))
    tif_files_sorted = sorted(tif_files, key=lambda x: extract_month_year(extract_date(x)))
    
    if not tif_files_sorted:
        raise ValueError(f"No se encontraron archivos TIFF en {recortes_folder}")

    # Cargar o crear stack NDVI
    stack_file = stack_folder / "stack_ndvi.tif"
    
    if not stack_file.exists():
        # Función para calcular NDVI
        def calculate_ndvi(nir_band, red_band):
            with np.errstate(divide='ignore', invalid='ignore'):
                ndvi = (nir_band - red_band) / (nir_band + red_band)
                return np.nan_to_num(ndvi, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Procesar archivos para crear stack
        ndvi_stack = []
        for tif_file in tif_files_sorted:
            ds = gdal.Open(str(tif_file))
            red = ds.GetRasterBand(3).ReadAsArray()
            nir = ds.GetRasterBand(4).ReadAsArray() 
            ndvi_stack.append(calculate_ndvi(nir, red))
            ds = None
        
        # Crear y guardar stack
        stacked_array = np.dstack(ndvi_stack)
        driver = gdal.GetDriverByName('GTiff')
        ds = driver.Create(str(stack_file), 
                         stacked_array.shape[1], 
                         stacked_array.shape[0],
                         stacked_array.shape[2], 
                         gdal.GDT_Float32)
        
        for i in range(stacked_array.shape[2]):
            ds.GetRasterBand(i+1).WriteArray(stacked_array[:, :, i])
        ds = None
        print(f"Stack creado: {stack_file}")
    
    # Cargar stack desde archivo
    ds = gdal.Open(str(stack_file))
    bands = ds.RasterCount
    ndvi_stack = np.dstack([ds.GetRasterBand(i+1).ReadAsArray() for i in range(bands)])
    ds = None

    # Cargar imagen RGB (usando el primer archivo TIFF)
    def load_rgb(path):
        with rasterio.open(path) as src:
            return np.dstack([src.read(3), src.read(2), src.read(1)])  # RGB
    
    rgb_image = load_rgb(tif_files_sorted[0])
    
    # Mejorar contraste RGB
    def enhance_rgb(img):
        return exposure.equalize_adapthist(img, clip_limit=0.03)
    
    enhanced_rgb = enhance_rgb(rgb_image)

    # Configurar figura
    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[3, 1, 1, 1])

    # Configuración de subplots
    ax_image = fig.add_subplot(gs[0, 0])
    ax_rgb = fig.add_subplot(gs[0, 1])
    ax_combined = fig.add_subplot(gs[1, :])
    ax_profile = fig.add_subplot(gs[2, 0])
    ax_trend = fig.add_subplot(gs[2, 1])
    ax_seasonal = fig.add_subplot(gs[3, 0])
    ax_residual = fig.add_subplot(gs[3, 1])

    # Lista plana de los ejes para manejarlos más fácilmente en las funciones
    axs = [ax_image, ax_rgb, ax_combined, ax_profile, ax_trend, ax_seasonal, ax_residual]

    # Mostrar imágenes iniciales
    im = ax_image.imshow(ndvi_stack[:, :, 10], cmap="RdYlGn")
    ax_image.set_title('Click a pixel to view its profile')

    # Crear espacio para la colorbar
    divider = make_axes_locatable(ax_image)
    cax = divider.append_axes("right", size="5%", pad=0.05)

    # Agregar la colorbar al subplot
    colorbar = fig.colorbar(im, cax=cax)

    ax_rgb.imshow(enhanced_rgb)
    ax_rgb.set_title('RGB Image')

    # Graficar la descomposición de la serie temporal media
    plot_mean_time_series_decomposition(ndvi_stack, ndvi_stack, enhanced_rgb, axs, tif_files_sorted)

    plt.tight_layout(pad=3.5)
    
    if output_folder:
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / f"properties_{polygon_path.name}.png"
        fig.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"✅ Gráfico guardado: {output_file}")
    else:
        plt.show()
        plt.close(fig)

def main(root_folder: str, output_folder: str = None):
    """
    Función principal para procesar todos los polígonos en root_folder.
    
    Args:
        root_folder: Carpeta raíz que contiene subcarpetas de polígonos
        output_folder: Carpeta donde guardar resultados (si se proporciona, guarda gráficos)
    """
    import matplotlib
    if output_folder:
        matplotlib.use('Agg')
    
    root_path = Path(root_folder)
    if not root_path.exists():
        raise FileNotFoundError(f"La carpeta raíz no existe: {root_folder}")
    
    polygon_folders = [d for d in root_path.iterdir() if d.is_dir()]
    
    if not polygon_folders:
        raise ValueError(f"No se encontraron carpetas de polígonos en {root_folder}")
    
    print(f"📁 Procesando {len(polygon_folders)} polígono(s) en {root_folder}")
    
    for polygon_folder in polygon_folders:
        try:
            print(f"🔄 Procesando polígono: {polygon_folder.name}")
            process_polygon_folder(str(polygon_folder), output_folder)
            print(f"✅ Polígono {polygon_folder.name} procesado exitosamente")
        except Exception as e:
            print(f"❌ Error procesando polígono {polygon_folder.name}: {str(e)}")
            continue

if __name__ == "__main__":
    # Ejemplo de uso (solo para pruebas)
    polygon_folder = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/nadia_sub_villap/RECORTES/1.0"
    if Path(polygon_folder).exists():
        process_polygon_folder(polygon_folder)
    else:
        print("⚠️ Carpeta no encontrada. Ejecuta desde la aplicación Streamlit con parámetros correctos.")