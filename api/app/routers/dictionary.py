"""
Router /dictionary — Dictionnaire créole martiniquais

IMPORTANT — ordre des routes :
  /search et /random AVANT /{mot_id}
  pour éviter que FastAPI interprète "search"/"random" comme un entier.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..dependencies import PaginationParams, require_admin
from ..models.models import Expression, Mot
from ..schemas.schemas import (
    DictionarySearchResponse,
    ExpressionOut,
    ExpressionsResponse,
    MotCreate,
    MotDetail,
    MotSearchResult,
    MotUpdate,
)


router = APIRouter(prefix="/dictionary", tags=["dictionnaire"])


# ---------------------------------------------------------------------------
# GET /dictionary   — liste paginée
# ---------------------------------------------------------------------------

@router.get("", response_model=DictionarySearchResponse, summary="Liste du dictionnaire")
def list_dictionary(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> DictionarySearchResponse:
    """Retourne la liste paginée des mots du dictionnaire, triée alphabétiquement."""
    query = (
        db.query(Mot)
        .options(
            selectinload(Mot.traductions),
            selectinload(Mot.definitions),
            joinedload(Mot.source),
        )
        .order_by(func.lower(Mot.mot_creole))
    )
    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()
    return DictionarySearchResponse(
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        results=[MotSearchResult.from_orm_mot(m) for m in items],
    )


# ---------------------------------------------------------------------------
# GET /dictionary/expressions   (AVANT /{mot_id})
# ---------------------------------------------------------------------------

@router.get("/expressions", response_model=ExpressionsResponse, summary="Expressions et proverbes")
def list_expressions(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> ExpressionsResponse:
    """Liste les expressions figées, proverbes et locutions créoles du dictionnaire Confiant."""
    query = db.query(Expression).options(joinedload(Expression.source))
    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()
    return ExpressionsResponse(
        total=total,
        results=[ExpressionOut.from_orm_expr(e) for e in items],
    )


# ---------------------------------------------------------------------------
# GET /dictionary/search   (AVANT /{mot_id})
# ---------------------------------------------------------------------------

@router.get("/search", response_model=DictionarySearchResponse, summary="Recherche dans le dictionnaire")
def search_dictionary(
    q: str,
    lang: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> DictionarySearchResponse:
    """Recherche floue sur les mots créoles via pg_trgm (similarity).

    Requiert l'extension pg_trgm (PostgreSQL). Non disponible en SQLite.
    """
    similarity = func.similarity(Mot.mot_creole, q)

    query = (
        db.query(Mot)
        .options(
            selectinload(Mot.traductions),
            selectinload(Mot.definitions),
            joinedload(Mot.source),
        )
        .filter(similarity > 0.1)
        .order_by(similarity.desc())
    )

    # Filtre langue : si lang="fr", chercher dans les traductions texte_source
    if lang == "fr":
        from ..models.models import Traduction
        query = (
            db.query(Mot)
            .options(
                selectinload(Mot.traductions),
                selectinload(Mot.definitions),
                joinedload(Mot.source),
            )
            .join(Mot.traductions)
            .filter(
                Traduction.langue_source == "fr",
                func.similarity(Traduction.texte_source, q) > 0.1,
            )
            .order_by(func.similarity(Traduction.texte_source, q).desc())
        )

    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()

    return DictionarySearchResponse(
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        results=[MotSearchResult.from_orm_mot(m) for m in items],
    )


# ---------------------------------------------------------------------------
# GET /dictionary/random   (AVANT /{mot_id})
# ---------------------------------------------------------------------------

@router.get("/random", response_model=MotDetail, summary="Mot aléatoire")
def random_word(db: Session = Depends(get_db)) -> MotDetail:
    """Retourne une entrée aléatoire (mot du jour)."""
    mot = (
        db.query(Mot)
        .options(
            joinedload(Mot.traductions),
            joinedload(Mot.definitions),
            joinedload(Mot.source),
        )
        .order_by(func.random())
        .first()
    )
    if not mot:
        raise HTTPException(status_code=404, detail="Aucun mot dans le dictionnaire")
    return MotDetail.from_orm_mot(mot)


# ---------------------------------------------------------------------------
# GET /dictionary/{mot_id}
# ---------------------------------------------------------------------------

@router.get("/{mot_id}", response_model=MotDetail, summary="Détail d'un mot")
def get_word(mot_id: int, db: Session = Depends(get_db)) -> MotDetail:
    """Retourne une entrée complète du dictionnaire."""
    mot = (
        db.query(Mot)
        .options(
            joinedload(Mot.traductions),
            joinedload(Mot.definitions),
            joinedload(Mot.source),
        )
        .filter(Mot.id == mot_id)
        .first()
    )
    if not mot:
        raise HTTPException(status_code=404, detail=f"Mot introuvable (id={mot_id})")
    return MotDetail.from_orm_mot(mot)


# ---------------------------------------------------------------------------
# POST /dictionary  🔒
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=MotDetail,
    status_code=201,
    summary="Ajoute un mot 🔒",
    dependencies=[Depends(require_admin)],
)
def create_word(body: MotCreate, db: Session = Depends(get_db)) -> MotDetail:
    """Ajoute une entrée dans le dictionnaire (authentification requise)."""
    mot = Mot(**body.model_dump(exclude_none=True))
    db.add(mot)
    db.commit()
    db.refresh(mot)
    # Reload avec relations
    return get_word(mot.id, db)


# ---------------------------------------------------------------------------
# PUT /dictionary/{mot_id}  🔒
# ---------------------------------------------------------------------------

@router.put(
    "/{mot_id}",
    response_model=MotDetail,
    summary="Modifie un mot 🔒",
    dependencies=[Depends(require_admin)],
)
def update_word(
    mot_id: int, body: MotUpdate, db: Session = Depends(get_db)
) -> MotDetail:
    """Modifie une entrée existante du dictionnaire (authentification requise)."""
    mot = db.get(Mot, mot_id)
    if not mot:
        raise HTTPException(status_code=404, detail=f"Mot introuvable (id={mot_id})")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(mot, field, value)

    db.commit()
    db.refresh(mot)
    return get_word(mot_id, db)
