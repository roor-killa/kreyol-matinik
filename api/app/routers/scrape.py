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
    Corpus, Definition, Expression, Media, Mot, ScrapeJob, ScrapeJobStatus, Source,
)
from ..scraper_bridge import (
    confirm_youtube_insert,
    run_audio_batch,
    run_audio_transcription,
    run_auto_scrape,
    run_url_scrape,
    run_youtube,
)
from ..schemas.schemas import (
    ScrapeJobOut,
    ScrapeUrlRequest,
    ScrapeYoutubeRequest,
    SourceCreate,
    SourceOut,
    SourceStats,
    SourceUpdate,
    TranscribeBatchOut,
    TranscribeReviewRequest,
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


# ===========================================================================
# Transcription audio (pseudo-labeling Whisper)
# ===========================================================================

@router.post(
    "/transcribe/media/{media_id}",
    response_model=ScrapeJobOut,
    status_code=202,
    summary="Transcrire un média audio avec Whisper 🔒",
)
def transcribe_media(
    media_id: int,
    background_tasks: BackgroundTasks,
    model_size: str = "large-v3",
    db: Session = Depends(get_db),
) -> ScrapeJobOut:
    """Lance la transcription Whisper d'un média audio existant en DB.

    - `model_size` : 'tiny' | 'base' | 'small' | 'medium' | 'large-v3' (défaut)
    - La transcription est stockée dans `medias.transcription` avec
      `transcription_src = 'auto'` et insérée dans le corpus Fèfèn.
    """
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Média introuvable.")
    if media.type != "audio":
        raise HTTPException(status_code=422, detail="Ce média n'est pas de type audio.")
    if media.transcription_src == "reviewed":
        raise HTTPException(
            status_code=409,
            detail="Ce média a déjà une transcription validée. Utilisez l'endpoint de révision pour la modifier.",
        )

    job = ScrapeJob(
        source_id=media.source_id,
        url=media.url,
        job_type="audio_transcription",
        status=ScrapeJobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_audio_transcription, job.id, media_id, model_size)
    return ScrapeJobOut.model_validate(job, from_attributes=True)


@router.post(
    "/transcribe/batch",
    response_model=TranscribeBatchOut,
    summary="Transcrire en batch tous les médias audio sans transcription 🔒",
)
def transcribe_batch(
    model_size: str = "large-v3",
) -> TranscribeBatchOut:
    """Lance la transcription Whisper sur tous les médias audio dont
    `transcription` est NULL. Les jobs tournent en threads d'arrière-plan.

    Recommandé : utiliser `model_size=large-v3` pour la meilleure qualité
    sur le créole martiniquais (détection automatique de langue).
    """
    result = run_audio_batch(model_size=model_size)
    return TranscribeBatchOut(
        launched=result["launched"],
        job_ids=result["job_ids"],
        model_size=model_size,
    )


@router.patch(
    "/transcribe/media/{media_id}/review",
    summary="Valider / corriger la transcription d'un média 🔒",
)
def review_transcription(
    media_id: int,
    body: TranscribeReviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Permet à un locuteur natif de corriger la transcription automatique.

    Met à jour `medias.transcription_src` à 'reviewed' — ce média devient
    une paire audio/texte de vérité terrain utilisable pour le fine-tuning Whisper.
    """
    media = db.get(Media, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Média introuvable.")

    media.transcription = body.transcription
    media.transcription_src = "reviewed"

    # Mettre à jour ou créer l'entrée corpus correspondante
    if body.also_update_corpus and body.transcription.strip():
        corpus_entry = Corpus(
            texte_creole=body.transcription,
            texte_fr=None,
            domaine=body.domaine or "lòt",
            source_id=media.source_id,
        )
        db.add(corpus_entry)

    db.commit()
    return {
        "media_id": media_id,
        "transcription_src": "reviewed",
        "corpus_updated": body.also_update_corpus,
    }
