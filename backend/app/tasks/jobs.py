import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import rasterio

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_raster_sentinel_status(db_url: str, raster_layer_id: int, extra: dict) -> None:
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models.models import RasterLayer

        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        raster = db.query(RasterLayer).filter(RasterLayer.id == raster_layer_id).first()
        if raster:
            raster.raster_metadata = {**(raster.raster_metadata or {}), **extra}
            db.commit()
        db.close()
    except Exception:
        logger.exception("Error updating raster metadata (sentinel status)")


@celery_app.task(name="tasks.process_raster")
def process_raster(file_path: str, output_path: str) -> dict:
    src_path = Path(file_path)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update({"driver": "GTiff", "compress": "lzw", "tiled": True})
        data = src.read()
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data)
    return {"status": "done", "cog_path": str(out_path)}


@celery_app.task(name="tasks.mock_inference")
def mock_inference(input_raster: str, output_json: str) -> dict:
    with rasterio.open(input_raster) as src:
        band = src.read(1)
        metrics = {
            "accuracy": float(np.clip(band.mean() / 255.0, 0.55, 0.95)),
            "iou": 0.71,
            "f1_score": 0.81,
        }
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(metrics), encoding="utf-8")
    return metrics


@celery_app.task(name="tasks.download_sentinel2", bind=True)
def download_sentinel2(
    self,
    wkt: str,
    start_date_str: str,
    end_date_str: str,
    output_dir: str,
    copernicus_user: str,
    copernicus_password: str,
    raster_layer_id: int,
    db_url: str,
) -> dict:
    from app.services.sentinel2 import search_and_download_monthly

    def progress_cb(current: int, total: int, message: str) -> None:
        pct = int((current / max(total, 1)) * 100)
        self.update_state(
            state="PROGRESS",
            meta={"progress": pct, "message": message, "phase": "downloading"},
        )
        _update_raster_sentinel_status(
            db_url,
            raster_layer_id,
            {"progress": pct, "progress_message": message, "status": "downloading"},
        )

    self.update_state(state="PROGRESS", meta={"progress": 0, "message": "Iniciando...", "phase": "downloading"})
    start = date.fromisoformat(start_date_str)
    end = date.fromisoformat(end_date_str)

    try:
        result = search_and_download_monthly(
            wkt,
            start,
            end,
            output_dir,
            copernicus_user,
            copernicus_password,
            progress_callback=progress_cb,
        )
    except Exception as exc:
        logger.exception("Sentinel-2 download failed")
        _update_raster_sentinel_status(
            db_url,
            raster_layer_id,
            {
                "status": "failed",
                "error": str(exc),
                "progress": 0,
                "progress_message": f"Error: {exc}",
            },
        )
        raise

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models.models import RasterLayer

        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        raster = db.query(RasterLayer).filter(RasterLayer.id == raster_layer_id).first()
        if raster:
            meta = {
                **(raster.raster_metadata or {}),
                "status": "completed",
                "total_downloaded": result["total_downloaded"],
                "total_size_mb": result["total_size_mb"],
                "files": [str(f) for f in result["files"]],
                "skipped_low_coverage": result.get("skipped_low_coverage", 0),
                "progress": 100,
                "progress_message": "Descarga terminada",
            }
            if result["files"]:
                meta["primary_file"] = result["files"][0]
                raster.file_path = result["files"][0]
            raster.raster_metadata = meta
            db.commit()
        db.close()
    except Exception:
        logger.exception("Error updating raster metadata after S2 download")

    self.update_state(state="SUCCESS", meta={"progress": 100, "message": "Terminado", "phase": "completed"})
    return result
