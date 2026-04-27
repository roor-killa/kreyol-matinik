"""
Tests pour pipeline/extractor.py — extraction linguistique.

Tous les tests sont indépendants de PostgreSQL :
- db_session = None  (known_words passé directement)
- Les logs sont des SimpleNamespace avec les attributs attendus.
"""
import uuid
from types import SimpleNamespace

import pytest

from pipeline.config import PipelineConfig
from pipeline.extractor import LinguisticExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log(
    user_message: str,
    bot_response: str = "réponse fèfèn",
    user_correction: str | None = None,
    user_id: int | None = None,
    session_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        session_id=session_id or uuid.uuid4(),
        user_id=user_id,
        user_message=user_message,
        bot_response=bot_response,
        user_correction=user_correction,
    )


def _make_extractor(
    known_words: set[str] | None = None,
    config: PipelineConfig | None = None,
) -> LinguisticExtractor:
    cfg = config or PipelineConfig(
        min_speakers=2,
        min_frequency=2,
        ngram_min_count=2,
    )
    return LinguisticExtractor(
        db_session=None,
        config=cfg,
        known_words=known_words or set(),
    )


# ---------------------------------------------------------------------------
# test_extract_new_words_basic
# ---------------------------------------------------------------------------

class TestExtractNewWords:
    def test_basic(self):
        """Un mot inconnu fréquent doit devenir candidat 'new_word'."""
        extractor = _make_extractor(
            known_words={"manjé", "ka"},
            config=PipelineConfig(min_speakers=2, min_frequency=2, ngram_min_count=99),
        )
        # "zanmi" est inconnu, utilisé par 2 locuteurs distincts, 2 fois
        sid_a, sid_b = uuid.uuid4(), uuid.uuid4()
        logs = [
            _make_log("zanmi ka manjé", session_id=sid_a),
            _make_log("zanmi vini", session_id=sid_b),
        ]
        candidates = extractor._extract_new_words(logs)
        words = [c["word"] for c in candidates]
        assert "zanmi" in words

    def test_known_word_excluded(self):
        """Un mot déjà dans le dictionnaire ne doit pas être candidat."""
        extractor = _make_extractor(
            known_words={"manjé"},
            config=PipelineConfig(min_speakers=1, min_frequency=1, ngram_min_count=99),
        )
        logs = [_make_log("manjé poul la")]
        candidates = extractor._extract_new_words(logs)
        words = [c["word"] for c in candidates]
        assert "manjé" not in words

    def test_candidate_type_is_new_word(self):
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=2, min_frequency=2, ngram_min_count=99),
        )
        sid_a, sid_b = uuid.uuid4(), uuid.uuid4()
        logs = [
            _make_log("zanmi vini", session_id=sid_a),
            _make_log("zanmi alé", session_id=sid_b),
        ]
        candidates = extractor._extract_new_words(logs)
        for c in candidates:
            assert c["candidate_type"] == "new_word"

    def test_source_log_ids_populated(self):
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=2, min_frequency=2, ngram_min_count=99),
        )
        sid_a, sid_b = uuid.uuid4(), uuid.uuid4()
        log1 = _make_log("zanmi vini", session_id=sid_a)
        log2 = _make_log("zanmi alé", session_id=sid_b)
        candidates = extractor._extract_new_words([log1, log2])
        zanmi = next(c for c in candidates if c["word"] == "zanmi")
        assert log1.id in zanmi["source_log_ids"]
        assert log2.id in zanmi["source_log_ids"]


# ---------------------------------------------------------------------------
# test_extract_new_words_min_speakers
# ---------------------------------------------------------------------------

