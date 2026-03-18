"""
pipeline_pdf.py — Pipeline complet PDFs Dictionnaire Confiant
=============================================================
Orchestre :
  1. Téléchargement des PDFs (PotomitanPDFScraper)
  2. Extraction et parsing (PDFExtractor)
  3. Sauvegarde JSONL pour le RAG Fèfèn
  4. Import PostgreSQL (optionnel — table mots + traductions)

Usage :
    python -m src.pipeline_pdf                   # télécharge + extrait + exporte
    python -m src.pipeline_pdf --no-download     # extrait depuis PDFs déjà présents
    python -m src.pipeline_pdf --no-db           # sans import PostgreSQL
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT        = Path(__file__).parent.parent
PDF_DIR     = ROOT / "data" / "raw" / "pdfs"
JSONL_OUT   = ROOT.parent / "dataset" / "data" / "dictionnaire_confiant" / "train.jsonl"


# ---------------------------------------------------------------------------
# JSONL export (pour le RAG Fèfèn)
# ---------------------------------------------------------------------------

def to_jsonl_record(entry: dict[str, Any]) -> dict[str, Any]:
    """Convertit une entrée du dictionnaire en enregistrement JSONL pour Fèfèn."""
    mot = entry["mot_creole"]
    dfn = entry["definition_fr"]
    num = entry.get("numero")

    # Texte enrichi pour l'indexation TF-IDF
    texte_parts = [f"{mot} : {dfn}"]
    if entry.get("variantes"):
        texte_parts.append("var. " + ", ".join(entry["variantes"]))
    if entry.get("synonymes"):
        texte_parts.append("syn. " + ", ".join(entry["synonymes"]))

    # Premier exemple créole (si disponible)
    exemple_creole = ""
    exemple_fr = ""
    exemples = entry.get("exemples", [])
    if exemples:
        exemple_creole = exemples[0]
        if len(exemples) > 1:
            exemple_fr = exemples[1]

    return {
        "id":             f"confiant_{entry['lettre'].lower()}_{mot}_{num or 0}",
        "mot":            mot,
        "numero":         num,
        "definition":     dfn,
        "exemple_creole": exemple_creole,
        "exemple_fr":     exemple_fr,
        "variantes":      entry.get("variantes", []),
        "synonymes":      entry.get("synonymes", []),
        "feminin":        entry.get("feminin"),
        "lettre":         entry["lettre"],
        "texte":          " | ".join(texte_parts),   # champ principal pour TF-IDF
        "source":         "potomitan.info/dictionnaire",
        "auteur":         "Raphaël Confiant",
        "categorie":      "dictionnaire",
        "licence":        "libre diffusion avec attribution",
        "language":       "crm",
    }


def export_jsonl(entries: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [to_jsonl_record(e) for e in entries]
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.info("JSONL exporté : %d entrées → %s", len(records), out_path)


# ---------------------------------------------------------------------------
# Import PostgreSQL (optionnel)
# ---------------------------------------------------------------------------

_SOURCE_URL = "https://www.potomitan.info/dictionnaire/"
_SOURCE_NOM = "Dictionnaire Créole Martiniquais — Raphaël Confiant"


def import_to_db(entries: list[dict[str, Any]]) -> None:
    """Importe les entrées dans PostgreSQL (mots + traductions + définitions + expressions)."""
    try:
        import psycopg2  # type: ignore
    except ImportError:
        log.warning("psycopg2 non installé — import DB ignoré")
        return

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        # Reconstruction depuis les variables individuelles
        host     = os.getenv("POSTGRES_HOST", "localhost")
        port     = os.getenv("POSTGRES_PORT", "5433")
        dbname   = os.getenv("POSTGRES_DB", "langmatinitje")
        user     = os.getenv("POSTGRES_USER", "creole")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db_url   = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cur = conn.cursor()

        # Récupérer ou créer la source (SELECT d'abord — évite la désynchronisation de séquence)
        cur.execute("SELECT id FROM sources WHERE url = %s", (_SOURCE_URL,))
        row = cur.fetchone()
        if row:
            source_id = row[0]
        else:
            cur.execute("""
                INSERT INTO sources (nom, url, type, robots_ok)
                VALUES (%s, %s, 'texte', TRUE)
                RETURNING id
            """, (_SOURCE_NOM, _SOURCE_URL))
            source_id = cur.fetchone()[0]

        inserted_mots  = 0
        inserted_trad  = 0
        inserted_defs  = 0
        inserted_exprs = 0

        for entry in entries:
            mot = entry["mot_creole"]
            dfn = entry["definition_fr"]
            if not mot or not dfn:
                continue

            # Exemples : exemples[0] = phrase créole, exemples[1] = traduction fr
            exemples       = entry.get("exemples", [])
            exemple_creole = exemples[0].strip() if exemples else ""
            exemple_fr     = exemples[1].strip() if len(exemples) > 1 else ""

            # Savepoint par entrée
            cur.execute("SAVEPOINT sp_entry")
            try:
                # ── mots ──────────────────────────────────────────────────────
                cur.execute("""
                    INSERT INTO mots (mot_creole, source_id, valide)
                    VALUES (%s, %s, FALSE)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (mot, source_id))
                row = cur.fetchone()
                if row:
                    mot_id = row[0]
                    inserted_mots += 1
                else:
                    cur.execute("SELECT id FROM mots WHERE mot_creole = %s", (mot,))
                    r = cur.fetchone()
                    mot_id = r[0] if r else None

                if mot_id:
                    # ── traductions (crm → fr) ─────────────────────────────
                    cur.execute("""
                        INSERT INTO traductions
                            (mot_id, langue_source, langue_cible,
                             texte_source, texte_cible, source_id, valide)
                        VALUES (%s, 'crm', 'fr', %s, %s, %s, FALSE)
                        ON CONFLICT DO NOTHING
                    """, (mot_id, mot, dfn, source_id))
                    inserted_trad += cur.rowcount

                    # ── definitions ───────────────────────────────────────
                    # Évite les doublons (même mot_id + même définition)
                    cur.execute("""
                        INSERT INTO definitions (mot_id, definition, exemple, source_id, valide)
                        SELECT %s, %s, %s, %s, FALSE
                        WHERE NOT EXISTS (
                            SELECT 1 FROM definitions
                            WHERE mot_id = %s AND definition = %s
                        )
                    """, (mot_id, dfn, exemple_creole or None, source_id,
                          mot_id, dfn))
                    inserted_defs += cur.rowcount

                # ── expressions (phrase créole + traduction) ───────────────
                # Seulement si l'exemple créole existe et n'est pas déjà présent
                if exemple_creole:
                    cur.execute("""
                        INSERT INTO expressions
                            (texte_creole, texte_fr, type, explication, source_id, valide)
                        SELECT %s, %s, 'expression', %s, %s, FALSE
                        WHERE NOT EXISTS (
                            SELECT 1 FROM expressions WHERE texte_creole = %s
                        )
                    """, (exemple_creole,
                          exemple_fr or None,
                          dfn[:200],          # la définition sert d'explication contextuelle
                          source_id,
                          exemple_creole))
                    inserted_exprs += cur.rowcount

                cur.execute("RELEASE SAVEPOINT sp_entry")

            except Exception as exc:
                cur.execute("ROLLBACK TO SAVEPOINT sp_entry")
                log.warning("Entrée ignorée (%s) : %s", mot, exc)

        conn.commit()
        log.info(
            "DB : %d mots + %d traductions + %d définitions + %d expressions insérés",
            inserted_mots, inserted_trad, inserted_defs, inserted_exprs,
        )
        cur.close()
        conn.close()

    except Exception as exc:
        log.error("Erreur connexion DB : %s", exc)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def run(no_download: bool = False, no_db: bool = False) -> list[dict[str, Any]]:
    from src.scrapers.potomitan_pdf_scraper import PotomitanPDFScraper
    from src.pdf_extractor import PDFExtractor, save_entries

    # 1. Téléchargement
    if not no_download:
        scraper = PotomitanPDFScraper(out_dir=PDF_DIR)
        scraper.run()
    else:
        log.info("Téléchargement ignoré (--no-download)")

    # 2. Extraction
    extractor = PDFExtractor()
    all_entries = extractor.extract_all(PDF_DIR)

    # 3. Sauvegarde JSON (debug)
    save_entries(all_entries, ROOT / "data" / "processed" / "confiant_dict.json")

    # 4. Export JSONL pour RAG
    export_jsonl(all_entries, JSONL_OUT)

    # 5. Import DB
    if not no_db:
        import_to_db(all_entries)

    print(f"\n{'='*50}")
    print(f"  Dictionnaire Confiant — résumé")
    print(f"{'='*50}")

    # Stats par lettre
    by_letter: dict[str, int] = {}
    for e in all_entries:
        by_letter[e["lettre"]] = by_letter.get(e["lettre"], 0) + 1
    for lettre, count in sorted(by_letter.items()):
        print(f"  Lettre {lettre:<4} {count:>5} entrées")
    print(f"  {'─'*30}")
    print(f"  {'TOTAL':<5} {len(all_entries):>5} entrées")
    print(f"{'='*50}")
    print(f"\n  JSONL → {JSONL_OUT}")

    return all_entries


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser(description="Pipeline PDFs Dictionnaire Confiant")
    parser.add_argument("--no-download", action="store_true",
                        help="Ne pas télécharger les PDFs (utiliser ceux déjà présents)")
    parser.add_argument("--no-db", action="store_true",
                        help="Ne pas importer en base de données")
    args = parser.parse_args()
    run(no_download=args.no_download, no_db=args.no_db)
