"""Scraper pour potomitan.info — contes, poèmes et proverbes créoles.

robots.txt : Crawl-delay de 60 secondes obligatoire.

Sections scrappées :
    - contes    : /atelier/contes/        → liste d'articles → texte complet
    - poemes    : /poemes/index.php       → liste par auteur → texte complet
    - proverbes : /duranty/belpoveb.php   → page unique, 836+ proverbes numérotés

Structure HTML des pages de contenu :
    - Pas de classes/IDs sémantiques sur ce site (HTML statique années 2000)
    - Contes    : titres en <h2>, texte en <p> + <blockquote>
    - Poèmes    : titre en <h1>/<h2>, texte en nœuds texte bruts entre heading et pied de page
    - Proverbes : <h4> numéroté + <p> avec proverbes créoles en <em>«guillemets»
                  Page en ISO-8859-1, une seule URL, pas de pagination
"""

import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString

from src.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Texte à exclure : navigation, en-tête et pied de page du site
_NOISE_PATTERNS = re.compile(
    r"(retour|sommaire|accueil|©|potomitan|haut de page"
    r"|annou voyé kreyòl|site de promotion|litérati|lyannaj"
    r"|bibliographie|livredor|rechercher"
    r"|^actualité$|^contes$|^poèmes$|^contacts$)",
    re.IGNORECASE,
)


