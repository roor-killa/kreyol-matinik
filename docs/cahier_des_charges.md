# Cahier des Charges — Projet Lang Matinitjé

**Projet :** API open source pour la langue créole martiniquaise
**Groupe :** Université des Antilles - NASDY
**Date :** Février 2026
**Dépôt :** github.com/roor-killa/langmatinitje — branche `main`
**Licence code :** MIT | **Licence données :** CC BY-SA 4.0

---

## 1. Contexte et Objectifs

### 1.1 Contexte

Le créole martiniquais (lang matinitjé / kréyol matinitjé / kréyol matinik) est une langue vivante parlée par environ 400 000 personnes en Martinique et dans la diaspora. Malgré sa richesse culturelle, cette langue reste sous-représentée dans les ressources numériques, les bases de données linguistiques et les modèles d'IA.

Ce projet vise à constituer, structurer et mettre à disposition la première infrastructure open source dédiée à la langue créole martiniquaise : collecte de données, API de traduction, dictionnaire, dataset public et chatbot conversationnel.

### 1.2 Objectifs

| # | Objectif | Type |
|---|---|---|



### 1.3 Périmètre

**Inclus :**
- Scraping de sources créolophones publiques (texte, liens audio/vidéo)
- API REST dictionnaire et traduction
- Interface web de contribution communautaire
- Dataset HuggingFace
- Chatbot Fèfèn (prototype)

**Exclus (hors périmètre v1) :**
- Traduction automatique temps réel (v2)
- Application mobile
- Reconnaissance vocale / transcription automatique (v2)

---

## 2. Sources de données cibles

### 2.1 Sources scraping

| Source | URL | Type de contenu | Priorité |
|---|---|---|---|
| Pawolotek | https://pawolotek.com/ | Texte, audio, vidéo | **P0** |
| À identifier | — | Presse créole, blogs | P1 |
| À identifier | — | Chansons, paroles | P1 |
| À identifier | — | Proverbes, expressions | P2 |

> Les sources P1/P2 seront identifiées durant la Phase 1. Chaque source nécessite une analyse préalable du `robots.txt` et des CGU.

### 2.2 Contraintes légales et éthiques

- Respect du `robots.txt` de chaque site
- Délai minimum de **2 secondes** entre chaque requête
- User-Agent identifié : `Lang-Matinitje-Bot/1.0 (Open Source; contact: roor@nasdy.fr)`
- Données utilisées exclusivement à des fins linguistiques et culturelles
- Attribution obligatoire des sources dans la base de données

---

## 3. Architecture technique

### 3.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                        COLLECTE                             │
│   Python Scrapers (POO)  →  data/raw/  →  data/processed/   │
└─────────────────────────┬───────────────────────────────────┘
                          │ import
┌─────────────────────────▼───────────────────────────────────┐
│                      BASE DE DONNÉES                        │
│                      PostgreSQL                             │
└──────┬──────────────────────────────────────────┬───────────┘
       │ ORM                                      │ ORM
┌──────▼──────────────┐              ┌────────────▼────────────┐
│   FastAPI (Python)  │              │    Laravel (PHP)        │
│   API dictionnaire  │◄─────────────│    Auth + Interface web │
│   API traduction    │   HTTP/JSON  │    Contributions        │
│   API chatbot       │              │    Validation           │
└──────┬──────────────┘              └─────────────────────────┘
       │
