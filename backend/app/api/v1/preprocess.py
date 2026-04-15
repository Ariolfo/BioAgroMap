import json
import re
import uuid

import numpy as np
import rasterio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import tenant_from_jwt
from app.api.v1.helpers import _existing_raster_path, _get_project_raster, _tenant_storage
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Layer, Project, RasterLayer
from app.schemas.schemas import (
    ClusterRequest,
    CropRequest,
    DownloadRequest,
    IndicesRequest,
    StackRequest,
)

router = APIRouter()


def _layer_to_geojson(layer: Layer) -> dict | None:
    """Convert any supported layer format to GeoJSON dict."""
    import zipfile
    from pathlib import Path

    from app.api.v1.layers import _kml_to_geojson, _safe_zip_name

    fp = Path(layer.file_path)
    if not fp.exists():
        return None

    ext = fp.suffix.lower()
    try:
        if ext in {".geojson", ".json"}:
            return json.loads(fp.read_text(encoding="utf-8"))
        if ext == ".kml":
            return _kml_to_geojson(fp.read_text(encoding="utf-8"))
        if ext == ".kmz":
            with zipfile.ZipFile(fp) as zf:
                for name in zf.namelist():
                    if not _safe_zip_name(name):
                        continue
                    if name.lower().endswith(".kml"):
                        result = _kml_to_geojson(zf.read(name).decode("utf-8"))
                        if result:
                            return result
        if ext == ".zip":
            with zipfile.ZipFile(fp) as zf:
                for name in zf.namelist():
                    if not _safe_zip_name(name):
                        continue
                    if name.lower().endswith((".geojson", ".json")):
                        return json.loads(zf.read(name).decode("utf-8"))
                    if name.lower().endswith(".kml"):
                        result = _kml_to_geojson(zf.read(name).decode("utf-8"))
                        if result:
                            return result
    except Exception:
        pass
    return None


def _wkt_from_project_layers(db: Session, project_id: int, tenant_id: int, layer_id: int | None = None) -> str | None:
    """Extract WKT polygon from a specific layer or all project vector layers."""
    if layer_id:
        layer = db.query(Layer).filter(
            Layer.id == layer_id, Layer.project_id == project_id, Layer.tenant_id == tenant_id
        ).first()
        layers = [layer] if layer else []
    else:
        layers = db.query(Layer).filter(
            Layer.project_id == project_id, Layer.tenant_id == tenant_id
        ).all()

    if not layers:
        return None

    from shapely.geometry import shape
    from shapely.ops import unary_union

    all_geoms = []
    for layer in layers:
        geojson_data = _layer_to_geojson(layer)
        if not geojson_data:
            continue
        features = geojson_data.get("features", [geojson_data])
        for f in features:
            geom_dict = f.get("geometry") or f
            if not geom_dict or not geom_dict.get("type"):
                continue
            try:
                all_geoms.append(shape(geom_dict))
            except Exception:
                continue

    if not all_geoms:
        return None

    union = unary_union(all_geoms)
    if union.geom_type == "MultiPolygon" and len(union.geoms) == 1:
        union = union.geoms[0]
    return union.wkt


