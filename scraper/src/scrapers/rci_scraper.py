"""RCIScraper — Articles d'actualité RCI (rci.fm).

Données extraites : titre, résumé, corps de l'article, catégorie, date, url
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class RCIScraper(BaseScraper):
    """Scraper pour rci.fm — radio et actualités caribéennes.

    Example:
        scraper = RCIScraper()
        scraper.scrape(max_pages=3)
        scraper.save_to_json("data/raw/rci_raw.json")

        from src.db_loader import get_connection
        conn = get_connection()
        scraper.save_to_db(conn)
        conn.close()
    """

    SOURCE   = "rci"
    DOC_TYPE = "actualite"

    def __init__(self, delay: float = 2.0) -> None:
        super().__init__(base_url="https://www.rci.fm", delay=delay)

    # ------------------------------------------------------------------
    # Méthodes abstraites obligatoires
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape les articles d'actualité page par page.

        Args:
            max_pages: Nombre de pages à scraper (0 = illimité).

        Returns:
            Liste des articles collectés (aussi dans self.data).
        """
        self.data = []
        page = 1
        while True:
            # TODO : adapter l'URL de pagination au site réel
            url = f"{self.base_url}/actualites?page={page}"
            soup = self.fetch_page(url)
            if soup is None:
                break

            items = self.parse(soup)
            if not items:
                break

            self.data.extend(items)
            self._notify("parse", {"page": page, "count": len(items)})
            logger.info("RCI page %d : %d articles", page, len(items))

            if max_pages and page >= max_pages:
                break
            page += 1

        self._notify("done", {"total": len(self.data)})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les articles depuis une page HTML.

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste de dicts avec les champs bruts du site.
        """
        items = []

        # TODO : identifier le bon sélecteur CSS/tag sur rci.fm
        for card in soup.select(".article-card"):  # ← à adapter
            try:
                item: dict[str, Any] = {
                    "titre":    _text(card, ".article-title"),    # ← à adapter
                    "resume":   _text(card, ".article-summary"),  # ← à adapter
                    "categorie":_text(card, ".article-category"), # ← à adapter
                    "date":     _text(card, ".article-date"),     # ← à adapter
                    "url":      _href(card, "a", self.base_url),  # ← à adapter
                }
                if item["titre"]:
                    items.append(item)
            except Exception as e:
                logger.warning("Erreur parsing article : %s", e)

        return items

    def _fetch_article_body(self, url: str) -> str:
        """Récupère le corps complet d'un article (optionnel, page détail).

        Si vous souhaitez plus que le résumé, appelez cette méthode dans
        scrape() pour chaque article et ajoutez le corps dans l'item.

        Args:
            url: URL de l'article complet.

        Returns:
            Texte du corps de l'article ou '' si erreur.
        """
        soup = self.fetch_page(url)
        if soup is None:
            return ""
        # TODO : adapter le sélecteur au site réel
        body = soup.select_one(".article-body")  # ← à adapter
        return body.get_text(separator=" ", strip=True) if body else ""

    # ------------------------------------------------------------------
    # Normalisation RAG — OBLIGATOIRE
    # ------------------------------------------------------------------

    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalise un article RCI vers le schéma commun `documents`.

        Fèfèn doit pouvoir répondre à "Quelle est l'actu en Martinique ?",
        donc le `content` combine titre + résumé + corps si disponible.

        Args:
            item: Entrée brute issue de parse().

        Returns:
            Dict conforme au schéma de la table `documents`.
        """
        parts = []
        if item.get("resume"):
            parts.append(item["resume"])
        if item.get("corps"):   # si _fetch_article_body a été appelé
            parts.append(item["corps"])
        if item.get("categorie"):
            parts.append(f"Catégorie : {item['categorie']}.")

        return {
            "source":       self.SOURCE,
            "doc_type":     self.DOC_TYPE,
            "title":        item.get("titre", "Article sans titre"),
            "content":      " ".join(parts) or item.get("titre", ""),
            "url":          item.get("url"),
            "published_at": item.get("date"),   # à parser si format non-ISO
            "metadata": {
                "categorie": item.get("categorie"),
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
