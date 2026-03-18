"""Classe abstraite BaseScraper — socle commun de tous les scrapers."""

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS: dict[str, str] = {
    "User-Agent": "Lang-Matinitje-Bot/1.0 (Open Source; contact: roor@nasdy.fr)",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BaseScraper(ABC):
    """Classe abstraite pour tous les scrapers Lang Matinitjé.

    Attributes:
        base_url: URL racine du site cible.
        delay: Délai en secondes entre chaque requête (rate limiting).
        headers: En-têtes HTTP envoyés avec chaque requête.
        data: Liste des entrées collectées.
        _observers: Liste des observateurs attachés (pattern Observer).
    """

    def __init__(self, base_url: str, delay: float = 2.0) -> None:
        self.base_url: str = base_url.rstrip("/")
        self.delay: float = delay
        self.headers: dict[str, str] = HEADERS.copy()
        self.data: list[dict[str, Any]] = []
        self._observers: list[Any] = []

    # ------------------------------------------------------------------
    # Observer Pattern
    # ------------------------------------------------------------------

    def attach(self, observer: Any) -> None:
        """Attache un observateur.

        Args:
            observer: Instance implémentant ScraperObserver.
        """
        self._observers.append(observer)

    def detach(self, observer: Any) -> None:
        """Détache un observateur.

        Args:
            observer: Instance à retirer.
        """
        self._observers.remove(observer)

    def _notify(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Notifie tous les observateurs d'un événement.

        Args:
            event: Nom de l'événement ('fetch', 'parse', 'error', 'done').
            payload: Données associées à l'événement.
        """
        for observer in self._observers:
            observer.update(event, payload or {})

    # ------------------------------------------------------------------
    # Méthodes concrètes
    # ------------------------------------------------------------------

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        """Récupère et parse une page HTML avec rate limiting.

        Args:
            url: URL complète à récupérer.

        Returns:
            Objet BeautifulSoup ou None en cas d'erreur réseau.
        """
        time.sleep(self.delay)
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            self._notify("fetch", {"url": url, "status": response.status_code})
            return BeautifulSoup(response.content, "lxml")
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP %s — %s", e.response.status_code, url)
            self._notify("error", {"url": url, "error": str(e)})
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Erreur réseau : %s — %s", type(e).__name__, url)
            self._notify("error", {"url": url, "error": str(e)})
            return None

    def save_to_json(self, path: str | Path) -> None:
        """Sauvegarde self.data dans un fichier JSON.

        Args:
            path: Chemin du fichier de sortie.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=2)
        logger.info("Sauvegardé : %s (%d entrées)", path, len(self.data))

    def save_to_csv(self, path: str | Path) -> None:
        """Sauvegarde self.data dans un fichier CSV.

        Args:
            path: Chemin du fichier de sortie.
        """
        import pandas as pd  # import local : pandas optionnel

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self.data).to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("Sauvegardé : %s (%d entrées)", path, len(self.data))

    # ------------------------------------------------------------------
    # Méthodes abstraites
    # ------------------------------------------------------------------

    @abstractmethod
    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Méthode principale de scraping.

        Args:
            max_pages: Nombre maximum de pages/items à scraper (0 = illimité).

        Returns:
            Liste de dictionnaires représentant les entrées collectées.
        """

    @abstractmethod
    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les données structurées depuis un objet BeautifulSoup.

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste de dictionnaires représentant les entrées extraites.
        """

    @abstractmethod
    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalise une entrée brute vers le schéma commun `documents`.

        Chaque scraper DOIT implémenter cette méthode pour que ses données
        puissent être intégrées dans la base RAG de Fèfèn.

        Args:
            item: Un élément de self.data (tel que retourné par parse()).

        Returns:
            Dictionnaire conforme au schéma de la table `documents` :

            Obligatoires :
                source   (str) : identifiant du scraper — ex: 'bizouk'
                doc_type (str) : type de document   — ex: 'annonce'
                title    (str) : titre principal
                content  (str) : texte principal utilisé pour la recherche RAG

            Optionnels :
                url          (str | None) : URL source (permet la déduplication)
                published_at (str | None) : date ISO-8601 — ex: '2026-01-15'
                metadata     (dict | None): champs spécifiques au scraper
                                            ex: {'prix': '120€', 'localisation': 'Fort-de-France'}
        """

    def save_to_db(self, conn: Any) -> int:
        """Sauvegarde self.data dans la table `documents` via DocumentLoader.

        Appelle to_document() sur chaque élément de self.data puis effectue
        un UPSERT groupé (idempotent : relancer ne crée pas de doublons).

        Args:
            conn: Connexion psycopg2 active.

        Returns:
            Nombre de documents insérés ou mis à jour.

        Example:
            from src.db_loader import get_connection
            conn = get_connection()
            scraper.scrape(max_pages=3)
            n = scraper.save_to_db(conn)
            conn.close()
        """
        from src.db_loader import DocumentLoader  # import local évite la dépendance circulaire

        loader = DocumentLoader(conn)
        return loader.upsert_many(self.data, self.to_document)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url={self.base_url!r}, items={len(self.data)})"
