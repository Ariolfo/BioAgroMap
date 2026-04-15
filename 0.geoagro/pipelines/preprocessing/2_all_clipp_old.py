import os
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping, box

def recortar_tifs_por_poligonos(source_folder, shapefile_path, destination_folder):
    # — (tu código de shapefile/CRS igual que antes) —
    shape = gpd.read_file(shapefile_path)
    if shape.crs is None:
        shape.set_crs(epsg=4326, inplace=True)
    else:
        shape = shape.to_crs(epsg=4326)
    shape_3857 = shape.to_crs(epsg=3857)
    os.makedirs(destination_folder, exist_ok=True)

    for tif_path in Path(source_folder).glob("*.tif"):
        with rasterio.open(tif_path) as src:
            # — TEST: ¿abre siquiera un píxel? —
            try:
                _ = src.read(1, window=((0, 1), (0, 1)))
            except Exception as e:
                print(f"⚠️ No leo {tif_path.name}: {e}")
                continue

            lb, bb, rb, tb = src.bounds
            # determinamos si están en lon/lat o metro
            if all(abs(v) <= 180 for v in (lb, bb, rb, tb)):
                mask_gdf = shape
            else:
                mask_gdf = shape_3857
            raster_bb = box(lb, bb, rb, tb)

            for _, row in mask_gdf.iterrows():
                fid, geom = row['id'], row.geometry
                fid_str = str(fid)
                if fid_str.isdigit():
                    fid_str = f"{fid_str}.0"
                elif fid_str.endswith(".0"):
                    pass
                out_dir = Path(destination_folder) / fid_str / "RECORTES"
                out_dir.mkdir(parents=True, exist_ok=True)
                if not geom.intersects(raster_bb):
                    continue
                try:
                    out_img, out_tr = mask(src, [mapping(geom)], crop=True)
                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_img.shape[1],
                        "width":  out_img.shape[2],
                        "transform": out_tr
                    })
                    out_fp = out_dir / tif_path.name
                    with rasterio.open(out_fp, "w", **out_meta) as dst:
                        dst.write(out_img)
                    print(f"✓ Recortado: {out_fp}")
                except Exception as e:
                    print(f"✗ Falló recorte {tif_path.name} polígono {fid}: {e}")

if __name__ == "__main__":
    recortar_tifs_por_poligonos(
        source_folder      = "/home/agrosavia/Documents/Geo_Agro/4.RASTER_CLEAN/nataima_cwc",
        shapefile_path     = "/home/agrosavia/Documents/Geo_Agro/3.POLYGON_TOWN/nataima/SHAPE_CWC/CWC.shp",
        destination_folder = "/home/agrosavia/Documents/Geo_Agro/5.RECORTES/nataima_cwc"
    )
