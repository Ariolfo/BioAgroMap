import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import re

def extract_date_from_tif(file_name):
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

def get_band_dates(polygon_id, base_dir):
    """
    Obtiene las fechas correspondientes a cada banda del stack NDVI a partir de 
    los archivos en la carpeta RECORTES.
    
    Parámetros:
    polygon_id: ID del polígono
    base_dir: Directorio base donde se encuentran las carpetas de los polígonos
    
    Retorna:
    list: Lista de fechas ordenadas correspondientes a cada banda
    """
    # Construir la ruta a la carpeta RECORTES
    recortes_path = os.path.join(base_dir, str(polygon_id), "RECORTES")
    
    # Verificar si existe la carpeta
    if not os.path.exists(recortes_path):
        print(f"No se encontró la carpeta RECORTES para el polígono {polygon_id}")
        return None
    
    # Obtener todos los archivos .tif en la carpeta RECORTES
    tif_files = list(Path(recortes_path).glob("*.tif"))
    
    # Extraer fechas y ordenar los archivos por fecha
    dates = [extract_date_from_tif(tif.name) for tif in tif_files]
    paired_list = [(tif, date) for tif, date in zip(tif_files, dates) if date is not None]
    sorted_pairs = sorted(paired_list, key=lambda x: extract_month_year(x[1]))
    
    # Extraer las fechas ordenadas
    sorted_dates = [date for _, date in sorted_pairs]
    
    return sorted_dates

