"""Import des données JSON scrappées vers PostgreSQL.

Sources traitées :
  - scraper/data/processed/confiant_dict.json    → mots + définitions
  - scraper/data/processed/pawolotek_processed.json  → corpus
  - scraper/data/processed/potomitan_processed.json  → corpus

Usage :
    cd kreyol-matinik/api
    python import_data.py
    python import_data.py --dry-run
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

DATA_DIR = Path(__file__).parent.parent / "scraper" / "data" / "processed"

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
# Helpers
# ---------------------------------------------------------------------------

def get_or_create_source(cur, nom: str, url: str, type_: str = "texte") -> int:
    cur.execute("SELECT id FROM sources WHERE url = %s", (url,))
    row = cur.fetchone()
    if row:
        log.info("Source existante '%s' (id=%d)", nom, row[0])
        return row[0]
    cur.execute(
        "INSERT INTO sources (nom, url, type, robots_ok, actif) VALUES (%s, %s, %s, TRUE, TRUE) RETURNING id",
        (nom, url, type_),
    )
    source_id = cur.fetchone()[0]
    log.info("Source créée '%s' (id=%d)", nom, source_id)
    return source_id


DOMAINE_MAP = {
    "lexique":  "koutidyen",
    "conte":    "kilti",
    "poème":    "kilti",
    "poeme":    "kilti",
    "chanson":  "mizik",
    "muzik":    "mizik",
    "proverbe": "kilti",
}


def categorie_to_domaine(cat: str) -> str:
    return DOMAINE_MAP.get((cat or "").lower().strip(), "lòt")


# ---------------------------------------------------------------------------
# Import Confiant → mots + définitions
# ---------------------------------------------------------------------------

def import_confiant(cur) -> tuple[int, int]:
    path = DATA_DIR / "confiant_dict.json"
    log.info("Lecture de %s", path)
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    log.info("%d entrées chargées", len(entries))

    source_id = get_or_create_source(
        cur,
        nom="Dictionnaire du Créole Martiniquais — Raphaël Confiant",
        url="https://www.potomitan.info/dictionnaire/",
    )

    # Upsert mots
    mots_batch = [
        {"mot_creole": e["mot_creole"].strip(), "source_id": source_id}
        for e in entries
        if (e.get("mot_creole") or "").strip()
    ]
    psycopg2.extras.execute_batch(
        cur,
        "INSERT INTO mots (mot_creole, source_id, valide) VALUES (%(mot_creole)s, %(source_id)s, TRUE) ON CONFLICT (mot_creole) DO NOTHING",
        mots_batch,
        page_size=200,
    )

    # Récupérer tous les ids
    cur.execute("SELECT mot_creole, id FROM mots")
    mot_ids: dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

    # Insérer définitions
    defs_batch = []
    for e in entries:
        mot = (e.get("mot_creole") or "").strip()
        definition = (e.get("definition_fr") or "").strip()
        if not mot or not definition:
            continue
        mot_id = mot_ids.get(mot)
        if mot_id is None:
            log.warning("Mot introuvable après insert : %r", mot)
            continue
        exemples = e.get("exemples") or []
        exemple_txt = "\n".join(ex for ex in exemples if ex) or None
        defs_batch.append({
            "mot_id": mot_id,
            "definition": definition,
            "exemple": exemple_txt,
            "source_id": source_id,
        })

    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO definitions (mot_id, definition, exemple, source_id, valide)
        VALUES (%(mot_id)s, %(definition)s, %(exemple)s, %(source_id)s, TRUE)
        ON CONFLICT DO NOTHING
        """,
        defs_batch,
        page_size=200,
    )

    return len(mots_batch), len(defs_batch)


# ---------------------------------------------------------------------------
# Import Corpus (pawolotek / potomitan)
# ---------------------------------------------------------------------------

