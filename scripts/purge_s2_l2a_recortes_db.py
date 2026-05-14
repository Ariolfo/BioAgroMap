#!/usr/bin/env python3
"""
Elimina filas ``raster_layers`` de recortes Sentinel-2 L2A (metadata ``s2_l2a_recorte``)
cuyo ``s2_sort_key`` coincide con las fechas dadas (YYYY-MM-DD), y borra los GeoTIFF/COG
asociados (misma lógica que DELETE /raster/...).

Ejemplo (4 capas negras 06/01/2026 y 11/02/2026 en la galería RGB):

  python3 scripts/purge_s2_l2a_recortes_db.py --project-id 1 --dates 2026-01-06,2026-02-11 --apply

Sin ``--apply`` solo lista las capas que se borrarían.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from app.api.v1.rasters import (  # noqa: E402
    _normalize_s2_sort_keys,
    _scene_iso_yyyy_mm_dd_for_purge,
    _s2_rgb_gallery_raster_meta,
    delete_raster_layer_row,
)
from app.db.session import SessionLocal  # noqa: E402
from app.models.models import RasterLayer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-id", type=int, required=True)
    ap.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Si se omite, se buscan capas del project_id en cualquier tenant (IDs de proyecto suelen ser únicos).",
    )
    ap.add_argument(
        "--dates",
        required=True,
        help="Lista separada por comas: YYYY-MM-DD,YYYY-MM-DD,...",
    )
    ap.add_argument("--apply", action="store_true", help="Ejecutar borrado (sin esto solo lista).")
    args = ap.parse_args()

    keys = _normalize_s2_sort_keys([x.strip() for x in args.dates.split(",") if x.strip()])
    if not keys:
        print("No quedó ninguna fecha válida (use YYYY-MM-DD).", file=sys.stderr)
        return 1
    key_set = set(keys)

    db = SessionLocal()
    try:
        q = db.query(RasterLayer).filter(RasterLayer.project_id == int(args.project_id))
        if args.tenant_id is not None:
            q = q.filter(RasterLayer.tenant_id == int(args.tenant_id))
        candidates = q.all()
        to_delete: list[RasterLayer] = []
        for r in candidates:
            meta = r.raster_metadata or {}
            if not _s2_rgb_gallery_raster_meta(meta):
                continue
            scene = _scene_iso_yyyy_mm_dd_for_purge(r)
            if scene and scene in key_set:
                to_delete.append(r)

        if not to_delete:
            print("No hay capas de galería RGB S2 que coincidan con esas fechas (ISO YYYY-MM-DD).")
            return 0

        for r in to_delete:
            meta = r.raster_metadata or {}
            print(
                f"  id={r.id} tenant={r.tenant_id} sort_key={meta.get('s2_sort_key')!r} "
                f"name={r.name!r} file_path={r.file_path!r}"
            )

        if not args.apply:
            print(f"\nDry-run: {len(to_delete)} capa(s). Repita con --apply para borrar.")
            return 0

        deleted: list[int] = []
        for r in to_delete:
            tid, pid, rid = r.tenant_id, r.project_id, r.id
            delete_raster_layer_row(db, tid, pid, r)
            deleted.append(rid)
        db.commit()
        print(f"\nBorradas {len(deleted)} capas: {deleted}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