def plot_ndvi_timeseries_from_csv(csv_path, polygon_id=None, base_dir=None, sample_size=None, 
                                include_mean=True, include_std=True, output_folder: str = None):
    """
    Genera gráficos de líneas de tiempo de NDVI para uno o todos los polígonos a partir del CSV.
    
    Parámetros:
    csv_path: Ruta al archivo CSV con los datos vectorizados
    polygon_id: ID del polígono para el cual generar las líneas de tiempo (si None, grafica todos)
    base_dir: Directorio base para buscar las fechas de las bandas (opcional)
    sample_size: Número de píxeles a mostrar (si None, muestra todos los píxeles)
    include_mean: Si se debe incluir la línea de tiempo media
    include_std: Si se debe incluir la desviación estándar
    
    Retorna:
    None
    """
    # Cargar los datos del CSV
    try:
        df = pd.read_csv(csv_path)
        print(f"📄 CSV cargado: {len(df)} filas, {len(df.columns)} columnas")
    except Exception as e:
        print(f"❌ Error al cargar el archivo CSV: {e}")
        return
    
    # Verificar que existe la columna polygon_fid
    if 'polygon_fid' not in df.columns:
        print("❌ No se encontró la columna 'polygon_fid' en el CSV")
        print(f"Columnas disponibles: {list(df.columns[:10])}")
        return
    
    # Manejar caso donde polygon_fid está vacío o es NaN
    if df['polygon_fid'].isna().all() or df['polygon_fid'].isna().sum() == len(df):
        print("⚠️ La columna 'polygon_fid' está vacía. Intentando inferir desde base_dir...")
        # Asignar un ID por defecto o intentar inferirlo de otra manera
        # Si hay base_dir, intentar obtener IDs de las carpetas
        assigned_id = None
        if base_dir:
            base_path = Path(base_dir)
            if base_path.exists():
                folder_ids = []
                for folder in base_path.iterdir():
                    if folder.is_dir():
                        try:
                            folder_id = float(folder.name)
                            folder_ids.append(folder_id)
                        except (ValueError, TypeError):
                            # Si el nombre es "nan" o similar, intentar usar el índice
                            continue
                
                # También buscar carpetas con nombres no numéricos pero que contengan stacks
                if not folder_ids:
                    counter = 1
                    for folder in base_path.iterdir():
                        if folder.is_dir():
                            stack_path = folder / "STACK" / "stack_ndvi.tif"
                            if stack_path.exists():
                                # Usar un contador como ID
                                folder_ids.append(counter)
                                print(f"  📁 Encontrada carpeta con stack: {folder.name} (asignado ID: {counter})")
                                counter += 1
                
                if folder_ids:
                    print(f"📁 Polígonos encontrados en base_dir: {folder_ids}")
                    # Usar el primer ID encontrado para todos los datos
                    assigned_id = folder_ids[0]
                else:
                    assigned_id = 1  # ID por defecto
            else:
                assigned_id = 1  # ID por defecto
        else:
            assigned_id = 1  # ID por defecto
        
        df['polygon_fid'] = assigned_id
        print(f"✅ Asignado polygon_fid = {assigned_id} a todas las filas ({len(df)} filas)")
    
    # Limpiar polygon_fid: eliminar NaN y convertir a numérico
    df = df.dropna(subset=['polygon_fid'])
    df['polygon_fid'] = pd.to_numeric(df['polygon_fid'], errors='coerce')
    df = df.dropna(subset=['polygon_fid'])
    
    if len(df) == 0:
        print("❌ No hay datos válidos después de limpiar polygon_fid")
        return
    
    # Obtener todos los polygon_id únicos si no se especifica uno
    if polygon_id is None:
        polygon_ids = sorted(df['polygon_fid'].unique())
        print(f"📊 Polígonos encontrados: {polygon_ids}")
    else:
        polygon_ids = [polygon_id]
    
    if len(polygon_ids) == 0:
        print("❌ No se encontraron polígonos en el CSV")
        return
    
    # Identificar columnas de bandas del DataFrame completo
    all_band_columns = [col for col in df.columns if col.startswith('band_')]
    if not all_band_columns:
        print("❌ No se encontraron columnas de banda en el CSV")
        print(f"Columnas disponibles: {list(df.columns)}")
        return
    
    # Ordenar columnas de bandas numéricamente
    all_band_columns = sorted(all_band_columns, key=lambda x: int(x.split('_')[1]) if x.split('_')[1].isdigit() else 0)
    num_bands = len(all_band_columns)
    print(f"📊 Detectadas {num_bands} bandas temporales: {all_band_columns[:5]}...{all_band_columns[-2:]}")
    
    # Crear una sola figura para todos los polígonos
    plt.figure(figsize=(14, 8))
    colors = plt.cm.tab10.colors  # Usar una paleta de colores para distinguir polígonos
    
    # Obtener fechas base (usar el primer polígono como referencia)
    dates = None
    if base_dir and len(polygon_ids) > 0:
        dates = get_band_dates(polygon_ids[0], base_dir)
    
    # Si no hay fechas, usar índices numéricos
    if not dates or len(dates) != num_bands:
        print(f"Usando índices numéricos para las fechas.")
        dates = [f"Time {i+1}" for i in range(num_bands)]
    
    # Contador de píxeles graficados
    total_pixels_plotted = 0
    
    # Iterar sobre cada polygon_id
    for idx, pid in enumerate(polygon_ids):
        # Filtrar por polígono específico
        polygon_df = df[df['polygon_fid'] == pid].copy()

        if len(polygon_df) == 0:
            print(f"⚠️ No se encontraron datos para el polígono {pid} en el CSV")
            continue
        
        print(f"📊 Polígono {pid}: {len(polygon_df)} píxeles")
        
        # Identificar columnas de bandas (deberían ser las mismas para todos)
        band_columns = sorted([col for col in polygon_df.columns if col.startswith('band_')], 
                              key=lambda x: int(x.split('_')[1]) if x.split('_')[1].isdigit() else 0)
        
        if len(band_columns) != num_bands:
            print(f"⚠️ Polígono {pid} tiene {len(band_columns)} bandas, esperadas {num_bands}")
            continue
        
        # Eliminar filas con valores NaN en las bandas
        polygon_df = polygon_df.dropna(subset=band_columns)
        
        if len(polygon_df) == 0:
            print(f"⚠️ Polígono {pid}: No hay datos válidos después de eliminar NaN")
            continue
        
        # Muestrear píxeles si se especifica sample_size
        if sample_size and sample_size < len(polygon_df):
            sampled_df = polygon_df.sample(n=sample_size, random_state=42)
            print(f"  → Muestreando {sample_size} de {len(polygon_df)} píxeles")
        else:
            sampled_df = polygon_df
        
        # Graficar cada píxel como una línea de tiempo
        pixels_plotted = 0
        for _, row in sampled_df.iterrows():
            try:
                values = [float(row[band]) for band in band_columns]
                # Verificar que los valores sean válidos
                if any(pd.isna(v) or pd.isinf(v) for v in values):
                    continue
                plt.plot(range(num_bands), values, color=colors[idx % len(colors)], alpha=0.3, linewidth=0.5)
                pixels_plotted += 1
            except Exception as e:
                print(f"  ⚠️ Error graficando píxel: {e}")
                continue
        
        total_pixels_plotted += pixels_plotted
        print(f"  ✅ {pixels_plotted} píxeles graficados para polígono {pid}")
        
        # Calcular y graficar la media y desviación estándar si se solicita
        if include_mean or include_std:
            mean_values = [polygon_df[band].mean() for band in band_columns]
            
            if include_mean:
                plt.plot(range(num_bands), mean_values, color=colors[idx % len(colors)], linewidth=2, label=f'Media Polígono {pid}')
            
            if include_std:
                std_values = [polygon_df[band].std() for band in band_columns]
                plt.fill_between(
                    range(num_bands),
                    [m - s for m, s in zip(mean_values, std_values)],
                    [m + s for m, s in zip(mean_values, std_values)],
                    color=colors[idx % len(colors)], alpha=0.2, label=f'Desv. Est. Polígono {pid}'
                )
    
    print(f"📊 Total de píxeles graficados: {total_pixels_plotted}")
    
    if total_pixels_plotted == 0:
        print("⚠️ No se graficaron píxeles. Verifica que el CSV tenga datos válidos.")

    
    # Configurar el gráfico
    plt.title('Evolución temporal del NDVI para todos los polígonos' if polygon_id is None else f'Evolución temporal del NDVI para el polígono {polygon_id}')
    plt.ylabel('NDVI')
    plt.xlabel('Temporalidad')
    plt.ylim(-0.05, 1.05)  # NDVI generalmente está entre -1 y 1
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Configurar las etiquetas del eje X
    plt.xticks(range(num_bands), dates, rotation=45, ha='right')
    
    # Añadir leyenda si corresponde
    if include_mean or include_std:
        plt.legend()

    """ if polygon_id is None:
        count_text = f"Total de firmas {len(df)}"
    else:
        count_text = f"Firmas (Poligono {polygon_id}: {len(df[df['polygon_fid'] == polygon_id])})" """
    
    #plt.text(0.95, 0.95, f"Firmas: {count_text}", fontsize=12, color='white', fontweight="bold", bbox=dict(facecolor="darkblue", alpha=0.6, edgecolor='none', boxstyle='round'), transform=plt.gca().transAxes, ha='right', va='top')

    # Ajustar la disposición
    plt.tight_layout()
    
    # Guardar o mostrar la figura
    if output_folder:
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        if polygon_id is None:
            output_file = output_path / "all_series.png"
        else:
            output_file = output_path / f"series_{polygon_id}.png"
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Gráfico guardado: {output_file}")
    else:
        plt.show()

