"""Import du dictionnaire créole martiniquais (creole_dict.json).

Lit les paires {"français": "créole"} et les insère dans :
  - sources     → une entrée pour ce dictionnaire
  - mots        → le mot créole (UPSERT, skip si déjà présent)
  - traductions → la paire FR→CRM (UPSERT, skip si doublon exact)

Usage :
    cd kreyol-matinik/scraper
    source .venv/bin/activate
    python import_creole_dict.py [--dry-run]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DICT_PATH = Path(__file__).parent.parent / "docs" / "def" / "creole_dict.json"
SOURCE_NOM = "Dictionnaire Créole Martiniquais — creole_dict"
SOURCE_URL = "https://bokaynou.mq/creole_dict"  # URL de référence interne

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        dbname=os.getenv("POSTGRES_DB", "langmatinitje"),
        user=os.getenv("POSTGRES_USER", "creole"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def get_or_create_source(cur: psycopg2.extensions.cursor) -> int:
    """Retourne l'id de la source, la crée si elle n'existe pas."""
    cur.execute("SELECT id FROM sources WHERE url = %s", (SOURCE_URL,))
    row = cur.fetchone()
    if row:
        log.info("Source existante (id=%d)", row[0])
        return row[0]

    cur.execute(
        """
        INSERT INTO sources (nom, url, type, robots_ok, actif)
        VALUES (%s, %s, 'texte', TRUE, TRUE)
        RETURNING id
        """,
        (SOURCE_NOM, SOURCE_URL),
    )
    source_id = cur.fetchone()[0]
    log.info("Source créée (id=%d)", source_id)
    return source_id


def import_dict(
    data: dict[str, str],
    source_id: int,
    cur: psycopg2.extensions.cursor,
) -> tuple[int, int]:
    """Insère les mots et traductions. Retourne (nb_mots_insérés, nb_trad_insérés)."""

    # 1. Upsert mots (skip si mot_creole déjà présent)
    mots_batch = [
        {"mot_creole": v.strip(), "source_id": source_id}
        for v in data.values()
    ]
    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO mots (mot_creole, source_id, valide)
        VALUES (%(mot_creole)s, %(source_id)s, TRUE)
        ON CONFLICT (mot_creole) DO NOTHING
        """,
        mots_batch,
        page_size=200,
    )

    # 2. Récupérer tous les ids (y compris ceux pré-existants)
    cur.execute("SELECT mot_creole, id FROM mots")
    mot_ids: dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

    # 3. Upsert traductions
    trad_batch = []
    for texte_fr, texte_crm in data.items():
        texte_crm = texte_crm.strip()
        mot_id = mot_ids.get(texte_crm)
        if mot_id is None:
            log.warning("Mot créole introuvable après insert : %r", texte_crm)
            continue
        trad_batch.append({
            "mot_id":       mot_id,
            "texte_source": texte_fr.strip(),
            "texte_cible":  texte_crm,
            "source_id":    source_id,
        })

    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO traductions
            (mot_id, langue_source, langue_cible, texte_source, texte_cible, source_id, valide)
        VALUES
            (%(mot_id)s, 'fr', 'crm', %(texte_source)s, %(texte_cible)s, %(source_id)s, TRUE)
        ON CONFLICT DO NOTHING
        """,
        trad_batch,
        page_size=200,
    )

    return len(mots_batch), len(trad_batch)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import creole_dict.json → PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans écrire en DB")
    args = parser.parse_args()

    if not DICT_PATH.exists():
        log.error("Fichier introuvable : %s", DICT_PATH)
        sys.exit(1)

    log.info("Lecture de %s", DICT_PATH)
    with open(DICT_PATH, encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)
    log.info("%d paires chargées", len(data))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            source_id = get_or_create_source(cur)
            nb_mots, nb_trad = import_dict(data, source_id, cur)

        if args.dry_run:
            log.info("[DRY-RUN] Rollback — rien écrit en DB.")
            conn.rollback()
        else:
            conn.commit()
            log.info("Commit OK — %d mots, %d traductions traités.", nb_mots, nb_trad)

        # Stats finales
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mots")
            total_mots = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM traductions")
            total_trad = cur.fetchone()[0]
        log.info("Total en base → mots: %d | traductions: %d", total_mots, total_trad)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
