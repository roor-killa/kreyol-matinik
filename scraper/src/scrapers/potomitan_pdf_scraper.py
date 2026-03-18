"""
potomitan_pdf_scraper.py — Scraper PDFs Dictionnaire Confiant
=============================================================
Télécharge les PDFs du Dictionnaire du Créole Martiniquais
(Raphaël Confiant) depuis potomitan.info/dictionnaire/.

Licence des données : libre diffusion avec attribution
© Raphaël Confiant — potomitan.info
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

BASE_URL  = "https://www.potomitan.info/dictionnaire/"
# Lettres disponibles (A–N confirmées, O–Z à vérifier)
PDF_SLUGS = ["a", "b", "ch", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n",
             "o", "p", "r", "s", "t", "u", "v", "w"]
DELAY     = 60.0   # robots.txt impose 60 s
HEADERS   = {"User-Agent": "Lang-Matinitje-Bot/1.0 (Open Source; contact: roor@nasdy.fr)"}


class PotomitanPDFScraper:
    """
    Télécharge les PDFs du dictionnaire créole martiniquais.

    Usage :
        scraper = PotomitanPDFScraper(out_dir=Path("data/raw/pdfs"))
        downloaded = scraper.run()
    """

    def __init__(
        self,
        out_dir: Path,
        delay: float = DELAY,
        slugs: list[str] | None = None,
    ) -> None:
        self.out_dir = out_dir
        self.delay   = delay
        self.slugs   = slugs or PDF_SLUGS
        self.out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def run(self) -> list[Path]:
        """Télécharge tous les PDFs manquants. Retourne les chemins."""
        downloaded: list[Path] = []

        for i, slug in enumerate(self.slugs):
            dest = self.out_dir / f"{slug}.pdf"

            if dest.exists():
                log.info("[%s] déjà téléchargé → %s", slug, dest)
                downloaded.append(dest)
                continue

            url = f"{BASE_URL}{slug}.pdf"
            log.info("[%s] téléchargement %s …", slug, url)

            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/pdf"):
                    dest.write_bytes(resp.content)
                    log.info("[%s] ✓ %d Ko → %s", slug, len(resp.content) // 1024, dest)
                    downloaded.append(dest)
                elif resp.status_code == 404:
                    log.warning("[%s] PDF non trouvé (404) — ignoré", slug)
                else:
                    log.warning("[%s] HTTP %d — ignoré", slug, resp.status_code)
            except requests.RequestException as exc:
                log.error("[%s] Erreur réseau : %s", slug, exc)

            # Délai robots.txt sauf après le dernier fichier
            if i < len(self.slugs) - 1:
                log.debug("Attente %.0f s (robots.txt)…", self.delay)
                time.sleep(self.delay)

        log.info("Scraping terminé : %d/%d PDFs téléchargés", len(downloaded), len(self.slugs))
        return downloaded
