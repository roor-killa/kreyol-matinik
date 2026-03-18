"""Point d'entrée du scraper Lang Matinitjé.

Usage :
    python main.py                         # scrape tout Pawolotek
    python main.py --source pawolotek      # source explicite
    python main.py --max 5                 # limite à 5 items par catégorie
    python main.py --import-db             # importe dans PostgreSQL après scraping
    python main.py --categories lexique    # une seule catégorie
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ajout du répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from src.manager import ScraperManager
from src.observers import LogObserver, StatsObserver
from src.pipeline import DataPipeline

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lang_matinitje")


def build_db_url() -> str | None:
    """Construit l'URL PostgreSQL depuis les variables d'environnement."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB", "langmatinitje")
    user = os.getenv("POSTGRES_USER", "creole")
    pwd  = os.getenv("POSTGRES_PASSWORD", "")
    if not pwd:
        return None
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scraper Lang Matinitjé — collecte de données créole martiniquais"
    )
    parser.add_argument(
        "--source", default="pawolotek",
        help="Source à scraper (défaut : pawolotek)"
    )
    parser.add_argument(
        "--max", type=int, default=0, metavar="N",
        help="Nombre max d'items par catégorie (0 = illimité)"
    )
    parser.add_argument(
        "--categories", nargs="+",
        help="Catégories/sections à scraper (ex : lexique societe | contes poemes)"
    )
    parser.add_argument(
        "--delay", type=float, default=None,
        help="Délai entre requêtes en secondes (défaut : selon le scraper)"
    )
    parser.add_argument(
        "--import-db", action="store_true",
        help="Importe les données dans PostgreSQL après scraping"
    )
    parser.add_argument(
        "--output-dir", default="data/raw",
        help="Répertoire de sortie pour les fichiers JSON/CSV"
    )
    args = parser.parse_args()

    # Création du scraper via Factory
    manager = ScraperManager()
    scraper_kwargs: dict = {}
    if args.delay is not None:
        scraper_kwargs["delay"] = args.delay
    if args.categories:
        scraper_kwargs["categories"] = args.categories

    try:
        scraper = ScraperManager.create_scraper(args.source, **scraper_kwargs)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Attacher les observateurs
    stats = StatsObserver()
    scraper.attach(LogObserver(args.source))
    scraper.attach(stats)

    manager.add_scraper(scraper)

    # Scraping
    logger.info("Démarrage du scraping — source : %s", args.source)
    manager.scrape_all(max_pages=args.max)

    # Sauvegarde brute
    output_dir = Path(args.output_dir)
    json_path = output_dir / f"{args.source}_raw.json"
    csv_path  = output_dir / f"{args.source}_raw.csv"
    scraper.save_to_json(json_path)
    scraper.save_to_csv(csv_path)

    # Pipeline de nettoyage
    pipeline = DataPipeline(db_url=build_db_url() if args.import_db else None)
    cleaned = pipeline.clean(scraper.data)

    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    import json
    processed_path = processed_dir / f"{args.source}_processed.json"
    with open(processed_path, "w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, ensure_ascii=False, indent=2)
    logger.info("Données nettoyées → %s", processed_path)

    # Import BDD
    if args.import_db:
        if not build_db_url():
            logger.error("POSTGRES_PASSWORD manquant dans .env — import annulé")
        else:
            pipeline.db_url = build_db_url()
            inserted = pipeline.import_to_db(cleaned)
            logger.info("Import PostgreSQL : %d entrées insérées", inserted)

    # Résumé final
    summary = stats.summary()
    logger.info(
        "Terminé — fetches: %d | erreurs: %d | items: %d | durée: %.1fs",
        summary["fetches"], summary["errors"],
        summary["items_parsed"], summary["duration_s"],
    )


if __name__ == "__main__":
    main()
