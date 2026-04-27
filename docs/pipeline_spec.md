# Spec Technique — Phase 8 : Pipeline d'Extraction Linguistique

**Projet :** kreyol-matinik (Lang Matinitjé)
**Feature :** Boucle de rétroaction conversationnelle → base linguistique
**Priorité :** Phase 8 (après les 7 phases existantes)

---

## 1. Résumé

Les conversations des utilisateurs avec Fèfèn (chatbot kreyol) doivent alimenter automatiquement la base linguistique du projet. Chaque échange est loggé, analysé par un pipeline NLP, soumis à modération humaine, puis intégré dans le dataset et l'index RAG.

**Flux :**
```
Utilisateur ↔ Fèfèn (chat)
       │
       ▼
 conversation_logs (PostgreSQL)
       │
       ▼
 pipeline/worker.py (cron ou async)
       │
       ▼
 moderation_candidates (PostgreSQL)
       │
       ▼
 Lingwis (modérateur humain via UI)
       │
       ▼
 linguistic_entries (PostgreSQL)
       │
       ├──→ dataset/ (export JSONL, HuggingFace)
       └──→ chatbot/ (rebuild TF-IDF index)
```

---

## 2. Nouvelles tables PostgreSQL

Ajouter au fichier `scraper/db/schema.sql` et créer une migration Alembic ou un script SQL dédié.

### 2.1 conversation_logs

```sql
CREATE TABLE conversation_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_message    TEXT NOT NULL,
    bot_response    TEXT NOT NULL,
    detected_lang   VARCHAR(10) DEFAULT 'crm',
    lang_confidence FLOAT DEFAULT 0.0,
    user_correction TEXT,                    -- si l'utilisateur corrige Fèfèn
    is_processed    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    processed_at    TIMESTAMP
);

CREATE INDEX idx_conv_logs_unprocessed ON conversation_logs (is_processed) WHERE NOT is_processed;
CREATE INDEX idx_conv_logs_session ON conversation_logs (session_id);
```

### 2.2 moderation_candidates

```sql
CREATE TYPE candidate_type AS ENUM (
    'new_word',           -- mot absent du dictionnaire
    'spelling_variant',   -- variante orthographique d'un mot existant
    'grammar_pattern',    -- pattern grammatical détecté
    'expression',         -- locution / expression figée
    'correction'          -- correction utilisateur d'une réponse Fèfèn
);

CREATE TYPE candidate_status AS ENUM (
    'pending',
    'approved',
    'rejected',
    'merged'              -- fusionné avec une entrée existante
);

CREATE TABLE moderation_candidates (
    id              SERIAL PRIMARY KEY,
    candidate_type  candidate_type NOT NULL,
    status          candidate_status DEFAULT 'pending',

    -- Contenu extrait
    word            VARCHAR(255),
    definition_kr   TEXT,
    definition_fr   TEXT,
    phonetic        VARCHAR(255),
    pos             VARCHAR(50),             -- catégorie grammaticale
    examples        JSONB DEFAULT '[]',      -- [{"kr": "...", "fr": "..."}]
    context         TEXT,                    -- phrase source d'où le candidat est extrait
    variants        JSONB DEFAULT '[]',      -- variantes orthographiques détectées

    -- Traçabilité
    source_log_ids  UUID[] NOT NULL,         -- conversation_logs.id ayant généré ce candidat
    speaker_count   INTEGER DEFAULT 1,       -- nombre de locuteurs distincts ayant utilisé ce mot
    frequency       INTEGER DEFAULT 1,       -- nombre d'occurrences total

    -- Modération
    reviewed_by     INTEGER REFERENCES users(id),
    reviewed_at     TIMESTAMP,
    reviewer_note   TEXT,

    -- Si approved → lien vers l'entrée créée
    linked_mot_id   INTEGER REFERENCES mots(id),

    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mod_candidates_status ON moderation_candidates (status);
CREATE INDEX idx_mod_candidates_type ON moderation_candidates (candidate_type);
```

### 2.3 linguistic_entries (entrées validées issues de conversations)

```sql
CREATE TABLE linguistic_entries (
    id              SERIAL PRIMARY KEY,
    mot_id          INTEGER REFERENCES mots(id) ON DELETE CASCADE,
    candidate_id    INTEGER REFERENCES moderation_candidates(id),
    source          VARCHAR(50) DEFAULT 'conversation',
    validated_by    INTEGER REFERENCES users(id),
    validated_at    TIMESTAMP DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'       -- infos supplémentaires (fréquence, contextes)
);
```

