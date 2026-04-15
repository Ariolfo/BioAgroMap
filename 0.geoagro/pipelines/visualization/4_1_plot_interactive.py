import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from osgeo import gdal
import rasterio
from rasterio.plot import show
from matplotlib.gridspec import GridSpec
from mpl_toolkits.axes_grid1 import make_axes_locatable
from statsmodels.tsa.seasonal import seasonal_decompose
from skimage import exposure
import re
import warnings
warnings.filterwarnings('ignore')

def extract_date(file_name):
    """
    Extrae la fecha en formato 'MM_YYYY' del nombre del archivo.
    """
    match = re.search(r'\d{2}_\d{4}', str(file_name))
    return match.group(0) if match else None

def extract_month_year(date_str):
    """
    Extrae el año y el mes como enteros a partir de una cadena 'MM_YYYY'.
    """
    if date_str:
        month, year = date_str.split('_')
        return int(year), int(month)
    return None, None

def process_polygon_folder(polygon_folder, ndvi_band=15):
    """
    Procesa la carpeta de un polígono para visualizar y analizar los datos NDVI.
    
    Args:
        polygon_folder (str): Ruta a la carpeta del polígono
        ndvi_band (int): Índice de la banda NDVI a visualizar inicialmente (por defecto: 15)
    """
    # Convertir a Path object
    polygon_path = Path(polygon_folder)
    
    # Verificar estructura de carpetas
    recortes_folder = polygon_path / "RECORTES"
    stack_folder = polygon_path / "STACK"
    
    if not recortes_folder.exists():
        raise ValueError(f"No existe la carpeta RECORTES en {polygon_path}")
        
    # Obtener lista de archivos TIFF ordenados
    tif_files = sorted(recortes_folder.glob("*.tif"))
    sorted(tif_files, key=lambda x: extract_month_year(extract_date(x.name)))
    if not tif_files:
        raise ValueError(f"No se encontraron archivos TIFF en {recortes_folder}")

    # Cargar o crear stack NDVI
    stack_file = stack_folder / "stack_ndvi.tif"
    
    if not stack_file.exists():
        raise ValueError(f"No se encontró el stack en {stack_folder}")
        
    # Cargar stack desde archivo
    ds = gdal.Open(str(stack_file))
    bands = ds.RasterCount
    
    # Verificar que el índice de banda sea válido
    if ndvi_band >= bands:
        print(f"Advertencia: El índice de banda {ndvi_band} es mayor que el número de bandas disponibles ({bands})")
        print(f"Usando la última banda disponible ({bands-1})")
        ndvi_band = bands - 1
    
    ndvi_stack = np.dstack([ds.GetRasterBand(i+1).ReadAsArray() for i in range(bands)])
    ds = None

    # Cargar imagen RGB (usando el primer archivo TIFF)
    def load_rgb(path):
        with rasterio.open(path) as src:
            return np.dstack([src.read(3), src.read(2), src.read(1)])  
    
    rgb_image = load_rgb(tif_files[0])
    
    # Mejorar contraste RGB
    def enhance_rgb(img):
        return exposure.equalize_adapthist(img, clip_limit=0.03)
    
    enhanced_rgb = enhance_rgb(rgb_image)

    # Configurar figura
    fig = plt.figure(figsize=(16, 13))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[3, 1, 1, 1])
    axs = [
        fig.add_subplot(gs[0, 0]),  
        fig.add_subplot(gs[0, 1]),  
        fig.add_subplot(gs[1, :]),  
        fig.add_subplot(gs[2, 0]), 
        fig.add_subplot(gs[2, 1]), 
        fig.add_subplot(gs[3, 0]),  
        fig.add_subplot(gs[3, 1])   
    ]

    # Mostrar imágenes iniciales - usando la banda especificada
    im = axs[0].imshow(ndvi_stack[:, :, ndvi_band], cmap="RdYlGn", vmin=0, vmax=1)
    axs[0].set_title(f'NDVI (Banda {ndvi_band}) - Click para ver perfiles')
    divider = make_axes_locatable(axs[0])
    cax = divider.append_axes("right", size="5%", pad=0.05)
    fig.colorbar(im, cax=cax)
    
    axs[1].imshow(enhanced_rgb)
    axs[1].set_title('RGB Mejorado')

    # Función de actualización con descomposición
    def update_plots(row, col):
        profile = ndvi_stack[row, col, :]
        time_points = np.arange(len(tif_files))
        
        try:
            decomposition = seasonal_decompose(
                profile, 
                period=max(2, len(tif_files)//2), 
                model='additive'
            )
        except ValueError as e:
            print(f"Error en descomposición: {e}")
            return

        # Limpiar ejes
        for ax in axs[2:]:
            ax.clear()
        
        # Actualizar plots
        axs[2].plot(time_points, profile, 'b-', label='Perfil')
        axs[2].plot(time_points, decomposition.trend, 'r-', label='Tendencia')
        axs[2].plot(time_points, decomposition.seasonal, 'g-', label='Estacional')
        axs[2].plot(time_points, decomposition.resid, 'm--', label='Residual')
        axs[2].set_title('Componentes Combinados')
        axs[2].legend()
        axs[2].grid(True)
        
        axs[3].plot(time_points, profile, 'bo-')
        axs[3].set_title('Perfil Temporal NDVI')
        axs[3].grid(True)
        
        axs[4].plot(time_points, decomposition.trend, 'ro-')
        axs[4].set_title('Tendencia')
        axs[4].grid(True)
        
        axs[5].plot(time_points, decomposition.seasonal, 'go-')
        axs[5].set_title('Estacionalidad')
        axs[5].grid(True)
        
        axs[6].plot(time_points, decomposition.resid, 'mo-')
        axs[6].set_title('Residuales')
        axs[6].grid(True)
        
        plt.tight_layout()
        fig.canvas.draw_idle()

    # Manejador de clicks
    def on_click(event):
        if event.inaxes == axs[0]:
            x, y = int(event.xdata), int(event.ydata)
            if 0 <= x < ndvi_stack.shape[1] and 0 <= y < ndvi_stack.shape[0]:
                update_plots(y, x)
                fig.suptitle(f'Perfil en posición ({x}, {y})', y=0.98)

    fig.canvas.mpl_connect('button_press_event', on_click)
    plt.tight_layout()
    plt.show()

def process_polygon_folder_save(polygon_folder, output_folder, ndvi_band=15):
    """
    Versión que guarda el gráfico en lugar de mostrarlo.
    """
    import matplotlib
    matplotlib.use('Agg')
    
    polygon_path = Path(polygon_folder)
    recortes_folder = polygon_path / "RECORTES"
    stack_folder = polygon_path / "STACK"
    
    if not recortes_folder.exists():
        raise ValueError(f"No existe la carpeta RECORTES en {polygon_path}")
    
    tif_files = sorted(recortes_folder.glob("*.tif"))
    sorted(tif_files, key=lambda x: extract_month_year(extract_date(x.name)))
    if not tif_files:
        raise ValueError(f"No se encontraron archivos TIFF en {recortes_folder}")
    
    stack_file = stack_folder / "stack_ndvi.tif"
    if not stack_file.exists():
        raise ValueError(f"No se encontró el stack en {stack_folder}")
    
    ds = gdal.Open(str(stack_file))
    bands = ds.RasterCount
    if ndvi_band >= bands:
        ndvi_band = bands - 1
    
    ndvi_stack = np.dstack([ds.GetRasterBand(i+1).ReadAsArray() for i in range(bands)])
    ds = None
    
    def load_rgb(path):
        with rasterio.open(path) as src:
            return np.dstack([src.read(3), src.read(2), src.read(1)])
    
    rgb_image = load_rgb(tif_files[0])
    enhanced_rgb = exposure.equalize_adapthist(rgb_image, clip_limit=0.03)
    
    fig = plt.figure(figsize=(16, 13))
    gs = GridSpec(4, 2, figure=fig, height_ratios=[3, 1, 1, 1])
    axs = [
        fig.add_subplot(gs[0, 0]),
        fig.add_subplot(gs[0, 1]),
        fig.add_subplot(gs[1, :]),
        fig.add_subplot(gs[2, 0]),
        fig.add_subplot(gs[2, 1]),
        fig.add_subplot(gs[3, 0]),
        fig.add_subplot(gs[3, 1])
    ]
    
    im = axs[0].imshow(ndvi_stack[:, :, ndvi_band], cmap="RdYlGn", vmin=0, vmax=1)
    axs[0].set_title(f'NDVI (Banda {ndvi_band})')
    divider = make_axes_locatable(axs[0])
    cax = divider.append_axes("right", size="5%", pad=0.05)
    fig.colorbar(im, cax=cax)
    
    axs[1].imshow(enhanced_rgb)
    axs[1].set_title('RGB Mejorado')
    
    # Calcular perfil medio
    mean_profile = ndvi_stack.mean(axis=(0, 1))
    time_points = np.arange(len(tif_files))
    
    try:
        decomposition = seasonal_decompose(mean_profile, period=max(2, len(tif_files)//2), model='additive')
    except ValueError:
        decomposition = None
    
    if decomposition:
        axs[2].plot(time_points, mean_profile, 'b-', label='Perfil Medio')
        axs[2].plot(time_points, decomposition.trend, 'r-', label='Tendencia')
        axs[2].plot(time_points, decomposition.seasonal, 'g-', label='Estacional')
        axs[2].plot(time_points, decomposition.resid, 'm--', label='Residual')
        axs[2].set_title('Componentes Combinados (Media)')
        axs[2].legend()
        axs[2].grid(True)
        
        axs[3].plot(time_points, mean_profile, 'bo-')
        axs[3].set_title('Perfil Temporal NDVI (Media)')
        axs[3].grid(True)
        
        axs[4].plot(time_points, decomposition.trend, 'ro-')
        axs[4].set_title('Tendencia')
        axs[4].grid(True)
        
        axs[5].plot(time_points, decomposition.seasonal, 'go-')
        axs[5].set_title('Estacionalidad')
        axs[5].grid(True)
        
        axs[6].plot(time_points, decomposition.resid, 'mo-')
        axs[6].set_title('Residuales')
        axs[6].grid(True)
    
    plt.tight_layout()
    
    # Guardar
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / f"interactive_{polygon_path.name}.png"
    fig.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ Gráfico guardado: {output_file}")

def main(root_folder: str, output_folder: str = None, ndvi_band: int = 0):
    """
    Función principal para procesar todos los polígonos en root_folder.
    
    Args:
        root_folder: Carpeta raíz que contiene subcarpetas de polígonos
        output_folder: Carpeta donde guardar resultados (si se proporciona, guarda gráficos)
        ndvi_band: Índice de banda NDVI a visualizar inicialmente
    """
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
            if output_folder:
                process_polygon_folder_save(str(polygon_folder), output_folder, ndvi_band=ndvi_band)
            else:
                process_polygon_folder(str(polygon_folder), ndvi_band=ndvi_band)
            print(f"✅ Polígono {polygon_folder.name} procesado exitosamente")
        except Exception as e:
            print(f"❌ Error procesando polígono {polygon_folder.name}: {str(e)}")
            continue

if __name__ == "__main__":
    # Ejemplo de uso (solo para pruebas)
    polygon_folder = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/464_moniquira/1687.0"
    if Path(polygon_folder).exists():
        process_polygon_folder(polygon_folder, ndvi_band=0)
    else:
        print("⚠️ Carpeta no encontrada. Ejecuta desde la aplicación Streamlit con parámetros correctos.")