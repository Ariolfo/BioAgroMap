import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import tenant_from_jwt
from app.api.v1.helpers import _tenant_storage, validate_upload_size
from app.db.session import get_db
from app.models.models import Project, RasterLayer
from app.tasks.jobs import process_raster

router = APIRouter()


def _project_downloads_dir(tenant_id: int, project_id: int, project_name: str) -> Path:
    slug = project_name.replace(" ", "_").lower()
    return _tenant_storage(tenant_id, project_id, "downloads") / slug


@router.get("/raster/project-downloads/{project_id}")
def list_project_download_files(
    project_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    """List files in the project's Sentinel-2 download folder (not shown as map layers until imported)."""
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    d = _project_downloads_dir(tenant_id, project_id, project.name)
    if not d.is_dir():
        return {"files": [], "folder": project.name}
    allowed = {".tif", ".tiff", ".jp2", ".zip", ".png", ".jpg", ".jpeg"}
    files = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.suffix.lower() in allowed:
            try:
                sz = p.stat().st_size
            except OSError:
                continue
            files.append({"name": p.name, "size_bytes": sz, "ext": p.suffix.lower()})
    return {"files": files, "folder": project.name}


@router.post("/raster/import-from-downloads")
def import_raster_from_downloads(
    project_id: int = Query(..., description="Project ID"),
    filename: str = Query(..., description="File name inside project download folder"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    """Copy a file from the project download folder into rasters and register as a normal raster layer."""
    safe = Path(filename).name
    if safe != filename or ".." in safe:
        raise HTTPException(status_code=400, detail="Invalid filename")

    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    src_dir = _project_downloads_dir(tenant_id, project_id, project.name)
    src = (src_dir / safe).resolve()
    base = src_dir.resolve()
    if not str(src).startswith(str(base)) or not src.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = src.suffix.lower()
    if ext not in {".tif", ".tiff", ".jp2", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden importar como capa raster: GeoTIFF, JP2 o imagen. Para .ZIP use extracción manual.",
        )

    out_dir = _tenant_storage(tenant_id, project_id, "rasters")
    destination = out_dir / f"{uuid.uuid4().hex}{ext}"
    shutil.copy2(src, destination)
    cog_path = out_dir / f"{destination.stem}_cog.tif"
    process_raster.delay(str(destination), str(cog_path))
    raster = RasterLayer(
        project_id=project_id,
        tenant_id=tenant_id,
        name=safe,
        file_path=str(destination),
        cog_path=str(cog_path),
        raster_metadata={
            "source_name": safe,
            "status": "processing",
            "imported_from": "project_downloads",
        },
    )
    db.add(raster)
    db.commit()
    db.refresh(raster)
    return {"raster_layer_id": raster.id, "name": safe}


@router.post("/upload-raster")
async def upload_raster(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await validate_upload_size(file)
    ext = Path(file.filename).suffix.lower()
    if ext not in {".tif", ".tiff", ".jp2", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Unsupported raster format")
    out_dir = _tenant_storage(tenant_id, project_id, "rasters")
    destination = out_dir / f"{uuid.uuid4().hex}{ext}"
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    cog_path = out_dir / f"{destination.stem}_cog.tif"
    process_raster.delay(str(destination), str(cog_path))
    raster = RasterLayer(
        project_id=project_id,
        tenant_id=tenant_id,
        name=file.filename,
        file_path=str(destination),
        cog_path=str(cog_path),
        raster_metadata={"source_name": file.filename, "status": "processing"},
    )
    db.add(raster)
    db.commit()
    db.refresh(raster)
    return {"raster_layer_id": raster.id}


@router.get("/raster/{project_id}")
def list_rasters(project_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(tenant_from_jwt)):
    rasters = (
        db.query(RasterLayer)
        .filter(RasterLayer.project_id == project_id, RasterLayer.tenant_id == tenant_id)
        .all()
    )
    return [{"id": r.id, "name": r.name, "metadata": r.raster_metadata} for r in rasters]


@router.delete("/raster/{project_id}/{raster_id}")
def delete_raster(
    project_id: int,
    raster_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    raster = (
        db.query(RasterLayer)
        .filter(RasterLayer.id == raster_id, RasterLayer.project_id == project_id, RasterLayer.tenant_id == tenant_id)
        .first()
    )
    if not raster:
        raise HTTPException(status_code=404, detail="Raster layer not found")
    for p in [raster.file_path, raster.cog_path]:
        if p:
            fp = Path(p)
            if fp.exists():
                fp.unlink(missing_ok=True)
    db.delete(raster)
    db.commit()
    return {"status": "ok", "deleted_raster_id": raster_id}
