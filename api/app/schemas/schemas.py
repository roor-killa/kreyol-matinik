"""
Schémas Pydantic v2 — Lang Matinitjé API
"""
from datetime import datetime
from typing import Any, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _domain(url: Optional[str]) -> Optional[str]:
    """Extrait le domaine d'une URL (ex: 'pawolotek.com')."""
    if not url:
        return None
    return urlparse(url).netloc or url


# ---------------------------------------------------------------------------
# Dictionnaire
# ---------------------------------------------------------------------------

class TraductionBrief(BaseModel):
    langue_source: str
    langue_cible: str
    texte_source: str
    texte_cible: str

    model_config = ConfigDict(from_attributes=True)


class TraductionWithId(TraductionBrief):
    id: int


class TraductionUpdate(BaseModel):
    texte_source: Optional[str] = None
    texte_cible: Optional[str] = None


class DefinitionBrief(BaseModel):
    definition: str
    exemple: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MotSearchResult(BaseModel):
    id: int
    mot_creole: str
    phonetique: Optional[str] = None
    categorie_gram: Optional[str] = None
    traductions: List[TraductionBrief] = []
    definitions: List[DefinitionBrief] = []
    source: Optional[str] = None
    valide: bool

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_mot(cls, mot) -> "MotSearchResult":
        return cls(
            id=mot.id,
            mot_creole=mot.mot_creole,
            phonetique=mot.phonetique,
            categorie_gram=mot.categorie_gram,
            traductions=[
                TraductionBrief(
                    langue_source=t.langue_source,
                    langue_cible=t.langue_cible,
                    texte_source=t.texte_source,
                    texte_cible=t.texte_cible,
                )
                for t in mot.traductions
            ],
            definitions=[
                DefinitionBrief(definition=d.definition, exemple=d.exemple)
                for d in mot.definitions
            ],
            source=_domain(mot.source.url) if mot.source else None,
            valide=mot.valide,
        )


class MotDetail(BaseModel):
    id: int
    mot_creole: str
    phonetique: Optional[str] = None
    categorie_gram: Optional[str] = None
    traductions: List[TraductionWithId] = []
    definitions: List[DefinitionBrief] = []
    expressions: List[dict] = []
    source_id: Optional[int] = None
    valide: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_mot(cls, mot) -> "MotDetail":
        return cls(
            id=mot.id,
            mot_creole=mot.mot_creole,
            phonetique=mot.phonetique,
            categorie_gram=mot.categorie_gram,
            traductions=[
                TraductionWithId(
                    id=t.id,
                    langue_source=t.langue_source,
                    langue_cible=t.langue_cible,
                    texte_source=t.texte_source,
                    texte_cible=t.texte_cible,
                )
                for t in mot.traductions
            ],
            definitions=[
                DefinitionBrief(definition=d.definition, exemple=d.exemple)
                for d in mot.definitions
            ],
            expressions=[],
            source_id=mot.source_id,
            valide=mot.valide,
            created_at=mot.created_at,
        )


class DictionarySearchResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[MotSearchResult]


class MotCreate(BaseModel):
    mot_creole: str
    phonetique: Optional[str] = None
    categorie_gram: Optional[str] = None
    source_id: Optional[int] = None


class MotUpdate(BaseModel):
    mot_creole: Optional[str] = None
    phonetique: Optional[str] = None
    categorie_gram: Optional[str] = None
    valide: Optional[bool] = None
    source_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Admin — Définitions
# ---------------------------------------------------------------------------

class DefinitionWithId(BaseModel):
    id: int
    definition: str
    exemple: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DefinitionCreate(BaseModel):
    definition: str
    exemple: Optional[str] = None


class DefinitionUpdate(BaseModel):
    definition: Optional[str] = None
    exemple: Optional[str] = None


# ---------------------------------------------------------------------------
# Admin — Corpus / Expressions (update)
# ---------------------------------------------------------------------------

