"""
Extraction de n-grammes et calcul PMI pour le pipeline linguistique.

Fonctions principales :
- tokenize(text)             → liste de tokens créoles nettoyés
- extract_ngrams(tokens, n)  → liste de tuples de n tokens
- build_counts(texts, range) → (unigrams Counter, ngrams Counter)
- pmi(ngram, ...)            → score PMI (log2)
- score_ngrams(texts, ...)   → liste de (ngram_str, freq, pmi) triée
"""
import math
import re
from collections import Counter
from typing import Iterator

# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

# Mots-outils créoles à exclure des n-grammes (stop words légers)
_STOP_WORDS: frozenset[str] = frozenset({
    # articles / déterminants
    "la", "a", "an", "dé", "sa",
    # pronoms
    "mwen", "moin", "ou", "aw", "li", "nou", "zot", "yo",
    # conjonctions / prépositions courtes
    "é", "ek", "pou", "an", "av", "si", "ni",
    # ponctuation résiduelle
    "-", "_",
})

_TOKEN_RE = re.compile(r"[a-záàâäãéèêëíìîïóòôõöúùûüçñœæ''\-]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Tokenise un texte créole en mots en minuscules.

    - Garde les lettres accentuées (fréquentes en créole martiniquais)
    - Supprime les tokens de longueur ≤ 1 et les stop words
    - N'applique pas de stemming (le créole n'a pas de modèle disponible)
    """
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOP_WORDS]


# ---------------------------------------------------------------------------
# Extraction de n-grammes
# ---------------------------------------------------------------------------

def extract_ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    """Retourne tous les n-grammes d'une liste de tokens.

    Args:
        tokens: liste de tokens (issu de tokenize())
        n: taille des n-grammes (2 = bigramme, 3 = trigramme, …)

    Returns:
        Liste de tuples de n tokens.
    """
    if n < 2 or len(tokens) < n:
        return []
    return [tuple(tokens[i: i + n]) for i in range(len(tokens) - n + 1)]


def _iter_ngrams_from_texts(
    texts: list[str], ngram_range: tuple[int, int]
) -> Iterator[tuple[str, ...]]:
    """Générateur interne : produit tous les n-grammes (toutes tailles) de tous les textes."""
    min_n, max_n = ngram_range
    for text in texts:
        tokens = tokenize(text)
        for n in range(min_n, max_n + 1):
            yield from extract_ngrams(tokens, n)


# ---------------------------------------------------------------------------
# Comptages
# ---------------------------------------------------------------------------

def build_counts(
    texts: list[str],
    ngram_range: tuple[int, int] = (2, 4),
) -> tuple[Counter, Counter]:
    """Construit les compteurs unigrammes et n-grammes à partir d'une liste de textes.

    Args:
        texts: liste de messages bruts
        ngram_range: (min_n, max_n) taille des n-grammes

    Returns:
        (unigram_counts, ngram_counts) — deux Counter
    """
    unigram_counts: Counter = Counter()
    ngram_counts: Counter = Counter()

    for text in texts:
        tokens = tokenize(text)
        unigram_counts.update(tokens)
        min_n, max_n = ngram_range
        for n in range(min_n, max_n + 1):
            ngram_counts.update(extract_ngrams(tokens, n))

    return unigram_counts, ngram_counts


# ---------------------------------------------------------------------------
# PMI — Pointwise Mutual Information
# ---------------------------------------------------------------------------

def pmi(
    ngram: tuple[str, ...],
    unigram_counts: Counter,
    ngram_counts: Counter,
    total_tokens: int,
    total_ngram_tokens: int | None = None,
) -> float:
    """Calcule le score PMI moyen d'un n-gramme (log2).

    Pour un bigramme (w1, w2) :
        PMI = log2( P(w1,w2) / (P(w1) * P(w2)) )
            = log2( count(w1,w2) * N / (count(w1) * count(w2)) )

    Pour n > 2 : moyenne des PMI de chaque paire consécutive.

    Args:
        ngram: tuple de tokens
        unigram_counts: Counter des tokens seuls
        ngram_counts: Counter des n-grammes
        total_tokens: nombre total de tokens (somme des unigrammes)
        total_ngram_tokens: nombre total d'occurrences de n-grammes de même
                            taille (facultatif, déduit de ngram_counts si omis)

    Returns:
        Score PMI moyen. Retourne -inf si un token est inconnu.
    """
    if total_tokens == 0:
        return float("-inf")

    n = len(ngram)
    if n < 2:
        return 0.0

    # Nombre total de bigrammes pour normaliser
    N = total_tokens

    scores: list[float] = []
    for i in range(n - 1):
        w1, w2 = ngram[i], ngram[i + 1]
        bigram = (w1, w2)

        count_w1 = unigram_counts.get(w1, 0)
        count_w2 = unigram_counts.get(w2, 0)
        count_bg = ngram_counts.get(bigram, 0)

        if count_w1 == 0 or count_w2 == 0 or count_bg == 0:
            return float("-inf")

        # PMI = log2( P(w1,w2) / P(w1)*P(w2) )
        #      = log2( (count_bg/N) / ((count_w1/N) * (count_w2/N)) )
        #      = log2( count_bg * N / (count_w1 * count_w2) )
        score = math.log2(count_bg * N / (count_w1 * count_w2))
        scores.append(score)

    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# Pipeline complet : filtrage par fréquence + PMI
# ---------------------------------------------------------------------------

def score_ngrams(
    texts: list[str],
    ngram_range: tuple[int, int] = (2, 4),
    min_count: int = 3,
    min_pmi: float = 0.0,
) -> list[tuple[str, int, float]]:
    """Extrait et score les n-grammes candidats à être des expressions.

    Pipeline :
        1. Compter tous les n-grammes
        2. Garder ceux dont la fréquence >= min_count
        3. Calculer le PMI et garder ceux dont PMI >= min_pmi
        4. Trier par PMI décroissant

    Args:
        texts: liste de messages bruts
        ngram_range: (min_n, max_n)
        min_count: fréquence minimale
        min_pmi: score PMI minimal (0.0 = association positive)

    Returns:
        Liste de (ngram_str, fréquence, pmi) triée par PMI décroissant.
        ngram_str : tokens joints par un espace.
    """
    unigram_counts, ngram_counts = build_counts(texts, ngram_range)
    total_tokens = sum(unigram_counts.values())

    results: list[tuple[str, int, float]] = []

    for ng, freq in ngram_counts.items():
        if freq < min_count:
            continue
        score = pmi(ng, unigram_counts, ngram_counts, total_tokens)
        if score < min_pmi or score == float("-inf"):
            continue
        results.append((" ".join(ng), freq, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results
