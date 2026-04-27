"""
fefen_rag.py — Moteur Fèfèn RAG pgvector + OpenAI
===================================================
Remplace FefenRAG (HuggingFace) par une recherche sémantique
dans la table fefen_documents (pgvector) + génération GPT-4o.

Variables d'env requises :
  OPENAI_API_KEY     — clé OpenAI
  PG_RAG_HOST        — host pgvector (défaut : langmatinitje_db)
  PG_RAG_PORT        — port (défaut : 5432)
  PG_RAG_DB          — base de données (défaut : langmatinitje)
  PG_RAG_USER        — utilisateur (défaut : creole)
  PG_RAG_PASSWORD    — mot de passe

Variables d'env optionnelles :
  PG_RAG_THRESHOLD   — seuil similarité (défaut : 0.5)
  PG_RAG_TOP_K       — nb de chunks récupérés (défaut : 5)
  FEFEN_LLM_MODEL    — modèle OpenAI (défaut : gpt-4o)
"""

from __future__ import annotations

import logging
import os
import random
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
PG_RAG_HOST     = os.getenv("PG_RAG_HOST", "langmatinitje_db")
PG_RAG_PORT     = int(os.getenv("PG_RAG_PORT", "5432"))
PG_RAG_DB       = os.getenv("PG_RAG_DB", "langmatinitje")
PG_RAG_USER     = os.getenv("PG_RAG_USER", "creole")
PG_RAG_PASSWORD = os.getenv("PG_RAG_PASSWORD", "")
PG_RAG_THRESHOLD = float(os.getenv("PG_RAG_THRESHOLD", "0.5"))
PG_RAG_TOP_K    = int(os.getenv("PG_RAG_TOP_K", "5"))
FEFEN_LLM_MODEL = os.getenv("FEFEN_LLM_MODEL", "gpt-4o")

SYSTEM_PROMPT = """\
Tu es Fèfèn, un assistant chaleureux et expert de la Martinique — \
sa langue créole (kréyòl matinitjé), son histoire, sa culture, son économie et sa société.

LANGUE :
- Réponds principalement en français, mais intègre naturellement des expressions \
ou phrases en kréyòl matinitjé quand c'est pertinent.
- Le kréyòl doit être authentique et martiniquais (pas guadeloupéen ou haïtien).
- Exemple de ton : "Bonjou ! Koman ou yé ? En Martinique, on dit..."

FORMAT :
- Réponse concise : 3 à 6 phrases maximum
- Structurée et facile à lire dans une interface chat
- Commence directement par la réponse, sans formule de politesse inutile

UTILISATION DU CONTEXTE :
- Si des documents de référence sont fournis, base ta réponse principalement dessus
- Cite implicitement les sources sans les nommer explicitement
- Si aucun document n'est fourni, utilise ta connaissance générale de la Martinique

DOCUMENTS DE RÉFÉRENCE :
{context}
"""

FALLBACKS = [
    "Man pa trouvé anyen pou sa-a. Mandé mwen anlè kréyòl matinitjé ou anlè Matinik !",
    "Sa-a pa nan mo kò mwen. Eséyé mandé mwen an lòt bagay anlè lang ou kilti matinitjé.",
    "Mwen pa ka réponn sa-a jòdi-a. Men si ou mandé mwen anlè Matinik, man la !",
]


# ---------------------------------------------------------------------------
# Classe FefenPGVector
# ---------------------------------------------------------------------------

