"""
Router /translate, /expressions, /corpus

/translate : recherche floue via func.similarity() (pg_trgm).
             Requiert PostgreSQL — les tests de cet endpoint sont skippés (SQLite).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import PaginationParams
from ..models.models import Corpus, Expression, Traduction
from ..schemas.schemas import (
    CorpusOut,
    CorpusResponse,
    ExpressionOut,
    ExpressionsResponse,
    TranslateRequest,
    TranslateResponse,
)


router = APIRouter(tags=["traduction"])


# ---------------------------------------------------------------------------
# POST /translate
# ---------------------------------------------------------------------------

@router.post("/translate", response_model=TranslateResponse, summary="Traduction fr ↔ crm")
def translate(request: TranslateRequest, db: Session = Depends(get_db)) -> TranslateResponse:
    """Traduit un texte via recherche floue dans le corpus (pg_trgm).

    Requiert l'extension pg_trgm (PostgreSQL). Non disponible en SQLite.
    """
    similarity = func.similarity(Traduction.texte_source, request.text)

    row = (
        db.query(Traduction, similarity.label("score"))
        .filter(
            Traduction.langue_source == request.source,
            Traduction.langue_cible == request.target,
            similarity > 0.2,
        )
        .order_by(similarity.desc())
        .first()
    )

    if row:
        trad, score = row
        return TranslateResponse(
            source=request.source,
            target=request.target,
            input=request.text,
            output=trad.texte_cible,
            confidence=round(float(score), 4),
            method="corpus_match",
        )

    # Aucune correspondance trouvée
    return TranslateResponse(
        source=request.source,
        target=request.target,
        input=request.text,
        output=request.text,
        confidence=0.0,
        method="corpus_match",
    )


# ---------------------------------------------------------------------------
# GET /expressions
# ---------------------------------------------------------------------------

@router.get("/expressions", response_model=ExpressionsResponse, summary="Expressions et proverbes")
def list_expressions(
    type: Optional[str] = Query(None, description="Filtre par type (pwovèb, expression, lokisyon)"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> ExpressionsResponse:
    """Liste les expressions figées, proverbes et locutions créoles."""
    query = db.query(Expression)
    if type:
        query = query.filter(Expression.type == type)

    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()

    return ExpressionsResponse(
        total=total,
        results=[ExpressionOut.from_orm_expr(e) for e in items],
    )


# ---------------------------------------------------------------------------
# GET /corpus
# ---------------------------------------------------------------------------

@router.get("/corpus", response_model=CorpusResponse, summary="Corpus IA")
def list_corpus(
    domaine: Optional[str] = Query(None, description="Filtre par domaine"),
    lang: Optional[str] = Query(
        None,
        description="Filtre par langue présente : crm | fr | both",
    ),
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    limit: int = Query(default=50, ge=1, le=500, description="Résultats par page"),
    db: Session = Depends(get_db),
) -> CorpusResponse:
    """Accède au corpus de phrases bilingues pour l'entraînement IA."""
    query = db.query(Corpus)

    if domaine:
        query = query.filter(Corpus.domaine == domaine)

    if lang == "fr":
        query = query.filter(Corpus.texte_fr.isnot(None))
    elif lang == "crm":
        query = query.filter(Corpus.texte_creole.isnot(None))

    total = query.count()
    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()

    return CorpusResponse(
        total=total,
        results=[CorpusOut.from_orm_corpus(c) for c in items],
    )