┌──────▼──────────────┐
│   HuggingFace       │
│   Dataset public    │
│   Modèle Fèfèn      │
└─────────────────────┘
```

### 3.2 Stack technique

| Couche | Technologie | Version cible |
|---|---|---|
| Scraping / data | Python | 3.10+ |
| Base de données | PostgreSQL | 15+ |
| API données | FastAPI | 0.110+ |
| ORM Python | SQLAlchemy | 2.x |
| API auth + web | Laravel | 11.x |
| ORM PHP | Eloquent (inclus Laravel) | — |
| Auth | Laravel Sanctum | — |
| Dataset | HuggingFace `datasets` | — |
| IA chatbot | HuggingFace Transformers | — |
| Containerisation | Docker + Docker Compose | — |

### 3.3 Architecture du dépôt

```
kreyol-matinik/
├── docs/
│   ├── cahier_des_charges.md       ← ce fichier
│   ├── uml/                        ← diagrammes de classes
│   └── api_contracts.md            ← contrats d'endpoints
│
├── scraper/                        ← Phase 1 (Python)
│   ├── src/
│   │   ├── __init__.py
│   │   ├── base_scraper.py         ← ABC BaseScraper
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── pawolotek_scraper.py
│   │   │   └── [autres_scrapers].py
│   │   ├── manager.py              ← ScraperManager (Factory)
│   │   ├── pipeline.py             ← DataPipeline (nettoyage)
│   │   └── observers.py            ← Observer Pattern (logs/alertes)
│   ├── data/
│   │   ├── raw/                    ← données brutes scrapées
│   │   └── processed/              ← données nettoyées
│   ├── tests/
│   ├── requirements.txt
│   └── main.py
│
├── api/                            ← Phase 3 (FastAPI)
│   ├── app/
│   │   ├── main.py
│   │   ├── models/                 ← modèles SQLAlchemy
│   │   ├── routers/
│   │   │   ├── dictionary.py
│   │   │   ├── translation.py
│   │   │   └── chat.py
│   │   └── schemas/                ← schémas Pydantic
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── web/                            ← Phase 5 (Laravel)
│   └── [structure Laravel standard]
│
├── dataset/                        ← Phase 4
│   ├── export_huggingface.py
│   └── dataset_card.md
│
├── chatbot/                        ← Phase 6
│   ├── train.py
│   └── inference.py
│
├── docker-compose.yml              ← orchestration globale
└── README.md
```

---

## 4. Modèle de données

### 4.1 Schéma PostgreSQL

```sql
-- Sources scrapées
CREATE TABLE sources (
    id          SERIAL PRIMARY KEY,
    nom         VARCHAR(255) NOT NULL,
    url         VARCHAR(500) NOT NULL UNIQUE,
    type        VARCHAR(50),            -- 'texte', 'audio', 'vidéo', 'mixte'
    langue      VARCHAR(50) DEFAULT 'kréyol matinitjé',
    scrape_at   TIMESTAMP DEFAULT NOW(),
    robots_ok   BOOLEAN DEFAULT FALSE
);

