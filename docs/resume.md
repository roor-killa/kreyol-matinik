# Résumé du projet — Lang Matinitjé

**Projet :** API open source pour la langue créole martiniquaise
**Groupe :** Université des Antilles - NASDY
**Période :** Février 2026
**Dépôt :** github.com/roor-killa/kreyol-matinik

---

## Vue d'ensemble

| Phase | Contenu | Statut | Commits |
|---|---|---|---|
| 0 | Cahier des charges + UML + contrats d'API | ✅ | `c5e2a34` |
| 1 | Scraper Python (Pawolotek + Potomitan) | ✅ | `da73beb`, `b3d936d` |
| 2 | Base de données PostgreSQL + import | ✅ | `906a70f`, `83bb13a` |
| 3 | API REST FastAPI | ✅ | `c08add8` |
| 4 | Export dataset HuggingFace | ✅ | `e6e4b80` |
| 5 | Interface web Laravel + Next.js | ✅ | `785c8a4`, `65abc3b` |
| 6 | Chatbot Fèfèn (TF-IDF + RAG HuggingFace) | ✅ | `860a4a4` → `cf56330` |
| 7 | Dictionnaire Confiant — PDFs → RAG | ✅ | `ae49771` → `9ade32b` |

---

## Phase 0 — Cahier des charges et architecture

**Commit :** `c5e2a34`

### Actions menées
- Rédaction du **cahier des charges** (`docs/cahier_des_charges.md`) :
  - Contexte : langue créole martiniquaise, ~400 000 locuteurs
  - 6 objectifs (O1–O6) : scraping, BDD, dictionnaire, dataset, interface web, chatbot
  - Stack technique : Python/FastAPI, PostgreSQL, Laravel, Next.js, HuggingFace
- Conception du **diagramme de classes UML** (`docs/uml/`) :
  - `BaseScraper` (ABC) → `PawoloTekScraper`, `PotomitanScraper`
  - `ScraperManager` (Factory Pattern)
  - `DataPipeline`, `ScraperObserver` (Observer Pattern)
- Rédaction des **contrats d'API** (`docs/api_contracts.md`) :
  - Endpoints dictionnaire, traduction, corpus, médias, chat
- Mise en place du `docker-compose.yml` initial (PostgreSQL + Adminer)

---

## Phase 1 — Scraper Python

**Commits :** `da73beb`, `b3d996d`

### Actions menées
- Implémentation du scraper selon les patrons de conception POO :
  - `BaseScraper` (ABC) : `fetch_page()`, `scrape()`, `parse()`, `save_to_csv/json()`
  - `PawoloTekScraper` : scraping du lexique créole (87 entrées)
  - `PotomitanScraper` : scraping de contes et poèmes (183 entrées)
  - `ScraperManager` : Factory Pattern pour instancier les scrapers
  - `DataPipeline` : nettoyage, normalisation, détection de langue
  - `LogObserver` / `StatsObserver` : Observer Pattern pour les logs
- Respect du `robots.txt` (délai 60 s entre requêtes Potomitan, 2 s Pawolotek)
- User-Agent identifié : `Lang-Matinitje-Bot/1.0`

### Données collectées
| Source | Entrées | Type |
|---|---|---|
| Pawolotek.com | 87 | Lexique créole (mots + définitions) |
| Potomitan.info | 183 | Contes (155) + Poèmes (28) |
| **Total** | **270** | |

### Bugs corrigés
- Pipeline import BDD : savepoints PostgreSQL pour éviter les rollbacks globaux
- Auto-insertion des sources manquantes avant import des mots
- Récupération du `mot_id` sur conflit d'unicité (ON CONFLICT)
- Traductions `titre_fr` manquantes comblées

---

## Phase 2 — Base de données PostgreSQL

**Commit :** `906a70f`

### Actions menées
- Conception et rédaction du schéma SQL (`scraper/db/schema.sql`) :
  - 9 tables : `sources`, `mots`, `traductions`, `definitions`, `expressions`,
    `medias`, `corpus`, `contributeurs`, `contributions`
  - Types ENUM natifs PostgreSQL : `source_type`, `langue_code`, `categorie_gram`,
    `action_type`, `statut_contrib`, `domaine_corpus`
  - Extensions : `unaccent`, `pg_trgm` (recherche floue)