@router.post("/preprocess/download")
def preprocess_download(payload: DownloadRequest, db: Session = Depends(get_db), tenant_id: int = Depends(tenant_from_jwt)):
    project = db.query(Project).filter(Project.id == payload.project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.source == "sentinel-2":
        if not settings.copernicus_user or not settings.copernicus_password:
            raise HTTPException(status_code=500, detail="Copernicus credentials not configured")
        if not payload.start_date or not payload.end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required for Sentinel-2")

        wkt = _wkt_from_project_layers(db, payload.project_id, tenant_id, payload.layer_id)
        if not wkt:
            raise HTTPException(status_code=400, detail="No vector layer found in project to define download area. Upload a lote first.")

        project_slug = project.name.replace(" ", "_").lower()
        out_dir = _tenant_storage(tenant_id, payload.project_id, "downloads") / project_slug
        out_dir.mkdir(parents=True, exist_ok=True)

        raster = RasterLayer(
            project_id=payload.project_id,
            tenant_id=tenant_id,
            name=f"Sentinel-2 ({payload.start_date} a {payload.end_date})",
            file_path=str(out_dir),
            cog_path=None,
            raster_metadata={
                "source": "sentinel-2",
                "type": "download",
                "status": "downloading",
                "start_date": payload.start_date,
                "end_date": payload.end_date,
            },
        )
        db.add(raster)
        db.commit()
        db.refresh(raster)

        from app.tasks.jobs import download_sentinel2

        async_result = download_sentinel2.delay(
            wkt,
            payload.start_date,
            payload.end_date,
            str(out_dir),
            settings.copernicus_user,
            settings.copernicus_password,
            raster.id,
            settings.database_url,
        )
        raster.raster_metadata = {
            **(raster.raster_metadata or {}),
            "celery_task_id": async_result.id,
        }
        db.commit()

        return {
            "status": "downloading",
            "raster_layer_id": raster.id,
            "task_id": async_result.id,
            "output_dir": str(out_dir),
        }

    out_dir = _tenant_storage(tenant_id, payload.project_id, "rasters")
    out_path = out_dir / f"download_{payload.source}_{uuid.uuid4().hex}.tif"

    width, height = 256, 256
    data = (np.random.rand(height, width) * 255).astype("uint8")
    transform = rasterio.transform.from_origin(-74.2, 4.9, 0.0005, 0.0005)
    with rasterio.open(
        out_path, "w", driver="GTiff", height=height, width=width,
        count=1, dtype=data.dtype, crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)

    raster = RasterLayer(
        project_id=payload.project_id,
        tenant_id=tenant_id,
        name=f"{payload.source}.tif",
        file_path=str(out_path),
        cog_path=str(out_path),
        raster_metadata={"source": payload.source, "type": "download"},
    )
    db.add(raster)
    db.commit()
    db.refresh(raster)
    return {"status": "ok", "raster_layer_id": raster.id}


@router.get("/preprocess/sentinel-status/{project_id}/{raster_id}")
def sentinel_download_status(
    project_id: int,
    raster_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    """Poll Sentinel-2 download progress (Celery + DB metadata)."""
    from celery.result import AsyncResult

    from app.tasks.celery_app import celery_app

    raster = (
        db.query(RasterLayer)
        .filter(
            RasterLayer.id == raster_id,
            RasterLayer.project_id == project_id,
            RasterLayer.tenant_id == tenant_id,
        )
        .first()
    )
    if not raster:
        raise HTTPException(status_code=404, detail="Raster not found")

    meta = raster.raster_metadata or {}
    db_status = meta.get("status")
    progress = int(meta.get("progress", 0) or 0)
    message = meta.get("progress_message") or "Preparando descarga..."

    if db_status == "completed":
        return {
            "ui_status": "completed",
            "progress": 100,
            "message": meta.get("progress_message") or "Descarga terminada",
            "total_downloaded": meta.get("total_downloaded"),
            "total_size_mb": meta.get("total_size_mb"),
        }

    if db_status == "failed":
        return {
            "ui_status": "failed",
            "progress": 0,
            "message": meta.get("error") or meta.get("progress_message") or "Error en descarga",
        }

    task_id = meta.get("celery_task_id")
    if task_id:
        ar = AsyncResult(task_id, app=celery_app)
        if ar.state == "PROGRESS" and isinstance(ar.info, dict):
            return {
                "ui_status": "downloading",
                "progress": int(ar.info.get("progress", progress)),
                "message": ar.info.get("message", message),
                "celery_state": ar.state,
            }
        if ar.state in ("PENDING", "STARTED"):
            return {
                "ui_status": "downloading",
                "progress": max(progress, 0),
                "message": "En cola o iniciando...",
                "celery_state": ar.state,
            }
        if ar.state == "SUCCESS":
            return {
                "ui_status": "completed",
                "progress": 100,
                "message": "Descarga terminada",
                "celery_state": ar.state,
            }
        if ar.state == "FAILURE":
            err = str(ar.result) if ar.result else "Error en la tarea"
            return {
                "ui_status": "failed",
                "progress": 0,
                "message": err,
                "celery_state": ar.state,
            }

    return {
        "ui_status": "downloading",
        "progress": progress,
        "message": message,
    }


@router.post("/preprocess/crop")
def preprocess_crop(payload: CropRequest, db: Session = Depends(get_db), tenant_id: int = Depends(tenant_from_jwt)):
    raster = _get_project_raster(db, tenant_id, payload.project_id, payload.raster_layer_id)
    src_path = _existing_raster_path(raster)
    out_path = _tenant_storage(tenant_id, payload.project_id, "preprocess") / f"crop_{uuid.uuid4().hex}.tif"

    ratio = max(0.2, min(1.0, payload.crop_ratio))
    with rasterio.open(src_path) as src:
        h = int(src.height * ratio)
        w = int(src.width * ratio)
        r0 = (src.height - h) // 2
        c0 = (src.width - w) // 2
        window = rasterio.windows.Window(c0, r0, w, h)
        data = src.read(window=window)
        profile = src.profile.copy()
        profile.update(height=h, width=w, transform=src.window_transform(window))
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data)
    return {"status": "ok"}


@router.post("/preprocess/indices")
def preprocess_indices(
    payload: IndicesRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    raster = _get_project_raster(db, tenant_id, payload.project_id, payload.raster_layer_id)
    src_path = _existing_raster_path(raster)
    out_path = _tenant_storage(tenant_id, payload.project_id, "preprocess") / f"{payload.index_type.lower()}_{uuid.uuid4().hex}.tif"

    with rasterio.open(src_path) as src:
        band = src.read(1).astype("float32")
        nir = band
        red = np.clip(band * 0.7, 1, 255)
        green = np.clip(band * 0.5, 1, 255)
        if payload.index_type.upper() == "NDVI":
            idx = (nir - red) / (nir + red + 1e-6)
        elif payload.index_type.upper() == "EVI":
            idx = 2.5 * (nir - red) / (nir + 6 * red - 7.5 * green + 1)
        elif payload.index_type.upper() == "NDWI":
            idx = (green - nir) / (green + nir + 1e-6)
        else:
            raise HTTPException(status_code=400, detail="Unsupported index type")
        profile = src.profile.copy()
        profile.update(dtype="float32", count=1)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(idx.astype("float32"), 1)
    return {"status": "ok", "index_type": payload.index_type.upper()}


@router.post("/preprocess/stack")
def preprocess_stack(payload: StackRequest, db: Session = Depends(get_db), tenant_id: int = Depends(tenant_from_jwt)):
    rasters = (
        db.query(RasterLayer)
        .filter(RasterLayer.project_id == payload.project_id, RasterLayer.tenant_id == tenant_id)
        .order_by(RasterLayer.id.desc())
        .all()
    )
    if not rasters:
        raise HTTPException(status_code=404, detail="No rasters available")
    if payload.mode.lower() == "visualizar":
        return {
            "status": "ok",
            "mode": "visualizar",
            "rasters": [{"id": r.id, "name": r.name} for r in rasters[:10]],
        }
    if payload.mode.lower() == "gif":
        out_path = _tenant_storage(tenant_id, payload.project_id, "preprocess") / f"stack_gif_manifest_{uuid.uuid4().hex}.json"
        out_path.write_text(
            json.dumps([{"id": r.id, "name": r.name} for r in rasters[:12]], indent=2),
            encoding="utf-8",
        )
        return {"status": "ok", "mode": "gif"}
    raise HTTPException(status_code=400, detail="Unsupported stack mode")


@router.post("/preprocess/cluster")
def preprocess_cluster(
    payload: ClusterRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    raster = _get_project_raster(db, tenant_id, payload.project_id, payload.raster_layer_id)
    src_path = _existing_raster_path(raster)
    out_path = _tenant_storage(tenant_id, payload.project_id, "preprocess") / f"cluster_{uuid.uuid4().hex}.tif"

    k = max(2, min(10, payload.clusters))
    with rasterio.open(src_path) as src:
        band = src.read(1).astype("float32")
        bins = np.quantile(band, np.linspace(0, 1, k + 1))
        classified = np.digitize(band, bins[1:-1]).astype("uint8")
        profile = src.profile.copy()
        profile.update(dtype="uint8", count=1)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(classified, 1)
    return {"status": "ok", "clusters": k}