-- Entrées du dictionnaire créole
CREATE TABLE mots (
    id              SERIAL PRIMARY KEY,
    mot_creole      VARCHAR(255) NOT NULL,
    phonetique      VARCHAR(255),
    categorie_gram  VARCHAR(50),        -- 'nom', 'vèb', 'adjektif', ...
    source_id       INTEGER REFERENCES sources(id),
    valide          BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Traductions FR ↔ Créole
CREATE TABLE traductions (
    id              SERIAL PRIMARY KEY,
    mot_id          INTEGER REFERENCES mots(id) ON DELETE CASCADE,
    langue_source   VARCHAR(10) NOT NULL,   -- 'fr' ou 'crm' (créole martiniquais)
    langue_cible    VARCHAR(10) NOT NULL,
    texte_source    TEXT NOT NULL,
    texte_cible     TEXT NOT NULL,
    contexte        TEXT,
    source_id       INTEGER REFERENCES sources(id),
    valide          BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Définitions en créole pur (dictionnaire monolingue)
CREATE TABLE definitions (
    id          SERIAL PRIMARY KEY,
    mot_id      INTEGER REFERENCES mots(id) ON DELETE CASCADE,
    definition  TEXT NOT NULL,          -- rédigée en créole
    exemple     TEXT,                   -- exemple d'usage en créole
    source_id   INTEGER REFERENCES sources(id),
    valide      BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Expressions et proverbes
CREATE TABLE expressions (
    id              SERIAL PRIMARY KEY,
    texte_creole    TEXT NOT NULL,
    texte_fr        TEXT,
    type            VARCHAR(50),        -- 'proverbe', 'expression', 'locution'
    source_id       INTEGER REFERENCES sources(id),
    valide          BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Médias (audio, vidéo)
CREATE TABLE medias (
    id          SERIAL PRIMARY KEY,
    url         VARCHAR(500) NOT NULL,
    type        VARCHAR(20) NOT NULL,   -- 'audio', 'vidéo'
    titre       TEXT,
    description TEXT,
    duree_sec   INTEGER,
    source_id   INTEGER REFERENCES sources(id),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Corpus de phrases pour l'entraînement IA
CREATE TABLE corpus (
    id              SERIAL PRIMARY KEY,
    texte_creole    TEXT NOT NULL,
    texte_fr        TEXT,
    domaine         VARCHAR(100),       -- 'quotidien', 'culture', 'nature', ...
    source_id       INTEGER REFERENCES sources(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Utilisateurs (géré par Laravel, référencé ici)
CREATE TABLE contributeurs (
    id          SERIAL PRIMARY KEY,
    laravel_id  INTEGER NOT NULL UNIQUE,
    pseudo      VARCHAR(100),
    nb_contrib  INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Historique des contributions/corrections
CREATE TABLE contributions (
    id              SERIAL PRIMARY KEY,
    contributeur_id INTEGER REFERENCES contributeurs(id),
    table_cible     VARCHAR(50),        -- 'mots', 'traductions', etc.
    entite_id       INTEGER,
    type_action     VARCHAR(20),        -- 'ajout', 'correction', 'validation'
    contenu_avant   JSONB,
    contenu_apres   JSONB,
    statut          VARCHAR(20) DEFAULT 'en_attente', -- 'validé', 'rejeté'
    created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Contrats d'API (FastAPI)

### 5.1 Dictionnaire

```
GET  /api/v1/dictionary/search?q={terme}&lang={fr|crm}&page={n}
GET  /api/v1/dictionary/{id}
GET  /api/v1/dictionary/random
POST /api/v1/dictionary          ← authentifié
PUT  /api/v1/dictionary/{id}     ← authentifié
```

### 5.2 Traduction

```
POST /api/v1/translate
     Body: { "text": "...", "source": "fr", "target": "crm" }

GET  /api/v1/expressions?type={proverbe|expression}
GET  /api/v1/corpus?domaine={...}&limit={n}
```

### 5.3 Médias

```
GET  /api/v1/media?type={audio|video}&page={n}
GET  /api/v1/media/{id}
```

### 5.4 Chatbot Fèfèn

```
POST /api/v1/chat
     Body: { "message": "...", "session_id": "..." }
     Response: { "reply": "...", "session_id": "..." }
```

### 5.5 Authentification

L'authentification est gérée par Laravel Sanctum. FastAPI valide les tokens via un middleware dédié interrogeant Laravel.

---

## 6. Architecture POO — Scraper (héritage TP_Scraping)

```
BaseScraper (ABC)
│   + base_url: str
│   + delay: float
│   + headers: dict
│   + data: list[dict]
│   ─────────────────────────
│   + fetch_page(url) → BeautifulSoup | None
│   + save_to_json(path)
│   + save_to_csv(path)
│   # scrape(max_pages) → list[dict]   [abstract]
│   # parse(soup) → list[dict]         [abstract]
│
├── PawoloTekScraper
│       scrape() → textes + liens médias
│       parse()  → extraction paragraphes créole
│
└── [FutureScraper...]

ScraperManager                         ← Factory Pattern
│   + create_scraper(source: str) → BaseScraper
│   + scrape_all(parallel: bool)
│   + aggregate() → dict unifié

DataPipeline
│   + clean(raw_data) → données normalisées
│   + detect_language(text) → 'fr' | 'crm' | 'mixed'
│   + import_to_db(processed_data)

ScraperObserver (ABC)                  ← Observer Pattern
├── LogObserver          → logs fichier
└── StatsObserver        → compteurs de progression
```

---

## 7. Phasage et jalons

| Phase | Contenu | Durée estimée | Livrable |
|-------|---|---|---|
| **0** | CDC + Architecture + UML | 1-2 sem | `docs/` complet |
| **1** | Scraping + Pipeline données | 2-3 sem | `data/processed/` + rapport |
| **2** | Schéma PostgreSQL + import | 2 sem | BDD peuplée |
| **3** | API FastAPI | 2 sem | API documentée (Swagger) |
| **4** | Dataset HuggingFace | 1 sem | Dataset publié |
| **5** | Interface Laravel | 3 sem | Web app déployée |
| **6** | Chatbot Fèfèn | 3-4 sem | Prototype intégré |

---

## 8. Livrables par phase

### Phase 0 (actuelle)
- [x] `docs/cahier_des_charges.md`
- [ ] `docs/uml/diagramme_classes.png` — diagramme de classes Phase 1
- [ ] `docs/api_contracts.md` — spécification complète des endpoints
- [ ] `docker-compose.yml` — squelette PostgreSQL + adminer

### Phase 1
- [ ] `scraper/src/base_scraper.py`
- [ ] `scraper/src/scrapers/pawolotek_scraper.py`
- [ ] `scraper/src/manager.py`
- [ ] `scraper/data/raw/*.json`
- [ ] `scraper/data/processed/*.json`
- [ ] `scraper/requirements.txt`

### Phase 2
- [ ] `scraper/db/schema.sql`
- [ ] `scraper/src/pipeline.py`
- [ ] Script d'import BDD

### Phases 3–6
- Définis dans les sprints suivants

---

## 9. Conventions de développement

### Git

- Branche principale du projet : `main`
- Branches de feature : `feat/phase1-scraper`, `feat/phase3-api`, etc.
- Commits : `[phase1] feat: ajout PawoloTekScraper`
- Pull requests vers `main` pour review avant merge

### Python

- Python 3.10+ avec type hints obligatoires
- PEP 8 — formatage avec `black`
- Docstrings Google style
- Logging via le module standard `logging` (pas de `print` en production)
- Tests avec `pytest`

### Divers

- Toutes les variables d'environnement dans `.env` (jamais commitées)
- `requirements.txt` maintenu à jour à chaque ajout de dépendance
- `robots.txt` vérifié et documenté pour chaque nouvelle source

---

## 10. Références

- TP_Scraping.md — architecture de base des scrapers
- [BeautifulSoup4 docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [Laravel 11 docs](https://laravel.com/docs/11.x)
- [HuggingFace datasets](https://huggingface.co/docs/datasets/)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers/)
- [Licence CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)


## Pour démarrer :

  cd kreyol-matinik
  cp .env.example .env
  # Éditer .env et changer POSTGRES_PASSWORD
  docker compose up -d

  # Adminer → http://localhost:8080
  # Serveur: db | User: creole | Mot de passe: [ton mdp] | BDD: langmatinitje

  ## Lancer le scraping
  cd kreyol-matinik/scraper
  .venv/bin/python main.py --source potomitan

  Le délai par défaut est 60 secondes entre chaque requête (imposé par le robots.txt du site). Avec ~170 contes + les poèmes, le scraping complet prendra plusieurs heures.

  Pour tester sur un sous-ensemble d'abord :

  # 10 articles par section (contes + poèmes) — ~22 min
  .venv/bin/python main.py --source potomitan --max 10

  # Seulement les contes
  .venv/bin/python main.py --source potomitan --categories contes

  # Seulement les poèmes
  .venv/bin/python main.py --source potomitan --categories poemes