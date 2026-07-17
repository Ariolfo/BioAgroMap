"""Lectura de AOI vectorial (GeoJSON, shapefile ZIP) con geopandas."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from shapely.geometry import mapping
from shapely.ops import unary_union


def _safe_zip_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if ".." in normalized:
        return False
    return not normalized.startswith(("/", "\\"))


def _normalize_zip_member(name: str) -> str:
    return name.replace("\\", "/")


def _shapefile_members(members: list[str]) -> list[str]:
    out = []
    for name in members:
        normalized = _normalize_zip_member(name)
        if not _safe_zip_member(normalized):
            continue
        if normalized.startswith("__MACOSX/") or "/__MACOSX/" in normalized:
            continue
        if normalized.lower().endswith(".shp"):
            out.append(normalized)
    return out


def read_geodataframe_from_path(path: Path):
    """Lee shapefile (.shp o .zip con componentes .shp/.dbf/.shx) y devuelve GeoDataFrame."""
    import geopandas as gpd

    p = path.resolve()
    if not p.exists():
        raise ValueError("El archivo vectorial no existe")

    ext = p.suffix.lower()
    read_path: str | Path = p
    tmp_dir: tempfile.TemporaryDirectory[str] | None = None
    errors: list[str] = []

    try:
        if ext == ".zip":
            with zipfile.ZipFile(p) as zf:
                shp_names = _shapefile_members(zf.namelist())
                if shp_names:
                    tmp_dir = tempfile.TemporaryDirectory()
                    zf.extractall(tmp_dir.name)
                    read_path = str(Path(tmp_dir.name) / shp_names[0])
                else:
                    for candidate in (f"/vsizip/{p}", f"zip://{p}"):
                        try:
                            gdf = gpd.read_file(candidate)
                            if not gdf.empty:
                                return gdf
                        except Exception as exc:
                            errors.append(str(exc))
                    members = [
                        _normalize_zip_member(n)
                        for n in zf.namelist()
                        if _safe_zip_member(_normalize_zip_member(n))
                    ]
                    suffixes = {Path(n).suffix.lower() for n in members if Path(n).suffix}
                    if ".shp" in suffixes:
                        raise ValueError(
                            "El ZIP contiene .shp pero faltan archivos del shapefile (.dbf y .shx en la misma carpeta)."
                        )
                    raise ValueError(
                        "El ZIP no contiene un shapefile válido (.shp con .dbf y .shx) ni otro vector reconocible."
                    )

        try:
            gdf = gpd.read_file(read_path)
        except Exception as exc:
            if ext == ".zip" and read_path != p:
                for candidate in (f"/vsizip/{p}", f"zip://{p}"):
                    try:
                        gdf = gpd.read_file(candidate)
                        break
                    except Exception as inner:
                        errors.append(str(inner))
                else:
                    raise ValueError(
                        "No se pudo leer el shapefile del ZIP. Incluya .shp, .dbf y .shx en la misma carpeta."
                    ) from exc
            else:
                raise ValueError("No se pudo leer el shapefile.") from exc

        if gdf.empty:
            raise ValueError("El archivo vectorial no contiene entidades")
        return gdf
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


def geojson_from_vector_path(path: Path) -> dict:
    """Convierte un vectorial (.shp o .zip shapefile) a GeoJSON en EPSG:4326."""
    gdf = read_geodataframe_from_path(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    else:
        gdf = gdf.to_crs(4326)
    return json.loads(gdf.to_json())


def geometry_wkt_from_vector_path(path: Path) -> tuple[str, dict]:
    """
    Lee un vectorial, reproyecta a EPSG:4326, unifica geometrías y devuelve WKT + bbox [minx,miny,maxx,maxy].
    """
    gdf = read_geodataframe_from_path(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    else:
        gdf = gdf.to_crs(4326)

    geom = unary_union(gdf.geometry.dropna().tolist())
    if geom.is_empty:
        raise ValueError("Geometría vacía")
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError("Geometría inválida tras corrección")

    wkt = geom.wkt
    b = geom.bounds
    meta = {
        "bounds_wgs84": [float(b[0]), float(b[1]), float(b[2]), float(b[3])],
        "geojson": mapping(geom),
    }
    return wkt, meta
