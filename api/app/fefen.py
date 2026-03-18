"""
fefen.py — Moteur Fèfèn intégré à l'API FastAPI
=================================================
Deux modes :
  - Fefen    : retrieval TF-IDF pur (retourne l'entrée la plus proche)
  - FefenRAG : TF-IDF (contexte) + LLM HuggingFace (génération)
               Activé si HF_TOKEN est défini dans l'environnement.

Variables d'env :
  FEFEN_DATASET_DIR — chemin du dataset JSONL (défaut : /app/dataset/data)
  HF_TOKEN          — token HuggingFace (active le mode RAG)
  FEFEN_MODEL       — modèle HF à utiliser (défaut : mistralai/Mistral-7B-Instruct-v0.3)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATASET_DIR  = Path(os.getenv("FEFEN_DATASET_DIR", "/app/dataset/data"))
HF_TOKEN     = os.getenv("HF_TOKEN", "")
FEFEN_MODEL  = os.getenv("FEFEN_MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")

SYSTEM_PROMPT = """\
Tu es Fèfèn, un assistant chaleureux spécialisé dans la langue et la culture créole martiniquaise.
Tu réponds en mêlant créole martiniquais et français, de façon concise et naturelle (3-5 phrases max).
Utilise les informations du corpus ci-dessous pour répondre. Si le corpus ne contient pas de réponse \
pertinente, réponds quand même de façon générale en restant dans le thème de la langue créole.

