"""
Modèles ORM SQLAlchemy — Lang Matinitjé

Notes sur les ENUMs :
- create_constraint=False  → pas de CHECK constraint (inutile avec native_enum)
- native_enum=True         → référence le type ENUM natif PostgreSQL existant
                            → en SQLite (tests), fall back sur VARCHAR
- Toutes les classes enum héritent de str, enum.Enum
  → la valeur EST la chaîne → sérialisation Pydantic sans config supplémentaire
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON, TypeDecorator

from ..database import Base


# ---------------------------------------------------------------------------
# Type personnalisé : UUID[] sur PostgreSQL, JSON sur SQLite (tests)
# ---------------------------------------------------------------------------

class UUIDArrayType(TypeDecorator):
    """ARRAY(UUID) sur PostgreSQL, JSON array de strings sur SQLite.

    Permet d'utiliser le même modèle ORM en production (PostgreSQL)
    et dans les tests unitaires (SQLite en mémoire).
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(UUID(as_uuid=True)))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value  # uuid.UUID objects → psycopg2 sait les gérer
        return [str(v) for v in value]  # stocké comme ["uuid-str", ...]

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value  # déjà des uuid.UUID
        import uuid as _uuid_mod
        return [_uuid_mod.UUID(str(v)) for v in (value or [])]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _pg_enum(py_enum: type, name: str) -> SAEnum:
    """Crée un SAEnum qui référence un type ENUM PostgreSQL existant.

    Sur SQLite (tests) : fall back sur VARCHAR (native_enum ignoré).
    create_constraint=False : ne génère pas de CHECK constraint.
    """
    return SAEnum(py_enum, name=name, create_constraint=False, native_enum=True)


# ---------------------------------------------------------------------------
# Python Enums (str subclass → valeur = chaîne SQL)
# ---------------------------------------------------------------------------

class SourceType(str, enum.Enum):
    texte = "texte"
    audio = "audio"
    video = "video"
    mixte = "mixte"


class MediaType(str, enum.Enum):
    audio = "audio"
    video = "video"


class LangueCode(str, enum.Enum):
    fr = "fr"
    crm = "crm"


class CategorieGram(str, enum.Enum):
    nom = "nom"
    vèb = "vèb"
    adjektif = "adjektif"
    advèb = "advèb"
    pwonon = "pwonon"
    prépoziksyon = "prépoziksyon"
    konjonksyon = "konjonksyon"
    entèjèksyon = "entèjèksyon"
    atik = "atik"
    lòt = "lòt"


class ActionType(str, enum.Enum):
    ajout = "ajout"
    correction = "correction"
    validation = "validation"
    rejet = "rejet"


class StatutContrib(str, enum.Enum):
    en_attente = "en_attente"
    validé = "validé"
    rejeté = "rejeté"


class DomaineCorpus(str, enum.Enum):
    koutidyen = "koutidyen"
    kilti = "kilti"
    nati = "nati"
    larel = "larel"
    istwa = "istwa"
    mistis = "mistis"
    kizin = "kizin"
    mizik = "mizik"
    lespò = "lespò"
    lòt = "lòt"


class UserRole(str, enum.Enum):
    contributeur = "contributeur"
    admin = "admin"
    lingwis = "lingwis"


class CandidateType(str, enum.Enum):
    new_word = "new_word"
    spelling_variant = "spelling_variant"
    grammar_pattern = "grammar_pattern"
    expression = "expression"
    correction = "correction"


class CandidateStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    merged = "merged"


# ---------------------------------------------------------------------------
# Modèles ORM
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(_pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.contributeur)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    contributeur = relationship("Contributeur", back_populates="user", uselist=False)


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    nom = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    type = Column(_pg_enum(SourceType, "source_type"), nullable=False, default="texte")
    robots_ok = Column(Boolean, nullable=False, default=False)
    actif = Column(Boolean, nullable=False, default=True)
    auto_scrape = Column(Boolean, nullable=False, default=False)
    scrape_interval_hours = Column(Integer, nullable=False, default=24)
    scrape_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    mots = relationship("Mot", back_populates="source")
    traductions = relationship("Traduction", back_populates="source")
    definitions = relationship("Definition", back_populates="source")
    expressions = relationship("Expression", back_populates="source")
    medias = relationship("Media", back_populates="source")
    corpus = relationship("Corpus", back_populates="source")
    scrape_jobs = relationship("ScrapeJob", back_populates="source")


class Mot(Base):
    __tablename__ = "mots"

    id = Column(Integer, primary_key=True)
    mot_creole = Column(String(255), nullable=False, unique=True)
    phonetique = Column(String(255))
    categorie_gram = Column(_pg_enum(CategorieGram, "categorie_gram"))
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))
    valide = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    source = relationship("Source", back_populates="mots")
    traductions = relationship(
        "Traduction", back_populates="mot", cascade="all, delete-orphan"
    )
    definitions = relationship(
        "Definition", back_populates="mot", cascade="all, delete-orphan"
    )


class Traduction(Base):
    __tablename__ = "traductions"

    id = Column(Integer, primary_key=True)
    mot_id = Column(
        Integer, ForeignKey("mots.id", ondelete="CASCADE"), nullable=False
    )
    langue_source = Column(_pg_enum(LangueCode, "langue_code"), nullable=False)
    langue_cible = Column(_pg_enum(LangueCode, "langue_code"), nullable=False)
    texte_source = Column(Text, nullable=False)
    texte_cible = Column(Text, nullable=False)
    contexte = Column(Text)
    registre = Column(String(50))
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))
    valide = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    mot = relationship("Mot", back_populates="traductions")
    source = relationship("Source", back_populates="traductions")


