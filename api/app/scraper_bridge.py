"""
scraper_bridge.py — Pont entre FastAPI et la logique de scraping/transcription.

Fournit les fonctions principales appelées en BackgroundTask :
  - run_url_scrape(job_id, url, source_id)       → extrait le texte d'une URL et insère en corpus
  - run_youtube(job_id, youtube_url)              → télécharge l'audio YouTube et transcrit avec Whisper
  - run_audio_transcription(job_id, media_id)    → transcrit un média audio existant (URL quelconque)
  - run_audio_batch(model_size)                  → transcrit en batch tous les médias sans transcription

Chaque fonction ouvre sa propre session SQLAlchemy (car la session request est
déjà fermée quand la BackgroundTask s'exécute).
"""

import logging
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models.models import Corpus, Expression, Media, Mot, ScrapeJob, ScrapeJobStatus, Source

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LangMatinitjeBot/1.0; "
        "+https://github.com/lang-matinitje)"
    )
}


# ---------------------------------------------------------------------------
# Helpers DB
# ---------------------------------------------------------------------------

def _set_running(db: Session, job: ScrapeJob) -> None:
    job.status     = ScrapeJobStatus.running
    job.started_at = datetime.now(timezone.utc)
    db.commit()


def _set_done(db: Session, job: ScrapeJob, nb: int, preview: Optional[str] = None) -> None:
    job.status      = ScrapeJobStatus.done
    job.nb_inserted = nb
    job.finished_at = datetime.now(timezone.utc)
    if preview:
        job.preview_text = preview
    db.commit()


def _set_error(db: Session, job: ScrapeJob, msg: str) -> None:
    job.status      = ScrapeJobStatus.error
    job.error_msg   = msg[:2000]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _get_or_create_source(db: Session, url: str, source_id: Optional[int]) -> Optional[Source]:
    """Retourne la source existante (par id ou url) ou en crée une générique."""
    if source_id:
        src = db.get(Source, source_id)
        if src:
            return src
    src = db.query(Source).filter(Source.url == url).first()
    if src:
        return src
    # Créer une source générique pour cette URL
    from urllib.parse import urlparse
    domain = urlparse(url).netloc or url
    src = Source(nom=domain, url=url, type="texte", robots_ok=False, actif=True)
    db.add(src)
    db.flush()
    return src


# ---------------------------------------------------------------------------
# URL Scraping
# ---------------------------------------------------------------------------

def _extract_text_from_url(url: str) -> str:
    """Récupère une page web et extrait son texte principal."""
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(url, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        # Détecter l'encodage
        if r.encoding and r.encoding.lower() in ("iso-8859-1", "latin-1"):
            r.encoding = "utf-8"
    except Exception as e:
        raise RuntimeError(f"Erreur HTTP : {e}")

    soup = BeautifulSoup(r.content, "lxml")

    # Supprimer scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    # Extraire les paragraphes
    paragraphs = []
    for p in soup.find_all(["p", "blockquote", "li", "h1", "h2", "h3", "h4"]):
        text = re.sub(r"\s+", " ", p.get_text(separator=" ", strip=True))
        if len(text) > 30:
            paragraphs.append(text)

    return "\n".join(paragraphs)


def run_url_scrape(job_id: int, url: str, source_id: Optional[int] = None) -> None:
    """BackgroundTask : scrape une URL et insère le texte en corpus."""
    db = SessionLocal()
    try:
        job = db.get(ScrapeJob, job_id)
        if not job:
            return
        _set_running(db, job)

        texte = _extract_text_from_url(url)
        if not texte.strip():
            _set_error(db, job, "Aucun texte extractible depuis cette URL.")
            return

        src = _get_or_create_source(db, url, source_id)

        entry = Corpus(
            texte_creole=texte,
            texte_fr=None,
            domaine="lòt",
            source_id=src.id if src else None,
        )
        db.add(entry)

        # Mettre à jour scrape_at sur la source
        if src:
            src.scrape_at = datetime.now(timezone.utc)

        db.commit()
        _set_done(db, job, nb=1)

    except Exception as e:
        log.exception("Erreur run_url_scrape job=%d", job_id)
        db = SessionLocal()
        job = db.get(ScrapeJob, job_id)
        if job:
            _set_error(db, job, str(e))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# YouTube → Whisper
# ---------------------------------------------------------------------------

def _download_youtube_audio(youtube_url: str, out_path: str) -> None:
    """Télécharge l'audio d'une vidéo YouTube en mp3 via yt-dlp."""
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "--output", out_path,
        "--no-playlist",
        "--quiet",
        youtube_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp error: {result.stderr[:500]}")


def _download_audio_url(url: str, out_path: str) -> None:
    """Télécharge un fichier audio depuis une URL HTTP directe (mp3, ogg, m4a…)."""
    import requests

    r = requests.get(url, headers=_HEADERS, stream=True, timeout=120)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)


