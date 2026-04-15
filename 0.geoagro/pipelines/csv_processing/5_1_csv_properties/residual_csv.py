import os
import rasterio
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose

def vectorize_residual_components(base_dir, csv_path=None, append=False, period=12):
    """
    Vectoriza los componentes residuales de los stacks de NDVI.
    """
    all_data = []
    
    for polygon_dir in os.listdir(base_dir):
        try:
            polygon_fid = float(polygon_dir)
            stack_path = os.path.join(base_dir, polygon_dir, "STACK", "stack_ndvi.tif")
            
            if os.path.exists(stack_path):
                print(f"Procesando polígono {polygon_fid}...")
                with rasterio.open(stack_path) as src:
                    stack_data = src.read()
                    num_bands, height, width = stack_data.shape
                    mask = np.any(stack_data != 0, axis=0)
                    pixel_count = 0
                    
                    for y in range(height):
                        for x in range(width):
                            if mask[y, x]:
                                pixel_vector = stack_data[:, y, x]
                                resid_vector = np.full_like(pixel_vector, np.nan)
                                
                                if len(pixel_vector) >= 2 * period:
                                    try:
                                        decomposition = seasonal_decompose(
                                            pixel_vector, 
                                            model='additive', 
                                            period=period
                                        )
                                        resid_vector = decomposition.resid
                                    except ValueError:
                                        pass
                                
                                pixel_data = {
                                    "polygon_fid": polygon_fid,
                                    "pixel_x": x,
                                    "pixel_y": y
                                }
                                for band_idx in range(num_bands):
                                    pixel_data[f"band_{band_idx+1}"] = resid_vector[band_idx]
                                
                                all_data.append(pixel_data)
                                pixel_count += 1
                                
                    print(f"  - {pixel_count} píxeles procesados")
        except ValueError:
            continue

    df = pd.DataFrame(all_data)
    if csv_path is None:
        csv_path = os.path.join(base_dir, "residual_components.csv")
    
    mode = 'a' if append and os.path.exists(csv_path) else 'w'
    df.to_csv(csv_path, mode=mode, index=False, header=(mode == 'w'))
    return csv_path

if __name__ == "__main__":
    directories = [
        "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/5.RECORTES/464_moniquira",
    ]
    final_csv = "/home/agrosavia/Documents/rs_agrosavia/DATA_CUBE_AGROSAVIA/ROI/GIS_FEDEPANELA/8.CSV_ALL/residual_components.csv"
    
    for i, base_dir in enumerate(directories):
        vectorize_residual_components(
            base_dir,
            csv_path=final_csv,
            append=(i > 0)
        )