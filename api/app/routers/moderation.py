"""
Router /moderation — File de modération linguistique (Phase 8)

Accès : rôle lingwis ou admin (require_lingwis)

Endpoints :
  GET   /moderation/queue           Liste les candidats (filtrables, paginés)
  GET   /moderation/stats           Comptages par statut et par type
  PATCH /moderation/{candidate_id}  Approuver / rejeter / fusionner un candidat
  PUT   /moderation/mots/{mot_id}   Modifier un mot approuvé
  DELETE /moderation/mots/{mot_id}  Supprimer un mot approuvé
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import PaginationParams, require_lingwis
from ..models.models import (
    CandidateStatus,
    Definition,
    LinguisticEntry,
    ModerationCandidate,
    Mot,
    Traduction,
)
from ..schemas.schemas import ModerationCandidateOut, ModerationReview

router = APIRouter(prefix="/moderation", tags=["moderation"])


class MotUpdate(BaseModel):
    mot_creole:     Optional[str] = None
    phonetique:     Optional[str] = None
    categorie_gram: Optional[str] = None


# Valeurs d'enum categorie_gram acceptées (de models.py)
_VALID_POS = {
    "nom", "vèb", "adjektif", "advèb", "pwonon",
    "prépoziksyon", "konjonksyon", "entèjèksyon", "atik", "lòt",
}


# ---------------------------------------------------------------------------
# GET /moderation/queue
# ---------------------------------------------------------------------------

@router.get("/queue", response_model=dict, summary="File de modération")
def get_queue(
    status: str = "pending",
    candidate_type: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    _user=Depends(require_lingwis),
):
    """Retourne les candidats paginés, filtrables par statut et type."""
    query = db.query(ModerationCandidate).filter(
        ModerationCandidate.status == status
    )
    if candidate_type:
        query = query.filter(ModerationCandidate.candidate_type == candidate_type)

    total = query.count()
    items = (
        query.order_by(ModerationCandidate.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
        .all()
    )

    return {
        "total": total,
        "page": pagination.page,
        "limit": pagination.limit,
        "results": [ModerationCandidateOut.model_validate(c) for c in items],
    }


# ---------------------------------------------------------------------------
# GET /moderation/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=dict, summary="Statistiques de modération")
def get_stats(
    db: Session = Depends(get_db),
    _user=Depends(require_lingwis),
):
    """Comptages par statut et par type de candidat."""
    from sqlalchemy import func

    by_status = (
        db.query(ModerationCandidate.status, func.count(ModerationCandidate.id))
        .group_by(ModerationCandidate.status)
        .all()
    )
    by_type = (
        db.query(ModerationCandidate.candidate_type, func.count(ModerationCandidate.id))
        .group_by(ModerationCandidate.candidate_type)
        .all()
    )

    def _val(v):
        return v.value if hasattr(v, "value") else str(v)

    return {
        "by_status": {_val(row[0]): row[1] for row in by_status},
        "by_type":   {_val(row[0]): row[1] for row in by_type},
        "total":     sum(row[1] for row in by_status),
    }


# ---------------------------------------------------------------------------
# PATCH /moderation/{candidate_id}
# ---------------------------------------------------------------------------

@router.patch("/{candidate_id}", response_model=dict, summary="Réviser un candidat")
def review_candidate(
    candidate_id: int,
    review: ModerationReview,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_lingwis),
):
    """Approuver, rejeter ou fusionner un candidat linguistique.

    - **approved** : crée une entrée dans `mots` + `linguistic_entries`
    - **merged**   : rattache la variante à un mot existant (`merge_with_mot_id`)
    - **rejected** : met à jour le statut avec une note optionnelle
    """
    if review.status not in ("approved", "rejected", "merged"):
        raise HTTPException(
            status_code=422,
            detail="status doit être 'approved', 'rejected' ou 'merged'",
        )

    candidate = db.get(ModerationCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    if candidate.status != CandidateStatus.pending:
        raise HTTPException(
            status_code=409,
            detail=f"Candidat déjà traité (statut : {candidate.status})",
        )

    now = datetime.utcnow()

    if review.status == "approved":
        mot_id = _approve(candidate, review, current_user.id, db)
        candidate.status = CandidateStatus.approved
        candidate.linked_mot_id = mot_id

    elif review.status == "merged":
        if not review.merge_with_mot_id:
            raise HTTPException(
                status_code=422,
                detail="merge_with_mot_id requis pour status='merged'",
            )
        mot_id = _merge(candidate, review, current_user.id, db)
        candidate.status = CandidateStatus.merged
        candidate.linked_mot_id = mot_id

    else:  # rejected
        candidate.status = CandidateStatus.rejected

    candidate.reviewed_by = current_user.id
    candidate.reviewed_at = now
    candidate.reviewer_note = review.reviewer_note
    db.commit()

    # Rebuild TF-IDF en arrière-plan si un mot a été ajouté au dictionnaire
    if review.status in ("approved", "merged") and candidate.linked_mot_id:
        mot = db.get(Mot, candidate.linked_mot_id)
        if mot:
            fefen_entry = _mot_to_fefen_entry(mot, candidate)
            fefen = getattr(request.app.state, "fefen", None)
            if fefen is not None:
                background_tasks.add_task(fefen.add_entry, fefen_entry)

    return {
        "candidate_id": candidate_id,
        "status": review.status,
        "linked_mot_id": candidate.linked_mot_id,
    }


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _mot_to_fefen_entry(mot: Mot, candidate: ModerationCandidate) -> dict:
    """Convertit un Mot approuvé en entrée compatible avec l'index Fèfèn."""
    definition = candidate.definition_fr or candidate.definition_kr or ""
    return {
        "id":             f"conv_{candidate.id}",
        "mot":            mot.mot_creole,
        "definition":     definition,
        "categorie_gram": mot.categorie_gram or "",
        "source":         "conversation",
        "language":       "crm",
        "licence":        "CC BY-SA 4.0",
    }