class FefenPGVector:
    """
    Moteur RAG Fèfèn utilisant pgvector pour la recherche sémantique
    et OpenAI GPT-4o pour la génération de réponses.
    """

    def __init__(self) -> None:
        self._openai_client = None
        self._pg_conn = None
        self._ready = False

    def build(self) -> "FefenPGVector":
        """Initialise les connexions OpenAI et PostgreSQL."""
        # Connexion OpenAI
        try:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=OPENAI_API_KEY)
            log.info("FefenPGVector : OpenAI connecté (modèle %s)", FEFEN_LLM_MODEL)
        except Exception as exc:
            log.error("FefenPGVector : échec connexion OpenAI — %s", exc)
            return self

        # Connexion PostgreSQL
        try:
            self._pg_conn = psycopg2.connect(
                host=PG_RAG_HOST,
                port=PG_RAG_PORT,
                dbname=PG_RAG_DB,
                user=PG_RAG_USER,
                password=PG_RAG_PASSWORD,
                connect_timeout=5,
            )
            self._pg_conn.autocommit = True
            log.info("FefenPGVector : pgvector connecté (%s:%s/%s)",
                     PG_RAG_HOST, PG_RAG_PORT, PG_RAG_DB)
            self._ready = True
        except Exception as exc:
            log.error("FefenPGVector : échec connexion pgvector — %s", exc)

        return self

    # ------------------------------------------------------------------
    # Embedding de la question
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float]:
        """Génère un embedding OpenAI pour le texte donné."""
        response = self._openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    # ------------------------------------------------------------------
    # Recherche sémantique dans pgvector
    # ------------------------------------------------------------------

    def _search(self, embedding: list[float]) -> list[dict[str, Any]]:
        """Recherche les chunks les plus proches dans fefen_documents."""
        if self._pg_conn is None or self._pg_conn.closed:
            self._reconnect()

        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"

        query = """
            SELECT content, source_name, source_type,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM fefen_documents
            WHERE 1 - (embedding <=> %s::vector) > %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """

        try:
            with self._pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (vector_str, vector_str, PG_RAG_THRESHOLD, vector_str, PG_RAG_TOP_K))
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            log.warning("FefenPGVector : erreur recherche pgvector — %s", exc)
            self._reconnect()
            return []

    def _reconnect(self) -> None:
        """Tente de reconnecter à PostgreSQL."""
        try:
            self._pg_conn = psycopg2.connect(
                host=PG_RAG_HOST,
                port=PG_RAG_PORT,
                dbname=PG_RAG_DB,
                user=PG_RAG_USER,
                password=PG_RAG_PASSWORD,
                connect_timeout=5,
            )
            self._pg_conn.autocommit = True
            log.info("FefenPGVector : reconnexion pgvector réussie")
        except Exception as exc:
            log.error("FefenPGVector : échec reconnexion — %s", exc)
            self._pg_conn = None

    # ------------------------------------------------------------------
    # Construction du contexte RAG
    # ------------------------------------------------------------------

    def _build_context(self, chunks: list[dict]) -> str:
        """Formate les chunks récupérés en bloc de contexte pour le prompt."""
        if not chunks:
            return "(aucun document de référence trouvé)"

        parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source_name", "source inconnue")
            content = chunk.get("content", "").strip()
            similarity = chunk.get("similarity", 0)
            parts.append(
                f"[Document {i} — {source} (pertinence: {similarity:.0%})]\n{content}"
            )

        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # Réponse principale
    # ------------------------------------------------------------------

    def reply(self, message: str) -> str:
        """
        Génère une réponse via RAG :
        1. Embedding de la question
        2. Recherche sémantique dans pgvector
        3. Génération GPT-4o avec contexte
        """
        if not self._ready or self._openai_client is None:
            return random.choice(FALLBACKS)

        try:
            # 1. Embedding de la question
            embedding = self._embed(message)

            # 2. Recherche sémantique
            chunks = self._search(embedding)

            # 3. Construction du prompt
            context = self._build_context(chunks)
            has_context = bool(chunks)

            system = SYSTEM_PROMPT.format(context=context)

            if not has_context:
                system += (
                    "\n\nNOTE : Aucun document spécifique trouvé pour cette question. "
                    "Réponds avec ta connaissance générale de la Martinique."
                )

            # 4. Génération GPT-4o
            response = self._openai_client.chat.completions.create(
                model=FEFEN_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                max_tokens=500,
                temperature=0.7,
            )

            reply = response.choices[0].message.content.strip()
            log.info(
                "FefenPGVector : réponse générée (%d chunks, modèle %s)",
                len(chunks), FEFEN_LLM_MODEL
            )
            return reply

        except Exception as exc:
            log.error("FefenPGVector : erreur génération — %s", exc)
            return random.choice(FALLBACKS)

    def close(self) -> None:
        """Ferme les connexions."""
        if self._pg_conn and not self._pg_conn.closed:
            self._pg_conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_fefen_pgvector() -> FefenPGVector | None:
    """
    Construit et retourne un moteur FefenPGVector.
    Retourne None si OPENAI_API_KEY n'est pas défini.
    """
    if not OPENAI_API_KEY:
        log.warning("FefenPGVector : OPENAI_API_KEY manquant — désactivé")
        return None

    engine = FefenPGVector()
    engine.build()

    if not engine._ready:
        log.warning("FefenPGVector : non disponible — vérifier pgvector")
        return None

    return engine
