"""Scraper pour pawolotek.com — lexique et corpus créole martiniquais.

Stratégie d'accès :
    Les pages individuelles `/index.php/podcast-item/{slug}/` retournent
    une erreur 500 côté serveur (bug WordPress). On utilise à la place
    les flux RSS par catégorie, qui sont stables et contiennent le contenu
    complet (titre, description, content:encoded, enclosure audio).

    Format RSS paginé : /index.php/podcast-category/{slug}/feed/?paged=N

Catégories :
    - podcast-parler-martiniquais  → lexique (mots et expressions)
    - podcast-societe-martinique   → société, quotidien
    - creation-sonore-martinique   → créations sonores
    - extraits                     → extraits divers
"""

import logging
import re
from email.utils import parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Catégories disponibles sur pawolotek.com
CATEGORIES: dict[str, str] = {
    "lexique":  "podcast-parler-martiniquais",
    "societe":  "podcast-societe-martinique",
    "creation": "creation-sonore-martinique",
    "extraits": "extraits",
}


class PawoloTekScraper(BaseScraper):
    """Scraper pour pawolotek.com via les flux RSS par catégorie.

    Extrait :
    - Entrées de lexique créole (mots, expressions, proverbes)
    - Corpus de phrases mêlant créole et français
    - URLs des fichiers audio (enclosure RSS si présente)

    Attributes:
        categories: Clés des catégories à scraper.
        source_id: ID de la source en base de données (table sources).
    """

    BASE_URL = "https://pawolotek.com"

    def __init__(
        self,
        categories: list[str] | None = None,
        source_id: int = 1,
        delay: float = 2.0,
    ) -> None:
        super().__init__(self.BASE_URL, delay=delay)
        self.categories: list[str] = categories or list(CATEGORIES.keys())
        self.source_id: int = source_id

    # ------------------------------------------------------------------
    # Méthodes abstraites implémentées
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape toutes les catégories configurées via leur flux RSS.

        Args:
            max_pages: Nombre maximum d'items par catégorie (0 = illimité).

        Returns:
            Liste complète des entrées extraites (self.data).
        """
        import time
        start = time.time()

        for cat_key in self.categories:
            slug = CATEGORIES.get(cat_key)
            if not slug:
                logger.warning("Catégorie inconnue : %s", cat_key)
                continue

            feed_base = f"{self.BASE_URL}/index.php/podcast-category/{slug}/feed/"
            logger.info("Scraping RSS catégorie : %s → %s", cat_key, feed_base)

            items = self._scrape_rss_feed(feed_base, cat_key, max_items=max_pages)
            self.data.extend(items)
            self._notify("parse", {"count": len(items)})
            logger.info("Catégorie %s → %d items", cat_key, len(items))

        self._notify("done", {"total": len(self.data), "duration": time.time() - start})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les items depuis un flux RSS parsé.

        Args:
            soup: Flux RSS parsé par BeautifulSoup (parser xml).

        Returns:
            Liste de dicts représentant les entrées extraites.
        """
        items: list[dict[str, Any]] = []
        for item_tag in soup.find_all("item"):
            entry = self._parse_rss_item(item_tag)
            if entry:
                items.append(entry)
        return items

    # ------------------------------------------------------------------
    # Méthodes spécifiques RSS
    # ------------------------------------------------------------------

    def _scrape_rss_feed(
        self, feed_base: str, category: str, max_items: int = 0
    ) -> list[dict[str, Any]]:
        """Parcourt toutes les pages d'un flux RSS WordPress.

        Args:
            feed_base: URL de base du flux RSS (sans paramètre paged).
            category: Clé de catégorie pour étiqueter les entrées.
            max_items: Limite du nombre d'items (0 = illimité).

        Returns:
            Liste des entrées extraites de l'ensemble du flux.
        """
        all_items: list[dict[str, Any]] = []
        page = 1

        while True:
            url = feed_base if page == 1 else f"{feed_base}?paged={page}"
            soup = self._fetch_xml(url)
            if not soup:
                break

            page_items = self.parse(soup)
            if not page_items:
                break

            for entry in page_items:
                entry["categorie"] = category
                all_items.append(entry)

            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break

            page += 1

        return all_items

    def _fetch_xml(self, url: str) -> BeautifulSoup | None:
        """Récupère et parse un flux XML/RSS.

        Args:
            url: URL du flux RSS.

        Returns:
            BeautifulSoup parsé en mode xml, ou None en cas d'erreur.
        """
        import time
        time.sleep(self.delay)

        import requests
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            self._notify("fetch", {"url": url, "status": r.status_code})
            return BeautifulSoup(r.content, "xml")
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP %s — %s", e.response.status_code, url)
            self._notify("error", {"url": url, "error": str(e)})
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Erreur réseau : %s — %s", type(e).__name__, url)
            self._notify("error", {"url": url, "error": str(e)})
            return None

    def _parse_rss_item(self, item_tag: Any) -> dict[str, Any] | None:
        """Extrait les données d'un élément <item> RSS.

        Args:
            item_tag: Tag BeautifulSoup représentant un <item> RSS.

        Returns:
            Dictionnaire de l'entrée, ou None si le titre est absent.
        """
        titre = item_tag.find("title")
        if not titre:
            return None
        titre_txt = titre.get_text(strip=True)
        if not titre_txt:
            return None

        # Lien de l'article (balise <link> ou <guid>)
        link_tag = item_tag.find("link")
        url = ""
        if link_tag:
            # En RSS, <link> est souvent suivi d'un nœud texte
            url = (link_tag.next_sibling or "").strip()
            if not url:
                url = link_tag.get_text(strip=True)
        if not url:
            guid = item_tag.find("guid")
            url = guid.get_text(strip=True) if guid else ""

        # Contenu textuel (préférer content:encoded sur description)
        content_tag = item_tag.find("encoded")  # content:encoded
        desc_tag = item_tag.find("description")
        raw_html = (
            content_tag.get_text() if content_tag and content_tag.get_text(strip=True)
            else (desc_tag.get_text() if desc_tag else "")
        )
        texte = BeautifulSoup(raw_html, "lxml").get_text(separator=" ", strip=True)
        texte = re.sub(r"\s+", " ", texte).strip()

        # Hashtags créole présents dans le texte
        hashtags = re.findall(r"#\w+", texte)

        # Date de publication
        pubdate_tag = item_tag.find("pubDate")
        date_pub = ""
        if pubdate_tag:
            try:
                dt = parsedate_to_datetime(pubdate_tag.get_text(strip=True))
                date_pub = dt.strftime("%Y-%m-%d")
            except Exception:
                date_pub = pubdate_tag.get_text(strip=True)[:10]

        # Fichier audio (enclosure RSS)
        enclosure = item_tag.find("enclosure")
        audio_url = enclosure.get("url", "") if enclosure else ""

        return {
            "source": "pawolotek.com",
            "source_id": self.source_id,
            "url": url,
            "categorie": "",        # complété par _scrape_rss_feed
            "titre": titre_txt,
            "texte_creole": texte,  # mélange FR/créole — pipeline détectera
            "texte_fr": "",
            "audio_url": audio_url,
            "hashtags": hashtags,
            "date_publication": date_pub,
        }
