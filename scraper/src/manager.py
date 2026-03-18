"""ScraperManager — Factory Pattern + orchestration des scrapers."""

import logging
from typing import Any

from src.base_scraper import BaseScraper
from src.scrapers.pawolotek_scraper import PawoloTekScraper
from src.scrapers.potomitan_scraper import PotomitanScraper

logger = logging.getLogger(__name__)

# Registre des sources disponibles
_SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "pawolotek": PawoloTekScraper,
    "potomitan": PotomitanScraper,
}


class ScraperManager:
    """Gère la création et l'exécution des scrapers (Factory Pattern).

    Attributes:
        _scrapers: Instances de scrapers créées via create_scraper().
    """

    def __init__(self) -> None:
        self._scrapers: list[BaseScraper] = []

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create_scraper(source: str, **kwargs: Any) -> BaseScraper:
        """Instancie le scraper correspondant à la source demandée.

        Args:
            source: Clé de la source (ex : 'pawolotek').
            **kwargs: Arguments transmis au constructeur du scraper.

        Returns:
            Instance du scraper.

        Raises:
            ValueError: Si la source n'est pas enregistrée.
        """
        scraper_class = _SCRAPER_REGISTRY.get(source.lower())
        if not scraper_class:
            available = ", ".join(_SCRAPER_REGISTRY.keys())
            raise ValueError(
                f"Source inconnue : '{source}'. Sources disponibles : {available}"
            )
        logger.info("Création scraper : %s", scraper_class.__name__)
        return scraper_class(**kwargs)

    @staticmethod
    def available_sources() -> list[str]:
        """Retourne la liste des sources enregistrées.

        Returns:
            Liste des clés de sources disponibles.
        """
        return list(_SCRAPER_REGISTRY.keys())

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def add_scraper(self, scraper: BaseScraper) -> None:
        """Ajoute un scraper déjà instancié à la file d'exécution.

        Args:
            scraper: Instance de BaseScraper à ajouter.
        """
        self._scrapers.append(scraper)

    def scrape_all(self, max_pages: int = 0) -> dict[str, list[dict[str, Any]]]:
        """Exécute séquentiellement tous les scrapers enregistrés.

        Args:
            max_pages: Nombre maximum d'items par scraper (0 = illimité).

        Returns:
            Dictionnaire {nom_scraper: liste_d_entrées}.
        """
        results: dict[str, list[dict[str, Any]]] = {}

        for scraper in self._scrapers:
            name = scraper.__class__.__name__
            logger.info("Démarrage : %s", name)
            try:
                data = scraper.scrape(max_pages=max_pages)
                results[name] = data
                logger.info("%s → %d entrées collectées", name, len(data))
            except Exception as exc:
                logger.error("Échec de %s : %s", name, exc)
                results[name] = []

        return results

    def aggregate(self) -> list[dict[str, Any]]:
        """Agrège toutes les données collectées par les scrapers actifs.

        Returns:
            Liste unifiée de toutes les entrées, toutes sources confondues.
        """
        all_data: list[dict[str, Any]] = []
        for scraper in self._scrapers:
            all_data.extend(scraper.data)
        return all_data

    def __repr__(self) -> str:
        names = [s.__class__.__name__ for s in self._scrapers]
        return f"ScraperManager(scrapers={names})"
