# 5_3_ADF_KPSS.py
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller, kpss
from joblib import Parallel, delayed
import multiprocessing
from pathlib import Path

def find_csv_file(base_path: Path, filename: str) -> Path:
    """Busca un archivo CSV en la estructura de carpetas"""
    for csv_file in base_path.rglob(filename):
        if csv_file.exists():
            return csv_file
    return None

def main(
    input_csv: str,
    output_clean_csv: str,
    output_all_csv: str,
    alpha: float = 0.05,
    n_jobs: int = None
):
    """
    1) Carga input_csv
    2) Aplica ADF y KPSS en paralelo a cada fila
    3) Guarda dos CSVs: 
       - output_clean_csv (solo series estacionarias)
       - output_all_csv   (todas las series con sus p-values y etiquetas)
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
            # Buscar archivos alternativos
            if "datos_sin_outliers_IQR.csv" in filename:
                for csv_file in base_path.rglob("*outliers*.csv"):
                    print(f"✅ Archivo alternativo encontrado: {csv_file}")
                    input_csv = str(csv_file)
                    break
                else:
                    raise FileNotFoundError(
                        f"❌ No se encontró el archivo {input_csv}.\n"
                        f"💡 Asegúrate de ejecutar primero el módulo '5_2_outliers_IQR' para generar el CSV sin outliers."
                    )
            else:
                raise FileNotFoundError(
                    f"❌ No se encontró el archivo {input_csv}.\n"
                    f"💡 Verifica que los módulos anteriores se hayan ejecutado correctamente."
                )
    
    # Asegurar que las carpetas de salida existen
    Path(output_clean_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(output_all_csv).parent.mkdir(parents=True, exist_ok=True)
    
    df = pd.read_csv(input_csv)
    band_cols = [c for c in df.columns if "band_" in c]
    n_jobs = n_jobs or multiprocessing.cpu_count()

    def process_row(idx, row):
        serie = row[band_cols].values
        try:
            adf_p = adfuller(serie, autolag="AIC")[1]
            adf_stat = adf_p < alpha
        except:
            adf_p, adf_stat = np.nan, False
        try:
            kpss_p = kpss(serie, regression="c", nlags="auto")[1]
            kpss_stat = kpss_p > alpha
        except:
            kpss_p, kpss_stat = np.nan, False

        if adf_stat and kpss_stat:
            label = "Stationary"
        elif not adf_stat and not kpss_stat:
            label = "Not Stationary"
        else:
            label = "Inconclusive"

        return {
            "idx": idx,
            "adf_pvalue": adf_p,
            "adf_stationary": adf_stat,
            "kpss_pvalue": kpss_p,
            "kpss_stationary": kpss_stat,
            "stationarity_double_validation": label,
        }

    results = Parallel(n_jobs=n_jobs)(
        delayed(process_row)(i, r) for i, r in df.iterrows()
    )
    res_df = pd.DataFrame(results).set_index("idx")
    df = df.join(res_df)

    # Guardar todas las filas + etiquetas
    df.to_csv(output_all_csv, index=False)
    # Guardar solo las estacionarias
    df[df.stationarity_double_validation == "Stationary"]\
      .to_csv(output_clean_csv, index=False)
    print(f"Guardados:\n • {output_all_csv} (todas)\n • {output_clean_csv} (stationary)")

if __name__ == "__main__":
    # Solo prototipo: reemplaza rutas si lo ejecutas aisladamente
    main(
        input_csv="datos_sin_outliers_IQR.csv",
        output_clean_csv="datos_stationary.csv", # CSV con solamente las firmas estacionarias
        output_all_csv="datos_stationarity_double_validation_parallel.csv", # CSV con todas las firmas, con la columna 'Stationary'
    )
