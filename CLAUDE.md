# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lang Matinitjé** is a multilingual platform for the Martinique Creole language (kréyòl matinitjé). It consists of 4 interconnected services:

- **scraper/** — Python data collection from web sources (BeautifulSoup4, pdfplumber)
- **api/** — FastAPI REST API with ML/AI (TF-IDF + HuggingFace RAG via the Fèfèn chatbot) + JWT auth
- **frontend/** — Next.js 15 multilingual UI (fr, en, crm locales via next-intl)
- **chatbot/** — Fèfèn chatbot engine (TF-IDF retrieval + HuggingFace LLM)
- **pipeline/** — Linguistic extraction pipeline (NEW — Phase 8)

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

### Pipeline (Phase 8 — NEW)
```bash
cd pipeline
pip install -r requirements.txt

# Run extraction worker (processes unprocessed conversations)
python -m pipeline.worker

# Run once (no loop)
python -m pipeline.worker --once

# Tests
pytest tests/ -v
```

## Architecture

### Data Flow
```
Web sources → Scrapers → DataPipeline → PostgreSQL → FastAPI → Next.js UI
                                              ↑                    │
                                              │                    ▼
                              pipeline/ ← conversation_logs ← Fèfèn chatbot
                                 │
                                 ▼
                          moderation_queue
                                 │ (human validation)
                                 ▼
                          dataset/ (enriched)
```

### API (`api/app/`)
- `main.py` — FastAPI app with lifespan, CORS, 7 routers
- `auth.py` — JWT utilities (hash_password, create_access_token, decode_token)
- `models/models.py` — 10+ SQLAlchemy ORM models (User, Mot, Traduction, Definition, Expression, Corpus, Media, Contributeur, Contribution, Source, **ConversationLog, ModerationCandidate, LinguisticEntry**)
- `schemas/schemas.py` — Pydantic v2 response schemas (incl. UserOut, TokenResponse, ContributionOut, **ConversationLogOut, ModerationCandidateOut**)
- `routers/auth.py` — POST /auth/register, /auth/login, GET /auth/me
- `routers/contributions.py` — CRUD /contributions (JWT protégé)
- `routers/dictionary.py` — GET/POST /dictionary, /search, /random
- `routers/translation.py` — POST /translate, GET /corpus, /expressions
- `routers/media.py` — GET /media, /media/{id}
- `routers/chat.py` — POST /chat (**now logs conversations**)
- `routers/admin.py` — Admin CRUD + modération contributions (JWT role:admin)
- `routers/moderation.py` — **NEW**: GET/PATCH /moderation (JWT role:admin|lingwis)
- `dependencies.py` — get_current_user (JWT Bearer), require_admin, **require_lingwis**, PaginationParams
- `fefen.py` — Fèfèn chatbot: TF-IDF retrieval with 3-level fallback for HuggingFace LLM calls

### Pipeline (`pipeline/`) — NEW Phase 8
- `extractor.py` — Extracts linguistic candidates from conversation logs
  - New words (not in existing dictionary)
  - Spelling variants (phonetic grouping via adapted Soundex)
  - Grammatical patterns (ka+verb, té+verb, etc.)
  - Expressions/collocations (frequent n-grams)
- `phonetics.py` — Creole-adapted phonetic matching (Soundex for kréyol)
- `ngrams.py` — N-gram extraction and frequency analysis
- `worker.py` — Async worker that processes unprocessed conversation logs
- `config.py` — Pipeline configuration (thresholds, batch sizes)

### Auth (JWT)
- Inscription : `POST /api/v1/auth/register` → crée User + Contributeur → retourne JWT
- Connexion : `POST /api/v1/auth/login` → retourne JWT
- Token : Bearer dans `Authorization` header (7 jours, configurable via `JWT_EXPIRE_MINUTES`)
- Rôles : `contributeur` (défaut), `admin`, ou `lingwis` (NEW) — stockés dans le JWT et en DB

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
- `app/[locale]/admin/moderation/` — **NEW**: Moderation panel for lingwis role

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
- `PIPELINE_BATCH_SIZE` — Number of conversations to process per worker run (default: 50) — **NEW**
- `PIPELINE_MIN_SPEAKERS` — Min. distinct speakers for a word to be candidate (default: 3) — **NEW**
- `PIPELINE_CRON` — Cron schedule for pipeline worker (default: "0 */6 * * *") — **NEW**

## Phase 8 — Linguistic Pipeline: Implementation Order

When implementing Phase 8, follow this sequence:

1. **Database migrations** — Add 3 new tables: `conversation_logs`, `moderation_candidates`, `linguistic_entries`
2. **Models + Schemas** — SQLAlchemy models + Pydantic schemas for the new tables
3. **Chat logging** — Modify `routers/chat.py` to log every exchange to `conversation_logs`
4. **Extractor core** — `pipeline/extractor.py` with word extraction + phonetic grouping
5. **Worker** — `pipeline/worker.py` that processes unprocessed logs in batches
6. **Moderation API** — `routers/moderation.py` with queue/approve/reject endpoints
7. **Moderation UI** — Frontend panel for lingwis role
8. **Dataset export** — Extend `export_huggingface.py` to include validated entries with `source: "conversation"`
9. **RAG refresh** — Hook validated entries into TF-IDF index rebuild

### Key Design Decisions
- Conversation logs store raw text + metadata (session, language confidence, user corrections)
- Pipeline extracts candidates but NEVER writes directly to the linguistic base
- All candidates go through human moderation (lingwis role)
- Validated entries get `source: "conversation"` for traceability
- Pipeline runs as async worker (not blocking the chat endpoint)
- Phonetic matching uses a Creole-adapted Soundex (not standard French/English Soundex)
