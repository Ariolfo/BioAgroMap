import os
import rasterio
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Optional

def vectorize_ndvi_stacks_multiband(base_dir, stack_type, csv_path=None, append=False):
    """
    Vectoriza los stacks de NDVI de múltiples polígonos y guarda los resultados en un CSV.
    Permite agregar los nuevos datos a un CSV existente.
    
    Parámetros:
    base_dir (str): Directorio base donde se encuentran las carpetas de los polígonos
    csv_path (str, opcional): Ruta al archivo CSV donde guardar/agregar los resultados. 
                             Si es None, se usa 'ndvi_vectors_multiband.csv' en el directorio base
    append (bool): Si es True, agrega los datos a un CSV existente en lugar de sobrescribirlo
    
    Retorna:
    str: Ruta al archivo CSV generado o actualizado
    """
    # Lista para almacenar todos los datos vectorizados
    base_path = Path(base_dir)
    all_data = []
    
    # Recorrer todas las carpetas en el directorio base
    polygon_counter = 1  # Contador para asignar IDs cuando el nombre no es numérico
    for polygon_dir in base_path.iterdir():
        # Verificar si es un directorio válido con un nombre de polígono
        if not polygon_dir.is_dir():
            continue
            
        # Verificar si el nombre es "nan" o similar primero
        folder_name = str(polygon_dir.name).lower()
        stack_path = polygon_dir / "STACK" / stack_type
        
        if folder_name in ['nan', 'none', '']:
            # Carpeta con nombre no válido, usar contador
            if not os.path.exists(stack_path):
                continue
            polygon_fid = polygon_counter
            polygon_counter += 1
            print(f"⚠️ Carpeta '{polygon_dir.name}' tiene nombre no válido. Asignado ID: {polygon_fid}")
        else:
            try:
                # Intentar convertir el nombre a float
                polygon_fid = float(str(polygon_dir.name))
                # Verificar que no sea NaN usando numpy
                if np.isnan(polygon_fid):
                    raise ValueError("Es NaN")
            except (ValueError, TypeError):
                # Si el nombre no es numérico, usar un ID basado en el contador
                if not os.path.exists(stack_path):
                    continue
                polygon_fid = polygon_counter
                polygon_counter += 1
                print(f"⚠️ Carpeta '{polygon_dir.name}' no es numérica. Asignado ID: {polygon_fid}")
        
        # Verificar si existe el archivo stack
        if os.path.exists(stack_path):
            print(f"Procesando polígono {polygon_fid}...")
            
            # Abrir el stack con rasterio
            with rasterio.open(stack_path) as src:
                # Leer todas las bandas
                stack_data = src.read()
                
                # Obtener dimensiones del stack
                num_bands, height, width = stack_data.shape
                
                # Crear máscara para identificar píxeles con información (no cero)
                mask = np.any(stack_data != 0, axis=0)
                
                # Vectorizar solo los píxeles con información
                pixel_count = 0
                for y in range(height):
                    for x in range(width):
                        if mask[y, x]:
                            # Extraer el vector para este píxel (todas las bandas)
                            pixel_vector = stack_data[:, y, x]
                            
                            # Crear un registro para este píxel con el identificador del polígono
                            pixel_data = {"polygon_fid": polygon_fid}
                            
                            # Añadir cada banda como una columna separada
                            for band_idx in range(num_bands):
                                pixel_data[f"band_{band_idx+1}"] = pixel_vector[band_idx]
                            
                            # Añadir las coordenadas del píxel
                            pixel_data["pixel_x"] = x
                            pixel_data["pixel_y"] = y
                            
                            # Añadir este registro a la lista
                            all_data.append(pixel_data)
                            pixel_count += 1
            
            print(f"  - {pixel_count} píxeles procesados para el polígono {polygon_fid}")
        else:
            print(f"No se encontró el archivo stack para el polígono {polygon_fid}")
    
    # Definir la ruta del CSV si no se proporcionó
    if csv_path is None:
        csv_path = os.path.join(base_dir, "ndvi_vectors_multiband.csv")
    
    # Crear el DataFrame para el CSV
    if all_data:
        new_df = pd.DataFrame(all_data)
        output_path = Path(csv_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if append and os.path.exists(csv_path):
            # Leer el CSV existente y agregar los nuevos datos
            try:
                existing_df = pd.read_csv(csv_path)
                # Verificar si las columnas coinciden
                if set(existing_df.columns) == set(new_df.columns):
                    # Combinar los DataFrames
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    combined_df.to_csv(csv_path, index=False)
                    print(f"\nDatos agregados al archivo CSV existente: {csv_path}")
                    print(f"  - Registros anteriores: {len(existing_df)}")
                    print(f"  - Nuevos registros: {len(new_df)}")
                    print(f"  - Total registros: {len(combined_df)}")
                else:
                    print(f"Error: Las columnas del CSV existente no coinciden con los nuevos datos.")
                    print(f"  - Columnas existentes: {sorted(existing_df.columns)}")
                    print(f"  - Columnas nuevas: {sorted(new_df.columns)}")
                    
                    # Intentar hacer una unión basada en columnas comunes
                    common_columns = set(existing_df.columns).intersection(set(new_df.columns))
                    if len(common_columns) > 0 and "polygon_fid" in common_columns:
                        print(f"Intentando unir basándose en {len(common_columns)} columnas comunes...")
                        # Crear un backup del archivo original
                        backup_path = csv_path + ".backup"
                        existing_df.to_csv(backup_path, index=False)
                        print(f"  - Se ha creado una copia de seguridad en: {backup_path}")
                        
                        # Guardar el nuevo DataFrame en un archivo separado
                        new_csv_path = csv_path.replace(".csv", "_new.csv")
                        new_df.to_csv(new_csv_path, index=False)
                        print(f"  - Los nuevos datos se han guardado en: {new_csv_path}")
                        
                        return new_csv_path
            except Exception as e:
                print(f"Error al intentar agregar al CSV existente: {e}")
                print(f"Creando un nuevo archivo CSV...")
                new_df.to_csv(csv_path, index=False)
                print(f"\nNuevo archivo CSV guardado en: {csv_path}")
        else:
            # Crear un nuevo CSV o sobrescribir el existente
            new_df.to_csv(csv_path, index=False)
            print(f"\nArchivo CSV guardado en: {csv_path}")
            print(f"  - Total registros: {len(new_df)}")
        
        return csv_path
    else:
        print("No se encontraron píxeles con información en ningún polígono")
        return None

def main(base_dirs: List[str],
         stack_type: str,
         output_csv: str,
         append: bool = False) -> None:
    
    for i, bd in enumerate(base_dirs):
        mode = append if i > 0 else False
        print(f"== Lote {i+1}/{len(base_dirs)}: {bd} (append={mode}) ==")
        vectorize_ndvi_stacks_multiband(
            base_dir=bd,
            stack_type=stack_type,
            csv_path=output_csv,
            append=mode 
        )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('base_dirs', nargs='+', help='Lista de carpetas base')
    parser.add_argument('stack_type', help='Nombre del archivo stack, ej: stack_ndvi.tif')
    parser.add_argument('output_csv', help='Ruta de salida CSV')
    parser.add_argument('--append', action='store_true', help='Permitir append en lotes posteriores')
    args = parser.parse_args()
    main(args.base_dirs, args.stack_type, args.output_csv, args.append)