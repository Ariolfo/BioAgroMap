import pandas as pd
from pathlib import Path

def find_csv_file(base_path: Path, filename: str) -> Path:
    """Busca un archivo CSV en la estructura de carpetas"""
    # Buscar en todas las subcarpetas
    for csv_file in base_path.rglob(filename):
        if csv_file.exists():
            return csv_file
    return None

def remove_outliers_iqr(input_csv: str, output_csv: str, factor: float = 1.5) -> pd.DataFrame:
    """
    Carga un CSV, detecta y filtra filas con outliers en columnas 'band*'
    usando el método IQR con el factor dado, y guarda el resultado.

    Parámetros:
    - input_csv: ruta al CSV de entrada.
    - output_csv: ruta donde se escribirá el CSV sin outliers.
    - factor: múltiplo del IQR para definir límites (por defecto 1.5).

    Retorna:
    - DataFrame limpio (sin outliers).
    """
    # 1) Leer datos
    df = pd.read_csv(input_csv)

    # 2) Columnas de interés 
    cols_bandas = [c for c in df.columns if "band" in c]

    # 3) DataFrame para flags de outlier
    flags = pd.DataFrame(False, index=df.index, columns=cols_bandas)

    # 4) Detectar outliers por columna
    for col in cols_bandas:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - factor * IQR
        upper = Q3 + factor * IQR

        flags[col] = (df[col] < lower) | (df[col] > upper)
        print(f"Columna {col}: umbrales [{lower:.3f}, {upper:.3f}], "
              f"outliers detectados = {flags[col].sum()}")
        
    # 5) Filtrar filas con outliers
    df_clean = df[~flags.any(axis=1)].copy()
    print(f"Filas sin outliers: {len(df_clean)}")

    # 6) Guardar CSV limpio
    df_clean.to_csv(output_csv, index=False)
    print(f"Se guardó '{output_csv}'")

    return df_clean

def main(input_csv: str, output_csv: str, factor: float = 1.5):
    """
    Función principal para detectar y eliminar outliers.
    
    Si el archivo input_csv no existe, intenta buscarlo en la estructura de carpetas.
    """
    input_path = Path(input_csv)
    
    # Si el archivo no existe, intentar buscarlo
    if not input_path.exists():
        print(f"⚠️ Archivo no encontrado: {input_csv}")
        print(f"🔍 Buscando archivo en estructura de carpetas...")
        
        # Buscar en la carpeta padre
        base_path = input_path.parent.parent.parent if input_path.parent else Path(input_csv).parent
        filename = input_path.name
        
        found_file = find_csv_file(base_path, filename)
        
        if found_file:
            print(f"✅ Archivo encontrado: {found_file}")
            input_csv = str(found_file)
        else:
            # Buscar cualquier CSV_ALL.csv en la estructura
            if "CSV_ALL.csv" in filename:
                for csv_file in base_path.rglob("CSV_ALL.csv"):
                    print(f"✅ Archivo alternativo encontrado: {csv_file}")
                    input_csv = str(csv_file)
                    break
                else:
                    raise FileNotFoundError(
                        f"❌ No se encontró el archivo {input_csv}.\n"
                        f"💡 Asegúrate de ejecutar primero el módulo '5_generate_csv_file' para generar el CSV."
                    )
            else:
                raise FileNotFoundError(
                    f"❌ No se encontró el archivo {input_csv}.\n"
                    f"💡 Verifica que los módulos anteriores se hayan ejecutado correctamente."
                )
    
    # Asegurar que la carpeta de salida existe
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    remove_outliers_iqr(input_csv, output_csv, factor)