class PotomitanScraper(BaseScraper):
    """Scraper pour potomitan.info (contes et poèmes créoles).

    Respecte le crawl-delay de 60 secondes imposé par le robots.txt du site.

    Attributes:
        sections: Sections à scraper ('contes', 'poemes', ou les deux).
        source_id: ID de la source en base de données (table sources).
    """

    BASE_URL = "https://www.potomitan.info"

    # URLs d'index par section
    _SECTION_URLS: dict[str, str] = {
        "contes":    "/atelier/contes/",
        "poemes":    "/poemes/index.php",
        "proverbes": "/duranty/belpoveb.php",
    }

    def __init__(
        self,
        sections: list[str] | None = None,
        source_id: int = 2,
        delay: float = 60.0,
    ) -> None:
        super().__init__(self.BASE_URL, delay=delay)
        self.sections: list[str] = sections or list(self._SECTION_URLS.keys())
        self.source_id: int = source_id

    # ------------------------------------------------------------------
    # Méthodes abstraites implémentées
    # ------------------------------------------------------------------

    def scrape(self, max_pages: int = 0) -> list[dict[str, Any]]:
        """Scrape toutes les sections configurées.

        Args:
            max_pages: Nombre maximum d'articles par section (0 = illimité).

        Returns:
            Liste complète des entrées extraites (self.data).
        """
        import time
        start = time.time()

        for section in self.sections:
            index_path = self._SECTION_URLS.get(section)
            if not index_path:
                logger.warning("Section inconnue : %s", section)
                continue

            index_url = self.BASE_URL + index_path
            logger.info("Scraping section : %s → %s", section, index_url)

            if section == "contes":
                items = self._scrape_contes(index_url, max_items=max_pages)
            elif section == "poemes":
                items = self._scrape_poemes(index_url, max_items=max_pages)
            elif section == "proverbes":
                items = self._scrape_proverbes(index_url, max_items=max_pages)
            else:
                items = []

            self.data.extend(items)
            self._notify("parse", {"count": len(items)})
            logger.info("Section %s → %d items", section, len(items))

        self._notify("done", {"total": len(self.data), "duration": time.time() - start})
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extrait les entrées depuis une page HTML.

        Implémentation générique (non utilisée directement — voir
        _parse_conte_page et _parse_poeme_page pour la logique métier).

        Args:
            soup: Page HTML parsée.

        Returns:
            Liste vide (parsing délégué aux méthodes spécifiques).
        """
        return []

    def to_document(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "source":       "potomitan",
            "doc_type":     item.get("categorie", "conte"),
            "title":        item.get("titre", ""),
            "content":      item.get("texte_creole", ""),
            "url":          item.get("url") or None,
            "published_at": item.get("date_publication") or None,
            "metadata":     {
                "titre_fr": item.get("titre_fr", ""),
                "auteur":   item.get("auteur", ""),
                "explication": item.get("explication", ""),
            },
        }

    # ------------------------------------------------------------------
    # Contes
    # ------------------------------------------------------------------

    def _scrape_contes(
        self, index_url: str, max_items: int = 0
    ) -> list[dict[str, Any]]:
        """Scrape la liste des contes puis chaque page individuelle.

        Args:
            index_url: URL de la page d'index des contes.
            max_items: Limite du nombre d'articles (0 = illimité).

        Returns:
            Liste des entrées extraites.
        """
        soup = self.fetch_page(index_url)
        if not soup:
            return []

        links = self._extract_conte_links(soup, index_url)
        if max_items:
            links = links[:max_items]

        entries: list[dict[str, Any]] = []
        for url in links:
            page = self.fetch_page(url)
            if not page:
                continue
            entry = self._parse_conte_page(page, url)
            if entry:
                entries.append(entry)

        return entries

    def _extract_conte_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[str]:
        """Extrait les URLs des contes depuis la page d'index.

        La page liste les contes dans un <ol> avec des <a href="...">

        Args:
            soup: Page d'index parsée.
            base_url: URL de base pour résoudre les chemins relatifs.

        Returns:
            Liste des URLs absolues des pages de contes.
        """
        links: list[str] = []
        for tag in soup.find_all("a", href=True):
            href: str = tag["href"]
            # Filtrer : uniquement les pages de contes (ex: conte_creole70.php)
            if re.search(r"conte_creole\d+\.php", href):
                links.append(urljoin(base_url, href))
        return links

    def _parse_conte_page(
        self, soup: BeautifulSoup, url: str
    ) -> dict[str, Any] | None:
        """Extrait le contenu d'une page de conte.

        Args:
            soup: Page individuelle du conte parsée.
            url: URL de la page (pour l'attribution).

        Returns:
            Dictionnaire de l'entrée, ou None si contenu insuffisant.
        """
        # Titre créole = premier h1, h2 ou h3 trouvé
        heading = soup.find(["h1", "h2", "h3"])
        titre_creole = heading.get_text(strip=True) if heading else ""
        # Titre français = second heading du même niveau si présent
        all_headings = soup.find_all(heading.name) if heading else []
        titre_fr = all_headings[1].get_text(strip=True) if len(all_headings) > 1 else ""

        # Texte : tous les <p> et <blockquote> du body, en filtrant la nav
        paragraphs: list[str] = []
        for tag in soup.find_all(["p", "blockquote"]):
            text = tag.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text)
            if text and not _NOISE_PATTERNS.search(text):
                paragraphs.append(text)

        texte = " ".join(paragraphs).strip()

        if not texte and not titre_creole:
            return None

        return {
            "source": "potomitan.info",
            "source_id": self.source_id,
            "url": url,
            "categorie": "conte",
            "titre": titre_creole,
            "titre_fr": titre_fr,
            "texte_creole": texte,
            "texte_fr": "",
            "audio_url": "",
            "hashtags": [],
            "date_publication": "",
        }

    # ------------------------------------------------------------------
    # Poèmes
    # ------------------------------------------------------------------

    def _scrape_poemes(
        self, index_url: str, max_items: int = 0
    ) -> list[dict[str, Any]]:
        """Scrape la liste des poèmes puis chaque page individuelle.

        Args:
            index_url: URL de la page d'index des poèmes.
            max_items: Limite du nombre d'articles (0 = illimité).

        Returns:
            Liste des entrées extraites.
        """
        soup = self.fetch_page(index_url)
        if not soup:
            return []

        links = self._extract_poeme_links(soup, index_url)
        if max_items:
            links = links[:max_items]

        entries: list[dict[str, Any]] = []
        for url, auteur in links:
            page = self.fetch_page(url)
            if not page:
                continue
            entry = self._parse_poeme_page(page, url, auteur)
            if entry:
                entries.append(entry)

        return entries

    def _extract_poeme_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[tuple[str, str]]:
        """Extrait les URLs des poèmes individuels depuis la page d'index.

        La page est organisée par auteur. On récupère uniquement les liens
        qui restent dans le répertoire /poemes/ (pas de remontée vers ../).

        Args:
            soup: Page d'index parsée.
            base_url: URL de base pour résoudre les chemins relatifs.

        Returns:
            Liste de tuples (url_absolue, nom_auteur).
        """
        # URL de référence pour filtrer : uniquement /poemes/
        poemes_base = urljoin(self.BASE_URL, "/poemes/")

        links: list[tuple[str, str]] = []
        current_author = ""

        for tag in soup.find_all(["a", "b", "strong"]):
            # Détecter les noms d'auteur (balises <b>/<strong> sans href)
            if tag.name in ("b", "strong") and not tag.find("a"):
                text = tag.get_text(strip=True)
                if text and len(text) > 2:
                    current_author = text

            # Récupérer les liens vers les poèmes individuels
            if tag.name == "a" and tag.get("href"):
                href: str = tag["href"]
                # Ignorer liens externes, mailto, ancres, remontées de dossier
                if href.startswith(("http", "mailto", "#", "..")) :
                    continue
                if not href.endswith(".php"):
                    continue
                if any(kw in href for kw in ("index", "sommaire", "livredor")):
                    continue

                abs_url = urljoin(base_url, href)
                # Garder uniquement les URL dans /poemes/
                if abs_url.startswith(poemes_base):
                    links.append((abs_url, current_author))

        # Déduplication sur l'URL
        seen: set[str] = set()
        unique: list[tuple[str, str]] = []
        for url, auteur in links:
            if url not in seen:
                seen.add(url)
                unique.append((url, auteur))

        return unique

    def _parse_poeme_page(
        self, soup: BeautifulSoup, url: str, auteur: str
    ) -> dict[str, Any] | None:
        """Extrait le contenu d'une page de poème.

        Les poèmes sont souvent du texte brut sans balises sémantiques.
        On extrait les nœuds texte du body en filtrant nav/footer.

        Args:
            soup: Page individuelle du poème parsée.
            url: URL de la page.
            auteur: Nom de l'auteur récupéré depuis l'index.

        Returns:
            Dictionnaire de l'entrée, ou None si contenu insuffisant.
        """
        # Titre : premier h1 ou h2
        titre_tag = soup.find("h1") or soup.find("h2")
        titre = titre_tag.get_text(strip=True) if titre_tag else ""

        # Texte : nœuds texte situés APRÈS le premier heading (évite la nav)
        lines: list[str] = []
        anchor = titre_tag  # on part du heading trouvé plus haut

        if anchor:
            for element in anchor.next_elements:
                if isinstance(element, NavigableString):
                    text = str(element).strip()
                    text = re.sub(r"\s+", " ", text)
                    if text and len(text) > 5 and not _NOISE_PATTERNS.search(text):
                        lines.append(text)
        else:
            # Pas de heading : extraction complète avec filtre nav
            body = soup.find("body") or soup
            for element in body.descendants:
                if isinstance(element, NavigableString):
                    text = str(element).strip()
                    text = re.sub(r"\s+", " ", text)
                    if text and len(text) > 5 and not _NOISE_PATTERNS.search(text):
                        lines.append(text)

        texte = "\n".join(lines).strip()

        if not texte and not titre:
            return None

        return {
            "source": "potomitan.info",
            "source_id": self.source_id,
            "url": url,
            "categorie": "poeme",
            "titre": titre,
            "titre_fr": "",
            "texte_creole": texte,
            "texte_fr": "",
            "audio_url": "",
            "hashtags": [],
            "date_publication": "",
            "auteur": auteur,
        }

    # ------------------------------------------------------------------
    # Proverbes
    # ------------------------------------------------------------------

    def _scrape_proverbes(
        self, page_url: str, max_items: int = 0
    ) -> list[dict[str, Any]]:
        """Scrape la page unique des proverbes créoles (belpoveb.php).

        La page contient 836+ proverbes numérotés structurés ainsi :
            <h4>Bel poveb kréyol N</h4>
            <p>contexte <em>«proverbe créole»</em> commentaire</p>

        Chaque balise <em> contient un proverbe distinct. Le texte hors <em>
        dans le même <p> constitue l'explication/contexte.

        Args:
            page_url: URL de la page des proverbes.
            max_items: Limite du nombre d'entrées (0 = illimité).

        Returns:
            Liste de dicts avec clé 'categorie' = 'proverbe'.
        """
        import requests

        # La page est encodée en ISO-8859-1
        try:
            r = requests.get(page_url, headers=self.headers, timeout=30)
            r.raise_for_status()
            r.encoding = "iso-8859-1"
            soup = BeautifulSoup(r.text, "lxml")
        except Exception as e:
            logger.error("Erreur fetch proverbes : %s", e)
            return []

        entries: list[dict[str, Any]] = []

        for h4 in soup.find_all("h4"):
            numero_txt = h4.get_text(strip=True)  # ex: "Bel poveb kréyol 40"

            # Trouver le <p> qui suit immédiatement le <h4>
            p_tag = h4.find_next_sibling("p")
            if not p_tag:
                continue

            # Extraire les proverbes créoles balisés dans <em>
            em_tags = p_tag.find_all("em")
            if not em_tags:
                continue

            # Texte complet du paragraphe sans les balises → explication
            full_text = re.sub(r"\s+", " ", p_tag.get_text(separator=" ", strip=True))

            for em in em_tags:
                texte_creole = re.sub(r"\s+", " ", em.get_text(strip=True))
                # Nettoyer les guillemets typographiques
                texte_creole = texte_creole.strip("«»\u00ab\u00bb").strip()
                if not texte_creole or len(texte_creole) < 5:
                    continue

                entries.append({
                    "source": "potomitan.info",
                    "source_id": self.source_id,
                    "url": page_url,
                    "categorie": "proverbe",
                    "titre": numero_txt,
                    "titre_fr": "",
                    "texte_creole": texte_creole,
                    "texte_fr": "",
                    "explication": full_text,
                    "audio_url": "",
                    "hashtags": [],
                    "date_publication": "",
                })

                if max_items and len(entries) >= max_items:
                    return entries

        logger.info("Proverbes extraits : %d", len(entries))
        return entries
