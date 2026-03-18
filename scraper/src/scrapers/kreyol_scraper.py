"""KreyolScraper — Dictionnaire créole martiniquais.

Adapte les scrapers Pawolotek/Potomitan existants vers la table `documents`.
Données extraites : mot, définition, traductions, catégorie grammaticale.
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class KreyolScraper(BaseScraper):
    """Scraper dictionnaire créole — alimente la table `documents` depuis
    les sources linguistiques (Pawolotek, Potomitan, etc.).

    Contrairement aux autres scrapers, les mots sont aussi insérés dans les
    tables spécialisées (mots, traductions, définitions) via scraper/db/.
    La table `documents` permet à Fèfèn d'y accéder via RAG.

    Example:
        scraper = KreyolScraper()
        scraper.scrape(max_pages=10)
        scraper.save_to_json("data/raw/kreyol_raw.json")

        from src.db_loader import get_connection
        conn = get_connection()
        scraper.save_to_db(conn)
        conn.close()
    """

    SOURCE   = "kreyol"
    DOC_TYPE = "mot"

    def __init__(self, delay: float = 2.0) -> None:
        super().__init__(base_url="https://pawolotek.com", delay=delay)

    # ------------------------------------------------------------------
    # Méthodes abstraites obligatoires
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape les mots créoles.

        Args:
            max_pages: Nombre de pages à scraper (0 = illimité).

        Returns:
            Liste des mots collectés (aussi dans self.data).
        """
        self.data = []
        page = 1
        while True:
            url = f"{self.base_url}/?page={page}"
            soup = self.fetch_page(url)
            if soup is None:
                break

            items = self.parse(soup)
            if not items:
                break

            self.data.extend(items)
            self._notify("parse", {"page": page, "count": len(items)})
            logger.info("Kreyol page %d : %d mots", page, len(items))

            if max_pages and page >= max_pages:
                break
            page += 1

        self._notify("done", {"total": len(self.data)})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les mots depuis une page HTML.

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste de dicts avec les champs bruts du site.
        """
        items = []

        for entry in soup.select(".word-entry"):  # ← à adapter selon le site
            try:
                item: dict[str, Any] = {
                    "mot":           _text(entry, ".word-creole"),
                    "definition":    _text(entry, ".word-definition"),
                    "traduction_fr": _text(entry, ".word-french"),
                    "categorie_gram":_text(entry, ".word-pos"),
                    "exemple":       _text(entry, ".word-example"),
                    "phonetique":    _text(entry, ".word-phonetic"),
                    "url":           _href(entry, "a", self.base_url),
                }
                if item["mot"]:
                    items.append(item)
            except Exception as e:
                logger.warning("Erreur parsing mot : %s", e)

        return items

    # ------------------------------------------------------------------
    # Normalisation RAG — OBLIGATOIRE
    # ------------------------------------------------------------------

    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalise un mot créole vers le schéma commun `documents`.

        Le `content` est une phrase naturelle pour que Fèfèn puisse
        répondre à "Que veut dire 'bonjan' en créole ?".

        Args:
            item: Entrée brute issue de parse().

        Returns:
            Dict conforme au schéma de la table `documents`.
        """
        parts = []
        if item.get("definition"):
            parts.append(item["definition"])
        if item.get("traduction_fr"):
            parts.append(f"En français : {item['traduction_fr']}.")
        if item.get("exemple"):
            parts.append(f"Exemple : {item['exemple']}.")
        if item.get("categorie_gram"):
            parts.append(f"Catégorie : {item['categorie_gram']}.")

        return {
            "source":       self.SOURCE,
            "doc_type":     self.DOC_TYPE,
            "title":        item.get("mot", "Mot inconnu"),
            "content":      " ".join(parts) or item.get("mot", ""),
            "url":          item.get("url"),
            "published_at": None,
            "metadata": {
                "traduction_fr": item.get("traduction_fr"),
                "categorie_gram":item.get("categorie_gram"),
                "phonetique":    item.get("phonetique"),
                "exemple":       item.get("exemple"),
            },
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _text(tag: Any, selector: str) -> str:
    el = tag.select_one(selector)
    return el.get_text(strip=True) if el else ""


def _href(tag: Any, selector: str, base_url: str) -> str | None:
    el = tag.select_one(selector)
    if el and el.get("href"):
        href = el["href"]
        return href if href.startswith("http") else f"{base_url}{href}"
    return None
