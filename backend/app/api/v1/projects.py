import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, tenant_from_jwt
from app.core.config import settings
from app.db.session import get_db
from app.models.models import AIResult, Layer, Project, RasterLayer, User
from app.api.v1.helpers import project_downloads_slug
from app.schemas.schemas import ProjectCreate, ProjectUpdate

router = APIRouter()


def _rewrite_raster_paths_after_downloads_move(
    db: Session,
    tenant_id: int,
    project_id: int,
    old_dir: Path,
    new_dir: Path,
) -> None:
    """Tras mover downloads/<slug>, actualizar file_path/cog_path que apuntaban bajo esa carpeta."""
    try:
        old_root = old_dir.resolve()
        new_root = new_dir.resolve()
    except OSError:
        return

    def rewrite(stored: str | None) -> str | None:
        if not stored:
            return stored
        try:
            p = Path(stored).resolve()
            rel = p.relative_to(old_root)
        except (ValueError, OSError):
            return stored
        return str(new_root / rel)

    for r in (
        db.query(RasterLayer)
        .filter(RasterLayer.project_id == project_id, RasterLayer.tenant_id == tenant_id)
        .all()
    ):
        new_fp = rewrite(r.file_path)
        if new_fp != r.file_path:
            r.file_path = new_fp
        if r.cog_path:
            new_cog = rewrite(r.cog_path)
            if new_cog != r.cog_path:
                r.cog_path = new_cog


@router.post("/projects")
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = Project(name=payload.name, tenant_id=user.tenant_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name}


@router.get("/projects")
def list_projects(db: Session = Depends(get_db), tenant_id: int = Depends(tenant_from_jwt)):
    projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
    return [{"id": p.id, "name": p.name} for p in projects]


@router.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(tenant_from_jwt),
):
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    old_name = project.name
    new_name = payload.name
    if new_name == old_name:
        return {"id": project.id, "name": project.name}

    old_slug = project_downloads_slug(old_name)
    new_slug = project_downloads_slug(new_name)
    if old_slug != new_slug:
        downloads_root = Path(settings.storage_path) / f"tenant_{tenant_id}" / f"project_{project_id}" / "downloads"
        old_path = downloads_root / old_slug
        new_path = downloads_root / new_slug
        if old_path.exists():
            if new_path.exists():
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una carpeta de descargas para el nuevo nombre. Elige otro nombre o elimina la carpeta duplicada en el servidor.",
                )
            downloads_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            _rewrite_raster_paths_after_downloads_move(db, tenant_id, project_id, old_path, new_path)

    project.name = new_name
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name}


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), tenant_id: int = Depends(tenant_from_jwt)):
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.query(AIResult).filter(AIResult.project_id == project_id, AIResult.tenant_id == tenant_id).delete()
    db.query(RasterLayer).filter(RasterLayer.project_id == project_id, RasterLayer.tenant_id == tenant_id).delete()
    db.query(Layer).filter(Layer.project_id == project_id, Layer.tenant_id == tenant_id).delete()
    db.delete(project)
    db.commit()
    storage_dir = Path(settings.storage_path) / f"tenant_{tenant_id}" / f"project_{project_id}"
    if storage_dir.exists():
        shutil.rmtree(storage_dir, ignore_errors=True)
    return {"status": "ok", "deleted_project_id": project_id}
