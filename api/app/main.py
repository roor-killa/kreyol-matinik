"""
Lang Matinitjé — API FastAPI

Endpoints:
  GET  /health
  POST /api/v1/auth/register   📝 Inscription
  POST /api/v1/auth/login      🔑 Connexion JWT
  GET  /api/v1/auth/me         🔒 Profil utilisateur
  ...  /api/v1/dictionary/*    Dictionnaire (public)
  POST /api/v1/translate       Traduction (public)
  GET  /api/v1/corpus          Corpus (public)
  GET  /api/v1/media           Médias (public)
  POST /api/v1/chat            Chatbot Fèfèn (public)
  ...  /api/v1/contributions/* 🔒 Contributions (JWT)
  ...  /api/v1/admin/*         🔒 Admin (JWT role:admin)
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import admin, chat, dictionary, media, translation
from .routers.auth import router as auth_router
from .routers.contributions import router as contributions_router
from .routers.scrape import router as scrape_router


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Tables gérées par schema.sql / Docker — pas de create_all ici.
    # Chargement de Fèfèn (TF-IDF) au démarrage
    try:
        from .fefen import build_fefen
        app.state.fefen = build_fefen()
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("Fèfèn non chargé : %s", exc)
        app.state.fefen = None

    # APScheduler — auto-scrape quotidien
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from .scraper_bridge import run_auto_scrape
        from .config import settings

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            lambda: run_auto_scrape(),
            trigger="cron",
            hour=getattr(settings, "auto_scrape_hour", 3),
            minute=0,
            id="auto_scrape",
            replace_existing=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("APScheduler non démarré : %s", exc)
        app.state.scheduler = None

    yield

    if getattr(app.state, "scheduler", None):
        app.state.scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Lang Matinitjé API",
    description=(
        "API REST pour le dictionnaire créole martiniquais (kréyòl matinitjé). "
        "Données issues de Pawolotek et Potomitan."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes globales
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"], summary="Santé de l'API")
def health():
    """Vérifie que l'API est opérationnelle."""
    return {"status": "ok", "service": "lang-matinitje-api"}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

PREFIX = "/api/v1"

app.include_router(auth_router, prefix=PREFIX)
app.include_router(contributions_router, prefix=PREFIX)
app.include_router(dictionary.router, prefix=PREFIX)
app.include_router(translation.router, prefix=PREFIX)
app.include_router(media.router, prefix=PREFIX)
app.include_router(chat.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)
app.include_router(scrape_router, prefix=PREFIX)
