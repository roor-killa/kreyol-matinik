"""MadianaScraper — Cinéma Madiana (madiana.com).

Données extraites : titre du film, description, prix_place, séances,
                    genre, images, url
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class MadianaScraper(BaseScraper):
    """Scraper pour madiana.com — programme cinéma en Martinique.

    Example:
        scraper = MadianaScraper()
        scraper.scrape(max_pages=1)   # 1 page suffit souvent pour le programme
        scraper.save_to_json("data/raw/madiana_raw.json")

        from src.db_loader import get_connection
        conn = get_connection()
        scraper.save_to_db(conn)
        conn.close()
    """

    SOURCE   = "madiana"
    DOC_TYPE = "film"

    def __init__(self, delay: float = 2.0) -> None:
        super().__init__(base_url="https://www.madiana.com", delay=delay)

    # ------------------------------------------------------------------
    # Méthodes abstraites obligatoires
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape le programme cinéma.

        Args:
            max_pages: Nombre de pages (0 = illimité). Souvent 1 seule page.

        Returns:
            Liste des films collectés (aussi dans self.data).
        """
        self.data = []
        page = 1
        while True:
            # TODO : adapter l'URL au site réel (parfois une seule page de programme)
            url = f"{self.base_url}/programme?page={page}"
            soup = self.fetch_page(url)
            if soup is None:
                break

            items = self.parse(soup)
            if not items:
                break

            self.data.extend(items)
            self._notify("parse", {"page": page, "count": len(items)})
            logger.info("Madiana page %d : %d films", page, len(items))

            if max_pages and page >= max_pages:
                break
            page += 1

        self._notify("done", {"total": len(self.data)})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les films depuis une page HTML.

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste de dicts avec les champs bruts du site.
        """
        items = []

        # TODO : identifier le bon sélecteur CSS/tag sur madiana.com
        for card in soup.select(".film-card"):  # ← à adapter
            try:
                item: dict[str, Any] = {
                    "titre":       _text(card, ".film-title"),       # ← à adapter
                    "description": _text(card, ".film-synopsis"),    # ← à adapter
                    "genre":       _text(card, ".film-genre"),       # ← à adapter
                    "seances":     _text(card, ".film-seances"),     # ← à adapter
                    "prix_place":  _text(card, ".film-prix"),        # ← à adapter
                    "images":      _src(card, "img"),                # ← à adapter
                    "url":         _href(card, "a", self.base_url),  # ← à adapter
                }
                if item["titre"]:
                    items.append(item)
            except Exception as e:
                logger.warning("Erreur parsing film : %s", e)

        return items

    # ------------------------------------------------------------------
    # Normalisation RAG — OBLIGATOIRE
    # ------------------------------------------------------------------

    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalise un film Madiana vers le schéma commun `documents`.

        Fèfèn doit pouvoir répondre à "Qu'est-ce qui passe au ciné en ce moment ?",
        donc le `content` doit contenir le synopsis et les séances.

        Args:
            item: Entrée brute issue de parse().

        Returns:
            Dict conforme au schéma de la table `documents`.
        """
        parts = []
        if item.get("description"):
            parts.append(item["description"])
        if item.get("genre"):
            parts.append(f"Genre : {item['genre']}.")
        if item.get("seances"):
            parts.append(f"Séances : {item['seances']}.")
        if item.get("prix_place"):
            parts.append(f"Prix : {item['prix_place']}.")

        return {
            "source":       self.SOURCE,
            "doc_type":     self.DOC_TYPE,
            "title":        item.get("titre", "Film sans titre"),
            "content":      " ".join(parts) or item.get("titre", ""),
            "url":          item.get("url"),
            "published_at": None,   # date de sortie non disponible ici
            "metadata": {
                "genre":      item.get("genre"),
                "seances":    item.get("seances"),
                "prix_place": item.get("prix_place"),
                "images":     item.get("images"),
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


def _src(tag: Any, selector: str) -> str | None:
    el = tag.select_one(selector)
    return el.get("src") if el else None
