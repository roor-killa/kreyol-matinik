"""
Extraction linguistique depuis les conversation_logs.

La classe LinguisticExtractor analyse un batch de ConversationLog et produit
des dicts "candidats" prêts à être insérés dans moderation_candidates.

Aucun accès direct au modèle ORM depuis ce module : les logs sont passés comme
objets duck-typed (attributs id, session_id, user_id, user_message,
bot_response, user_correction) pour faciliter les tests sans base de données.
"""
import re
from collections import defaultdict
from typing import Any

from sqlalchemy import text

from .config import PipelineConfig
from .ngrams import score_ngrams, tokenize
from .phonetics import soundex_kreyol

# Tokeniseur brut : garde tous les mots > 1 char, sans supprimer les stop words.
# Utilisé pour la détection de nouveaux mots et de variantes (on veut voir
# les pronoms, articles, etc., contrairement à l'extraction n-grammes).
_WORD_RE = re.compile(r"[a-záàâäãéèêëíìîïóòôõöúùûüçñœæ'\-]+", re.IGNORECASE)


def _tokenize_all(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text) if len(t) > 1]


# ---------------------------------------------------------------------------
# Type alias (évite l'import ORM dans ce module)
# ---------------------------------------------------------------------------

# Un "log-like" est tout objet avec les attributs attendus.
# En production : instance de models.ConversationLog
# En test : simple dataclass ou objet Namespace