class CorpusUpdate(BaseModel):
    texte_creole: Optional[str] = None
    texte_fr: Optional[str] = None
    domaine: Optional[str] = None


class ExpressionUpdate(BaseModel):
    texte_creole: Optional[str] = None
    texte_fr: Optional[str] = None
    explication: Optional[str] = None
    type: Optional[str] = None


# ---------------------------------------------------------------------------
# Traduction
# ---------------------------------------------------------------------------

class TranslateRequest(BaseModel):
    text: str
    source: str = "fr"
    target: str = "crm"


class TranslateResponse(BaseModel):
    source: str
    target: str
    input: str
    output: str
    confidence: float
    method: str


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

class ExpressionOut(BaseModel):
    id: int
    texte_creole: str
    texte_fr: Optional[str] = None
    traduction_fr: Optional[str] = None   # alias de texte_fr pour le frontend
    type: str
    explication: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_expr(cls, expr) -> "ExpressionOut":
        return cls(
            id=expr.id,
            texte_creole=expr.texte_creole,
            texte_fr=expr.texte_fr,
            traduction_fr=expr.texte_fr,
            type=expr.type,
            explication=expr.explication,
            source=_domain(expr.source.url) if expr.source else None,
        )


class ExpressionsResponse(BaseModel):
    total: int
    results: List[ExpressionOut]


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

class CorpusOut(BaseModel):
    id: int
    texte_creole: str
    texte_fr: Optional[str] = None
    domaine: str
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_corpus(cls, c) -> "CorpusOut":
        return cls(
            id=c.id,
            texte_creole=c.texte_creole,
            texte_fr=c.texte_fr,
            domaine=c.domaine,
            source=_domain(c.source.url) if c.source else None,
        )


class CorpusResponse(BaseModel):
    total: int
    results: List[CorpusOut]


# ---------------------------------------------------------------------------
# Médias
# ---------------------------------------------------------------------------

class MediaOut(BaseModel):
    id: int
    url: str
    type: str
    titre: Optional[str] = None
    duree_sec: Optional[int] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_media(cls, m) -> "MediaOut":
        return cls(
            id=m.id,
            url=m.url,
            type=m.type,
            titre=m.titre,
            duree_sec=m.duree_sec,
            source=_domain(m.source.url) if m.source else None,
        )


class MediaResponse(BaseModel):
    total: int
    results: List[MediaOut]


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    model_version: str


# ---------------------------------------------------------------------------
# Contributeur
# ---------------------------------------------------------------------------

class ContributeurOut(BaseModel):
    id: int
    pseudo: Optional[str] = None
    nb_contrib: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth — Utilisateurs
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ContributeurBrief(BaseModel):
    id: int
    pseudo: Optional[str] = None
    nb_contrib: int
    de_confiance: bool


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    contributeur: Optional[ContributeurBrief] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user) -> "UserOut":
        contrib = user.contributeur
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.value,
            contributeur=ContributeurBrief(
                id=contrib.id,
                pseudo=contrib.pseudo,
                nb_contrib=contrib.nb_contrib,
                de_confiance=contrib.de_confiance,
            ) if contrib else None,
        )


class TokenResponse(BaseModel):
    """Réponse login/register — champ `token` pour compatibilité frontend."""
    token: str
    user: UserOut


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sources (admin)
# ---------------------------------------------------------------------------

class SourceStats(BaseModel):
    nb_mots:        int = 0
    nb_corpus:      int = 0
    nb_expressions: int = 0
    nb_definitions: int = 0


class SourceOut(BaseModel):
    id:                    int
    nom:                   str
    url:                   str
    type:                  str
    robots_ok:             bool
    actif:                 bool
    auto_scrape:           bool
    scrape_interval_hours: int
    scrape_at:             Optional[datetime] = None
    created_at:            datetime
    stats:                 SourceStats = SourceStats()

    model_config = ConfigDict(from_attributes=True)


