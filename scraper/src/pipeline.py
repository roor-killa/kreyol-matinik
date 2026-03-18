"""DataPipeline — nettoyage, normalisation et import PostgreSQL."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Codes de langue supportés par langdetect pour le créole
_LANG_CREOLE_HINTS: set[str] = {"fr", "ht"}  # ht = haïtien, proxy pour le créole


class DataPipeline:
    """Nettoie, normalise et importe les données scrapées vers PostgreSQL.

    Attributes:
        db_url: URL de connexion PostgreSQL (format SQLAlchemy).
    """

    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = db_url

    # ------------------------------------------------------------------
    # Nettoyage
    # ------------------------------------------------------------------

    def clean(self, raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Nettoie et normalise une liste d'entrées brutes.

        Opérations appliquées :
        - Suppression des entrées sans texte créole
        - Normalisation des espaces et sauts de ligne
        - Déduplication sur (url)
        - Détection de langue si non renseignée

        Args:
            raw_data: Entrées brutes issues du scraper.

        Returns:
            Entrées nettoyées et filtrées.
        """
        seen_urls: set[str] = set()
        cleaned: list[dict[str, Any]] = []

        for entry in raw_data:
            url = entry.get("url", "")
            if url in seen_urls:
                logger.debug("Doublon ignoré : %s", url)
                continue
            seen_urls.add(url)

            entry = self._normalize_text_fields(entry)

            if not entry.get("texte_creole") and not entry.get("titre"):
                logger.debug("Entrée vide ignorée : %s", url)
                continue

            cleaned.append(entry)

        logger.info("Pipeline clean : %d → %d entrées", len(raw_data), len(cleaned))
        return cleaned

    def _normalize_text_fields(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Normalise tous les champs texte d'une entrée.

        Args:
            entry: Dictionnaire de l'entrée à normaliser.

        Returns:
            Entrée avec champs texte normalisés.
        """
        text_fields = ("titre", "texte_creole", "texte_fr")
        for field in text_fields:
            value = entry.get(field, "") or ""
            value = re.sub(r"\s+", " ", value).strip()
            value = value.replace("\u00a0", " ")  # espace insécable
            entry[field] = value
        return entry

    def detect_language(self, text: str) -> str:
        """Tente de détecter si un texte est en créole ou en français.

        Utilise langdetect avec des heuristiques supplémentaires pour
        distinguer le créole martiniquais (non supporté nativement).

        Args:
            text: Texte à analyser.

        Returns:
            'crm' (créole martiniquais), 'fr' (français) ou 'unknown'.
        """
        if not text or len(text) < 10:
            return "unknown"

        # Marqueurs lexicaux créole martiniquais fréquents
        creole_markers = [
            r"\bnou\b", r"\bman\b", r"\bkè\b", r"\bété\b", r"\bpou\b",
            r"\bté\b", r"\bay\b", r"\bka\b", r"\bla\b", r"\bsa\b",
            r"\bjouk\b", r"\bannou\b", r"\bfò\b", r"\bdéwò\b",
        ]
        creole_score = sum(
            1 for pattern in creole_markers
            if re.search(pattern, text, re.IGNORECASE)
        )

        if creole_score >= 3:
            return "crm"

        try:
            from langdetect import detect
            lang = detect(text)
            return "fr" if lang == "fr" else "unknown"
        except Exception:
            return "unknown"

    # ------------------------------------------------------------------
    # Import PostgreSQL
    # ------------------------------------------------------------------

    def import_to_db(self, processed_data: list[dict[str, Any]]) -> int:
        """Importe les entrées nettoyées dans PostgreSQL.

        Insère dans les tables sources, mots, traductions, medias et corpus
        selon le contenu de chaque entrée.

        Args:
            processed_data: Entrées issues de clean().

        Returns:
            Nombre d'entrées insérées avec succès.

        Raises:
            RuntimeError: Si db_url n'est pas configurée.
        """
        if not self.db_url:
            raise RuntimeError("db_url non configurée — initialisez DataPipeline(db_url=...)")

        import psycopg2
        from psycopg2.extras import execute_values

        inserted = 0
        conn = psycopg2.connect(self.db_url)

        try:
            with conn:
                with conn.cursor() as cur:
                    # S'assurer que chaque source référencée existe en base
                    self._ensure_sources(cur, processed_data)
                    # Insérer chaque entrée dans un savepoint indépendant
                    for entry in processed_data:
                        cur.execute("SAVEPOINT sp_entry")
                        try:
                            inserted += self._insert_entry(cur, entry)
                            cur.execute("RELEASE SAVEPOINT sp_entry")
                        except Exception as exc:
                            cur.execute("ROLLBACK TO SAVEPOINT sp_entry")
                            logger.error(
                                "Erreur insertion : %s — %s",
                                entry.get("url"), exc,
                            )
            logger.info("Import BDD : %d entrées insérées", inserted)
        finally:
            conn.close()

        return inserted

    def _ensure_sources(
        self, cur: Any, data: list[dict[str, Any]]
    ) -> None:
        """Insère dans la table sources les sources référencées si absentes.

        Args:
            cur: Curseur psycopg2 actif.
            data: Entrées à importer (chacune contient 'source' et 'source_id').
        """
        seen: set[str] = set()
        for entry in data:
            nom = entry.get("source", "")
            source_id = entry.get("source_id", 1)
            url_source = entry.get("url", "").split("/")[0:3]
            base_url = "/".join(url_source) if url_source else nom
            key = f"{nom}:{source_id}"
            if key in seen:
                continue
            seen.add(key)
            cur.execute(
                """
                INSERT INTO sources (id, nom, url, type, robots_ok)
                VALUES (%s, %s, %s, 'mixte', TRUE)
                ON CONFLICT (id) DO NOTHING
                """,
                (source_id, nom, base_url),
            )
            logger.debug("Source assurée : %s (id=%s)", nom, source_id)

    def _insert_entry(self, cur: Any, entry: dict[str, Any]) -> int:
        """Insère une entrée dans les tables appropriées.

        Args:
            cur: Curseur psycopg2 actif.
            entry: Entrée nettoyée à insérer.

        Returns:
            1 si insertion réussie, 0 sinon.
        """
        try:
            titre = entry.get("titre", "")
            texte_creole = entry.get("texte_creole", "")
            texte_fr = entry.get("texte_fr", "")
            # titre_fr = titre français (ex: contes bilingues Potomitan)
            titre_fr = entry.get("titre_fr", "")
            audio_url = entry.get("audio_url", "")
            source_id = entry.get("source_id", 1)

            # Insertion dans corpus (texte créole brut)
            if texte_creole:
                cur.execute(
                    """
                    INSERT INTO corpus (texte_creole, texte_fr, source_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (texte_creole, texte_fr or None, source_id),
                )

            # Insertion du mot dans le dictionnaire
            if titre:
                cur.execute(
                    """
                    INSERT INTO mots (mot_creole, source_id)
                    VALUES (%s, %s)
                    ON CONFLICT (mot_creole) DO NOTHING
                    RETURNING id
                    """,
                    (titre, source_id),
                )
                row = cur.fetchone()
                if row:
                    mot_id = row[0]
                else:
                    # Le mot existait déjà : récupérer son id
                    cur.execute(
                        "SELECT id FROM mots WHERE mot_creole = %s", (titre,)
                    )
                    existing = cur.fetchone()
                    mot_id = existing[0] if existing else None

                # Traduction FR → créole : texte_fr ou titre_fr si disponibles
                traduction_fr = texte_fr or titre_fr
                if mot_id and traduction_fr:
                    cur.execute(
                        """
                        INSERT INTO traductions
                            (mot_id, langue_source, langue_cible, texte_source, texte_cible, source_id)
                        VALUES (%s, 'fr', 'crm', %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (mot_id, traduction_fr, titre, source_id),
                    )

            # Insertion du média audio
            if audio_url:
                cur.execute(
                    """
                    INSERT INTO medias (url, type, titre, source_id)
                    VALUES (%s, 'audio', %s, %s)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    (audio_url, titre or None, source_id),
                )

            return 1

        except Exception as exc:
            logger.error("Erreur insertion : %s — %s", entry.get("url"), exc)
            return 0