class TestExtractNewWordsMinSpeakers:
    def test_below_min_speakers_excluded(self):
        """Un mot utilisé par un seul locuteur (seuil=2) ne doit pas être candidat."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=2, min_frequency=2, ngram_min_count=99),
        )
        shared_session = uuid.uuid4()
        logs = [
            _make_log("rarmo vini", session_id=shared_session),
            _make_log("rarmo alé", session_id=shared_session),  # même session
        ]
        candidates = extractor._extract_new_words(logs)
        words = [c["word"] for c in candidates]
        assert "rarmo" not in words, "Un seul locuteur ne doit pas suffire"

    def test_meets_min_speakers(self):
        """Exactement min_speakers locuteurs → candidat accepté."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=2, min_frequency=2, ngram_min_count=99),
        )
        sid_a, sid_b = uuid.uuid4(), uuid.uuid4()
        logs = [
            _make_log("rarmo vini", session_id=sid_a),
            _make_log("rarmo alé", session_id=sid_b),
        ]
        candidates = extractor._extract_new_words(logs)
        words = [c["word"] for c in candidates]
        assert "rarmo" in words

    def test_user_id_counts_as_speaker(self):
        """user_id doit être utilisé comme clé locuteur si non None."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=2, min_frequency=2, ngram_min_count=99),
        )
        logs = [
            _make_log("rarmo vini", user_id=1),
            _make_log("rarmo alé",  user_id=2),
        ]
        candidates = extractor._extract_new_words(logs)
        words = [c["word"] for c in candidates]
        assert "rarmo" in words


# ---------------------------------------------------------------------------
# test_extract_variants_phonetic_match
# ---------------------------------------------------------------------------

class TestExtractVariants:
    def test_phonetic_match_detected(self):
        """Un mot inconnu phonétiquement proche d'un mot connu → spelling_variant."""
        # "tjenbé" (orthographe moderne) est dans le dictionnaire
        # "tchenbé" (orthographe ancienne) devrait être détecté comme variante
        extractor = _make_extractor(known_words={"tjenbé"})
        logs = [_make_log("tchenbé fò")]
        candidates = extractor._extract_variants(logs)
        assert len(candidates) == 1
        c = candidates[0]
        assert c["candidate_type"] == "spelling_variant"
        assert c["word"] == "tchenbé"
        assert "tjenbé" in c["variants"]

    def test_no_variant_for_known_word(self):
        """Un mot déjà connu ne doit pas générer de candidat variant."""
        extractor = _make_extractor(known_words={"tjenbé", "tchenbé"})
        logs = [_make_log("tjenbé fò")]
        candidates = extractor._extract_variants(logs)
        assert all(c["word"] != "tjenbé" for c in candidates)

    def test_no_variant_when_phonetic_index_empty(self):
        """Sans mots connus, aucune variante ne peut être détectée."""
        extractor = _make_extractor(known_words=set())
        logs = [_make_log("tchenbé fò")]
        assert extractor._extract_variants(logs) == []

    def test_mwen_moin_variant(self):
        """'moin' (variante de 'mwen') doit être détecté."""
        extractor = _make_extractor(known_words={"mwen"})
        logs = [_make_log("moin ka alé")]
        candidates = extractor._extract_variants(logs)
        words = [c["word"] for c in candidates]
        assert "moin" in words


# ---------------------------------------------------------------------------
# test_extract_patterns_ka_verb
# ---------------------------------------------------------------------------

class TestExtractPatterns:
    def test_ka_verb_pattern(self):
        """Le pattern 'ka + verbe' doit être détecté quand il est assez fréquent."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=1, min_frequency=3, ngram_min_count=99),
        )
        # "ka manjé" répété 3 fois (seuil = 3)
        logs = [_make_log("mwen ka manjé") for _ in range(3)]
        candidates = extractor._extract_patterns(logs)
        assert len(candidates) > 0
        types = {c["candidate_type"] for c in candidates}
        assert "grammar_pattern" in types

    def test_pattern_below_frequency_excluded(self):
        """Un pattern qui n'apparaît qu'une fois (seuil=3) doit être exclu."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=1, min_frequency=3, ngram_min_count=99),
        )
        logs = [_make_log("mwen ka manjé")]  # 1 seul log
        candidates = extractor._extract_patterns(logs)
        # Chaque match n'apparaît qu'une fois → tous sous le seuil
        assert candidates == []

    def test_té_pattern(self):
        """Le pattern 'té + verbe' (passé) doit être détecté quand répété."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=1, min_frequency=3, ngram_min_count=99),
        )
        # Même pattern "té alé" répété 3 fois
        logs = [_make_log("li té alé") for _ in range(3)]
        candidates = extractor._extract_patterns(logs)
        words = [c["word"] for c in candidates]
        assert any("té" in w for w in words)

    def test_pattern_frequency_counted(self):
        """La fréquence du candidat pattern doit refléter le nb d'occurrences."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=1, min_frequency=3, ngram_min_count=99),
        )
        # "ka manjé" répété 4 fois
        logs = [_make_log("mwen ka manjé") for _ in range(4)]
        candidates = extractor._extract_patterns(logs)
        ka_manje = [c for c in candidates if "ka manjé" in c["word"]]
        assert len(ka_manje) > 0
        assert ka_manje[0]["frequency"] == 4


# ---------------------------------------------------------------------------
# test_extract_expressions_ngram
# ---------------------------------------------------------------------------

