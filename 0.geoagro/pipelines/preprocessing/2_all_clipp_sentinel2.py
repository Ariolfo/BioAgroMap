"""
Recorte de imágenes Sentinel-2 por polígonos (shapefile).

Adaptado desde 2_all_clipp para:
- Productos .SAFE (carpeta con estructura GRANULE/.../IMG_DATA/R10m|R20m|R60m)
- Carpeta con TIFs planos (misma lógica que el recorte original)

Salida: destination_folder/<fid>/RECORTES/<nombre_banda>.tif
"""
import os
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping, box
import warnings


def _collect_tifs_sentinel2(source_folder: Path):
    """
    Recoge todos los .tif a recortar desde una carpeta o producto Sentinel-2 (.SAFE).

    - Si source_folder es un directorio .SAFE (nombre termina en .SAFE), busca
      recursivamente todos los *.tif dentro (IMG_DATA/R10m, R20m, R60m, etc.).
    - Si source_folder contiene subcarpetas .SAFE, busca en todas.
    - Si no, usa solo *.tif en la raíz de source_folder (comportamiento clásico).
    """
    source_folder = Path(source_folder)
    if not source_folder.exists() or not source_folder.is_dir():
        return []

    tifs = []

    # Caso 1: La propia carpeta es un producto .SAFE
    if source_folder.name.upper().endswith(".SAFE"):
        tifs = list(source_folder.rglob("*.tif"))
        tifs += list(source_folder.rglob("*.TIF"))
        return sorted(set(tifs))

    # Caso 2: La carpeta contiene uno o más .SAFE
    safe_dirs = [p for p in source_folder.iterdir() if p.is_dir() and p.name.upper().endswith(".SAFE")]
    if safe_dirs:
        for safe in safe_dirs:
            tifs.extend(safe.rglob("*.tif"))
            tifs.extend(safe.rglob("*.TIF"))
        return sorted(set(tifs))

    # Caso 3: Carpeta plana con TIFs (como 2_all_clipp original)
    tifs = list(source_folder.glob("*.tif")) + list(source_folder.glob("*.tiff"))
    tifs += list(source_folder.glob("*.TIF")) + list(source_folder.glob("*.TIFF"))
    return sorted(set(tifs))