Candidate = dict[str, Any]


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class LinguisticExtractor:
    """Analyse un batch de logs et retourne des candidats linguistiques.

    Args:
        db_session: session SQLAlchemy (peut être None si known_words fourni)
        config: PipelineConfig
        known_words: ensemble de mots créoles déjà dans le dictionnaire.
                     Si fourni, court-circuite _load_known_words (utile pour
                     les tests sans base de données).
    """

    def __init__(
        self,
        db_session,
        config: PipelineConfig,
        known_words: set[str] | None = None,
    ):
        self.db = db_session
        self.config = config
        self.known_words: set[str] = set()
        self.phonetic_index: dict[str, list[str]] = {}  # soundex_code → [mot, …]

        if known_words is not None:
            self._set_known_words(known_words)
        else:
            self._load_known_words()

    # ------------------------------------------------------------------
    # Chargement du dictionnaire existant
    # ------------------------------------------------------------------

    def _load_known_words(self) -> None:
        """Charge tous les mots créoles existants depuis la base (SQL brut)."""
        rows = self.db.execute(text("SELECT mot_creole FROM mots")).fetchall()
        self._set_known_words({row[0] for row in rows})

    def _set_known_words(self, words: set[str]) -> None:
        """Initialise l'ensemble et l'index phonétique."""
        self.known_words = {w.lower() for w in words}
        self.phonetic_index = defaultdict(list)
        for w in self.known_words:
            code = soundex_kreyol(w)
            if code:
                self.phonetic_index[code].append(w)

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    def extract_batch(self, logs: list) -> list[Candidate]:
        """Traite un batch de logs et retourne tous les candidats détectés."""
        candidates: list[Candidate] = []
        candidates += self._extract_new_words(logs)
        candidates += self._extract_variants(logs)
        candidates += self._extract_patterns(logs)
        candidates += self._extract_expressions(logs)
        candidates += self._extract_corrections(logs)
        return candidates

    # ------------------------------------------------------------------
    # 1. Nouveaux mots absents du dictionnaire
    # ------------------------------------------------------------------

    def _extract_new_words(self, logs: list) -> list[Candidate]:
        """Mots présents dans les messages utilisateurs mais absents du dictionnaire.

        Un mot devient candidat si :
        - il est absent de known_words
        - il a été utilisé par >= config.min_speakers locuteurs distincts
        - sa fréquence totale >= config.min_frequency
        """
        # word → {log_id: ..., speakers: set, frequency: int, contexts: []}
        word_stats: dict[str, dict] = defaultdict(
            lambda: {"log_ids": [], "speakers": set(), "frequency": 0, "contexts": []}
        )

        for log in logs:
            tokens = _tokenize_all(log.user_message)
            speaker_key = str(log.user_id) if log.user_id else str(log.session_id)
            for token in tokens:
                if token in self.known_words:
                    continue
                stats = word_stats[token]
                stats["log_ids"].append(log.id)
                stats["speakers"].add(speaker_key)
                stats["frequency"] += 1
                if len(stats["contexts"]) < 3:  # garder max 3 exemples
                    stats["contexts"].append(log.user_message)

        candidates = []
        for word, stats in word_stats.items():
            if (
                len(stats["speakers"]) >= self.config.min_speakers
                and stats["frequency"] >= self.config.min_frequency
            ):
                candidates.append({
                    "candidate_type": "new_word",
                    "word": word,
                    "phonetic": soundex_kreyol(word),
                    "source_log_ids": list(dict.fromkeys(stats["log_ids"])),  # dédupliqué
                    "speaker_count": len(stats["speakers"]),
                    "frequency": stats["frequency"],
                    "context": stats["contexts"][0] if stats["contexts"] else None,
                    "examples": [{"kr": c} for c in stats["contexts"]],
                    "variants": [],
                })
        return candidates

    # ------------------------------------------------------------------
    # 2. Variantes orthographiques
    # ------------------------------------------------------------------

    def _extract_variants(self, logs: list) -> list[Candidate]:
        """Variantes orthographiques d'un mot connu via Soundex créole.

        Un mot inconnu est une variante si son code Soundex correspond à
        celui d'un mot déjà dans le dictionnaire.
        """
        variant_stats: dict[str, dict] = defaultdict(
            lambda: {"log_ids": [], "speakers": set(), "frequency": 0,
                     "known_match": None, "contexts": []}
        )

        for log in logs:
            tokens = _tokenize_all(log.user_message)
            speaker_key = str(log.user_id) if log.user_id else str(log.session_id)
            for token in tokens:
                if token in self.known_words:
                    continue
                code = soundex_kreyol(token)
                if not code or code not in self.phonetic_index:
                    continue
                stats = variant_stats[token]
                stats["log_ids"].append(log.id)
                stats["speakers"].add(speaker_key)
                stats["frequency"] += 1
                stats["known_match"] = self.phonetic_index[code][0]  # premier match
                if len(stats["contexts"]) < 3:
                    stats["contexts"].append(log.user_message)

        candidates = []
        for word, stats in variant_stats.items():
            if stats["frequency"] >= 1:  # seuil bas : toute occurrence est intéressante
                candidates.append({
                    "candidate_type": "spelling_variant",
                    "word": word,
                    "phonetic": soundex_kreyol(word),
                    "source_log_ids": list(dict.fromkeys(stats["log_ids"])),
                    "speaker_count": len(stats["speakers"]),
                    "frequency": stats["frequency"],
                    "context": stats["contexts"][0] if stats["contexts"] else None,
                    "examples": [{"kr": c} for c in stats["contexts"]],
                    "variants": [stats["known_match"]],
                })
        return candidates

    # ------------------------------------------------------------------
    # 3. Patterns grammaticaux
    # ------------------------------------------------------------------

    def _extract_patterns(self, logs: list) -> list[Candidate]:
        """Patterns grammaticaux récurrents (ka+V, té+V, ké+V, pa+V).

        Chaque match unique (pattern, token_suivant) devient un candidat
        s'il atteint le seuil de fréquence min_frequency.
        """
        compiled = [re.compile(p, re.IGNORECASE) for p in self.config.known_patterns]

        # (pattern_str, match_str) → stats
        pattern_stats: dict[tuple, dict] = defaultdict(
            lambda: {"log_ids": [], "speakers": set(), "frequency": 0, "contexts": []}
        )

        for log in logs:
            speaker_key = str(log.user_id) if log.user_id else str(log.session_id)
            for pattern, regex in zip(self.config.known_patterns, compiled):
                for match in regex.finditer(log.user_message):
                    key = (pattern, match.group(0).lower().strip())
                    stats = pattern_stats[key]
                    stats["log_ids"].append(log.id)
                    stats["speakers"].add(speaker_key)
                    stats["frequency"] += 1
                    if len(stats["contexts"]) < 3:
                        stats["contexts"].append(log.user_message)

        candidates = []
        for (pattern, match_str), stats in pattern_stats.items():
            if stats["frequency"] >= self.config.min_frequency:
                candidates.append({
                    "candidate_type": "grammar_pattern",
                    "word": match_str,
                    "source_log_ids": list(dict.fromkeys(stats["log_ids"])),
                    "speaker_count": len(stats["speakers"]),
                    "frequency": stats["frequency"],
                    "context": stats["contexts"][0] if stats["contexts"] else None,
                    "examples": [{"kr": c} for c in stats["contexts"]],
                    "variants": [],
                    "phonetic": None,
                })
        return candidates

    # ------------------------------------------------------------------
    # 4. Expressions figées (n-grammes à PMI élevé)
    # ------------------------------------------------------------------

    def _extract_expressions(self, logs: list) -> list[Candidate]:
        """Expressions figées / locutions via analyse n-grammes + PMI.

        Utilise score_ngrams() pour identifier les collocations fréquentes,
        puis filtre celles qui ne sont pas déjà dans la table expressions.
        (La vérification DB est optionnelle — skippée si db est None.)
        """
        texts = [log.user_message for log in logs]
        log_by_text: dict[str, Any] = {log.user_message: log for log in logs}

        scored = score_ngrams(
            texts,
            ngram_range=self.config.ngram_range,
            min_count=self.config.ngram_min_count,
        )

        # Charger les expressions connues si DB disponible
        known_expressions: set[str] = set()
        if self.db is not None:
            try:
                rows = self.db.execute(
                    text("SELECT texte_creole FROM expressions")
                ).fetchall()
                known_expressions = {row[0].lower() for row in rows}
            except Exception:
                pass

        candidates = []
        for ngram_str, freq, pmi_score in scored:
            if ngram_str.lower() in known_expressions:
                continue
            # Trouver un log exemple contenant cette expression
            example_log = next(
                (log for log in logs if ngram_str in log.user_message.lower()),
                None,
            )
            log_ids = [
                log.id for log in logs if ngram_str in log.user_message.lower()
            ]
            speakers = {
                str(log.user_id) if log.user_id else str(log.session_id)
                for log in logs
                if ngram_str in log.user_message.lower()
            }
            candidates.append({
                "candidate_type": "expression",
                "word": ngram_str,
                "phonetic": None,
                "source_log_ids": list(dict.fromkeys(log_ids)),
                "speaker_count": len(speakers),
                "frequency": freq,
                "context": example_log.user_message if example_log else None,
                "examples": [{"kr": ngram_str}],
                "variants": [],
                "definition_kr": None,
                "definition_fr": None,
            })
        return candidates

    # ------------------------------------------------------------------
    # 5. Corrections explicites de l'utilisateur
    # ------------------------------------------------------------------

    def _extract_corrections(self, logs: list) -> list[Candidate]:
        """Corrections explicites saisies via POST /chat/correct.

        Chaque log avec user_correction non vide devient directement un
        candidat de type 'correction' — sans seuil de fréquence.
        """
        candidates = []
        for log in logs:
            if not log.user_correction or not log.user_correction.strip():
                continue
            candidates.append({
                "candidate_type": "correction",
                "word": log.user_correction.strip(),
                "phonetic": soundex_kreyol(log.user_correction.strip()),
                "source_log_ids": [log.id],
                "speaker_count": 1,
                "frequency": 1,
                "context": log.user_message,
                "examples": [{"kr": log.user_correction, "original": log.bot_response}],
                "variants": [],
                "definition_kr": None,
                "definition_fr": None,
            })
        return candidates
