"""KiprixScraper — Comparateur de prix antillais (kiprix.com).

Données extraites : nom, prix, magasin, disponibilité, catégorie, url
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class KiprixScraper(BaseScraper):
    """Scraper pour kiprix.com — comparateur de prix en Martinique.

    Example:
        scraper = KiprixScraper()
        scraper.scrape(max_pages=5)
        scraper.save_to_json("data/raw/kiprix_raw.json")

        from src.db_loader import get_connection
        conn = get_connection()
        scraper.save_to_db(conn)
        conn.close()
    """

    SOURCE   = "kiprix"
    DOC_TYPE = "produit"

    def __init__(self, delay: float = 2.0) -> None:
        super().__init__(base_url="https://www.kiprix.com", delay=delay)

    # ------------------------------------------------------------------
    # Méthodes abstraites obligatoires
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape les produits page par page.

        Args:
            max_pages: Nombre de pages à scraper (0 = illimité).

        Returns:
            Liste des produits collectés (aussi dans self.data).
        """
        self.data = []
        page = 1
        while True:
            # TODO : adapter l'URL de pagination au site réel
            url = f"{self.base_url}/produits?page={page}"
            soup = self.fetch_page(url)
            if soup is None:
                break

            items = self.parse(soup)
            if not items:
                break

            self.data.extend(items)
            self._notify("parse", {"page": page, "count": len(items)})
            logger.info("Kiprix page %d : %d produits", page, len(items))

            if max_pages and page >= max_pages:
                break
            page += 1

        self._notify("done", {"total": len(self.data)})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les produits depuis une page HTML.

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste de dicts avec les champs bruts du site.
        """
        items = []

        # TODO : identifier le bon sélecteur CSS/tag sur kiprix.com
        for card in soup.select(".product-card"):  # ← à adapter
            try:
                item: dict[str, Any] = {
                    "nom":          _text(card, ".product-name"),         # ← à adapter
                    "prix":         _text(card, ".product-price"),        # ← à adapter
                    "magasin":      _text(card, ".product-store"),        # ← à adapter
                    "disponibilite":_text(card, ".product-availability"), # ← à adapter
                    "categorie":    _text(card, ".product-category"),     # ← à adapter
                    "url":          _href(card, "a", self.base_url),      # ← à adapter
                }
                if item["nom"]:
                    items.append(item)
            except Exception as e:
                logger.warning("Erreur parsing produit : %s", e)

        return items

    # ------------------------------------------------------------------
    # Normalisation RAG — OBLIGATOIRE
    # ------------------------------------------------------------------

    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalise un produit Kiprix vers le schéma commun `documents`.

        Le champ `content` est formulé comme une phrase naturelle pour que
        Fèfèn puisse répondre à "Où acheter du lait pas cher en Martinique ?".

        Args:
            item: Entrée brute issue de parse().

        Returns:
            Dict conforme au schéma de la table `documents`.
        """
        # Phrase naturelle optimisée pour l'embedding
        parts = [item.get("nom", "Produit")]
        if item.get("magasin"):
            parts.append(f"disponible chez {item['magasin']}")
        if item.get("prix"):
            parts.append(f"au prix de {item['prix']}")
        if item.get("disponibilite"):
            parts.append(f"({item['disponibilite']})")
        if item.get("categorie"):
            parts.append(f"— catégorie {item['categorie']}")

        return {
            "source":       self.SOURCE,
            "doc_type":     self.DOC_TYPE,
            "title":        item.get("nom", "Produit sans nom"),
            "content":      " ".join(parts),
            "url":          item.get("url"),
            "published_at": None,   # Kiprix n'a pas de date de publication
            "metadata": {
                "prix":          item.get("prix"),
                "magasin":       item.get("magasin"),
                "disponibilite": item.get("disponibilite"),
                "categorie":     item.get("categorie"),
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