---

## 3. Modèles SQLAlchemy

Ajouter dans `api/app/models/models.py` :

```python
import uuid
from sqlalchemy import Column, String, Text, Float, Boolean, Integer, DateTime, ForeignKey, Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

class ConversationLog(Base):
    __tablename__ = "conversation_logs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id      = Column(UUID(as_uuid=True), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_message    = Column(Text, nullable=False)
    bot_response    = Column(Text, nullable=False)
    detected_lang   = Column(String(10), default="crm")
    lang_confidence = Column(Float, default=0.0)
    user_correction = Column(Text, nullable=True)
    is_processed    = Column(Boolean, default=False)
    created_at      = Column(DateTime, server_default=func.now())
    processed_at    = Column(DateTime, nullable=True)


class ModerationCandidate(Base):
    __tablename__ = "moderation_candidates"

    id              = Column(Integer, primary_key=True)
    candidate_type  = Column(PgEnum("new_word", "spelling_variant", "grammar_pattern",
                                     "expression", "correction", name="candidate_type"), nullable=False)
    status          = Column(PgEnum("pending", "approved", "rejected", "merged",
                                     name="candidate_status"), default="pending")
    word            = Column(String(255))
    definition_kr   = Column(Text)
    definition_fr   = Column(Text)
    phonetic        = Column(String(255))
    pos             = Column(String(50))
    examples        = Column(JSONB, default=[])
    context         = Column(Text)
    variants        = Column(JSONB, default=[])
    source_log_ids  = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    speaker_count   = Column(Integer, default=1)
    frequency       = Column(Integer, default=1)
    reviewed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at     = Column(DateTime, nullable=True)
    reviewer_note   = Column(Text, nullable=True)
    linked_mot_id   = Column(Integer, ForeignKey("mots.id"), nullable=True)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LinguisticEntry(Base):
    __tablename__ = "linguistic_entries"

    id              = Column(Integer, primary_key=True)
    mot_id          = Column(Integer, ForeignKey("mots.id", ondelete="CASCADE"))
    candidate_id    = Column(Integer, ForeignKey("moderation_candidates.id"))
    source          = Column(String(50), default="conversation")
    validated_by    = Column(Integer, ForeignKey("users.id"))
    validated_at    = Column(DateTime, server_default=func.now())
    metadata        = Column(JSONB, default={})
```

---

## 4. Schemas Pydantic

Ajouter dans `api/app/schemas/schemas.py` :

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class ConversationLogOut(BaseModel):
    id: UUID
    session_id: UUID
    user_message: str
    bot_response: str
    detected_lang: str
    user_correction: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class ModerationCandidateOut(BaseModel):
    id: int
    candidate_type: str
    status: str
    word: Optional[str]
    definition_kr: Optional[str]
    definition_fr: Optional[str]
    pos: Optional[str]
    examples: list
    context: Optional[str]
    variants: list
    speaker_count: int
    frequency: int
    reviewer_note: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class ModerationReview(BaseModel):
    status: str                              # "approved", "rejected", "merged"
    reviewer_note: Optional[str] = None
    word_override: Optional[str] = None      # le lingwis peut corriger le mot
    definition_kr: Optional[str] = None
    definition_fr: Optional[str] = None
    pos_override: Optional[str] = None
    merge_with_mot_id: Optional[int] = None  # si status="merged"
```

---

## 5. Structure du dossier pipeline/

```
pipeline/
├── __init__.py
├── config.py           ← Configuration (seuils, taille de batch)
├── extractor.py        ← Extraction linguistique depuis les logs
├── phonetics.py        ← Soundex adapté au créole martiniquais
├── ngrams.py           ← Extraction n-grammes et fréquences
├── worker.py           ← Worker principal (cron ou asyncio)
├── requirements.txt    ← dépendances spécifiques au pipeline
└── tests/
    ├── __init__.py
    ├── test_extractor.py
    ├── test_phonetics.py
    └── test_ngrams.py
```

---

## 6. Composants du pipeline — détails

### 6.1 config.py

```python
from pydantic_settings import BaseSettings

