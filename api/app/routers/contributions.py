"""
Router /contributions — CRUD des contributions utilisateur
Protégé par JWT (rôle contributeur ou admin).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models.models import Contribution, Contributeur, User
from ..schemas.schemas import ContributionCreate, ContributionOut

router = APIRouter(prefix="/contributions", tags=["contributions"])


@router.get("", response_model=list[ContributionOut])
def list_contributions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContributionOut]:
    """Liste les contributions de l'utilisateur connecté."""
    contrib = db.query(Contributeur).filter(Contributeur.user_id == current_user.id).first()
    if not contrib:
        return []
    items = (
        db.query(Contribution)
        .filter(Contribution.contributeur_id == contrib.id)
        .order_by(Contribution.created_at.desc())
        .all()
    )
    return [ContributionOut.from_contribution(c) for c in items]


@router.post("", response_model=ContributionOut, status_code=201)
def submit_contribution(
    body: ContributionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContributionOut:
    """Soumet une nouvelle contribution."""
    contrib = db.query(Contributeur).filter(Contributeur.user_id == current_user.id).first()
    if not contrib:
        raise HTTPException(status_code=404, detail="Profil contributeur introuvable")
    c = Contribution(
        contributeur_id=contrib.id,
        table_cible=body.table_cible,
        entite_id=body.entite_id,
        type_action="ajout",
        contenu_apres=body.contenu_apres,
        statut="en_attente",
    )
    db.add(c)
    contrib.nb_contrib += 1
    db.commit()
    db.refresh(c)
    return ContributionOut.from_contribution(c)


@router.delete("/{contribution_id}", status_code=204)
def delete_contribution(
    contribution_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Supprime une contribution de l'utilisateur connecté."""
    contrib = db.query(Contributeur).filter(Contributeur.user_id == current_user.id).first()
    if not contrib:
        raise HTTPException(status_code=404, detail="Profil contributeur introuvable")
    c = (
        db.query(Contribution)
        .filter(
            Contribution.id == contribution_id,
            Contribution.contributeur_id == contrib.id,
        )
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contribution introuvable")
    db.delete(c)
    db.commit()