def recortar_sentinel2_por_poligonos(
    source_folder: str,
    shapefile_path: str,
    destination_folder: str,
    resolucion: str = "10m",
) -> None:
    """
    Recorta todas las bandas TIF (Sentinel-2 .SAFE o carpeta de TIFs) usando cada
    polígono del shapefile. Guarda en destination_folder/<fid>/RECORTES/.

    Parámetros:
    - source_folder: ruta a la carpeta .SAFE de Sentinel-2, carpeta con .SAFE,
                     o carpeta con TIFs planos.
    - shapefile_path: ruta al shapefile (campo 'fid' o 'id').
    - destination_folder: ruta base de salida.
    - resolucion: solo para .SAFE; filtrar bandas por resolución: "10m", "20m", "60m"
                  o "todas" para no filtrar. Por defecto "10m".
    """
    src_folder = Path(source_folder)
    dest_base = Path(destination_folder)
    dest_base.mkdir(parents=True, exist_ok=True)

    if not src_folder.exists():
        raise FileNotFoundError(f"❌ No se encontró la carpeta fuente: {source_folder}")

    if not Path(shapefile_path).exists():
        raise FileNotFoundError(f"❌ No se encontró el shapefile: {shapefile_path}")

    # Recoger TIFs (SAFE o planos)
    all_tifs = _collect_tifs_sentinel2(src_folder)
    if not all_tifs:
        raise FileNotFoundError(
            f"❌ No se encontraron archivos .tif en: {source_folder}\n"
            f"   Para .SAFE, use una ruta a la carpeta .SAFE o a una carpeta que contenga .SAFE."
        )

    # Filtrar por resolución si hay rutas tipo .../R10m/... o .../IMG_DATA/R10m/...
    if resolucion != "todas" and resolucion in ("10m", "20m", "60m"):
        all_tifs = [t for t in all_tifs if f"R{resolucion}" in str(t) or f"/{resolucion}/" in str(t)]
        if not all_tifs:
            # Si el filtro dejó vacío, usar todos (p. ej. carpeta plana)
            all_tifs = _collect_tifs_sentinel2(src_folder)
    total_tifs = len(all_tifs)

    # Leer shapefile
    print(f"📂 Leyendo shapefile: {shapefile_path}")
    try:
        gdf = gpd.read_file(shapefile_path)
        print(f"✅ Shapefile cargado: {len(gdf)} polígonos")
    except Exception as e:
        raise ValueError(f"❌ Error al leer el shapefile: {e}")

    if len(gdf) == 0:
        raise ValueError("❌ El shapefile no contiene polígonos")

    if gdf.crs is None:
        print("⚠️  Shapefile sin CRS. Se asume EPSG:4326")
        gdf.set_crs(epsg=4326, inplace=True)

    processed_polygons = 0
    total_clips = 0
    errors = []

    print(f"📊 Archivos TIF a recortar: {total_tifs} (Sentinel-2 / planos)")
    print(f"📊 Polígonos: {len(gdf)}\n")

    for idx, row in gdf.iterrows():
        fid = row.get("id", row.get("fid", row.get("Id", row.get("FID", None))))
        if fid is None:
            print(f"⚠️  Fila {idx}: sin campo 'id'/'fid' - se omite")
            continue

        geom = row.geometry
        if geom is None or geom.is_empty:
            print(f"⚠️  Polígono {fid}: geometría vacía - se omite")
            continue

        poly_folder = dest_base / str(fid) / "RECORTES"
        poly_folder.mkdir(parents=True, exist_ok=True)
        print(f"📁 Polígono {fid}...")

        polygon_clips = 0
        for tif_path in all_tifs:
            try:
                with rasterio.open(tif_path) as src:
                    raster_crs = src.crs
                    if raster_crs is None:
                        continue

                    if gdf.crs != raster_crs:
                        temp_gdf = gpd.GeoDataFrame([row], crs=gdf.crs, geometry="geometry")
                        geom_reprojected = temp_gdf.to_crs(raster_crs).geometry.iloc[0]
                    else:
                        geom_reprojected = geom

                    raster_bounds = box(*src.bounds)
                    if not geom_reprojected.intersects(raster_bounds):
                        continue

                    out_img, out_tf = mask(src, [mapping(geom_reprojected)], crop=True, all_touched=False)
                    if out_img.size == 0 or out_img.shape[0] == 0:
                        continue

                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_img.shape[1],
                        "width": out_img.shape[2],
                        "transform": out_tf,
                        "compress": "lzw",
                    })

                    out_path = poly_folder / tif_path.name
                    with rasterio.open(out_path, "w", **out_meta) as dst:
                        dst.write(out_img)

                    polygon_clips += 1
                    total_clips += 1
            except Exception as e:
                err = f"Error recortando {tif_path.name} con polígono {fid}: {e}"
                errors.append(err)
                print(f"❌ {err}")

        if polygon_clips > 0:
            print(f"   ✅ {polygon_clips} recortes\n")
            processed_polygons += 1
        else:
            print(f"   ⚠️  Sin intersección con rasters\n")

    print(f"{'='*60}")
    print(f"📊 Resumen Sentinel-2:")
    print(f"   Polígonos procesados: {processed_polygons}/{len(gdf)}")
    print(f"   Recortes generados: {total_clips}")
    if errors:
        print(f"   Errores: {len(errors)}")
    print(f"{'='*60}\n")

    if processed_polygons == 0:
        raise RuntimeError(
            "❌ No se procesó ningún polígono.\n"
            "💡 Revisa: intersección con rasters, CRS del shapefile y de las bandas, campo 'id'/'fid'."
        )
    if total_clips == 0:
        raise RuntimeError("❌ No se generaron recortes. Verifica que los polígonos intersecten los rasters.")


def main(
    source_folder: str,
    shape_file: str,
    destination_folder: str,
    resolucion: str = "10m",
) -> None:
    """
    Punto de entrada para el pipeline (Streamlit / run_pipeline).
    """
    recortar_sentinel2_por_poligonos(
        source_folder,
        shape_file,
        destination_folder,
        resolucion=resolucion,
    )


if __name__ == "__main__":
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else "/path/to/S2A_...SAFE"
    shape = sys.argv[2] if len(sys.argv) > 2 else "/path/to/polygons.shp"
    dest = sys.argv[3] if len(sys.argv) > 3 else "/path/to/5.RECORTES/proyecto_s2"
    main(source, shape, dest, resolucion="10m")