class PipelineConfig(BaseSettings):
    batch_size: int = 50
    min_speakers: int = 3          # nb locuteurs min pour qu'un mot soit candidat
    min_frequency: int = 5         # nb occurrences min
    ngram_min_count: int = 3       # fréquence min pour détecter une expression
    ngram_range: tuple = (2, 4)    # bi-grammes à quadri-grammes
    known_patterns: list = [
        r"\bka\s+\w+",             # présent progressif : "ka manjé"
        r"\bté\s+\w+",            # passé : "té ka alé"
        r"\bké\s+\w+",            # futur : "ké rivé"
        r"\bpa\s+\w+",            # négation : "pa ni"
    ]

    class Config:
        env_prefix = "PIPELINE_"
```

### 6.2 phonetics.py — Soundex kréyol

Le créole martiniquais a des particularités phonétiques :
- "tch" et "ch" sont des phonèmes distincts
- "dj" est un phonème unique
- Les nasales (an, en, on, in) sont très fréquentes
- "w" et "ou" sont souvent interchangeables

```python
def soundex_kreyol(word: str) -> str:
    """
    Soundex adapté au créole martiniquais.
    Regroupe les variantes phonétiques d'un même mot.

    Exemples :
        soundex_kreyol("mwen") == soundex_kreyol("moin")  # True
        soundex_kreyol("tjenbé") == soundex_kreyol("tchenbé")  # True
    """
    # 1. Normaliser : minuscules, supprimer accents (sauf è/é pour le créole)
    # 2. Remplacer les digrammes créoles par des codes uniques :
    #    tch→T, ch→S, dj→J, an→A, en→E, on→O, in→I, ou→W
    # 3. Supprimer les voyelles internes (garder la première)
    # 4. Mapper les consonnes restantes vers des chiffres (adapté)
    # 5. Tronquer à 4 caractères
    pass
```

### 6.3 extractor.py

```python
class LinguisticExtractor:
    """
    Analyse les conversation_logs non traités et génère des
    moderation_candidates.
    """

    def __init__(self, db_session, config: PipelineConfig):
        self.db = db_session
        self.config = config
        self._load_known_words()

    def _load_known_words(self):
        """Charge tous les mots existants du dictionnaire en mémoire."""
        # SELECT mot_creole FROM mots → set()
        # + index phonétique pour chaque mot

    def extract_batch(self, logs: list[ConversationLog]) -> list[dict]:
        """
        Traite un batch de logs et retourne les candidats.
        """
        candidates = []
        candidates += self._extract_new_words(logs)
        candidates += self._extract_variants(logs)
        candidates += self._extract_patterns(logs)
        candidates += self._extract_expressions(logs)
        candidates += self._extract_corrections(logs)
        return candidates

    def _extract_new_words(self, logs) -> list[dict]:
        """
        Mots présents dans les messages utilisateurs mais absents
        du dictionnaire existant.

        Logique :
        1. Tokeniser chaque user_message
        2. Filtrer les mots < 2 caractères et les stop words
        3. Chercher chaque mot dans self.known_words
        4. Si absent ET utilisé par >= min_speakers locuteurs distincts → candidat
        """

    def _extract_variants(self, logs) -> list[dict]:
        """
        Variantes orthographiques d'un mot existant.

        Logique :
        1. Pour chaque mot inconnu, calculer soundex_kreyol()
        2. Comparer avec l'index phonétique des mots connus
        3. Si match → candidat de type 'spelling_variant'
        """

    def _extract_patterns(self, logs) -> list[dict]:
        """
        Patterns grammaticaux récurrents (ka+V, té+V, etc.)

        Logique :
        1. Appliquer les regex de config.known_patterns
        2. Compter les occurrences de chaque pattern
        3. Si fréquence >= seuil → candidat de type 'grammar_pattern'
        """

    def _extract_expressions(self, logs) -> list[dict]:
        """
        Expressions figées / locutions via analyse n-grammes.

        Logique :
        1. Extraire tous les n-grammes (2 à 4 mots) des messages
        2. Filtrer par fréquence >= ngram_min_count
        3. Filtrer ceux dont le PMI (pointwise mutual information) est élevé
        4. Si l'expression n'est pas dans la table expressions → candidat
        """

    def _extract_corrections(self, logs) -> list[dict]:
        """
        Corrections explicites par l'utilisateur.

        Logique :
        1. Filtrer les logs où user_correction IS NOT NULL
        2. Chaque correction = candidat direct de type 'correction'
        """
