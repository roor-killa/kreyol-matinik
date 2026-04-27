"""
Soundex adapté au créole martiniquais (kréyòl matinitjé).

Particularités phonétiques prises en compte :
- Digrammes  : tch → T, ch → S, dj → J
- Nasales    : an → A, en → E, on → O, in → I
- Semi-voy.  : ou → W  (interchangeable avec "w")
- Consonnes  : mapping inspiré du Soundex anglais, ajusté pour le créole

Exemples :
    soundex_kreyol("mwen") == soundex_kreyol("moin")     # True
    soundex_kreyol("tjenbé") == soundex_kreyol("tchenbé") # True
"""
import re
import unicodedata


# ---------------------------------------------------------------------------
# Tables de remplacement
# ---------------------------------------------------------------------------

# Ordre important : les digrammes/trigrammes avant les caractères simples
_DIGRAMS: list[tuple[str, str]] = [
    ("tch", "T"),
    ("tj",  "T"),  # orthographe moderne créole pour le même phonème /tʃ/
    ("ch",  "S"),
    ("dj",  "J"),
    ("an",  "A"),
    ("en",  "E"),
    ("on",  "O"),
    ("in",  "I"),
    ("ou",  "W"),
]

# Mapping consonne → chiffre Soundex (adapté kréyol)
_CONSONANT_MAP: dict[str, str] = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
    "d": "3", "t": "3",
    "l": "4",
    "m": "5", "n": "5",
    "r": "6",
    # codes spéciaux pour les substitutions créoles
    "T": "3",  # tch
    "S": "2",  # ch
    "J": "2",  # dj
    # voyelles nasales et semi-voyelles → ignorées (traitées comme voyelles)
    "A": "0", "E": "0", "I": "0", "O": "0", "W": "0",
}

# Voyelles simples (supprimées en position interne)
_VOWELS = set("aeiouy")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _remove_accents(text: str) -> str:
    """Supprime les accents sauf é/è (pertinents en créole)."""
    result = []
    for ch in text:
        if ch in ("é", "è"):
            result.append(ch)
            continue
        nfkd = unicodedata.normalize("NFKD", ch)
        ascii_ch = nfkd.encode("ascii", "ignore").decode("ascii")
        result.append(ascii_ch if ascii_ch else ch)
    return "".join(result)


def _apply_digrams(word: str) -> str:
    """Remplace les digrammes/trigrammes créoles par leurs codes."""
    for pattern, code in _DIGRAMS:
        word = word.replace(pattern, code)
    return word


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def soundex_kreyol(word: str) -> str:
    """Retourne le code Soundex adapté au kréyòl matinitjé.

    Args:
        word: mot en créole martiniquais (casse libre, accents tolérés)

    Returns:
        Code de 4 caractères : lettre initiale + 3 chiffres (ex: "M500")
        Retourne "" si l'entrée est vide ou ne contient pas de lettres.

    Examples:
        >>> soundex_kreyol("mwen") == soundex_kreyol("moin")
        True
        >>> soundex_kreyol("tjenbé") == soundex_kreyol("tchenbé")
        True
    """
    if not word:
        return ""

    # 1. Normaliser : minuscules, supprimer accents (sauf é/è)
    word = _remove_accents(word.lower())

    # 2. Remplacer les digrammes créoles par leurs codes
    word = _apply_digrams(word)

    # 3. Garder uniquement les lettres et codes
    word = re.sub(r"[^a-zA-Z]", "", word)
    if not word:
        return ""

    # 4. Conserver la première lettre (avant encodage)
    first_letter = word[0].upper()

    # 5. Encoder le reste : mapper vers chiffres, supprimer voyelles internes
    #    et doublons consécutifs
    encoded = []
    prev_code = _CONSONANT_MAP.get(word[0], "0")  # éviter les doublons avec le 1er car.

    for ch in word[1:]:
        code = _CONSONANT_MAP.get(ch)
        if code is None:
            # lettre non mappée → traiter comme voyelle (séparateur de doublons)
            prev_code = "0"
            continue
        if code == "0":
            # voyelle (nasale ou semi-voyelle) → séparateur seulement
            prev_code = "0"
            continue
        if code != prev_code:
            encoded.append(code)
        prev_code = code

    # 6. Tronquer / compléter à 3 chiffres
    digits = "".join(encoded)[:3].ljust(3, "0")

    return first_letter + digits


def are_variants(word_a: str, word_b: str) -> bool:
    """Retourne True si deux mots sont des variantes phonétiques l'un de l'autre."""
    return soundex_kreyol(word_a) == soundex_kreyol(word_b)
