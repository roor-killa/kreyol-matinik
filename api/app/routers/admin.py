"""
Router /admin — Modification directe des données (mots, définitions, corpus, expressions)

Tous les endpoints requièrent X-Api-Key.
Destiné à l'interface d'administration du frontend.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..dependencies import require_admin
from ..models.models import Contribution, Contributeur, Corpus, Definition, Expression, Mot, Traduction
from ..schemas.schemas import (
    ContributionOut,
    CorpusOut,
    CorpusUpdate,
    DefinitionCreate,
    DefinitionUpdate,
    DefinitionWithId,
    ExpressionOut,
    ExpressionUpdate,
    MotDetail,
    MotUpdate,
    TraductionUpdate,
    TraductionWithId,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


# ===========================================================================
# Mots
# ===========================================================================

@router.put(
    "/mots/{mot_id}",
    response_model=MotDetail,
    summary="Modifier un mot 🔒",
)
def update_mot(mot_id: int, body: MotUpdate, db: Session = Depends(get_db)) -> MotDetail:
    mot = db.get(Mot, mot_id)
    if not mot:
        raise HTTPException(status_code=404, detail=f"Mot introuvable (id={mot_id})")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mot, field, value)
    db.commit()
    db.refresh(mot)
    mot = (
        db.query(Mot)
        .options(joinedload(Mot.traductions), joinedload(Mot.definitions), joinedload(Mot.source))
        .filter(Mot.id == mot_id)
        .first()
    )
    return MotDetail.from_orm_mot(mot)


@router.delete(
    "/mots/{mot_id}",
    status_code=204,
    summary="Supprimer un mot 🔒",
)
def delete_mot(mot_id: int, db: Session = Depends(get_db)) -> None:
    mot = db.get(Mot, mot_id)
    if not mot:
        raise HTTPException(status_code=404, detail=f"Mot introuvable (id={mot_id})")
    db.delete(mot)
    db.commit()


# ===========================================================================
# Traductions
# ===========================================================================

@router.put(
    "/traductions/{trad_id}",
    response_model=TraductionWithId,
    summary="Modifier une traduction 🔒",
)
def update_traduction(trad_id: int, body: TraductionUpdate, db: Session = Depends(get_db)) -> TraductionWithId:
    t = db.get(Traduction, trad_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Traduction introuvable (id={trad_id})")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return TraductionWithId(
        id=t.id,
        langue_source=t.langue_source,
        langue_cible=t.langue_cible,
        texte_source=t.texte_source,
        texte_cible=t.texte_cible,
    )


# ===========================================================================
# Définitions
# ===========================================================================

@router.post(
    "/mots/{mot_id}/definitions",
    response_model=DefinitionWithId,
    status_code=201,
    summary="Ajouter une définition à un mot 🔒",
)
def create_definition(
    mot_id: int, body: DefinitionCreate, db: Session = Depends(get_db)
) -> DefinitionWithId:
    if not db.get(Mot, mot_id):
        raise HTTPException(status_code=404, detail=f"Mot introuvable (id={mot_id})")
    d = Definition(mot_id=mot_id, definition=body.definition, exemple=body.exemple)
    db.add(d)
    db.commit()
    db.refresh(d)
    return DefinitionWithId(id=d.id, definition=d.definition, exemple=d.exemple)


@router.get(
    "/mots/{mot_id}/definitions",
    response_model=List[DefinitionWithId],
    summary="Liste des définitions d'un mot avec leurs IDs 🔒",
)
def list_definitions(mot_id: int, db: Session = Depends(get_db)) -> List[DefinitionWithId]:
    mot = db.get(Mot, mot_id)
    if not mot:
        raise HTTPException(status_code=404, detail=f"Mot introuvable (id={mot_id})")
    defs = db.query(Definition).filter(Definition.mot_id == mot_id).all()
    return [DefinitionWithId(id=d.id, definition=d.definition, exemple=d.exemple) for d in defs]


@router.put(
    "/mots/{mot_id}/definitions/{def_id}",
    response_model=DefinitionWithId,
    summary="Modifier une définition 🔒",
)
def update_definition(
    mot_id: int, def_id: int, body: DefinitionUpdate, db: Session = Depends(get_db)
) -> DefinitionWithId:
    d = (
        db.query(Definition)
        .filter(Definition.id == def_id, Definition.mot_id == mot_id)
        .first()
    )
    if not d:
        raise HTTPException(status_code=404, detail=f"Définition introuvable (id={def_id})")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(d, field, value)
    db.commit()
    db.refresh(d)
    return DefinitionWithId(id=d.id, definition=d.definition, exemple=d.exemple)


@router.delete(
    "/mots/{mot_id}/definitions/{def_id}",
    status_code=204,
    summary="Supprimer une définition 🔒",
)
def delete_definition(mot_id: int, def_id: int, db: Session = Depends(get_db)) -> None:
    d = (
        db.query(Definition)
        .filter(Definition.id == def_id, Definition.mot_id == mot_id)
        .first()
    )
    if not d:
        raise HTTPException(status_code=404, detail=f"Définition introuvable (id={def_id})")
    db.delete(d)
    db.commit()


# ===========================================================================
# Corpus
# ===========================================================================

@router.put(
    "/corpus/{corpus_id}",
    response_model=CorpusOut,
    summary="Modifier une entrée corpus 🔒",
)
def update_corpus(corpus_id: int, body: CorpusUpdate, db: Session = Depends(get_db)) -> CorpusOut:
    c = db.get(Corpus, corpus_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"Entrée corpus introuvable (id={corpus_id})")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return CorpusOut.from_orm_corpus(c)


@router.delete(
    "/corpus/{corpus_id}",
    status_code=204,
    summary="Supprimer une entrée corpus 🔒",
)
def delete_corpus(corpus_id: int, db: Session = Depends(get_db)) -> None:
    c = db.get(Corpus, corpus_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"Entrée corpus introuvable (id={corpus_id})")
    db.delete(c)
    db.commit()


# ===========================================================================
# Expressions
# ===========================================================================

@router.put(
    "/expressions/{expr_id}",
    response_model=ExpressionOut,
    summary="Modifier une expression 🔒",
)
def update_expression(
    expr_id: int, body: ExpressionUpdate, db: Session = Depends(get_db)
) -> ExpressionOut:
    e = db.get(Expression, expr_id)
    if not e:
        raise HTTPException(status_code=404, detail=f"Expression introuvable (id={expr_id})")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    db.commit()
    db.refresh(e)
    return ExpressionOut.from_orm_expr(e)


@router.delete(
    "/expressions/{expr_id}",
    status_code=204,
    summary="Supprimer une expression 🔒",
)
def delete_expression(expr_id: int, db: Session = Depends(get_db)) -> None:
    e = db.get(Expression, expr_id)
    if not e:
        raise HTTPException(status_code=404, detail=f"Expression introuvable (id={expr_id})")
    db.delete(e)
    db.commit()


# ===========================================================================
# Modération des contributions
# ===========================================================================

@router.get(
    "/contributions",
    response_model=List[ContributionOut],
    summary="Lister les contributions en attente 🔒",
)
def list_pending_contributions(db: Session = Depends(get_db)) -> List[ContributionOut]:
    items = (
        db.query(Contribution)
        .filter(Contribution.statut == "en_attente")
        .order_by(Contribution.created_at.desc())
        .all()
    )
    return [ContributionOut.from_contribution(c) for c in items]


@router.put(
    "/contributions/{contribution_id}/validate",
    summary="Valider une contribution 🔒",
)
def validate_contribution(contribution_id: int, db: Session = Depends(get_db)) -> dict:
    c = db.get(Contribution, contribution_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contribution introuvable")
    c.statut = "validé"
    db.commit()
    return {"message": "Contribution validée"}


@router.put(
    "/contributions/{contribution_id}/reject",
    summary="Rejeter une contribution 🔒",
)
def reject_contribution(contribution_id: int, db: Session = Depends(get_db)) -> dict:
    c = db.get(Contribution, contribution_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contribution introuvable")
    c.statut = "rejeté"
    db.commit()
    return {"message": "Contribution rejetée"}