class Definition(Base):
    __tablename__ = "definitions"

    id = Column(Integer, primary_key=True)
    mot_id = Column(
        Integer, ForeignKey("mots.id", ondelete="CASCADE"), nullable=False
    )
    definition = Column(Text, nullable=False)
    exemple = Column(Text)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))
    valide = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    mot = relationship("Mot", back_populates="definitions")
    source = relationship("Source", back_populates="definitions")


class Expression(Base):
    __tablename__ = "expressions"

    id = Column(Integer, primary_key=True)
    texte_creole = Column(Text, nullable=False)
    texte_fr = Column(Text)
    type = Column(String(50), nullable=False, default="expression")
    explication = Column(Text)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))
    valide = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    source = relationship("Source", back_populates="expressions")


class Media(Base):
    __tablename__ = "medias"

    id = Column(Integer, primary_key=True)
    url = Column(String(500), nullable=False, unique=True)
    type = Column(_pg_enum(MediaType, "media_type"), nullable=False)
    titre = Column(Text)
    description = Column(Text)
    duree_sec = Column(Integer)
    transcription = Column(Text)
    # "auto" = générée par Whisper, "reviewed" = corrigée par un locuteur natif
    transcription_src = Column(String(20), nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    source = relationship("Source", back_populates="medias")


class Corpus(Base):
    __tablename__ = "corpus"

    id = Column(Integer, primary_key=True)
    texte_creole = Column(Text, nullable=False)
    texte_fr = Column(Text)
    domaine = Column(
        _pg_enum(DomaineCorpus, "domaine_corpus"), nullable=False, default="lòt"
    )
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    source = relationship("Source", back_populates="corpus")


class Contributeur(Base):
    __tablename__ = "contributeurs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    pseudo = Column(String(100))
    nb_contrib = Column(Integer, nullable=False, default=0)
    de_confiance = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="contributeur")


class ScrapeJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done    = "done"
    error   = "error"


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id           = Column(Integer, primary_key=True)
    source_id    = Column(Integer, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    url          = Column(String(500))
    job_type     = Column(String(50), nullable=False, default="url")
    status       = Column(_pg_enum(ScrapeJobStatus, "scrape_job_status"), nullable=False, default=ScrapeJobStatus.pending)
    nb_inserted  = Column(Integer, nullable=False, default=0)
    preview_text = Column(Text)
    error_msg    = Column(Text)
    started_at   = Column(DateTime(timezone=True))
    finished_at  = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    source = relationship("Source", back_populates="scrape_jobs")


class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(Integer, primary_key=True)
    contributeur_id = Column(
        Integer, ForeignKey("contributeurs.id"), nullable=False
    )
    table_cible = Column(String(50), nullable=False)
    entite_id = Column(Integer, nullable=False)
    type_action = Column(_pg_enum(ActionType, "action_type"), nullable=False)
    # JSON plutôt que JSONB pour compatibilité SQLite (tests)
    contenu_avant = Column(JSON)
    contenu_apres = Column(JSON)
    statut = Column(
        _pg_enum(StatutContrib, "statut_contrib"),
        nullable=False,
        default="en_attente",
    )
    moderateur_id = Column(Integer, ForeignKey("contributeurs.id"))
    modere_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    contributeur = relationship("Contributeur", foreign_keys=[contributeur_id])
    moderateur = relationship("Contributeur", foreign_keys=[moderateur_id])


# ---------------------------------------------------------------------------
# Phase 8 — Pipeline linguistique
# Note : UUID et ARRAY sont des types natifs PostgreSQL.
#        Sur SQLite (tests unitaires sans DB), ces colonnes ne sont pas
#        supportées nativement — prévoir des tests avec une vraie PG ou des mocks.
# ---------------------------------------------------------------------------

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
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at    = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])


class ModerationCandidate(Base):
    __tablename__ = "moderation_candidates"

    id              = Column(Integer, primary_key=True)
    candidate_type  = Column(
        _pg_enum(CandidateType, "candidate_type"), nullable=False
    )
    status          = Column(
        _pg_enum(CandidateStatus, "candidate_status"), default=CandidateStatus.pending
    )
    word            = Column(String(255))
    definition_kr   = Column(Text)
    definition_fr   = Column(Text)
    phonetic        = Column(String(255))
    pos             = Column(String(50))
    examples        = Column(JSON, default=list)   # JSON pour compat SQLite (tests)
    context         = Column(Text)
    variants        = Column(JSON, default=list)
    source_log_ids  = Column(UUIDArrayType, nullable=False, default=list)
    speaker_count   = Column(Integer, default=1)
    frequency       = Column(Integer, default=1)
    reviewed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at     = Column(DateTime(timezone=True), nullable=True)
    reviewer_note   = Column(Text, nullable=True)
    linked_mot_id   = Column(Integer, ForeignKey("mots.id"), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at      = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    reviewer    = relationship("User", foreign_keys=[reviewed_by])
    linked_mot  = relationship("Mot", foreign_keys=[linked_mot_id])


class LinguisticEntry(Base):
    __tablename__ = "linguistic_entries"

    id           = Column(Integer, primary_key=True)
    mot_id       = Column(Integer, ForeignKey("mots.id", ondelete="CASCADE"))
    candidate_id = Column(Integer, ForeignKey("moderation_candidates.id"))
    source       = Column(String(50), default="conversation")
    validated_by = Column(Integer, ForeignKey("users.id"))
    validated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    extra_data   = Column("metadata", JSON, default=dict)  # "metadata" est réservé par SQLAlchemy

    mot       = relationship("Mot", foreign_keys=[mot_id])
    candidate = relationship("ModerationCandidate", foreign_keys=[candidate_id])
    validator = relationship("User", foreign_keys=[validated_by])
