"""DocumentLoader — insère ou met à jour les documents dans la table `documents`.

Usage typique (dans chaque scraper) :
    from src.db_loader import DocumentLoader, get_connection

    conn = get_connection()
    loader = DocumentLoader(conn)
    loader.upsert_many(scraper.data, scraper.to_document)
    conn.close()
"""

import json
import logging
import os
from typing import Any, Callable

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# SQL — UPSERT idempotent
# Un document est identifié par son URL.
# Si l'URL existe déjà, on met à jour uniquement si le contenu a changé.
# -----------------------------------------------------------------------------

_UPSERT_SQL = """
    INSERT INTO documents
        (source, doc_type, title, content, url, published_at, metadata)
    VALUES
        (%(source)s, %(doc_type)s, %(title)s, %(content)s,
         %(url)s, %(published_at)s, %(metadata)s)
    ON CONFLICT (url) DO UPDATE SET
        title      = EXCLUDED.title,
        content    = EXCLUDED.content,
        metadata   = EXCLUDED.metadata,
        scraped_at = NOW()
    WHERE
        documents.content  IS DISTINCT FROM EXCLUDED.content
     OR documents.metadata IS DISTINCT FROM EXCLUDED.metadata;
"""


# -----------------------------------------------------------------------------
# Connexion
# -----------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    """Crée une connexion PostgreSQL depuis les variables d'environnement.

    Variables lues (celles du .env du projet) :
        POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
        POSTGRES_USER, POSTGRES_PASSWORD

    Returns:
        Connexion psycopg2 ouverte.
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "langmatinitje"),
        user=os.getenv("POSTGRES_USER", "creole"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


# -----------------------------------------------------------------------------
# DocumentLoader
# -----------------------------------------------------------------------------

class DocumentLoader:
    """Charge des documents normalisés dans la table `documents`.

    Args:
        conn: Connexion psycopg2 active (non fermée par cette classe).

    Example:
        conn = get_connection()
        loader = DocumentLoader(conn)
        n = loader.upsert_many(items, scraper.to_document)
        print(f"{n} documents insérés/mis à jour")
        conn.close()
    """

    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self._conn = conn

    def upsert_many(
        self,
        items: list[dict[str, Any]],
        to_document: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> int:
        """Normalise et upserte une liste d'entrées brutes.

        Args:
            items:       Liste brute issue de scraper.data.
            to_document: Fonction de normalisation (scraper.to_document).

        Returns:
            Nombre de lignes traitées.
        """
        if not items:
            logger.warning("DocumentLoader.upsert_many : liste vide, rien à faire.")
            return 0

        docs = []
        for item in items:
            try:
                doc = to_document(item)
                doc = _validate_and_prepare(doc)
                docs.append(doc)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("to_document a échoué sur %r : %s", item, e)

        if not docs:
            logger.error("Aucun document valide après normalisation.")
            return 0

        with self._conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, _UPSERT_SQL, docs, page_size=100)
        self._conn.commit()

        logger.info("DocumentLoader : %d documents upsertés.", len(docs))
        return len(docs)


# -----------------------------------------------------------------------------
# Helpers internes
# -----------------------------------------------------------------------------

_VALID_SOURCES   = {"bizouk", "kiprix", "madiana", "rci", "kreyol"}
_VALID_DOC_TYPES = {"annonce", "produit", "film", "actualite", "mot"}


def _validate_and_prepare(doc: dict[str, Any]) -> dict[str, Any]:
    """Valide les champs obligatoires et sérialise metadata en JSON.

    Args:
        doc: Dictionnaire retourné par to_document().

    Returns:
        Dictionnaire prêt pour psycopg2 (metadata sérialisé).

    Raises:
        ValueError: Si un champ obligatoire est absent ou invalide.
    """
    for field in ("source", "doc_type", "title", "content"):
        if not doc.get(field):
            raise ValueError(f"Champ obligatoire manquant ou vide : '{field}'")

    if doc["source"] not in _VALID_SOURCES:
        raise ValueError(
            f"source '{doc['source']}' invalide. Valeurs attendues : {_VALID_SOURCES}"
        )
    if doc["doc_type"] not in _VALID_DOC_TYPES:
        raise ValueError(
            f"doc_type '{doc['doc_type']}' invalide. Valeurs attendues : {_VALID_DOC_TYPES}"
        )

    prepared = {
        "source":       doc["source"],
        "doc_type":     doc["doc_type"],
        "title":        doc["title"][:500],   # tronque si titre trop long
        "content":      doc["content"],
        "url":          doc.get("url"),
        "published_at": doc.get("published_at"),
        "metadata":     None,
    }

    raw_meta = doc.get("metadata")
    if isinstance(raw_meta, dict):
        prepared["metadata"] = json.dumps(raw_meta, ensure_ascii=False)
    elif isinstance(raw_meta, str):
        prepared["metadata"] = raw_meta  # déjà sérialisé

    return prepared
