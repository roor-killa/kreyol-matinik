"""
Router /media — Ressources audio et vidéo
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import PaginationParams
from ..models.models import Media
from ..schemas.schemas import MediaOut, MediaResponse


router = APIRouter(prefix="/media", tags=["media"])


@router.get("", response_model=MediaResponse, summary="Liste les médias")
def list_media(
    type: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> MediaResponse:
    """Liste les fichiers audio et vidéo, avec filtre optionnel par type."""
    query = db.query(Media)
    if type:
        query = query.filter(Media.type == type)

    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()

    return MediaResponse(
        total=total,
        results=[MediaOut.from_orm_media(m) for m in items],
    )


@router.get("/{media_id}", response_model=MediaOut, summary="Détail d'un média")
def get_media(media_id: int, db: Session = Depends(get_db)) -> MediaOut:
    """Retourne les métadonnées d'un média."""
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=404, detail=f"Média introuvable (id={media_id})")
    return MediaOut.from_orm_media(media)
