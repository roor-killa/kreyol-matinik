# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lang Matinitjé** is a multilingual platform for the Martinique Creole language (kréyòl matinitjé). It consists of 4 interconnected services:

- **scraper/** — Python data collection from web sources (BeautifulSoup4, pdfplumber)
- **api/** — FastAPI REST API with ML/AI (TF-IDF + HuggingFace RAG via the Fèfèn chatbot) + JWT auth
- **frontend/** — Next.js 15 multilingual UI (fr, en, crm locales via next-intl)
- **chatbot/** — Fèfèn chatbot engine (TF-IDF retrieval + HuggingFace LLM)

PostgreSQL (with pgvector) is the single shared database for all services.

## Commands

### Full Stack (Docker)
```bash
docker compose up --build        # Start all services (db, adminer, api, frontend)
docker compose up db -d          # Start only PostgreSQL
docker compose logs -f <service> # Follow logs (api, frontend, db)
```

### API (FastAPI — port 8000)
```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tests
pytest tests/ -v
pytest tests/ --cov=app
pytest tests/test_api.py::test_name -v
```

### Scraper
```bash
cd scraper
pip install -r requirements.txt

python main.py --source pawolotek --max 10 --import-db
python main.py --source potomitan --categories contes poemes
python main.py --help

pytest tests/ -v
```

### Frontend (Next.js — port 3000)
```bash
cd frontend
npm install
npm run dev    # Development
npm run build  # Production build
npm run lint   # ESLint
```

## Architecture

### Data Flow
Web sources → Scrapers (Factory pattern) → DataPipeline (clean/normalize) → PostgreSQL → FastAPI → Next.js UI

### API (`api/app/`)
- `main.py` — FastAPI app with lifespan, CORS, 7 routers
- `auth.py` — JWT utilities (hash_password, create_access_token, decode_token)
- `models/models.py` — 10 SQLAlchemy ORM models (User, Mot, Traduction, Definition, Expression, Corpus, Media, Contributeur, Contribution, Source)
- `schemas/schemas.py` — Pydantic v2 response schemas (incl. UserOut, TokenResponse, ContributionOut)
- `routers/auth.py` — POST /auth/register, /auth/login, GET /auth/me
- `routers/contributions.py` — CRUD /contributions (JWT protégé)
- `routers/dictionary.py` — GET/POST /dictionary, /search, /random
- `routers/translation.py` — POST /translate, GET /corpus, /expressions
- `routers/media.py` — GET /media, /media/{id}
- `routers/chat.py` — POST /chat
- `routers/admin.py` — Admin CRUD + modération contributions (JWT role:admin)
- `dependencies.py` — get_current_user (JWT Bearer), require_admin, PaginationParams
- `fefen.py` — Fèfèn chatbot: TF-IDF retrieval with 3-level fallback for HuggingFace LLM calls

### Auth (JWT)
- Inscription : `POST /api/v1/auth/register` → crée User + Contributeur → retourne JWT
- Connexion : `POST /api/v1/auth/login` → retourne JWT
- Token : Bearer dans `Authorization` header (7 jours, configurable via `JWT_EXPIRE_MINUTES`)
- Rôles : `contributeur` (défaut) ou `admin` — stockés dans le JWT et en DB

### Scraper (`scraper/src/`)
- `base_scraper.py` — Abstract base class all scrapers inherit from
- `manager.py` — ScraperManager factory (maps source name → scraper class)
- `pipeline.py` — DataPipeline: cleaning, normalization, language detection
- `observers.py` — Observer pattern: LogObserver, StatsObserver
- `scrapers/` — 8 concrete scrapers (pawolotek, potomitan HTML/PDF, bizouk, kiprix, kreyol, madiana, rci)

### Frontend (`frontend/src/`)
- App Router with `[locale]` dynamic segment for i18n (fr/en/crm)
- `lib/api.ts` — HTTP clients : `fastapi` (public), `fastapiAuth` (JWT), `fastapiContrib` (JWT), `adminApi` (JWT role:admin)
- `lib/auth.ts` — Zustand store with localStorage persistence (`isAdmin()` checks `user.role === "admin"`)
- `middleware.ts` — next-intl locale routing
- `i18n/messages/` — Translation files (en.json, fr.json, crm.json)
- `components/ui/` — shadcn/ui components

### Chatbot (`chatbot/`)
- `train.py` — Builds and serializes TF-IDF index to `models/fefen_index.joblib`
- `fefen.py` — TF-IDF retrieval + RAG context formatting for LLM queries
- `inference.py` — CLI for interactive testing

## Environment Variables

Copy `.env.example` to `.env`. Key variables:
- `POSTGRES_*` — Database credentials
- `API_KEY` — FastAPI internal API key (scraper/admin legacy)
- `JWT_SECRET` — JWT signing secret (min. 32 chars, **change in production**)
- `HF_TOKEN` — HuggingFace token for Fèfèn LLM inference (optional)
- `NEXT_PUBLIC_FASTAPI_URL` — Frontend → FastAPI URL (browser-side)
