"""
pdf_extractor.py — Extraction et parsing du Dictionnaire Confiant
==================================================================
Lit les PDFs téléchargés par PotomitanPDFScraper et extrait les
entrées du dictionnaire créole martiniquais.

Structure d'une entrée (format A — dot+définition sur même ligne) :
    mot [numéro]            ← en-tête (ligne seule)
    . définition française  ← définition (commence par .)
    Exemple créole          ← phrase d'exemple (optionnel)
    Traduction française    ← traduction de l'exemple (optionnel)

Structure d'une entrée (format B — dot seul sur sa ligne) :
    mot [numéro]            ← en-tête (ligne seule)
    .                       ← marqueur de définition (ligne seule)
    définition française    ← définition (ligne suivante)
    Exemple créole          ← phrase d'exemple (optionnel)
    Traduction française    ← traduction de l'exemple (optionnel)

Marqueurs communs :
    var. variante1, var2    ← variantes orthographiques
    syn. synonyme1, syn2    ← synonymes
    fém. forme féminine     ← féminin
    exp. expression         ← expression / locution
    pvb. proverbe           ← proverbe
    gwd. mot guadeloupéen   ← variante guadeloupéenne

Données extraites pour chaque entrée :
    mot_creole, numero, definition_fr, exemples, variantes, synonymes,
    expressions, proverbes, lettre
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber  # type: ignore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns regex
# ---------------------------------------------------------------------------

# En-tête d'entrée : mot créole seul sur une ligne (avec accents, tirets, apostrophes)
# Optionnellement suivi d'un numéro (homonymes : a 1, a 2, ababa 1…)
_RE_HEADER = re.compile(
    r"^([A-ZÀ-Öa-zà-öØ-öø-ÿ''\-]+(?:[- ][A-ZÀ-Öa-zà-öØ-öø-ÿ''\-]+)*)"
    r"(?:\s+(\d+))?\s*$"
)
# Définition : ligne commençant par "." suivi de texte
_RE_DEF = re.compile(r"^\.\s+(.+)")
# Définition : ligne qui est juste un "." (dot seul — le texte suit sur la ligne suivante)
_RE_DOT_ONLY = re.compile(r"^\.\s*$")
# Variante : "var. ..."
_RE_VAR = re.compile(r"^var\.\s*(.*)")
# Synonyme : "syn. ..."
_RE_SYN = re.compile(r"^syn\.\s*(.*)")
# Féminin : "fém. ..."
_RE_FEM = re.compile(r"^fém\.\s*(.*)")
# Expression : "exp. ..."
_RE_EXP = re.compile(r"^exp\.\s*(.*)")
# Proverbe : "pvb. ..."
_RE_PVB = re.compile(r"^pvb\.\s*(.*)")
# Guadeloupéen : "gwd. ..."
_RE_GWD = re.compile(r"^gwd\.\s*(.*)")
# Pied de page à supprimer
_RE_FOOTER = re.compile(
    r"Dictionnaire du créole martiniquais.+\d{4}\s+\d+$",
    re.IGNORECASE,
)
# Titre de page (ex: "Raphaël CONFIANT", "DICTIONNAIRE DU CREOLE MARTINIQUAIS", lettre seule)
_RE_PAGE_TITLE = re.compile(
    r"^(Raphaël CONFIANT|DICTIONNAIRE DU CREOLE MARTINIQUAIS|[A-Z]{1,3})$"
)


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class PDFExtractor:
    """
    Extrait les entrées du dictionnaire depuis un PDF Confiant.

    Usage :
        extractor = PDFExtractor()
        entries = extractor.extract(Path("data/raw/pdfs/a.pdf"))
    """

    def extract(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extrait et retourne toutes les entrées du PDF."""
        lettre = pdf_path.stem.upper()
        log.info("Extraction %s (%s)…", pdf_path.name, lettre)

        lines = self._read_lines(pdf_path)
        entries = self._parse(lines, lettre)
        log.info("  → %d entrées extraites", len(entries))
        return entries

    def extract_all(self, pdf_dir: Path) -> list[dict[str, Any]]:
        """Extrait les entrées de tous les PDFs d'un répertoire."""
        all_entries: list[dict[str, Any]] = []
        for pdf_path in sorted(pdf_dir.glob("*.pdf")):
            all_entries.extend(self.extract(pdf_path))
        log.info("Total : %d entrées extraites", len(all_entries))
        return all_entries

    # ------------------------------------------------------------------
    # Lecture du PDF → liste de lignes nettoyées
    # ------------------------------------------------------------------

    def _read_lines(self, pdf_path: Path) -> list[str]:
        lines: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    line = line.strip()
                    # Supprimer les pieds de page
                    if _RE_FOOTER.search(line):
                        continue
                    # Supprimer les titres de page répétés
                    if _RE_PAGE_TITLE.match(line):
                        continue
                    if line:
                        lines.append(line)
        return lines

    # ------------------------------------------------------------------
    # Parser : transforme les lignes en entrées structurées
    # ------------------------------------------------------------------

    def _parse(self, lines: list[str], lettre: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        # Flag: the previous line was a dot-only, so the next line is the definition
        expect_def = False

        for line in lines:
            # --- If previous line was a dot-only, this line IS the definition ---
            if expect_def and current is not None:
                expect_def = False
                # This line could still match a marker (edge case), but usually it's plain text
                dfn = line.strip()
                if dfn:
                    if current["definition_fr"]:
                        current["definition_fr"] += " " + dfn
                    else:
                        current["definition_fr"] = dfn
                continue

            # --- En-tête d'entrée ---
            m = _RE_HEADER.match(line)
            if m and self._is_header(line, m):
                if current and current.get("definition_fr"):
                    entries.append(current)
                current = self._new_entry(m, lettre)
                continue

            if current is None:
                continue

            # --- Dot seul (format B : définition sur la ligne suivante) ---
            if _RE_DOT_ONLY.match(line):
                expect_def = True
                continue

            # --- Définition (format A : ". texte" sur même ligne) ---
            m_def = _RE_DEF.match(line)
            if m_def:
                dfn = m_def.group(1).strip()
                if current["definition_fr"]:
                    current["definition_fr"] += " " + dfn
                else:
                    current["definition_fr"] = dfn
                continue

            # --- Expression ---
            m_exp = _RE_EXP.match(line)
            if m_exp:
                current["expressions"].append(m_exp.group(1).strip())
                continue

            # --- Proverbe ---
            m_pvb = _RE_PVB.match(line)
            if m_pvb:
                current["proverbes"].append(m_pvb.group(1).strip())
                continue

            # --- Variantes ---
            m_var = _RE_VAR.match(line)
            if m_var:
                current["variantes"] = [
                    v.strip() for v in m_var.group(1).split(",") if v.strip()
                ]
                continue

            # --- Synonymes ---
            m_syn = _RE_SYN.match(line)
            if m_syn:
                current["synonymes"] = [
                    s.strip() for s in m_syn.group(1).split(",") if s.strip()
                ]
                continue

            # --- Féminin ---
            m_fem = _RE_FEM.match(line)
            if m_fem:
                current["feminin"] = m_fem.group(1).strip()
                continue

            # --- Guadeloupéen ---
            m_gwd = _RE_GWD.match(line)
            if m_gwd:
                current["variantes"].append("gwd. " + m_gwd.group(1).strip())
                continue

            # --- Exemple (toute autre ligne non-vide) ---
            if current["definition_fr"]:
                current["exemples"].append(line)

        # Dernière entrée
        if current and current.get("definition_fr"):
            entries.append(current)

        return entries

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _new_entry(self, match: re.Match, lettre: str) -> dict[str, Any]:
        return {
            "mot_creole":    match.group(1),
            "numero":        int(match.group(2)) if match.group(2) else None,
            "definition_fr": "",
            "exemples":      [],
            "variantes":     [],
            "synonymes":     [],
            "expressions":   [],
            "proverbes":     [],
            "feminin":       None,
            "lettre":        lettre,
            "source":        "Dictionnaire du Créole Martiniquais, Raphaël Confiant",
            "source_url":    f"https://www.potomitan.info/dictionnaire/{lettre.lower()}.pdf",
        }

    def _is_header(self, line: str, match: re.Match) -> bool:
        """
        Un en-tête valide est :
        - Uniquement le mot (+ numéro optionnel) — pas de ponctuation
        - Longueur raisonnable (< 50 chars)
        - Ne commence pas par une majuscule suivie d'un texte long
          (ce serait un exemple ou une traduction)
        """
        if len(line) > 50:
            return False
        word = match.group(1)
        # Ignorer les lignes qui ressemblent à des noms propres en milieu de phrase
        if word[0].isupper() and len(word) > 15:
            return False
        return True


# ---------------------------------------------------------------------------
# Sauvegarde JSON
# ---------------------------------------------------------------------------

def save_entries(entries: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    log.info("Sauvegardé %d entrées → %s", len(entries), out_path)
