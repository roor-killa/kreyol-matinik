"""
Tests pour pipeline/phonetics.py — Soundex kréyòl matinitjé.
"""
import pytest
from pipeline.phonetics import soundex_kreyol, are_variants


# ---------------------------------------------------------------------------
# test_soundex_mwen_moin
# "mwen" et "moin" sont deux formes du pronom "je/moi" en créole :
# variante phonétique pure (w ↔ oi/in)
# ---------------------------------------------------------------------------

def test_soundex_mwen_moin():
    assert soundex_kreyol("mwen") == soundex_kreyol("moin"), (
        f"mwen={soundex_kreyol('mwen')} moin={soundex_kreyol('moin')}"
    )


# ---------------------------------------------------------------------------
# test_soundex_tjenbé_tchenbé
# "tjenbé" et "tchenbé" (tenir / tenir bon) : tch vs tj → même phonème /tʃ/
# ---------------------------------------------------------------------------

def test_soundex_tjenbé_tchenbé():
    assert soundex_kreyol("tjenbé") == soundex_kreyol("tchenbé"), (
        f"tjenbé={soundex_kreyol('tjenbé')} tchenbé={soundex_kreyol('tchenbé')}"
    )


# ---------------------------------------------------------------------------
# test_soundex_distinct_words
# Des mots phonétiquement différents ne doivent PAS partager le même code.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("word_a,word_b", [
    ("mwen", "fanm"),    # "je" vs "femme"
    ("ka",   "la"),      # marqueur progressif vs article
    ("manjé", "bwè"),    # "manger" vs "boire"
    ("bon",  "mal"),     # "bon" vs "mauvais"
])
def test_soundex_distinct_words(word_a, word_b):
    assert soundex_kreyol(word_a) != soundex_kreyol(word_b), (
        f"Collision inattendue : {word_a} == {word_b} "
        f"({soundex_kreyol(word_a)})"
    )


# ---------------------------------------------------------------------------
# test_soundex_nasals
# Les nasales an/en/on/in sont des phonèmes distincts en créole.
# Deux mots qui ne diffèrent que par leur nasale ne doivent pas coïncider.
# ---------------------------------------------------------------------------

def test_soundex_nasals_are_separators():
    """La nasale remet à zéro le 'previous code', permettant à la même
    consonne d'être encodée à nouveau après elle.

    "kankann" (commérages) : K-[an]-K-[an]-N → code K250 (K + 2 + 5)
    "kann" (canne à sucre)  : K-[an]-N        → code K500 (K + 5)
    La consonne K du milieu de "kankann" apparaît grâce au séparateur nasale.
    """
    code_kankann = soundex_kreyol("kankann")
    code_kann = soundex_kreyol("kann")
    assert code_kankann != code_kann, (
        f"kankann={code_kankann} kann={code_kann}"
    )


def test_soundex_nasals_variant_same_word():
    """Deux variantes orthographiques par gémination donnent le même code.

    "bèl" et "bèll" (beau/belle) : seule la consonne finale est doublée.
    Le Soundex déduplique les consonnes consécutives identiques → même code.
    """
    assert soundex_kreyol("bèl") == soundex_kreyol("bèll"), (
        f"bèl={soundex_kreyol('bèl')} bèll={soundex_kreyol('bèll')}"
    )


# ---------------------------------------------------------------------------
# Tests de la fonction are_variants
# ---------------------------------------------------------------------------

def test_are_variants_true():
    assert are_variants("mwen", "moin") is True


def test_are_variants_false():
    assert are_variants("mwen", "fanm") is False


# ---------------------------------------------------------------------------
# Tests de robustesse (edge cases)
# ---------------------------------------------------------------------------

def test_soundex_empty_string():
    assert soundex_kreyol("") == ""


def test_soundex_single_letter():
    code = soundex_kreyol("a")
    assert len(code) == 4
    assert code[0] == "A"
    assert code[1:] == "000"


def test_soundex_returns_4_chars():
    for word in ["ka", "mwen", "manjé", "tchenbé", "kréyòl"]:
        code = soundex_kreyol(word)
        assert len(code) == 4, f"Longueur incorrecte pour '{word}' : {code!r}"


def test_soundex_case_insensitive():
    assert soundex_kreyol("Mwen") == soundex_kreyol("mwen")
    assert soundex_kreyol("MANJÉ") == soundex_kreyol("manjé")