def _resolve_pos(pos_raw: Optional[str]) -> Optional[str]:
    """Retourne une valeur enum valide pour categorie_gram, ou None."""
    if pos_raw and pos_raw.lower() in _VALID_POS:
        return pos_raw.lower()
    return None


def _approve(candidate: ModerationCandidate, review: ModerationReview, reviewer_id: int, db: Session) -> int:
    """Crée le Mot + éventuellement Definition/Traduction + LinguisticEntry."""
    word = review.word_override or candidate.word
    if not word:
        raise HTTPException(status_code=422, detail="Impossible d'approuver : mot manquant")

    # Vérifier unicité (le mot peut déjà exister si race condition)
    existing_mot = db.query(Mot).filter(Mot.mot_creole == word).first()
    if existing_mot:
        mot_id = existing_mot.id
    else:
        pos = _resolve_pos(review.pos_override or candidate.pos)
        mot = Mot(
            mot_creole=word,
            phonetique=candidate.phonetic,
            categorie_gram=pos,
            valide=True,
        )
        db.add(mot)
        db.flush()  # obtenir l'id sans commit
        mot_id = mot.id

        # Définition créole
        definition_kr = review.definition_kr or candidate.definition_kr
        if definition_kr:
            db.add(Definition(mot_id=mot_id, definition=definition_kr, valide=True))

        # Traduction français
        definition_fr = review.definition_fr or candidate.definition_fr
        if definition_fr:
            db.add(Traduction(
                mot_id=mot_id,
                langue_source="fr",
                langue_cible="crm",
                texte_source=definition_fr,
                texte_cible=word,
                valide=True,
            ))

    _create_linguistic_entry(mot_id, candidate.id, reviewer_id, db)
    return mot_id


def _merge(candidate: ModerationCandidate, review: ModerationReview, reviewer_id: int, db: Session) -> int:
    """Rattache la variante à un mot existant et crée un LinguisticEntry."""
    mot = db.get(Mot, review.merge_with_mot_id)
    if mot is None:
        raise HTTPException(
            status_code=404,
            detail=f"Mot {review.merge_with_mot_id} introuvable pour la fusion",
        )
    _create_linguistic_entry(mot.id, candidate.id, reviewer_id, db)
    return mot.id


def _create_linguistic_entry(
    mot_id: int,
    candidate_id: int,
    reviewer_id: Optional[int],
    db: Session,
) -> None:
    entry = LinguisticEntry(
        mot_id=mot_id,
        candidate_id=candidate_id,
        source="conversation",
        validated_by=reviewer_id,
    )
    db.add(entry)


# ---------------------------------------------------------------------------
# PUT /moderation/mots/{mot_id} — modifier un mot approuvé
# ---------------------------------------------------------------------------

@router.put("/mots/{mot_id}", response_model=dict, summary="Modifier un mot approuvé")
def update_mot(
    mot_id: int,
    data: MotUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_lingwis),
):
    """Permet à un lingwis de corriger un mot créé via l'approbation d'un candidat."""
    mot = db.get(Mot, mot_id)
    if mot is None:
        raise HTTPException(status_code=404, detail=f"Mot {mot_id} introuvable")

    if data.mot_creole:
        mot.mot_creole = data.mot_creole
    if data.phonetique is not None:
        mot.phonetique = data.phonetique or None
    if data.categorie_gram is not None:
        mot.categorie_gram = _resolve_pos(data.categorie_gram)

    # Synchroniser le candidat lié pour que la queue reflète les changements
    candidate = db.query(ModerationCandidate).filter(
        ModerationCandidate.linked_mot_id == mot_id
    ).first()
    if candidate:
        if data.mot_creole:
            candidate.word = data.mot_creole
        if data.phonetique is not None:
            candidate.phonetic = data.phonetique or None
        if data.categorie_gram is not None:
            candidate.pos = _resolve_pos(data.categorie_gram)

    db.commit()
    db.refresh(mot)
    return {
        "id":             mot.id,
        "mot_creole":     mot.mot_creole,
        "phonetique":     mot.phonetique,
        "categorie_gram": mot.categorie_gram,
        "valide":         mot.valide,
    }


# ---------------------------------------------------------------------------
# DELETE /moderation/mots/{mot_id} — supprimer un mot approuvé
# ---------------------------------------------------------------------------

@router.delete("/mots/{mot_id}", status_code=204, summary="Supprimer un mot approuvé")
def delete_mot(
    mot_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_lingwis),
):
    """Supprime un mot du dictionnaire (accessible aux lingwis et admins)."""
    mot = db.get(Mot, mot_id)
    if mot is None:
        raise HTTPException(status_code=404, detail=f"Mot {mot_id} introuvable")

    # Détacher les candidats liés avant suppression (contrainte FK)
    db.query(ModerationCandidate).filter(
        ModerationCandidate.linked_mot_id == mot_id
    ).update({"linked_mot_id": None, "status": CandidateStatus.pending})

    db.delete(mot)
    db.commit()
