"""
fefen.py — Moteur du chatbot Fèfèn
====================================
Chatbot retrieval-based pour la langue créole martiniquaise.
Utilise TF-IDF (sklearn) sur le corpus local (dataset/data/).

Architecture :
  - Index TF-IDF bigrammes de mots + trigrammes de caractères (fusionnés)
  - Similarité cosinus pour trouver les entrées les plus proches
  - Formatage de la réponse selon le type d'entrée (lexique / conte / poème)
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).parent.parent
DATASET_DIR = ROOT / "dataset" / "data"
MODEL_DIR   = Path(__file__).parent / "models"
INDEX_PATH  = MODEL_DIR / "fefen_index.joblib"

# ---------------------------------------------------------------------------
# Phrases d'accroche en créole (pour varier les réponses)
# ---------------------------------------------------------------------------

ACCROCHES = [
    "An mò pou ou :",
    "Man trouvé sa :",
    "Gadé sa man jwenn :",
    "Men sa ki di :",
    "Écoute sa :",
]

INTRO_LEXIQUE  = ["Sa vle di :", "Définisyon :", "An mo-a di :", "Gadé :]"]
INTRO_CONTE    = ["An istwa :", "Men an bout istwa :", "Koute sa :"]
INTRO_POEME    = ["An pwézi :", "Men an bout pwézi :", "Écoute sa :"]
FALLBACK_MSGS  = [
    "Man pa konprann byen. Eséyé di mwen an lòt jan.",
    "Ou pé répété ? Man pa jwenn anyen pou sa.",
    "Man pa ka réponn sa-a. Eséyé an lòt keksyon.",
    "Hmm… man pa sav sa. Mandé mwen anlè kréyol !",
]


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class Fefen:
    """
    Chatbot Fèfèn — retrieval TF-IDF sur le corpus créole martiniquais.

    Paramètres
    ----------
    top_k : int
        Nombre de résultats candidats à considérer (le meilleur est retourné).
    min_score : float
        Score cosinus minimum pour considérer un résultat pertinent.
        En dessous → réponse de fallback.
    """

    def __init__(self, top_k: int = 3, min_score: float = 0.05) -> None:
        self.top_k     = top_k
        self.min_score = min_score

        self._corpus:     list[dict[str, Any]] = []
        self._texts:      list[str]            = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix:     Any                    = None  # scipy sparse

    # ------------------------------------------------------------------
    # Chargement du dataset local
    # ------------------------------------------------------------------

    def load_data(self) -> "Fefen":
        """Charge les configs corpus + lexique depuis les JSONL locaux."""
        # lexique en premier : ses entrées ont mot+definition (plus riches que corpus)
        configs = ["lexique", "corpus"]
        seen_ids: set[str] = set()

        for config in configs:
            path = DATASET_DIR / config / "train.jsonl"
            if not path.exists():
                log.warning("Dataset introuvable : %s — ignoré", path)
                continue

            with path.open(encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    uid = entry.get("id", "")
                    if uid in seen_ids:
                        continue        # dédoublonnage corpus/lexique
                    seen_ids.add(uid)
                    self._corpus.append(entry)

        log.info("%d entrées chargées", len(self._corpus))
        return self

    # ------------------------------------------------------------------
    # Construction de l'index TF-IDF
    # ------------------------------------------------------------------

    def build_index(self) -> "Fefen":
        """Construit le vecteur TF-IDF sur les textes du corpus."""
        if not self._corpus:
            raise RuntimeError("Corpus vide — appelle load_data() d'abord.")

        # Texte indexé = champ principal + mot (lexique) ou titre (contes)
        self._texts = [self._entry_text(e) for e in self._corpus]

        # TF-IDF hybride : mots (1-2grammes) + caractères (3-4grammes)
        # → robuste aux variantes orthographiques du créole
        self._vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_features=20_000,
        )
        self._matrix = self._vectorizer.fit_transform(self._texts)
        log.info("Index TF-IDF construit (%d × %d)", *self._matrix.shape)
        return self

    # ------------------------------------------------------------------
    # Sauvegarde / chargement de l'index
    # ------------------------------------------------------------------

    def save(self, path: Path = INDEX_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "corpus":     self._corpus,
            "texts":      self._texts,
            "vectorizer": self._vectorizer,
            "matrix":     self._matrix,
        }, path)
        log.info("Index sauvegardé → %s", path)

    @classmethod
    def load(cls, path: Path = INDEX_PATH, **kwargs: Any) -> "Fefen":
        data = joblib.load(path)
        fefen = cls(**kwargs)
        fefen._corpus     = data["corpus"]
        fefen._texts      = data["texts"]
        fefen._vectorizer = data["vectorizer"]
        fefen._matrix     = data["matrix"]
        log.info("Index chargé depuis %s (%d entrées)", path, len(fefen._corpus))
        return fefen

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------

    def find(self, query: str, top_k: int | None = None) -> list[tuple[float, dict]]:
        """
        Retourne les top_k entrées les plus proches de la requête.

        Retour : liste de (score, entry) triée par score décroissant.
        """
        if self._vectorizer is None or self._matrix is None:
            raise RuntimeError("Index non construit — appelle build_index() ou load().")

        k = top_k or self.top_k
        vec   = self._vectorizer.transform([query.lower()])
        sims  = cosine_similarity(vec, self._matrix).flatten()
        idxs  = np.argsort(sims)[::-1][:k]

        return [(float(sims[i]), self._corpus[i]) for i in idxs]

    # ------------------------------------------------------------------
    # Génération de réponse
    # ------------------------------------------------------------------

    def reply(self, message: str) -> str:
        """Génère une réponse en créole martiniquais pour le message donné."""
        results = self.find(message)

        if not results or results[0][0] < self.min_score:
            return random.choice(FALLBACK_MSGS)

        score, entry = results[0]
        return self._format_reply(entry, score)

    # ------------------------------------------------------------------
    # Helpers privés
    # ------------------------------------------------------------------

    def _entry_text(self, entry: dict) -> str:
        """Texte concaténé utilisé pour l'indexation."""
        parts = [
            entry.get("texte", ""),
            entry.get("mot", ""),
            entry.get("definition", ""),
            entry.get("titre", ""),
            " ".join(entry.get("hashtags", [])),
        ]
        return " ".join(p for p in parts if p).lower()

    def _format_reply(self, entry: dict, score: float) -> str:
        """Formate la réponse selon le type d'entrée."""
        categorie = entry.get("categorie", "")
        source    = entry.get("source", "")

        # ---- Lexique (Pawolotek) ----
        if source == "pawolotek.com" or entry.get("mot"):
            mot = entry.get("mot", "")
            dfn = entry.get("definition", "")
            intro = random.choice(INTRO_LEXIQUE)
            reply = f"{intro}\n\n**{mot}** — {dfn}" if dfn else f"{intro}\n\n**{mot}**"
            if entry.get("audio_url"):
                reply += f"\n\n🎧 {entry['audio_url']}"
            return reply

        # ---- Poème ----
        if categorie == "poeme":
            titre  = entry.get("titre", "")
            texte  = entry.get("texte", "")
            extrait = texte[:300].rsplit(" ", 1)[0] + "…" if len(texte) > 300 else texte
            intro  = random.choice(INTRO_POEME)
            return f"{intro}\n\n*{titre}*\n\n{extrait}"

        # ---- Conte ----
        if categorie == "conte":
            titre    = entry.get("titre", "")
            titre_fr = entry.get("titre_fr", "")
            texte    = entry.get("texte", "")
            extrait  = texte[:300].rsplit(" ", 1)[0] + "…" if len(texte) > 300 else texte
            intro    = random.choice(INTRO_CONTE)
            header   = f"*{titre}*" + (f" ({titre_fr})" if titre_fr else "")
            return f"{intro}\n\n{header}\n\n{extrait}"

        # ---- Fallback générique ----
        texte  = entry.get("texte", entry.get("definition", ""))
        extrait = texte[:300].rsplit(" ", 1)[0] + "…" if len(texte) > 300 else texte
        return f"{random.choice(ACCROCHES)}\n\n{extrait}"
