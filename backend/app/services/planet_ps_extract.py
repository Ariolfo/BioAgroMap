"""Extracción de imágenes composite/PSScene desde zips PlanetScope hacia ``recortesPS/``."""

from __future__ import annotations

import logging
import posixpath
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_YMD_PREFIX = re.compile(r"^(\d{4})(\d{2})(\d{2})_")


def _find_composite_in_zip(names: list[str]) -> str | None:
    """
    Localiza la imagen analítica principal del paquete PlanetScope.

    Prioriza ``composite.tif`` (órdenes/mosaicos) y, si no existe, acepta el
    producto SR de una escena PSScene: ``*_AnalyticMS_SR_8b_clip.tif``.
    Nunca selecciona la máscara UDM2.
    """
    loose: list[str] = []
    ps_scene_sr: list[str] = []
    for n in names:
        n = n.replace("\\", "/")
        low = posixpath.basename(n).lower()
        if low == "composite.tif":
            return n
        if low.endswith("composite.tif") and "udm2" not in low:
            loose.append(n)
        if low.endswith("_analyticms_sr_8b_clip.tif") and "udm2" not in low:
            ps_scene_sr.append(n)
    if loose:
        if len(loose) == 1:
            return loose[0]
        return max(loose, key=lambda p: (len(posixpath.basename(p)), p))
    if ps_scene_sr:
        # Normalmente hay uno; orden estable si el paquete contiene más de una escena.
        return sorted(ps_scene_sr)[0]
    return None


def _same_dir_sidecars(names: list[str], composite_inner: str) -> list[str]:
    """XML, JSON, ``*udm2*.tif`` y otros TIF auxiliares en la misma carpeta (no el composite principal)."""
    d = posixpath.dirname(composite_inner)
    out: list[str] = []
    for n in names:
        n = n.replace("\\", "/")
        if n == composite_inner:
            continue
        if posixpath.dirname(n) != d:
            continue
        low = posixpath.basename(n).lower()
        if low.endswith(".xml") or low.endswith(".json"):
            out.append(n)
        elif low.endswith(".tif") and "udm2" in low:
            out.append(n)
    return sorted(out)


def _yyyymmdd_from_basenames(paths: list[str]) -> str | None:
    """Fecha desde prefijo ``YYYYMMDD_`` (p. ej. XML Planet ``20260323_154447_...``)."""
    for n in paths:
        base = posixpath.basename(n)
        m = _YMD_PREFIX.match(base)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
                return f"{y}{mo}{d}"
    return None


def _dest_tif_name(yyyymmdd: str) -> str:
    y, mo, d = int(yyyymmdd[0:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8])
    yy = y % 100
    return f"PS_{d:02d}-{mo:02d}-{yy:02d}.tif"


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suf = target.stem, target.suffix
    n = 1
    while True:
        alt = target.with_name(f"{stem}_{n}{suf}")
        if not alt.exists():
            return alt
        n += 1


def extract_planet_zips_from_raster_ps(
    raster_ps_root: Path,
    recortes_ps_root: Path,
) -> dict:
    """
    Por cada ``*.zip`` en ``raster_ps_root``: localiza ``composite.tif`` o un
    ``*_AnalyticMS_SR_8b_clip.tif`` de PSScene y los metadatos en su mismo
    directorio interno. Extrae la imagen a ``recortes_ps_root`` como
    ``PS_dd-mm-yy.tif`` según el prefijo YYYYMMDD_ de sus metadatos.

    Idempotente: re-ejecutar reemplaza las salidas de la misma fecha (incluidos
    sidecars y duplicados ``_N`` de corridas anteriores) en vez de acumularlas.
    """
    raster_ps_root = raster_ps_root.resolve()
    recortes_ps_root = recortes_ps_root.resolve()
    recortes_ps_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    errors: list[str] = []
    dates_written_this_run: set[str] = set()

    zips = sorted(raster_ps_root.glob("*.zip"))
    if not zips:
        return {
            "ok": False,
            "error": "no_zips",
            "message": f"No hay archivos .zip en {raster_ps_root}",
            "results": results,
            "errors": errors,
            "pipeline": "ps_planet_zip_extract",
        }

    for zp in zips:
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                names = zf.namelist()
                comp = _find_composite_in_zip(names)
                if not comp:
                    errors.append(
                        f"{zp.name}: no se encontró composite.tif ni "
                        "*_AnalyticMS_SR_8b_clip.tif dentro del zip"
                    )
                    continue
                sidecars = _same_dir_sidecars(names, comp)
                ymd = _yyyymmdd_from_basenames(sidecars)
                if not ymd:
                    errors.append(
                        f"{zp.name}: no se pudo obtener fecha YYYYMMDD_ desde nombres en la carpeta del composite (XML/JSON)"
                    )
                    continue
                base_dest = recortes_ps_root / _dest_tif_name(ymd)
                if ymd in dates_written_this_run:
                    # Dos zips con la misma fecha en la misma corrida: no pisarse entre sí.
                    dest_tif = _unique_path(base_dest)
                else:
                    # Limpia la salida previa de esta fecha (composite, sidecars y duplicados _N).
                    for stale in recortes_ps_root.glob(f"{base_dest.stem}*"):
                        if stale.is_file():
                            stale.unlink(missing_ok=True)
                    dest_tif = base_dest
                dates_written_this_run.add(ymd)

                with tempfile.TemporaryDirectory(prefix="ps_zip_") as tmp:
                    td = Path(tmp)
                    zf.extract(comp, td)
                    src_tif = td / comp
                    if not src_tif.is_file():
                        errors.append(f"{zp.name}: fallo al extraer composite interno")
                        continue
                    shutil.copy2(src_tif, dest_tif)

                for sc_inner in sidecars:
                    with tempfile.TemporaryDirectory(prefix="ps_side_") as xtmp:
                        xd = Path(xtmp)
                        zf.extract(sc_inner, xd)
                        src_sc = xd / sc_inner
                        if not src_sc.is_file():
                            continue
                        sc_base = posixpath.basename(sc_inner)
                        dest_sc = recortes_ps_root / f"{dest_tif.stem}_{sc_base}"
                        shutil.copy2(src_sc, dest_sc)

                results.append(
                    {
                        "zip": zp.name,
                        "composite_out": dest_tif.name,
                        "sidecars_copied": len(sidecars),
                        "date_yyyymmdd": ymd,
                    }
                )
                logger.info("Planet PS extract ok: %s -> %s", zp.name, dest_tif.name)
        except Exception as exc:
            logger.exception("Planet PS extract failed: %s", zp)
            errors.append(f"{zp.name}: {exc}")

    return {
        "ok": bool(results),
        "processed": len(results),
        "results": results,
        "errors": errors,
        "pipeline": "ps_planet_zip_extract",
        "message": f"Extraídos {len(results)} composite(s) en {recortes_ps_root}",
    }
