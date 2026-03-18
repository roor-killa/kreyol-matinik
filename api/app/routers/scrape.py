"""
Router /admin/scrape — Récupération de données (scraping URL, YouTube, auto)
et CRUD des sources avec statistiques.

Tous les endpoints requièrent le rôle admin (JWT).
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_admin
from ..models.models import (
    Corpus, Definition, Expression, Mot, ScrapeJob, ScrapeJobStatus, Source,
)
from ..scraper_bridge import confirm_youtube_insert, run_auto_scrape, run_url_scrape, run_youtube
from ..schemas.schemas import (
    ScrapeJobOut,
    ScrapeUrlRequest,
    ScrapeYoutubeRequest,
    SourceCreate,
    SourceOut,
    SourceStats,
    SourceUpdate,
    YoutubeConfirmRequest,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-scrape"],
    dependencies=[Depends(require_admin)],
)


# ===========================================================================
# Sources CRUD + stats
# ===========================================================================

def _source_with_stats(db: Session, source: Source) -> SourceOut:
    nb_mots  = db.query(func.count(Mot.id)).filter(Mot.source_id == source.id).scalar() or 0
    nb_corp  = db.query(func.count(Corpus.id)).filter(Corpus.source_id == source.id).scalar() or 0
    nb_expr  = db.query(func.count(Expression.id)).filter(Expression.source_id == source.id).scalar() or 0
    nb_defs  = db.query(func.count(Definition.id)).filter(Definition.source_id == source.id).scalar() or 0
    return SourceOut(
        id=source.id,
        nom=source.nom,
        url=source.url,
        type=source.type,
        robots_ok=source.robots_ok,
        actif=source.actif,
        auto_scrape=source.auto_scrape,
        scrape_interval_hours=source.scrape_interval_hours,
        scrape_at=source.scrape_at,
        created_at=source.created_at,
        stats=SourceStats(
            nb_mots=nb_mots,
            nb_corpus=nb_corp,
            nb_expressions=nb_expr,
            nb_definitions=nb_defs,
        ),
    )


@router.get("/sources", response_model=List[SourceOut], summary="Lister les sources 🔒")
def list_sources(db: Session = Depends(get_db)) -> List[SourceOut]:
    sources = db.query(Source).order_by(Source.created_at.desc()).all()
    return [_source_with_stats(db, s) for s in sources]


@router.post("/sources", response_model=SourceOut, status_code=201, summary="Créer une source 🔒")
def create_source(body: SourceCreate, db: Session = Depends(get_db)) -> SourceOut:
    if db.query(Source).filter(Source.url == body.url).first():
        raise HTTPException(status_code=409, detail="URL déjà enregistrée.")
    src = Source(**body.model_dump())
    db.add(src)
    db.commit()
    db.refresh(src)
    return _source_with_stats(db, src)


@router.put("/sources/{source_id}", response_model=SourceOut, summary="Modifier une source 🔒")
def update_source(source_id: int, body: SourceUpdate, db: Session = Depends(get_db)) -> SourceOut:
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source introuvable.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(src, field, value)
    db.commit()
    db.refresh(src)
    return _source_with_stats(db, src)


@router.delete("/sources/{source_id}", status_code=204, summary="Supprimer une source 🔒")
def delete_source(source_id: int, db: Session = Depends(get_db)) -> None:
    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source introuvable.")
    db.delete(src)
    db.commit()


# ===========================================================================
# Jobs
# ===========================================================================

@router.get("/scrape/jobs", response_model=List[ScrapeJobOut], summary="Historique des jobs 🔒")
def list_jobs(limit: int = 50, db: Session = Depends(get_db)) -> List[ScrapeJobOut]:
    jobs = (
        db.query(ScrapeJob)
        .order_by(ScrapeJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [ScrapeJobOut.model_validate(j, from_attributes=True) for j in jobs]


@router.get("/scrape/jobs/{job_id}", response_model=ScrapeJobOut, summary="Statut d'un job 🔒")
def get_job(job_id: int, db: Session = Depends(get_db)) -> ScrapeJobOut:
    job = db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    return ScrapeJobOut.model_validate(job, from_attributes=True)


# ===========================================================================
# Scraping URL
# ===========================================================================

@router.post("/scrape/url", response_model=ScrapeJobOut, status_code=202, summary="Scraper une URL 🔒")
def scrape_url(
    body: ScrapeUrlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ScrapeJobOut:
    job = ScrapeJob(
        source_id=body.source_id,
        url=body.url,
        job_type="url",
        status=ScrapeJobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_url_scrape, job.id, body.url, body.source_id)
    return ScrapeJobOut.model_validate(job, from_attributes=True)


# ===========================================================================
# YouTube
# ===========================================================================

@router.post("/scrape/youtube", response_model=ScrapeJobOut, status_code=202, summary="Transcrire YouTube 🔒")
def scrape_youtube(
    body: ScrapeYoutubeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ScrapeJobOut:
    job = ScrapeJob(
        url=body.youtube_url,
        job_type="youtube",
        status=ScrapeJobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_youtube, job.id, body.youtube_url)
    return ScrapeJobOut.model_validate(job, from_attributes=True)


@router.post(
    "/scrape/youtube/{job_id}/confirm",
    summary="Confirmer l'insertion du transcript YouTube 🔒",
)
def confirm_youtube(
    job_id: int,
    body: YoutubeConfirmRequest,
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(ScrapeJob, job_id)
    if not job or job.job_type != "youtube":
        raise HTTPException(status_code=404, detail="Job YouTube introuvable.")
    if job.status != ScrapeJobStatus.done:
        raise HTTPException(status_code=409, detail="La transcription n'est pas encore terminée.")

    entry_id = confirm_youtube_insert(
        db=db,
        texte=body.texte,
        table_cible=body.table_cible,
        domaine=body.domaine,
        source_id=job.source_id,
    )
    db.commit()
    return {"inserted": True, "table": body.table_cible, "id": entry_id}


# ===========================================================================
# Auto-scrape
# ===========================================================================

@router.post("/scrape/run-auto", summary="Lancer l'auto-scrape 🔒")
def trigger_auto_scrape() -> dict:
    return run_auto_scrape()
