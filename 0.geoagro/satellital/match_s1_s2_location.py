#!/usr/bin/env python3
"""
Relaciona imágenes Sentinel-1 y Sentinel-2 por ubicación (footprint).

Para cada S2 encuentra el S1 con mayor superposición espacial (intersección)
y opcionalmente cercanía en fecha. Salida: tabla, CSV y/o reorganización en carpetas.

Uso:
  python match_s1_s2_location.py
  python match_s1_s2_location.py -o pares_s1_s2.csv
  python match_s1_s2_location.py --reorganize pares_por_fecha  # carpetas por fecha con S2 y S1
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


# Reutilizar lógica de footprints
from s2_footprint import (
    bounds_to_polygon_wgs84,
    footprint_from_raster,
    footprint_from_safe,
    get_raster_bounds,
)

# Directorios por defecto
DEFAULT_S1_DIR = Path("downloads_sentinel1")
DEFAULT_S2_DIR = Path("downloads_sentinel2")


def first_raster_in_s1_safe(safe_path: Path) -> Path | None:
    """Devuelve la ruta al primer raster en measurement/ de un .SAFE de S1."""
    safe_path = Path(safe_path)
    measurement = safe_path / "measurement"
    if not measurement.is_dir():
        return None
    for f in sorted(measurement.iterdir()):
        if f.suffix.lower() in (".tif", ".tiff"):
            return f
    return None


def footprint_from_s1_safe(safe_path: Path):
    """Footprint en WGS84 de un producto S1 (.SAFE con measurement/*.tiff)."""
    raster_path = first_raster_in_s1_safe(safe_path)
    if raster_path is None:
        return None
    return footprint_from_raster(raster_path)


def parse_date_from_name(name: str) -> str | None:
    """Extrae YYYY-MM-DD del nombre (S2: ..._20230828T..., S1: ..._20230829T...)."""
    m = re.search(r"(\d{4})(\d{2})(\d{2})T", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def collect_s2_footprints(s2_dir: Path) -> list[tuple[str, object]]:
    """Lista (nombre, polígono WGS84) para cada S2 (.tif o .SAFE)."""
    s2_dir = Path(s2_dir)
    if not s2_dir.is_dir():
        return []
    out = []
    for item in sorted(s2_dir.iterdir()):
        if item.suffix.lower() in (".tif", ".tiff"):
            try:
                geom, _ = footprint_from_raster(item)
                out.append((item.name, geom))
            except Exception:
                pass
        elif item.is_dir() and item.name.endswith(".SAFE"):
            try:
                result = footprint_from_safe(item)
                if result:
                    geom, _ = result
                    out.append((item.name, geom))
            except Exception:
                pass
    return out


def collect_s1_footprints(s1_dir: Path) -> list[tuple[str, object]]:
    """Lista (nombre, polígono WGS84) para cada S1 (.SAFE)."""
    s1_dir = Path(s1_dir)
    if not s1_dir.is_dir():
        return []
    out = []
    for item in sorted(s1_dir.iterdir()):
        if item.is_dir() and ".SAFE" in item.name:
            try:
                result = footprint_from_s1_safe(item)
                if result:
                    geom, _ = result
                    out.append((item.name, geom))
            except Exception:
                pass
    return out


def match_s2_to_s1(
    s2_list: list[tuple[str, object]],
    s1_list: list[tuple[str, object]],
    use_iou: bool = True,
):
    """
    Para cada S2 devuelve el S1 con mayor superposición.
    use_iou: si True, ordenar por IoU (intersección/unión); si False, por área de intersección.
    """
    results = []
    for s2_name, poly_s2 in s2_list:
        if not poly_s2.is_valid:
            poly_s2 = poly_s2.buffer(0)
        best_s1 = None
        best_score = -1.0
        best_intersection_area = 0.0
        best_distance = float("inf")  # por si no hay intersección

        for s1_name, poly_s1 in s1_list:
            if not poly_s1.is_valid:
                poly_s1 = poly_s1.buffer(0)
            try:
                inter = poly_s2.intersection(poly_s1)
                inter_area = inter.area if not inter.is_empty else 0.0
                if inter_area > 0:
                    if use_iou:
                        un = poly_s2.union(poly_s1)
                        score = inter_area / un.area if un.area > 0 else 0
                    else:
                        score = inter_area
                    if score > best_score:
                        best_score = score
                        best_intersection_area = inter_area
                        best_s1 = s1_name
                        best_distance = 0
                else:
                    # Sin superposición: elegir el S1 más cercano (menor distancia entre polígonos)
                    dist = poly_s2.distance(poly_s1)
                    if dist < best_distance:
                        best_distance = dist
                        if best_s1 is None or best_score < 0:
                            best_s1 = s1_name
                            best_score = -dist  # negativo para indicar "por distancia"
            except Exception:
                continue

        date_s2 = parse_date_from_name(s2_name)
        date_s1 = parse_date_from_name(best_s1) if best_s1 else None
        # Si solo hay match por distancia, guardar distancia en lugar de IoU
        score_val = best_score if best_score >= 0 else best_distance
        match_type = "overlap" if best_score >= 0 else "nearest"
        results.append({
            "s2": s2_name,
            "s1": best_s1 or "",
            "match_type": match_type,
            "iou" if use_iou else "overlap_area": round(score_val, 6),
            "intersection_area": round(best_intersection_area, 6),
            "distance": round(best_distance, 6),
            "date_s2": date_s2 or "",
            "date_s1": date_s1 or "",
        })
    return results


def deduplicate_results_by_date(results: list[dict]) -> list[dict]:
    """Un resultado por date_s2: se queda el S2 .SAFE si existe, si no el .tif."""
    by_date = {}
    for r in results:
        d = r.get("date_s2") or "sin_fecha"
        if d not in by_date:
            by_date[d] = r
        else:
            # Preferir .SAFE sobre .tif para S2
            if r["s2"].endswith(".SAFE") and not by_date[d]["s2"].endswith(".SAFE"):
                by_date[d] = r
    return list(by_date.values())


def reorganize_into_folders(
    results: list[dict],
    s1_dir: Path,
    s2_dir: Path,
    out_root: Path,
    symlink: bool = True,
) -> list[Path]:
    """
    Crea una carpeta por fecha (date_s2) con enlaces o copias a S2 y S1 emparejados.
    Estructura: out_root/YYYY-MM-DD/S2 -> producto S2, out_root/YYYY-MM-DD/S1 -> producto S1.
    results: lista ya deduplicada por fecha (un S2 por fecha).
    symlink: si True crea symlinks; si False copia (no implementado, solo symlink).
    """
    out_root = Path(out_root).resolve()
    s1_dir = Path(s1_dir).resolve()
    s2_dir = Path(s2_dir).resolve()
    created = []
    for r in results:
        date_s2 = (r.get("date_s2") or "sin_fecha").strip()
        if not date_s2 or not r.get("s1"):
            continue
        folder = out_root / date_s2
        folder.mkdir(parents=True, exist_ok=True)
        path_s2 = s2_dir / r["s2"]
        path_s1 = s1_dir / r["s1"]
        link_s2 = folder / "S2"
        link_s1 = folder / "S1"
        if path_s2.exists():
            if link_s2.exists():
                link_s2.unlink()
            os.symlink(path_s2, link_s2)
            created.append(link_s2)
        if path_s1.exists():
            if link_s1.exists():
                link_s1.unlink()
            os.symlink(path_s1, link_s1)
            created.append(link_s1)
    return created


def main():
    parser = argparse.ArgumentParser(
        description="Relaciona S1 y S2 por ubicación (mayor superposición de footprint)."
    )
    parser.add_argument(
        "--s1-dir",
        type=Path,
        default=DEFAULT_S1_DIR,
        help="Directorio con productos S1 (.SAFE).",
    )
    parser.add_argument(
        "--s2-dir",
        type=Path,
        default=DEFAULT_S2_DIR,
        help="Directorio con productos S2 (.tif o .SAFE).",
    )
    parser.add_argument(
        "-o", "--out",
        type=Path,
        default=None,
        help="Archivo CSV de salida con pares S2,S1.",
    )
    parser.add_argument(
        "--by-area",
        action="store_true",
        help="Ordenar por área de intersección en lugar de IoU.",
    )
    parser.add_argument(
        "-r", "--reorganize",
        type=Path,
        default=None,
        metavar="DIR",
        help="Crea carpetas por fecha (DIR/YYYY-MM-DD/S2, DIR/YYYY-MM-DD/S1) con enlaces al S2 y S1 emparejados.",
    )
    args = parser.parse_args()

    s2_list = collect_s2_footprints(args.s2_dir)
    s1_list = collect_s1_footprints(args.s1_dir)

    if not s2_list:
        print(f"No se encontraron S2 en {args.s2_dir}")
        return 1
    if not s1_list:
        print(f"No se encontraron S1 en {args.s1_dir}")
        return 1

    print(f"S2: {len(s2_list)}  |  S1: {len(s1_list)}")
    print()

    results = match_s2_to_s1(s2_list, s1_list, use_iou=not args.by_area)
    score_key = "overlap_area" if args.by_area else "iou"

    # Tabla
    print("S2 (origen)                    | S1 (más parecido)                   | Tipo     | IoU/Dist  | Fecha S2   | Fecha S1")
    print("-" * 120)
    for r in results:
        s2_short = (r["s2"][:30] + "…") if len(r["s2"]) > 33 else r["s2"]
        s1_short = (r["s1"][:30] + "…") if len(r["s1"]) > 33 else r["s1"]
        val = r[score_key]
        print(f"{s2_short:<33} | {s1_short:<33} | {r['match_type']:<8} | {val:>9.4f} | {r['date_s2']:<10} | {r['date_s1']}")

    if args.out:
        import csv
        out_path = Path(args.out)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["s2", "s1", "match_type", score_key, "intersection_area", "distance", "date_s2", "date_s1"],
            )
            w.writeheader()
            w.writerows(results)
        print(f"\nGuardado: {out_path}")

    if args.reorganize:
        unique = deduplicate_results_by_date(results)
        created = reorganize_into_folders(
            unique, args.s1_dir, args.s2_dir, args.reorganize, symlink=True
        )
        n_folders = len(set(p.parent for p in created))
        print(f"\nReorganizado: {args.reorganize}/  ({n_folders} carpetas por fecha, enlaces S2 y S1)")

    return 0


if __name__ == "__main__":
    exit(main())