```

### 6.4 worker.py

```python
import asyncio
from datetime import datetime

class PipelineWorker:
    """
    Worker qui tourne en boucle (ou en one-shot) pour traiter
    les conversation_logs non traités.
    """

    def __init__(self, db_session, config: PipelineConfig):
        self.db = db_session
        self.config = config
        self.extractor = LinguisticExtractor(db_session, config)

    async def run_once(self):
        """Traite un batch de logs."""
        # 1. SELECT * FROM conversation_logs WHERE NOT is_processed
        #    ORDER BY created_at LIMIT batch_size
        logs = self._fetch_unprocessed()
        if not logs:
            return 0

        # 2. Extraire les candidats
        candidates = self.extractor.extract_batch(logs)

        # 3. Dédupliquer et fusionner avec les candidats existants
        self._upsert_candidates(candidates)

        # 4. Marquer les logs comme traités
        self._mark_processed(logs)

        return len(candidates)

    def _upsert_candidates(self, candidates):
        """
        Si un candidat similaire existe déjà en pending :
        - Incrémenter frequency et speaker_count
        - Ajouter les source_log_ids
        Sinon : INSERT
        """

    async def run_loop(self, interval_seconds=21600):  # 6h par défaut
        """Boucle infinie avec intervalle."""
        while True:
            count = await self.run_once()
            print(f"[pipeline] {count} candidats extraits à {datetime.now()}")
            await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    # Setup DB session, config, then run
```

---

## 7. Nouveaux endpoints API

### 7.1 Modifier POST /chat (routers/chat.py)

Ajouter le logging de chaque échange :

```python
@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db),
               current_user = Depends(get_current_user_optional)):
    # 1. Appeler Fèfèn comme avant
    reply = fefen.answer(request.message)

    # 2. Logger la conversation
    log = ConversationLog(
        session_id=request.session_id or uuid.uuid4(),
        user_id=current_user.id if current_user else None,
        user_message=request.message,
        bot_response=reply,
        detected_lang=detect_language(request.message),
        lang_confidence=detect_confidence(request.message),
    )
    db.add(log)
    db.commit()

    return {"reply": reply, "session_id": str(log.session_id)}
```

### 7.2 Endpoint correction utilisateur

```python
@router.post("/chat/correct")
async def correct_response(
    log_id: UUID,
    correction: str,
    db: Session = Depends(get_db)
):
    """L'utilisateur corrige une réponse de Fèfèn."""
    log = db.query(ConversationLog).filter_by(id=log_id).first()
    if not log:
        raise HTTPException(404, "Log introuvable")
    log.user_correction = correction
    db.commit()
    return {"status": "correction enregistrée"}
```

### 7.3 Nouveau router : routers/moderation.py

```python
@router.get("/moderation/queue")
async def get_queue(
    status: str = "pending",
    candidate_type: Optional[str] = None,
    page: int = 1, limit: int = 20,
    db: Session = Depends(get_db),
    _admin = Depends(require_lingwis)
):
    """Liste les candidats en attente de modération."""

@router.get("/moderation/stats")
async def get_stats(db: Session = Depends(get_db), _admin = Depends(require_lingwis)):
    """Statistiques de modération (pending, approved, rejected, par type)."""

@router.patch("/moderation/{candidate_id}")
async def review_candidate(
    candidate_id: int,
    review: ModerationReview,
    db: Session = Depends(get_db),
    current_user = Depends(require_lingwis)
):
    """
    Approuver, rejeter ou fusionner un candidat.

    Si approved :
    1. Créer une entrée dans `mots` (+ traductions, definitions)
    2. Créer une entrée dans `linguistic_entries` (traçabilité)
    3. Mettre à jour le status du candidat

    Si merged :
    1. Ajouter la variante au mot existant (merge_with_mot_id)
    2. Créer linguistic_entry avec lien vers le mot existant

    Si rejected :
    1. Mettre à jour le status + reviewer_note
    """
```

---

## 8. Rôle "lingwis"

Ajouter un nouveau rôle dans le système d'auth existant :

```python
# Dans dependencies.py
def require_lingwis(current_user = Depends(get_current_user)):
    if current_user.role not in ("admin", "lingwis"):
        raise HTTPException(403, "Rôle lingwis ou admin requis")
    return current_user
