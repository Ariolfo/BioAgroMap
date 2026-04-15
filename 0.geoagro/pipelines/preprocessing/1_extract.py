import os
import re
import shutil
from pathlib import Path

def mover_y_renombrar_tifs(source_folder, destination_folder):
    """
    Mueve y renombra archivos .tif desde subcarpetas con formato específico.
    
    Args:
        source_folder: Carpeta fuente que contiene subcarpetas con formato 
                       'planet_medres_normalized_analytic_YYYY-MM_mosaic'
        destination_folder: Carpeta destino donde se guardarán los archivos renombrados
    """
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Expresión regular para extraer el mes y el año del nombre de la carpeta
    pattern = re.compile(r'planet_medres_normalized_analytic_(\d{4})-(\d{2})_mosaic')

    # Recorrer las subcarpetas en la carpeta fuente
    moved_count = 0
    for subdir, dirs, files in os.walk(source_folder):
        for dir_name in dirs:
            match = pattern.match(dir_name)
            if match:
                year, month = match.groups()  # Extraer el año y el mes
                folder_path = os.path.join(subdir, dir_name)

                # Buscar archivos .tif en la carpeta
                for file_name in os.listdir(folder_path):
                    if file_name.endswith('.tif'):
                        new_file_name = f"{month}_{year}.tif"
                        old_file_path = os.path.join(folder_path, file_name)
                        new_file_path = os.path.join(destination_folder, new_file_name)

                        # Mover y renombrar el archivo
                        shutil.move(old_file_path, new_file_path)
                        print(f"Renombrado y movido: {old_file_path} a {new_file_path}")
                        moved_count += 1
    
    print(f"✅ Total de archivos movidos: {moved_count}")
    return moved_count

def main(source_folder: str, destination_folder: str):
    """
    Función principal para integrar en el pipeline.
    
    Args:
        source_folder: Ruta a la carpeta fuente con subcarpetas de imágenes
        destination_folder: Ruta a la carpeta destino donde se guardarán los archivos
    """
    source_path = Path(source_folder)
    dest_path = Path(destination_folder)
    
    if not source_path.exists():
        raise FileNotFoundError(f"La carpeta fuente no existe: {source_folder}")
    
    print(f"📁 Carpeta fuente: {source_folder}")
    print(f"📁 Carpeta destino: {destination_folder}")
    
    mover_y_renombrar_tifs(source_folder, destination_folder)
    print(f"✅ Proceso de extracción completado")

if __name__ == "__main__":
    # Ejemplo de uso (solo para pruebas)
    source_folder = Path('/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/RASTER/NICFI/Ocamonte6071060')
    destination_folder = Path('/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/4.RASTER_CLEAN/ocamonte')
    
    if source_folder.exists():
        main(str(source_folder), str(destination_folder))
    else:
        print("⚠️ Carpeta fuente no encontrada. Ejecuta desde la aplicación Streamlit con parámetros correctos.")