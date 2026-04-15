import os
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
        print(f"{recortes_path}")
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


def _parse_temporal_sequence(values: Sequence[str], fmt: str = "%m_%Y") -> List[pd.Timestamp]:
    parsed = []
    for val in values:
        if val is None:
            return []
        try:
            parsed.append(pd.to_datetime(val, format=fmt))
        except Exception:
            try:
                parsed.append(pd.to_datetime(val))
            except Exception:
                return []
    return parsed


def build_time_axis(num_bands: int,
                    default_dates: Iterable[str],
                    mode: str = "dates",
                    custom_timeline: Optional[Sequence] = None,
                    reference_date: Optional[str] = None,
                    timeline_unit: Optional[str] = None) -> Tuple[List[float], List[str], str]:
    """
    Genera las coordenadas numéricas del eje X, sus etiquetas visibles y el texto del eje.
    """
    default_dates = list(default_dates)
    fallback_positions = list(range(num_bands))
    fallback_labels = [f"Banda {i + 1}" for i in range(num_bands)]

    mode = (mode or "dates").lower()
    timeline_unit = timeline_unit or ""

    if custom_timeline is not None:
        timeline_list = [
            custom_timeline[i] if i < len(custom_timeline) else fallback_labels[i]
            for i in range(num_bands)
        ]
    else:
        timeline_list = default_dates if all(default_dates) else fallback_labels

    def _format_numeric(values: Sequence[float]) -> List[str]:
        formatted = []
        for val in values:
            formatted.append(str(int(val)) if float(val).is_integer() else f"{val:.2f}")
        return formatted

    def _coerce_numeric(seq: Sequence) -> Optional[List[float]]:
        result = []
        for val in seq:
            try:
                result.append(float(val))
            except Exception:
                return None
        return result

    numeric_from_timeline = _coerce_numeric(timeline_list)
    parsed_dates = _parse_temporal_sequence(default_dates)

    def _ensure_length(values: Sequence[float]) -> List[float]:
        vals = list(values)
        if len(vals) != num_bands:
            return fallback_positions
        return vals

    if mode in {"bands", "band"}:
        return fallback_positions, fallback_labels, "Bandas"

    if mode in {"dates", "date"}:
        labels = [str(label).replace("_", "-") for label in timeline_list]
        return fallback_positions, labels, "Fecha"

    if mode in {"days", "day"}:
        if numeric_from_timeline is not None:
            values = _ensure_length(numeric_from_timeline)
        elif parsed_dates:
            ref = pd.to_datetime(reference_date) if reference_date else parsed_dates[0]
            values = _ensure_length([(dt - ref).days for dt in parsed_dates])
        else:
            values = fallback_positions
        labels = _format_numeric(values)
        axis_label = timeline_unit or "Días"
        return values, labels, axis_label

    if mode in {"hours", "hour"}:
        if numeric_from_timeline is not None:
            values = _ensure_length(numeric_from_timeline)
        elif parsed_dates:
            ref = pd.to_datetime(reference_date) if reference_date else parsed_dates[0]
            values = _ensure_length([(dt - ref).total_seconds() / 3600 for dt in parsed_dates])
        else:
            values = fallback_positions
        labels = _format_numeric(values)
        axis_label = timeline_unit or "Horas"
        return values, labels, axis_label

    if mode in {"months", "month"}:
        if numeric_from_timeline is not None:
            values = _ensure_length(numeric_from_timeline)
        elif parsed_dates:
            ref = pd.to_datetime(reference_date) if reference_date else parsed_dates[0]
            values = _ensure_length([(dt.year - ref.year) * 12 + (dt.month - ref.month) for dt in parsed_dates])
        else:
            values = fallback_positions
        labels = _format_numeric(values)
        axis_label = timeline_unit or "Meses"
        return values, labels, axis_label

    # Por defecto usamos índices
    labels = [str(label).replace("_", "-") for label in timeline_list]
    axis_label = timeline_unit or "Índice temporal"
    return fallback_positions, labels, axis_label