- Import complet des données scrapées via `DataPipeline` :
  - 164 mots insérés dans `mots`
  - 39 traductions dans `traductions`
  - 625 entrées dans `corpus`
- Configuration Docker : PostgreSQL 15 + Adminer (port 8080)

---

## Phase 3 — API REST FastAPI

**Commit :** `c08add8`

### Actions menées
- Implémentation de l'API FastAPI (`api/`) :
  - `app/config.py` : Settings via pydantic-settings (lecture `.env`)
  - `app/database.py` : moteur SQLAlchemy + `get_db()`
  - `app/dependencies.py` : authentification `X-API-Key` + pagination
  - `app/models/models.py` : 9 modèles ORM + enums Python (subclass `str`)
  - `app/schemas/schemas.py` : schémas Pydantic v2

- Routers implémentés :

| Router | Endpoints |
|---|---|
| `dictionary.py` | `GET /dictionary`, `/dictionary/{id}`, `/random`, `/search`, `/expressions` |
| `translation.py` | `POST /translate`, `GET /corpus` |
| `media.py` | `GET /media`, `/media/{id}` |
| `chat.py` | `POST /chat` (stub déterministe pour les tests) |

- Décisions techniques clés :
  - ENUMs : helper `_pg_enum()` → `create_constraint=False, native_enum=True`
    (compatible PostgreSQL natif ET SQLite pour les tests)
  - `JSONB` remplacé par `JSON` (compatibilité SQLite tests)
  - `create_all()` uniquement dans les tests (SQLite) ; production via `schema.sql`
  - Routes `/random` et `/search` déclarées **avant** `/{mot_id}` (ordre FastAPI)

- Suite de tests (`tests/test_api.py`) : **16 tests passent**, 2 skippés (pg_trgm)
- Documentation Swagger auto-générée : `http://localhost:8000/docs`

---

## Phase 4 — Dataset HuggingFace

**Commit :** `e6e4b80`

### Actions menées
- Création du répertoire `dataset/` et du script `export_huggingface.py`
- Export des données en **3 configurations** (subsets) :

| Config | Entrées | Description |
|---|---|---|
| `corpus` | 268 | Tous les textes créoles fusionnés |
| `lexique` | 87 | Mots + définitions (Pawolotek) |
| `contes_poemes` | 183 | Contes et poèmes (Potomitan) |
| **Total** | **538** | |

- Format de sortie : **JSONL** (sans dépendances) + **Parquet** optionnel (`datasets`)
- Génération automatique de la **Dataset Card** `dataset/README.md` :
  - Métadonnées YAML HuggingFace (langue `crm`, licence CC BY-SA 4.0)
  - Schéma des champs, exemples d'utilisation, citation BibTeX
- Instructions de publication : `huggingface-cli upload kreyol-matinik/lang-matinitje`

---

## Phase 5 — Interface web Laravel + Next.js

**Commits :** `785c8a4`, `65abc3b`

### Backend Laravel 11 (`backend/`)
- **Auth** : Laravel Sanctum — register, login, logout, profil (`/api/auth/*`)
- **Rôles** : Spatie Permission — rôles `contributeur` et `admin`
- **UserObserver** : création automatique d'un `Contributeur` et attribution du rôle
  à chaque inscription
- **Contributions** : CRUD (ajout, liste, suppression) protégé par `auth:sanctum`
- **Admin** : validation/rejet des contributions (`role:admin`)
- **Healthcheck** : `GET /api/health`
- **Docker** : `docker-entrypoint.sh` — migrations + seeder automatiques au démarrage

### Frontend Next.js 15 (`frontend/`)
- **App Router** + **next-intl** : 3 locales (`fr`, `en`, `crm`)
- **Pages** : accueil, dictionnaire, corpus, expressions, contribuer, profil, admin,
  connexion, inscription, **chat**