class TestExtractExpressions:
    def test_frequent_ngram_becomes_expression(self):
        """Un bigramme fréquent à PMI élevé doit être candidat 'expression'."""
        extractor = _make_extractor(
            config=PipelineConfig(
                min_speakers=1, min_frequency=1,
                ngram_min_count=3, ngram_range=(2, 2),
            ),
        )
        # "ka manjé" répété dans plusieurs messages
        logs = [
            _make_log("mwen ka manjé poul"),
            _make_log("li ka manjé diri"),
            _make_log("nou ka manjé ansanm"),
        ]
        candidates = extractor._extract_expressions(logs)
        assert len(candidates) > 0
        types = {c["candidate_type"] for c in candidates}
        assert "expression" in types

    def test_expression_word_is_ngram_string(self):
        """Le champ 'word' d'un candidat expression doit être la chaîne du n-gramme."""
        extractor = _make_extractor(
            config=PipelineConfig(
                min_speakers=1, min_frequency=1,
                ngram_min_count=3, ngram_range=(2, 2),
            ),
        )
        logs = [
            _make_log("ka manjé poul"),
            _make_log("ka manjé diri"),
            _make_log("ka manjé ansanm"),
        ]
        candidates = extractor._extract_expressions(logs)
        words = [c["word"] for c in candidates]
        assert any(len(w.split()) >= 2 for w in words)

    def test_no_expressions_below_min_count(self):
        """Aucun n-gramme sous le seuil ngram_min_count ne doit passer."""
        extractor = _make_extractor(
            config=PipelineConfig(
                min_speakers=1, min_frequency=1,
                ngram_min_count=10,   # seuil très haut
                ngram_range=(2, 2),
            ),
        )
        logs = [_make_log("ka manjé poul"), _make_log("ka palé vit")]
        candidates = extractor._extract_expressions(logs)
        assert candidates == []


# ---------------------------------------------------------------------------
# test_extract_corrections
# ---------------------------------------------------------------------------

class TestExtractCorrections:
    def test_correction_creates_candidate(self):
        """Un log avec user_correction doit générer un candidat 'correction'."""
        extractor = _make_extractor()
        log = _make_log(
            "ki sa yé sa",
            bot_response="Je ne sais pas",
            user_correction="sa vle di : c'est quoi ça",
        )
        candidates = extractor._extract_corrections([log])
        assert len(candidates) == 1
        c = candidates[0]
        assert c["candidate_type"] == "correction"
        assert c["word"] == "sa vle di : c'est quoi ça"
        assert c["source_log_ids"] == [log.id]
        assert c["context"] == log.user_message

    def test_no_correction_field_skipped(self):
        """Un log sans correction ne doit pas générer de candidat."""
        extractor = _make_extractor()
        log = _make_log("ka manjé poul", user_correction=None)
        assert extractor._extract_corrections([log]) == []

    def test_empty_correction_skipped(self):
        """Une correction vide ou blanche doit être ignorée."""
        extractor = _make_extractor()
        log = _make_log("ka manjé", user_correction="   ")
        candidates = extractor._extract_corrections([log])
        assert candidates == []

    def test_multiple_corrections(self):
        """Plusieurs logs corrigés → autant de candidats."""
        extractor = _make_extractor()
        logs = [
            _make_log("msg1", user_correction="correction1"),
            _make_log("msg2", user_correction=None),
            _make_log("msg3", user_correction="correction3"),
        ]
        candidates = extractor._extract_corrections(logs)
        assert len(candidates) == 2

    def test_correction_includes_original_response(self):
        """Le champ examples doit inclure la réponse originale de Fèfèn."""
        extractor = _make_extractor()
        log = _make_log("ki moun ou yé", bot_response="Mwen Fèfèn", user_correction="mwen se fèfèn")
        candidates = extractor._extract_corrections([log])
        example = candidates[0]["examples"][0]
        assert example["original"] == "Mwen Fèfèn"


# ---------------------------------------------------------------------------
# test_extract_batch (intégration légère)
# ---------------------------------------------------------------------------

class TestExtractBatch:
    def test_batch_returns_list(self):
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=1, min_frequency=1, ngram_min_count=99),
        )
        logs = [_make_log("zanmi ka manjé", user_correction="zanmi = ami")]
        result = extractor.extract_batch(logs)
        assert isinstance(result, list)

    def test_all_candidate_types_have_required_fields(self):
        """Chaque candidat doit avoir les champs minimum requis."""
        extractor = _make_extractor(
            config=PipelineConfig(min_speakers=1, min_frequency=1, ngram_min_count=99),
        )
        logs = [_make_log("zanmi ka alé", user_correction="zanmi = ami")]
        candidates = extractor.extract_batch(logs)
        required = {"candidate_type", "word", "source_log_ids", "speaker_count", "frequency"}
        for c in candidates:
            missing = required - c.keys()
            assert not missing, f"Champs manquants dans {c['candidate_type']}: {missing}"