def plot_ndvi_timeseries_from_csv(
        csv_path,
        polygon_id=None,
        base_dir=None,
        sample_size=None,
        include_mean=True,
        include_std=True,
        x_axis_mode: str = "dates",
        custom_timeline: Optional[Sequence] = None,
        reference_date: Optional[str] = None,
        timeline_unit: Optional[str] = None,
        day_axis_limit: Optional[float] = None,
        day_reference_points: Optional[Sequence[float]] = None,
        output_folder: str = None):
    """
    Genera gráficos de líneas de tiempo de NDVI para un polígono específico a partir del CSV.

    Parámetros:
    csv_path: Ruta al archivo CSV con los datos vectorizados
    polygon_id: ID del polígono para el cual generar las líneas de tiempo
    base_dir: Directorio base para buscar las fechas de las bandas (opcional)
    sample_size: Número de píxeles a mostrar (si None, muestra todos los píxeles)
    include_mean: Si se debe incluir la línea de tiempo media
    include_std: Si se debe incluir la desviación estándar
    x_axis_mode: 'dates', 'bands', 'days', 'hours' u 'months'; define cómo se rotulan las bandas
    custom_timeline: Secuencia opcional de valores numéricos o etiquetas para usar como eje temporal
    reference_date: Fecha de referencia (YYYY-MM-DD) para calcular deltas en modos 'days'/'hours'/'months'
    timeline_unit: Texto descriptivo para el eje cuando se utilizan etiquetas personalizadas
    day_axis_limit: Límite superior del eje X cuando se usa 'days'
    day_reference_points: Lista de días para destacar como líneas verticales de referencia
    
    Retorna:
    None
    """
    # Cargar los datos del CSV
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error al cargar el archivo CSV: {e}")
        return
    
    if polygon_id is None:
        polygon_ids = df['polygon_fid'].unique()
    else:
        polygon_ids= [polygon_id]

    colors = plt.cm.tab10.colors

    for idx, pid in enumerate(polygon_ids):
        # Crear una nueva figura para cada polígono
        plt.figure(figsize=(14, 8))
        
        polygon_df = df[df['polygon_fid']==pid]

        num_firmas = len(polygon_df)

        if len(polygon_df) == 0:
            print(f"No se encontraron datos para el poligono {pid} en el CSV") 
            continue
    
        # Identificar columnas de bandas
        band_columns = [col for col in polygon_df.columns if col.startswith('band_')]
        num_bands = len(band_columns)
    
        if num_bands == 0:
            print(f"No se encontraron columnas de banda en el CSV")
            return
    
        # Obtener fechas si base_dir existe
        dates = None
        if base_dir:
            dates = get_band_dates(pid, base_dir)
            if dates:
                print(f"[INFO] Polígono {pid} - fechas encontradas: {len(dates)} bandas vs {num_bands} columnas")

        # Si no hay fechas, usar índices numéricos
        if not dates or len(dates) != num_bands:
            print("No se pudieron obtener fechas para las bandas. Usando índices numéricos.")
            dates = [f"Banda {i+1}" for i in range(num_bands)]

        x_values, x_labels, x_axis_label = build_time_axis(
            num_bands=num_bands,
            default_dates=dates,
            mode=x_axis_mode,
            custom_timeline=custom_timeline,
            reference_date=reference_date,
            timeline_unit=timeline_unit
        )

        # Muestrear píxeles si se especifica sample_size
        if sample_size and sample_size < len(polygon_df):
            sampled_df = polygon_df.sample(n=sample_size, random_state=42)
        else:
            sampled_df = polygon_df

        # Graficar cada píxel como una línea de tiempo
        for _, row in sampled_df.iterrows():
            values = [row[band] for band in band_columns]
            plt.plot(x_values, values, color=colors[idx % len(colors)], alpha=0.3, linewidth=0.5)

        # Calcular y graficar la media y desviación estándar si se solicita
        if include_mean or include_std:
            mean_values = [polygon_df[band].mean() for band in band_columns]

            if include_mean:
                plt.plot(x_values, mean_values, color=colors[idx % len(colors)], linewidth=3, label=f'Media (Polígono {pid})')

            if include_std:
                std_values = [polygon_df[band].std() for band in band_columns]
                plt.fill_between(
                    x_values,
                    [m - s for m, s in zip(mean_values, std_values)],
                    [m + s for m, s in zip(mean_values, std_values)],
                    color=colors[idx % len(colors)], alpha=0.2, label=f'Desviación estándar (Polígono {pid})'
                )

        # Configurar el gráfico
        plt.title('Evolución temporal del NDVI para todos los polígonos' if polygon_id is None else f'Evolución temporal del NDVI para el polígono {polygon_id}')
        plt.ylabel('NDVI')
        plt.xlabel(x_axis_label)
        plt.ylim(-0.05, 1.05)  # NDVI generalmente está entre -1 y 1
        plt.grid(True, linestyle='--', alpha=0.7)

        # Configurar las etiquetas del eje X
        label_display = [lbl.replace("_", "-") for lbl in x_labels]
        plt.xticks(x_values, label_display, rotation=45, ha='right')

        if x_axis_mode in {"days", "day"}:
            if day_axis_limit is not None:
                plt.xlim(0, day_axis_limit)
            if day_reference_points:
                y_min, y_max = plt.ylim()
                for point in sorted(day_reference_points):
                    plt.axvline(point, color='gray', linestyle='--', linewidth=0.8, alpha=0.6)
                    plt.text(
                        point, y_max, f"{int(point)}d" if float(point).is_integer() else f"{point:.1f}d",
                        rotation=90, va='bottom', ha='center', fontsize=9, color='gray'
                    )

        plt.text(0.95, 0.95, f"Firmas: {num_firmas}", fontsize=12, color='white', fontweight="bold", bbox=dict(facecolor="darkblue", alpha=0.6, edgecolor='none', boxstyle='round'), transform=plt.gca().transAxes, ha='right', va='top')
    
        # Añadir leyenda si corresponde
        if include_mean or include_std:
            plt.legend()
    
        # Ajustar la disposición
        plt.tight_layout()
        
        # Guardar o mostrar la figura (por polígono si output_folder está especificado)
        if output_folder:
            output_path = Path(output_folder)
            output_path.mkdir(parents=True, exist_ok=True)
            output_file = output_path / f"series_{pid}.png"
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"✅ Gráfico guardado: {output_file}")
        elif idx == len(polygon_ids) - 1:
            # Solo mostrar al final si no se está guardando
            plt.show()