- **Composants** : NavBar, SearchBar, WordCard, LanguageSwitcher, shadcn/ui
- **Clients HTTP** (`src/lib/api.ts`) : FastAPI (lecture) + Laravel (auth + contributions)
- **Store Zustand** (`src/lib/auth.ts`) : persisté en localStorage

### Bugs corrigés (commit `65abc3b`)
| Bug | Cause | Correction |
|---|---|---|
| Build Docker échoué | `npm ci` sans `package-lock.json` | Remplacé par `npm install` |
| Page blanche (React #418) | `globals.css` importé deux fois | Supprimé du root layout |
| Page blanche (React #418) | Zustand `persist` + SSR mismatch | Guard `mounted` dans NavBar |
| HTTP 419 (CSRF) | `EnsureFrontendRequestsAreStateful` sur routes API | Supprimé (auth Bearer token) |

---

## Phase 6 — Chatbot Fèfèn

**Commits :** `860a4a4` → `cf56330`

### Architecture

```
Question utilisateur
        │
        ▼
  TF-IDF (sklearn)
  Recherche top-3 entrées
  les plus proches dans le corpus
        │
        ▼
  Contexte RAG injecté dans le prompt
        │
        ▼
  LLM HuggingFace
  Génération de réponse en créole/français
        │
        ▼
  Réponse affichée dans le chat Next.js
```

### Composants créés

**`chatbot/` (CLI)**
- `fefen.py` : moteur TF-IDF — index bigrammes, similarité cosinus, formatage
  contextuel (lexique / conte / poème)
- `train.py` : construction et sauvegarde de l'index (joblib, 0.44 s)
- `inference.py` : interface CLI interactive + mode `--query` non-interactif

**`api/app/fefen.py` (intégration FastAPI)**
- Classe `Fefen` : TF-IDF + méthode `retrieve()` pour le RAG
- Classe `FefenRAG` : 3 tentatives d'appel LLM en cascade :
  1. `chat_completion` (TGI — modèles récents)
  2. `text_generation` (format prompt Mistral/Mixtral)
  3. `text2text_generation` avec `google/flan-t5-large` (toujours gratuit)
  4. Fallback TF-IDF pur si toutes les tentatives échouent
- `build_fefen()` : active `FefenRAG` si `HF_TOKEN` présent, sinon `Fefen`

**`frontend/src/app/[locale]/chat/page.tsx`**
- Interface de chat avec bulles de messages (utilisateur / Fèfèn)
- Scroll automatique, indicateur de chargement, gestion des erreurs
- Multilingue (fr / en / crm)

### Configuration
- `HF_TOKEN` dans `.env` → active le mode RAG
- `FEFEN_MODEL` → modèle HuggingFace (défaut : `mistralai/Mixtral-8x7B-Instruct-v0.1`)
- Dataset monté via volume Docker : `./dataset/data:/app/dataset/data:ro`

---

## Phase 7 — Dictionnaire Confiant (PDFs → RAG)

**Commits :** `ae49771` → `9ade32b`

### Actions menées
- Création du scraper PDF (`PotomitanPDFScraper`) :
  - Télécharge les PDFs du *Dictionnaire du Créole Martiniquais* (Raphaël Confiant)
  - Source : `potomitan.info/dictionnaire/{lettre}.pdf` — lettres A à N disponibles
  - Respect du `robots.txt` : délai 60 s, User-Agent identifié
  - 13 PDFs téléchargés (L, O–W : 404)
- Création du parseur PDF (`PDFExtractor`) :
  - Extraction du texte via `pdfplumber`
  - Patterns regex : en-têtes d'entrée, définitions (`.`), variantes (`var.`),
    synonymes (`syn.`), féminin (`fém.`), exemples
  - Suppression des pieds de page automatique
  - Heuristique `_is_header()` pour distinguer mots-vedettes du corps du texte
- Pipeline complet (`pipeline_pdf.py`) : download → extract → JSONL → import DB
- Export JSONL → `dataset/data/dictionnaire_confiant/train.jsonl` :
  - 919 entrées (867 lettre A + 52 lettres B–N)
  - Champs enrichis pour TF-IDF : `texte`, `variantes`, `synonymes`, `exemples`
- Intégration Fèfèn RAG :
  - `fefen.py` charge `dictionnaire_confiant` en **priorité** avant lexique/corpus
  - +919 entrées dictionnairiques dans l'index TF-IDF
- Dataset HuggingFace : ajout config `dictionnaire_confiant` dans `export_huggingface.py`

### Données clés
| Source | Entrées |
|---|---|
| Lettre A | 867 |
| Lettres B, CH, D–K, M, N | 52 |
| **Total** | **919** |

---

## Architecture finale du projet

```
kreyol-matinik/
├── docs/                        ← Phase 0 : cahier des charges, UML, contrats API
├── scraper/                     ← Phase 1 : scrapers Python (POO)
│   ├── src/
│   │   ├── base_scraper.py      — ABC BaseScraper
│   │   ├── scrapers/            — PawoloTekScraper, PotomitanScraper
│   │   ├── manager.py           — ScraperManager (Factory)
│   │   ├── pipeline.py          — DataPipeline
│   │   └── observers.py         — Observer Pattern
│   ├── db/schema.sql            ← Phase 2 : schéma PostgreSQL
│   └── data/processed/          — 270 entrées JSON
├── api/                         ← Phase 3 : FastAPI
│   └── app/
│       ├── routers/             — dictionary, translation, media, chat
│       ├── models/, schemas/    — ORM SQLAlchemy + Pydantic v2
│       └── fefen.py             ← Phase 6 : moteur Fèfèn (TF-IDF + RAG)
├── dataset/                     ← Phase 4 : export HuggingFace
│   ├── export_huggingface.py
│   ├── README.md                — Dataset Card
│   └── data/                   — corpus (268), lexique (87), contes_poemes (183)
├── backend/                     ← Phase 5 : Laravel 11
│   ├── app/Http/Controllers/Api/
│   ├── app/Models/              — User, Contributeur, Contribution
│   └── routes/api.php
├── frontend/                    ← Phase 5 : Next.js 15
│   └── src/
│       ├── app/[locale]/        — pages fr/en/crm
│       ├── components/          — NavBar, SearchBar, WordCard, chat
│       └── lib/                 — api.ts, auth.ts
├── chatbot/                     ← Phase 6 : CLI Fèfèn
│   ├── fefen.py, train.py, inference.py
│   └── models/fefen_index.joblib
└── docker-compose.yml           ← orchestration : db, adminer, api, backend, frontend
```

---

## Données clés

| Indicateur | Valeur |
|---|---|
| Entrées scrapées HTML | 270 (87 Pawolotek + 183 Potomitan) |
| Entrées dictionnaire Confiant (PDFs) | 919 (13 PDFs, lettres A–N) |
| Mots dans la BDD | 164 |
| Entrées corpus BDD | 625 |
| Traductions BDD | 39 |
| Entrées dataset HuggingFace | 538 + 919 (4 configs) |
| Index TF-IDF Fèfèn | ~1 457 entrées (lexique + corpus + Confiant) |
| Endpoints API FastAPI | 12 |
| Tests API | 16 passent, 2 skippés |
| Locales frontend | 3 (fr / en / crm) |
| Services Docker | 5 (db, adminer, api, backend, frontend) |

---

## Services et ports

| Service | Technologie | Port |
|---|---|---|
| Base de données | PostgreSQL 15 | 5433 |
| Adminer | Adminer 4 | 8080 |
| API dictionnaire + Fèfèn | FastAPI + Uvicorn | 8000 |
| API auth + contributions | Laravel 11 | 8001 |
| Interface web | Next.js 15 | 3000 |

---

## Lancer le projet

```bash
cd kreyol-matinik
cp .env.example .env
# Remplir POSTGRES_PASSWORD, JWT_SECRET, HF_TOKEN

docker compose up --build
```

| URL | Description |
|---|---|
| http://localhost:3000/fr | Interface web (français) |
| http://localhost:3000/crm | Interface web (créole) |
| http://localhost:3000/fr/chat | Chatbot Fèfèn |
| http://localhost:8000/docs | Documentation API Swagger |
| http://localhost:8080 | Adminer (BDD) |