class SourceCreate(BaseModel):
    nom:                   str
    url:                   str
    type:                  str = "texte"
    robots_ok:             bool = False
    actif:                 bool = True
    auto_scrape:           bool = False
    scrape_interval_hours: int  = 24


class SourceUpdate(BaseModel):
    nom:                   Optional[str]  = None
    url:                   Optional[str]  = None
    type:                  Optional[str]  = None
    robots_ok:             Optional[bool] = None
    actif:                 Optional[bool] = None
    auto_scrape:           Optional[bool] = None
    scrape_interval_hours: Optional[int]  = None


# ---------------------------------------------------------------------------
# Scrape jobs (admin)
# ---------------------------------------------------------------------------

class ScrapeJobOut(BaseModel):
    id:           int
    source_id:    Optional[int]      = None
    url:          Optional[str]      = None
    job_type:     str
    status:       str
    nb_inserted:  int
    preview_text: Optional[str]      = None
    error_msg:    Optional[str]      = None
    started_at:   Optional[datetime] = None
    finished_at:  Optional[datetime] = None
    created_at:   datetime

    model_config = ConfigDict(from_attributes=True)


class ScrapeUrlRequest(BaseModel):
    url:       str
    source_id: Optional[int] = None   # rattacher à une source existante


class ScrapeYoutubeRequest(BaseModel):
    youtube_url: str


class YoutubeConfirmRequest(BaseModel):
    texte:       str
    table_cible: str   # 'corpus' | 'expression'
    domaine:     Optional[str] = "lòt"   # pour corpus seulement


class TranscribeBatchOut(BaseModel):
    launched:   int
    job_ids:    List[int]
    model_size: str


class TranscribeReviewRequest(BaseModel):
    transcription:      str
    domaine:            Optional[str] = "lòt"
    also_update_corpus: bool = True   # insérer la version corrigée en corpus Fèfèn


class ContributionCreate(BaseModel):
    table_cible: str
    entite_id: int
    contenu_apres: dict


class ContributionOut(BaseModel):
    id: int
    table_cible: str
    entite_id: int
    type_action: str
    contenu_apres: Optional[dict] = None
    statut: str
    created_at: datetime
    moderateur_id: Optional[int] = None
    modere_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_contribution(cls, c) -> "ContributionOut":
        return cls(
            id=c.id,
            table_cible=c.table_cible,
            entite_id=c.entite_id,
            type_action=c.type_action,
            contenu_apres=c.contenu_apres,
            statut=str(c.statut),
            created_at=c.created_at,
            moderateur_id=c.moderateur_id,
            modere_at=c.modere_at,
        )


# ---------------------------------------------------------------------------
# Phase 8 — Pipeline linguistique
# ---------------------------------------------------------------------------

class ConversationLogOut(BaseModel):
    id: UUID
    session_id: UUID
    user_message: str
    bot_response: str
    detected_lang: str
    lang_confidence: float
    user_correction: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModerationCandidateOut(BaseModel):
    id: int
    candidate_type: str
    status: str
    word: Optional[str] = None
    definition_kr: Optional[str] = None
    definition_fr: Optional[str] = None
    phonetic: Optional[str] = None
    pos: Optional[str] = None
    examples: List[Any] = []
    context: Optional[str] = None
    variants: List[Any] = []
    source_log_ids: List[UUID] = []
    speaker_count: int
    frequency: int
    reviewer_note: Optional[str] = None
    linked_mot_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModerationReview(BaseModel):
    status: str                              # "approved", "rejected", "merged"
    reviewer_note: Optional[str] = None
    word_override: Optional[str] = None      # le lingwis peut corriger le mot
    definition_kr: Optional[str] = None
    definition_fr: Optional[str] = None
    pos_override: Optional[str] = None
    merge_with_mot_id: Optional[int] = None  # si status="merged"