def main(csv_path: str, output_folder: str = None, base_dir: str = None, 
         polygon_id=None, sample_size: int = 100, include_mean: bool = True, 
         include_std: bool = True, x_axis_mode: str = "dates"):
    """
    Función principal para generar gráficos de series temporales desde CSV.
    
    Args:
        csv_path: Ruta al CSV con datos vectorizados
        output_folder: Carpeta donde guardar gráficos
        base_dir: Directorio base para buscar fechas de bandas
        polygon_id: ID del polígono (None = todos)
        sample_size: Número de píxeles a mostrar
        include_mean: Incluir línea de tiempo media
        include_std: Incluir desviación estándar
        x_axis_mode: Modo del eje X ('dates', 'bands', 'days', etc.)
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
        x_axis_mode=x_axis_mode,
        output_folder=output_folder
    )
    
    print(f"✅ Proceso completado")

if __name__ == "__main__":
    # Ruta al CSV con los datos vectorizados
    csv_path = "/home/agrosavia/Documents/Geo_Agro/8.CSV_ALL/CWC_C1/ndvi/serie/datos_sin_outliers_IQR.csv"
  
    # Directorio base donde se encuentran las carpetas de los polígonos
    base_dir = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/CWC_C1" # Agregar bien este parametro para que se agreguen las fechas correspondientes
    
    #polygon_id = None
    polygon_id = None

    plot_ndvi_timeseries_from_csv(
        csv_path=csv_path,
        polygon_id=polygon_id,
        base_dir=base_dir,
        sample_size=100,  # Número de píxeles a graficar. None para mostrar todos.
        x_axis_mode="days",
        custom_timeline=[0, 35, 49, 57, 66, 71, 84, 113],
        reference_date="2021-05-12",
        timeline_unit="Dias",  # Días después de siembra
        day_axis_limit=120,
        day_reference_points=[0, 35, 49, 57, 66, 71, 84, 113],
        # En caso de dejar un número entero (por ejemplo, 100), se seleccionan aleatoriamente pixeles segun el número de muestra seleccionado 
    )
