"""BizoukScraper — Petites annonces caribéennes (bizouk.com).

Données extraites : titre, prix, catégorie, localisation, date, url
"""

import logging
from typing import Any

from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class BizoukScraper(BaseScraper):
    """Scraper pour bizouk.com — petites annonces caribéennes.

    Example:
        scraper = BizoukScraper()
        scraper.scrape(max_pages=3)
        scraper.save_to_json("data/raw/bizouk_raw.json")

        from src.db_loader import get_connection
        conn = get_connection()
        scraper.save_to_db(conn)
        conn.close()
    """

    SOURCE   = "bizouk"
    DOC_TYPE = "annonce"

    def __init__(self, delay: float = 2.0) -> None:
        super().__init__(base_url="https://www.bizouk.com", delay=delay)

    # ------------------------------------------------------------------
    # Méthodes abstraites obligatoires
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape les annonces page par page.

        Args:
            max_pages: Nombre de pages à scraper (0 = illimité).

        Returns:
            Liste des annonces collectées (aussi dans self.data).
        """
        self.data = []
        page = 1
        while True:
            # TODO : adapter l'URL de pagination au site réel
            url = f"{self.base_url}/annonces?page={page}"
            soup = self.fetch_page(url)
            if soup is None:
                break

            items = self.parse(soup)
            if not items:
                break

            self.data.extend(items)
            self._notify("parse", {"page": page, "count": len(items)})
            logger.info("Bizouk page %d : %d annonces", page, len(items))

            if max_pages and page >= max_pages:
                break
            page += 1

        self._notify("done", {"total": len(self.data)})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les annonces depuis une page HTML.

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste de dicts avec les champs bruts du site.
        """
        items = []

        # TODO : identifier le bon sélecteur CSS/tag sur bizouk.com
        for card in soup.select(".annonce-card"):  # ← à adapter
            try:
                item: dict[str, Any] = {
                    "titre":       _text(card, ".annonce-titre"),     # ← à adapter
                    "prix":        _text(card, ".annonce-prix"),      # ← à adapter
                    "categorie":   _text(card, ".annonce-categorie"), # ← à adapter
                    "localisation":_text(card, ".annonce-lieu"),      # ← à adapter
                    "date":        _text(card, ".annonce-date"),      # ← à adapter
                    "description": _text(card, ".annonce-desc"),      # ← à adapter
                    "url":         _href(card, "a", self.base_url),   # ← à adapter
                }
                if item["titre"]:
                    items.append(item)
            except Exception as e:
                logger.warning("Erreur parsing annonce : %s", e)

        return items

    # ------------------------------------------------------------------
    # Normalisation RAG — OBLIGATOIRE
    # ------------------------------------------------------------------

    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalise une annonce Bizouk vers le schéma commun `documents`.

        Le champ `content` est le texte principal que Fèfèn lira pour répondre.
        Il doit être lisible et complet (pas juste un titre).

        Args:
            item: Entrée brute issue de parse().

        Returns:
            Dict conforme au schéma de la table `documents`.
        """
        # Construit un texte de recherche naturel pour le RAG
        content_parts = []
        if item.get("description"):
            content_parts.append(item["description"])
        if item.get("categorie"):
            content_parts.append(f"Catégorie : {item['categorie']}.")
        if item.get("prix"):
            content_parts.append(f"Prix : {item['prix']}.")
        if item.get("localisation"):
            content_parts.append(f"Localisation : {item['localisation']}.")

        return {
            "source":       self.SOURCE,
            "doc_type":     self.DOC_TYPE,
            "title":        item.get("titre", "Annonce sans titre"),
            "content":      " ".join(content_parts) or item.get("titre", ""),
            "url":          item.get("url"),
            "published_at": item.get("date"),       # à parser si format non-ISO
            "metadata": {
                "prix":         item.get("prix"),
                "categorie":    item.get("categorie"),
                "localisation": item.get("localisation"),
            },
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _text(tag: Any, selector: str) -> str:
    """Extrait le texte d'un sélecteur CSS, renvoie '' si absent."""
    el = tag.select_one(selector)
    return el.get_text(strip=True) if el else ""


def _href(tag: Any, selector: str, base_url: str) -> str | None:
    """Extrait l'href d'un lien, préfixe avec base_url si relatif."""
    el = tag.select_one(selector)
    if el and el.get("href"):
        href = el["href"]
        return href if href.startswith("http") else f"{base_url}{href}"
    return None