```

Ajouter "lingwis" dans l'enum des rôles en BDD si nécessaire.

---

## 9. Frontend — Panel de modération

Nouvelle page : `frontend/src/app/[locale]/admin/moderation/page.tsx`

Fonctionnalités :
- Tableau des candidats avec filtres (status, type)
- Pour chaque candidat : contexte (phrase source), exemples, fréquence, nb de locuteurs
- Boutons : Approuver / Rejeter / Fusionner
- Champ note du modérateur
- Sur approbation : formulaire d'édition (mot, définition, catégorie grammaticale)

---

## 10. Extension dataset HuggingFace

Modifier `dataset/export_huggingface.py` pour ajouter une 5ème config :

```python
# Nouvelle config : "conversations_validated"
{
    "config_name": "conversations_validated",
    "description": "Entrées linguistiques validées issues des conversations Fèfèn",
    "query": """
        SELECT le.*, m.mot_creole, m.phonetique, m.categorie_gram,
               mc.examples, mc.context, mc.speaker_count, mc.frequency
        FROM linguistic_entries le
        JOIN mots m ON le.mot_id = m.id
        LEFT JOIN moderation_candidates mc ON le.candidate_id = mc.id
        WHERE le.source = 'conversation'
    """
}
```

---

## 11. Rebuild TF-IDF après validation

Quand un candidat est approuvé, déclencher un rebuild de l'index :

```python
# Dans routers/moderation.py, après approbation
from chatbot.train import rebuild_index

async def _post_approval_hook(mot_id: int, db: Session):
    """Ajoute le nouveau mot à l'index TF-IDF de Fèfèn."""
    # Option A : rebuild complet (simple, ok si < 10k entrées)
    rebuild_index()

    # Option B : ajout incrémental (si perf nécessaire)
    # fefen_instance.add_to_index(mot_id, ...)
```

---

## 12. Tests à écrire

```
pipeline/tests/
├── test_extractor.py
│   ├── test_extract_new_words_basic
│   ├── test_extract_new_words_min_speakers
│   ├── test_extract_variants_phonetic_match
│   ├── test_extract_patterns_ka_verb
│   ├── test_extract_expressions_ngram
│   └── test_extract_corrections
├── test_phonetics.py
│   ├── test_soundex_mwen_moin
│   ├── test_soundex_tjenbé_tchenbé
│   ├── test_soundex_distinct_words
│   └── test_soundex_nasals
└── test_ngrams.py
    ├── test_bigram_extraction
    ├── test_trigram_filtering
    └── test_pmi_calculation
```

Tests API (ajouter dans `api/tests/`) :
```
├── test_chat_logging.py
│   ├── test_chat_creates_log
│   ├── test_chat_correction
│   └── test_chat_anonymous_user
└── test_moderation.py
    ├── test_queue_requires_lingwis
    ├── test_approve_creates_mot
    ├── test_reject_sets_status
    ├── test_merge_links_variant
    └── test_stats_counts
```

---

## 13. Ordre d'implémentation recommandé pour Claude Code

```
Tâche 1 │ SQL migration : 3 nouvelles tables
Tâche 2 │ Models SQLAlchemy + Schemas Pydantic
Tâche 3 │ Modifier POST /chat pour logger
Tâche 4 │ POST /chat/correct endpoint
Tâche 5 │ pipeline/config.py + pipeline/phonetics.py + tests
Tâche 6 │ pipeline/ngrams.py + tests
Tâche 7 │ pipeline/extractor.py + tests
Tâche 8 │ pipeline/worker.py (--once mode)
Tâche 9 │ routers/moderation.py + dependency require_lingwis
Tâche 10│ tests API modération
Tâche 11│ Frontend moderation panel
Tâche 12│ Extension export_huggingface.py
Tâche 13│ Hook rebuild TF-IDF post-approbation
```

Chaque tâche est autonome et testable. Commencer par `Tâche 1` dans Claude Code.

---

## 14. Dépendances supplémentaires

### pipeline/requirements.txt
```
sqlalchemy>=2.0
psycopg2-binary
pydantic-settings
```

Pas de dépendance NLP lourde — le pipeline utilise :
- `re` (stdlib) pour les patterns grammaticaux
- L'algorithme Soundex custom pour la phonétique
- Des compteurs simples pour les n-grammes et PMI

Si besoin ultérieur de tokenisation plus fine, ajouter `spacy` avec un modèle français (pas de modèle créole existant).