def _transcribe_audio(
    audio_path: str,
    model_size: str = "base",
    language: Optional[str] = "fr",
) -> str:
    """Transcrit un fichier audio avec faster-whisper.

    Pour la transcription créole, passer language=None pour que Whisper
    détecte automatiquement la langue (large-v3 gère mieux le mélange
    créole/français que le forçage sur 'fr').
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper non installé. Ajoutez-le aux requirements.")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    kwargs: dict = {"beam_size": 3}
    if language:
        kwargs["language"] = language
    segments, _ = model.transcribe(audio_path, **kwargs)
    return " ".join(seg.text.strip() for seg in segments)


def run_youtube(job_id: int, youtube_url: str) -> None:
    """BackgroundTask : télécharge audio YouTube et transcrit avec Whisper."""
    db = SessionLocal()
    audio_path = None
    try:
        job = db.get(ScrapeJob, job_id)
        if not job:
            return
        _set_running(db, job)
        db.close()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = str(Path(tmpdir) / f"yt_{job_id}.mp3")
            _download_youtube_audio(youtube_url, audio_path)
            transcript = _transcribe_audio(audio_path)

        db = SessionLocal()
        job = db.get(ScrapeJob, job_id)
        if job:
            _set_done(db, job, nb=0, preview=transcript)

    except Exception as e:
        log.exception("Erreur run_youtube job=%d", job_id)
        db = SessionLocal()
        job = db.get(ScrapeJob, job_id)
        if job:
            _set_error(db, job, str(e))
    finally:
        db.close()


def confirm_youtube_insert(
    db: Session,
    texte: str,
    table_cible: str,
    domaine: Optional[str],
    source_id: Optional[int] = None,
) -> int:
    """Insère le texte confirmé dans la table choisie. Retourne l'id créé."""
    if table_cible == "corpus":
        entry = Corpus(
            texte_creole=texte,
            texte_fr=None,
            domaine=domaine or "lòt",
            source_id=source_id,
        )
        db.add(entry)
        db.flush()
        return entry.id

    elif table_cible == "expression":
        entry = Expression(
            texte_creole=texte,
            type="expression",
            source_id=source_id,
            valide=False,
        )
        db.add(entry)
        db.flush()
        return entry.id

    raise ValueError(f"table_cible inconnue : {table_cible!r}")


# ---------------------------------------------------------------------------
# Transcription audio — URL directe (Pawolotek, RCI, etc.)
# ---------------------------------------------------------------------------

def run_audio_transcription(
    job_id: int,
    media_id: int,
    model_size: str = "large-v3",
) -> None:
    """BackgroundTask : télécharge et transcrit un média audio existant en DB.

    Met à jour medias.transcription et medias.transcription_src = 'auto'.
    Insère également le texte dans corpus pour enrichir l'index Fèfèn TF-IDF.
    """
    db = SessionLocal()
    try:
        job = db.get(ScrapeJob, job_id)
        media = db.get(Media, media_id)
        if not job or not media:
            return
        _set_running(db, job)
        media_url = media.url          # lire avant de fermer la session
        media_source_id = media.source_id
        db.close()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = str(Path(tmpdir) / f"media_{media_id}.mp3")
            _download_audio_url(media_url, audio_path)
            transcript = _transcribe_audio(audio_path, model_size=model_size, language=None)

        db = SessionLocal()
        media = db.get(Media, media_id)
        job = db.get(ScrapeJob, job_id)
        if not media or not job:
            return

        media.transcription = transcript
        media.transcription_src = "auto"

        # Alimenter le corpus Fèfèn avec la transcription
        if transcript.strip():
            corpus_entry = Corpus(
                texte_creole=transcript,
                texte_fr=None,
                domaine="lòt",
                source_id=media_source_id,
            )
            db.add(corpus_entry)

        _set_done(db, job, nb=1, preview=transcript[:300])

    except Exception as e:
        log.exception("Erreur run_audio_transcription job=%d media=%d", job_id, media_id)
        db = SessionLocal()
        job = db.get(ScrapeJob, job_id)
        if job:
            _set_error(db, job, str(e))
    finally:
        db.close()


def run_audio_batch(model_size: str = "large-v3") -> dict:
    """Transcrit en batch tous les médias audio sans transcription.

    Lance un thread par média (les jobs sont créés en amont par l'endpoint).
    Retourne le nombre de jobs lancés.
    """
    db = SessionLocal()
    launched = []
    try:
        medias = (
            db.query(Media)
            .filter(Media.transcription.is_(None), Media.type == "audio")
            .all()
        )
        for media in medias:
            job = ScrapeJob(
                source_id=media.source_id,
                url=media.url,
                job_type="audio_transcription",
                status=ScrapeJobStatus.pending,
            )
            db.add(job)
            db.flush()
            launched.append((job.id, media.id))

        db.commit()
    finally:
        db.close()

    import threading
    for job_id, media_id in launched:
        t = threading.Thread(
            target=run_audio_transcription,
            args=(job_id, media_id, model_size),
            daemon=True,
        )
        t.start()

    return {"launched": len(launched), "job_ids": [j[0] for j in launched]}


# ---------------------------------------------------------------------------
# Auto-scrape (APScheduler)
# ---------------------------------------------------------------------------

def run_auto_scrape() -> dict:
    """Lance le scraping de toutes les sources auto_scrape=True non scrapées aujourd'hui."""
    from datetime import date

    db = SessionLocal()
    launched = []
    try:
        sources = (
            db.query(Source)
            .filter(Source.auto_scrape.is_(True), Source.actif.is_(True))
            .all()
        )
        today = date.today()
        for src in sources:
            last = src.scrape_at
            if last and last.date() >= today:
                continue  # déjà scrapé aujourd'hui

            job = ScrapeJob(
                source_id=src.id,
                url=src.url,
                job_type="auto",
                status=ScrapeJobStatus.pending,
            )
            db.add(job)
            db.flush()
            launched.append((job.id, src.url, src.id))

        db.commit()
    finally:
        db.close()

    # Lancer les jobs en threads (hors request cycle)
    import threading
    for job_id, url, src_id in launched:
        t = threading.Thread(target=run_url_scrape, args=(job_id, url, src_id), daemon=True)
        t.start()

    return {"launched": len(launched), "job_ids": [j[0] for j in launched]}
