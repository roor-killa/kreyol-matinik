"""
Tests pour pipeline/ngrams.py — extraction n-grammes et PMI.
"""
import math
from collections import Counter

import pytest
from pipeline.ngrams import (
    build_counts,
    extract_ngrams,
    pmi,
    score_ngrams,
    tokenize,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Corpus minimal simulant des messages de locuteurs créoles
_CORPUS = [
    "ka manjé poul la",
    "mwen ka manjé",
    "li ka manjé diri",
    "ka manjé poul la menm",
    "nou ka manjé ansanm",
    "sa ka manjé là a",
    "aw ka manjé tou",
    "yo ka manjé poul",
    "bèl fanm ka manjé",
    "ka manjé poul la toujou",
]


# ---------------------------------------------------------------------------
# test_bigram_extraction
# ---------------------------------------------------------------------------

class TestBigramExtraction:
    def test_basic_bigrams(self):
        tokens = ["ka", "manjé", "poul"]
        bigrams = extract_ngrams(tokens, 2)
        assert ("ka", "manjé") in bigrams
        assert ("manjé", "poul") in bigrams
        assert len(bigrams) == 2

    def test_trigrams(self):
        tokens = ["ka", "manjé", "poul", "la"]
        trigrams = extract_ngrams(tokens, 3)
        assert ("ka", "manjé", "poul") in trigrams
        assert ("manjé", "poul", "la") in trigrams
        assert len(trigrams) == 2

    def test_empty_tokens(self):
        assert extract_ngrams([], 2) == []

    def test_not_enough_tokens(self):
        assert extract_ngrams(["ka"], 2) == []
        assert extract_ngrams(["ka", "manjé"], 3) == []

    def test_n_equals_len(self):
        tokens = ["ka", "manjé"]
        result = extract_ngrams(tokens, 2)
        assert result == [("ka", "manjé")]

    def test_tokenize_removes_stopwords(self):
        # "la", "ou", "mwen" sont des stop words
        tokens = tokenize("ou ka manjé la")
        assert "ou" not in tokens
        assert "la" not in tokens
        assert "ka" in tokens
        assert "manjé" in tokens

    def test_tokenize_lowercases(self):
        tokens = tokenize("Ka Manjé POUL")
        assert tokens == ["ka", "manjé", "poul"]

    def test_tokenize_filters_short_tokens(self):
        tokens = tokenize("a b ka")
        # "a" et "b" ont longueur 1 → filtrés
        assert "a" not in tokens
        assert "b" not in tokens


# ---------------------------------------------------------------------------
# test_trigram_filtering
# ---------------------------------------------------------------------------

class TestTrigramFiltering:
    def test_frequency_filter(self):
        """score_ngrams doit exclure les n-grammes sous le seuil min_count."""
        results = score_ngrams(_CORPUS, ngram_range=(2, 2), min_count=3)
        ngram_strings = [r[0] for r in results]
        # "ka manjé" apparaît dans tous les messages → doit passer
        assert "ka manjé" in ngram_strings

    def test_rare_ngrams_excluded(self):
        """Un n-gramme qui n'apparaît qu'une fois doit être exclu."""
        results = score_ngrams(_CORPUS, ngram_range=(2, 2), min_count=3)
        frequencies = {r[0]: r[1] for r in results}
        for ngram_str, freq in frequencies.items():
            assert freq >= 3, f"'{ngram_str}' a fréquence {freq} < 3"

    def test_build_counts_unigrams(self):
        texts = ["ka manjé poul", "ka manjé diri"]
        unigrams, ngrams = build_counts(texts, ngram_range=(2, 2))
        assert unigrams["ka"] == 2
        assert unigrams["manjé"] == 2
        assert unigrams["poul"] == 1
        assert unigrams["diri"] == 1

    def test_build_counts_bigrams(self):
        texts = ["ka manjé poul", "ka manjé diri"]
        _, ngrams = build_counts(texts, ngram_range=(2, 2))
        assert ngrams[("ka", "manjé")] == 2
        assert ngrams[("manjé", "poul")] == 1
        assert ngrams[("manjé", "diri")] == 1

    def test_result_sorted_by_pmi(self):
        """Les résultats doivent être triés par PMI décroissant."""
        results = score_ngrams(_CORPUS, ngram_range=(2, 2), min_count=2)
        pmi_scores = [r[2] for r in results]
        assert pmi_scores == sorted(pmi_scores, reverse=True)

    def test_ngram_range_respected(self):
        """Seuls des bigrammes doivent être retournés quand range=(2,2)."""
        results = score_ngrams(_CORPUS, ngram_range=(2, 2), min_count=2)
        for ngram_str, _, _ in results:
            assert len(ngram_str.split()) == 2, f"'{ngram_str}' n'est pas un bigramme"


# ---------------------------------------------------------------------------
# test_pmi_calculation
# ---------------------------------------------------------------------------

class TestPmiCalculation:
    def _make_counts(self):
        """Corpus contrôlé pour des calculs PMI vérifiables manuellement."""
        # 10 tokens : "ka" x5, "manjé" x5, bigramme ("ka","manjé") x4
        unigrams = Counter({"ka": 5, "manjé": 5, "diri": 1})
        ngrams = Counter({("ka", "manjé"): 4, ("manjé", "diri"): 1})
        return unigrams, ngrams

    def test_pmi_positive_for_collocations(self):
        """Un bigramme fréquent comparé à ses composantes doit avoir PMI > 0."""
        unigrams, ngrams = self._make_counts()
        total = sum(unigrams.values())  # 11
        score = pmi(("ka", "manjé"), unigrams, ngrams, total)
        assert score > 0, f"PMI attendu > 0, obtenu {score}"

    def test_pmi_formula(self):
        """Vérifie la formule : PMI = log2(count_bg * N / (count_w1 * count_w2))."""
        unigrams, ngrams = self._make_counts()
        total = sum(unigrams.values())  # 11
        score = pmi(("ka", "manjé"), unigrams, ngrams, total)
        expected = math.log2(4 * 11 / (5 * 5))
        assert abs(score - expected) < 1e-9, f"attendu {expected}, obtenu {score}"

    def test_pmi_unknown_token_returns_neginf(self):
        unigrams, ngrams = self._make_counts()
        total = sum(unigrams.values())
        score = pmi(("ka", "xxxxxx"), unigrams, ngrams, total)
        assert score == float("-inf")

    def test_pmi_empty_corpus(self):
        score = pmi(("ka", "manjé"), Counter(), Counter(), 0)
        assert score == float("-inf")

    def test_pmi_trigram_is_average_of_bigram_pmis(self):
        """PMI d'un trigramme = moyenne des PMI des bigrammes consécutifs."""
        unigrams = Counter({"ka": 4, "manjé": 4, "poul": 4})
        ngrams = Counter({
            ("ka", "manjé"): 3,
            ("manjé", "poul"): 3,
            ("ka", "manjé", "poul"): 3,
        })
        total = sum(unigrams.values())  # 12
        score_tri = pmi(("ka", "manjé", "poul"), unigrams, ngrams, total)
        score_bg1 = pmi(("ka", "manjé"), unigrams, ngrams, total)
        score_bg2 = pmi(("manjé", "poul"), unigrams, ngrams, total)
        expected = (score_bg1 + score_bg2) / 2
        assert abs(score_tri - expected) < 1e-9

    def test_score_ngrams_returns_tuple_structure(self):
        """Chaque entrée doit être (str, int, float)."""
        results = score_ngrams(_CORPUS, ngram_range=(2, 2), min_count=2)
        assert len(results) > 0
        for ngram_str, freq, score in results:
            assert isinstance(ngram_str, str)
            assert isinstance(freq, int)
            assert isinstance(score, float)