def import_corpus(cur, filename: str, source_nom: str, source_url: str) -> int:
    path = DATA_DIR / filename
    log.info("Lecture de %s", path)
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    log.info("%d entrées chargées", len(entries))

    source_id = get_or_create_source(cur, source_nom, source_url)

    corpus_batch = []
    medias_batch = []
    for e in entries:
        texte_creole = (e.get("texte_creole") or "").strip()
        if not texte_creole:
            continue
        corpus_batch.append({
            "texte_creole": texte_creole,
            "texte_fr": (e.get("texte_fr") or "").strip() or None,
            "domaine": categorie_to_domaine(e.get("categorie", "")),
            "source_id": source_id,
        })
        audio_url = (e.get("audio_url") or "").strip()
        if audio_url:
            medias_batch.append({
                "url": audio_url,
                "titre": (e.get("titre") or "").strip() or None,
                "source_id": source_id,
            })

    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO corpus (texte_creole, texte_fr, domaine, source_id)
        VALUES (%(texte_creole)s, %(texte_fr)s, %(domaine)s, %(source_id)s)
        ON CONFLICT DO NOTHING
        """,
        corpus_batch,
        page_size=200,
    )

    if medias_batch:
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO medias (url, type, titre, source_id)
            VALUES (%(url)s, 'audio', %(titre)s, %(source_id)s)
            ON CONFLICT (url) DO NOTHING
            """,
            medias_batch,
            page_size=200,
        )

    return len(corpus_batch)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Import Expressions / Proverbes
# ---------------------------------------------------------------------------

def import_expressions(cur, filename: str, source_nom: str, source_url: str) -> int:
    path = DATA_DIR / filename
    if not path.exists():
        log.warning("Fichier introuvable : %s — ignoré", path)
        return 0

    log.info("Lecture de %s", path)
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)

    # Filtrer uniquement les proverbes/expressions
    expr_entries = [e for e in entries if e.get("categorie") in ("proverbe", "expression")]
    log.info("%d entrées expressions/proverbes chargées", len(expr_entries))
    if not expr_entries:
        return 0

    source_id = get_or_create_source(cur, source_nom, source_url)

    batch = []
    for e in expr_entries:
        texte_creole = (e.get("texte_creole") or "").strip()
        if not texte_creole:
            continue
        batch.append({
            "texte_creole": texte_creole,
            "texte_fr":     (e.get("texte_fr") or "").strip() or None,
            "type":         e.get("categorie", "expression"),
            "explication":  (e.get("explication") or "").strip() or None,
            "source_id":    source_id,
        })

    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO expressions (texte_creole, texte_fr, type, explication, source_id, valide)
        VALUES (%(texte_creole)s, %(texte_fr)s, %(type)s, %(explication)s, %(source_id)s, TRUE)
        ON CONFLICT DO NOTHING
        """,
        batch,
        page_size=200,
    )
    return len(batch)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import JSON scrappés → PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans écrire en DB")
    args = parser.parse_args()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nb_mots, nb_defs = import_confiant(cur)
            log.info("[confiant] %d mots, %d définitions traités", nb_mots, nb_defs)

            nb = import_corpus(cur, "pawolotek_processed.json", "Pawolotek", "https://pawolotek.com")
            log.info("[pawolotek] %d entrées corpus traitées", nb)

            nb = import_corpus(cur, "potomitan_processed.json", "Potomitan", "https://www.potomitan.info")
            log.info("[potomitan] %d entrées corpus traitées", nb)

            nb = import_expressions(cur, "potomitan_proverbes.json", "Potomitan — Bel poveb kréyol", "https://www.potomitan.info/duranty/belpoveb.php")
            log.info("[proverbes] %d expressions/proverbes traités", nb)

        if args.dry_run:
            log.info("[DRY-RUN] Rollback — rien écrit en DB.")
            conn.rollback()
        else:
            conn.commit()
            log.info("Commit OK.")

        # Stats finales
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mots")
            log.info("Total mots en base : %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM definitions")
            log.info("Total définitions en base : %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM corpus")
            log.info("Total corpus en base : %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM expressions")
            log.info("Total expressions en base : %d", cur.fetchone()[0])

    finally:
        conn.close()


if __name__ == "__main__":
    main()