def main(csv_path: str, output_folder: str = None, base_dir: str = None, 
         polygon_id=None, sample_size: int = 100, include_mean: bool = True, 
         include_std: bool = True):
    """
    Función principal para generar gráficos de todas las series temporales desde CSV.
    
    Args:
        csv_path: Ruta al CSV con datos vectorizados
        output_folder: Carpeta donde guardar gráficos
        base_dir: Directorio base para buscar fechas de bandas
        polygon_id: ID del polígono (None = todos)
        sample_size: Número de píxeles a mostrar
        include_mean: Incluir línea de tiempo media
        include_std: Incluir desviación estándar
    """
    import matplotlib
    matplotlib.use('Agg')  # Usar backend no interactivo
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"El archivo CSV no existe: {csv_path}")
    
    print(f"📊 Procesando CSV: {csv_path}")
    
    plot_ndvi_timeseries_from_csv(
        csv_path=csv_path,
        polygon_id=polygon_id,
        base_dir=base_dir,
        sample_size=sample_size,
        include_mean=include_mean,
        include_std=include_std,
        output_folder=output_folder
    )
    
    print(f"✅ Proceso completado")

if __name__ == "__main__":
    # Ejemplo de uso (solo para pruebas)
    csv_path = "/home/agrosavia/Documents/Geo_Agro/8.CSV_ALL/Fpapa_Toca/ndvi/serie/CSV_ALL.csv"
    base_dir = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/Fpapa_Toca"
    polygon_id = None
    
    if Path(csv_path).exists():
        plot_ndvi_timeseries_from_csv(
            csv_path=csv_path,
            polygon_id=polygon_id,
            base_dir=base_dir,
            sample_size=100
        )
    else:
        print("⚠️ Archivo no encontrado. Ejecuta desde la aplicación Streamlit con parámetros correctos.")