Corpus de référence :
{context}
"""

# ---------------------------------------------------------------------------
# Phrases de réponse en créole
# ---------------------------------------------------------------------------

INTRO_LEXIQUE = ["Sa vle di :", "Définisyon :", "An mo-a di :"]
INTRO_CONTE   = ["An istwa :", "Men an bout istwa :"]
INTRO_POEME   = ["An pwézi :", "Men an bout pwézi :"]
ACCROCHES     = ["An mò pou ou :", "Man trouvé sa :", "Gadé sa man jwenn :"]
FALLBACKS     = [
    "Man pa konprann byen. Eséyé di mwen an lòt jan.",
    "Ou pé répété ? Man pa jwenn anyen pou sa.",
    "Man pa ka réponn sa-a. Mandé mwen anlè kréyol !",
]


# ---------------------------------------------------------------------------
# Classe Fèfèn
# ---------------------------------------------------------------------------

class Fefen:
    """Chatbot retrieval-based TF-IDF pour le créole martiniquais."""

    def __init__(self, min_score: float = 0.05) -> None:
        self.min_score   = min_score
        self._corpus:     list[dict[str, Any]] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix:     Any = None

    # ------------------------------------------------------------------
    # Construction de l'index
    # ------------------------------------------------------------------

    def build(self) -> "Fefen":
        """Charge le dataset local et construit l'index TF-IDF."""
        self._load_data()
        if not self._corpus:
            log.warning("Corpus vide — Fèfèn en mode fallback uniquement")
            return self

        texts = [self._entry_text(e) for e in self._corpus]
        self._vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_features=20_000,
        )
        self._matrix = self._vectorizer.fit_transform(texts)
        log.info("Fèfèn : index TF-IDF (%d entrées, %d features)",
                 *self._matrix.shape)
        return self

    def _load_data(self) -> None:
        seen: set[str] = set()
        # Ordre de priorité : dictionnaire Confiant > lexique > corpus
        for config in ("dictionnaire_confiant", "lexique", "corpus"):
            path = DATASET_DIR / config / "train.jsonl"
            if not path.exists():
                log.warning("Dataset introuvable : %s", path)
                continue
            with path.open(encoding="utf-8") as f:
                for line in f:
                    e = json.loads(line)
                    uid = e.get("id", "")
                    if uid not in seen:
                        seen.add(uid)
                        self._corpus.append(e)
        log.info("Fèfèn : %d entrées chargées depuis %s", len(self._corpus), DATASET_DIR)

    # ------------------------------------------------------------------
    # Récupération des entrées les plus proches (pour le RAG)
    # ------------------------------------------------------------------

    def retrieve(self, message: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Retourne les top_k entrées du corpus les plus proches du message."""
        if self._vectorizer is None or not self._corpus:
            return []
        vec  = self._vectorizer.transform([message.lower()])
        sims = cosine_similarity(vec, self._matrix).flatten()
        idxs = sims.argsort()[::-1][:top_k]
        return [self._corpus[i] for i in idxs if sims[i] >= self.min_score]

    # ------------------------------------------------------------------
    # Réponse TF-IDF pure (fallback sans LLM)
    # ------------------------------------------------------------------

    def reply(self, message: str) -> str:
        """Retourne une réponse en créole pour le message donné."""
        results = self.retrieve(message, top_k=1)
        if not results:
            return random.choice(FALLBACKS)
        return self._format(results[0])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _entry_text(self, e: dict) -> str:
        parts = [
            e.get("texte", ""), e.get("mot", ""),
            e.get("definition", ""), e.get("titre", ""),
            " ".join(e.get("hashtags", [])),
        ]
        return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).lower()

    def _format(self, e: dict) -> str:
        cat    = e.get("categorie", "")
        source = e.get("source", "")

        if source == "pawolotek.com" or e.get("mot"):
            mot = e.get("mot", "")
            dfn = e.get("definition", "")
            txt = f"**{mot}** — {dfn}" if dfn else f"**{mot}**"
            return f"{random.choice(INTRO_LEXIQUE)}\n\n{txt}"

        texte   = e.get("texte", "")
        extrait = texte[:300].rsplit(" ", 1)[0] + "…" if len(texte) > 300 else texte

        if cat == "poeme":
            titre = e.get("titre", "")
            return f"{random.choice(INTRO_POEME)}\n\n*{titre}*\n\n{extrait}"

        if cat == "conte":
            titre    = e.get("titre", "")
            titre_fr = e.get("titre_fr", "")
            header   = f"*{titre}*" + (f" ({titre_fr})" if titre_fr else "")
            return f"{random.choice(INTRO_CONTE)}\n\n{header}\n\n{extrait}"

        return f"{random.choice(ACCROCHES)}\n\n{extrait}"


# ---------------------------------------------------------------------------
# FefenRAG — TF-IDF + LLM HuggingFace Inference API
# ---------------------------------------------------------------------------

class FefenRAG(Fefen):
    """
    Extension RAG de Fèfèn.
    Utilise TF-IDF pour récupérer du contexte, puis appelle un LLM
    HuggingFace pour générer une réponse naturelle en créole/français.
    """

    def __init__(self, hf_token: str, model: str = FEFEN_MODEL, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        from huggingface_hub import InferenceClient  # type: ignore
        self._client = InferenceClient(model=model, token=hf_token)
        self._model  = model
        log.info("FefenRAG : modèle %s", model)

    def reply(self, message: str) -> str:
        """Génère une réponse via RAG : contexte TF-IDF + LLM HuggingFace."""
        entries = self.retrieve(message, top_k=3)
        context = self._build_context(entries)
        system  = SYSTEM_PROMPT.format(context=context)

        # Tentative 1 : chat_completion (TGI chat — modèles récents)
        try:
            response = self._client.chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": message},
                ],
                max_tokens=300,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            log.warning("FefenRAG chat_completion échoué (%s) — tentative text_generation", exc)

        # Tentative 2 : text_generation (format prompt Mistral/Mixtral)
        try:
            prompt = f"<s>[INST] {system}\n\nQuestion : {message} [/INST]"
            result = self._client.text_generation(
                prompt,
                max_new_tokens=300,
                temperature=0.7,
                do_sample=True,
            )
            return result.strip()
        except Exception as exc:
            log.warning("FefenRAG text_generation échoué (%s) — tentative flan-t5", exc)

        # Tentative 3 : text2text_generation avec flan-t5-large (toujours gratuit)
        try:
            from huggingface_hub import InferenceClient  # type: ignore
            flan = InferenceClient(model="google/flan-t5-large", token=self._client.token)
            prompt = (
                f"Tu es Fèfèn, assistant créole martiniquais. "
                f"Contexte : {context[:400]} "
                f"Question : {message} "
                f"Réponse courte en créole et français :"
            )
            result = flan.text2text_generation(prompt, parameters={"max_length": 200})
            text = result[0]["generated_text"] if isinstance(result, list) else str(result)
            return text.strip() or super().reply(message)
        except Exception as exc:
            log.warning("FefenRAG flan-t5 échoué (%s) — fallback TF-IDF", exc)
            return super().reply(message)

    def _build_context(self, entries: list[dict]) -> str:
        """Formate les entrées récupérées en bloc de contexte pour le prompt."""
        if not entries:
            return "(aucun contexte trouvé dans le corpus)"

        lines: list[str] = []
        for e in entries:
            if e.get("mot"):
                lines.append(f"Mot : {e['mot']} — {e.get('definition', '')}")
            elif e.get("titre"):
                texte = e.get("texte", "")[:200]
                lines.append(f"Titre : {e['titre']}\nExtrait : {texte}…")
            else:
                lines.append(e.get("texte", "")[:200] + "…")

        return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Factory : choisit FefenRAG si HF_TOKEN présent, sinon Fefen
# ---------------------------------------------------------------------------

def build_fefen() -> Fefen:
    """Construit et retourne le moteur Fèfèn adapté à la configuration."""
    base = Fefen().build()

    if HF_TOKEN:
        try:
            rag = FefenRAG(hf_token=HF_TOKEN, model=FEFEN_MODEL)
            rag._corpus     = base._corpus
            rag._vectorizer = base._vectorizer
            rag._matrix     = base._matrix
            log.info("Fèfèn démarré en mode RAG (modèle : %s)", FEFEN_MODEL)
            return rag
        except Exception as exc:
            log.warning("FefenRAG indisponible (%s) — mode TF-IDF", exc)

    log.info("Fèfèn démarré en mode TF-IDF (pas de HF_TOKEN)")
    return base
