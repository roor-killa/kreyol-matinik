"""
Worker du pipeline d'extraction linguistique — Phase 8.

Usage :
    python -m pipeline.worker            # boucle toutes les 6h (défaut)
    python -m pipeline.worker --once     # un seul passage et exit
    python -m pipeline.worker --interval 3600  # boucle toutes les heures

Le worker :
1. Récupère les conversation_logs non traités (batch_size)
2. Les passe à LinguisticExtractor → liste de candidats
3. Upsert les candidats dans moderation_candidates
4. Marque les logs comme traités
"""
import argparse
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import PipelineConfig, config as default_config
from .extractor import LinguisticExtractor

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pipeline] %(levelname)s %(message)s",
)


# ---------------------------------------------------------------------------
# Helpers SQL
# ---------------------------------------------------------------------------

def _uuid_array(ids: list) -> str:
    """Formate une liste d'UUIDs en littéral tableau PostgreSQL.

    Ex : [uuid1, uuid2] → '{uuid1,uuid2}'
    Utilisé comme paramètre lié : :ids::UUID[] dans les requêtes text().
    """
    return "{" + ",".join(str(i) for i in ids) + "}"


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class PipelineWorker:
    """Traite les conversation_logs non traités et génère des moderation_candidates.

    Args:
        db_session: session SQLAlchemy active
        config: PipelineConfig (defaults à l'instance partagée)
    """

    def __init__(self, db_session: Session, config: PipelineConfig = default_config):
        self.db = db_session
        self.config = config
        self.extractor = LinguisticExtractor(db_session, config)

    # ------------------------------------------------------------------
    # Récupération des logs non traités
    # ------------------------------------------------------------------

    def _fetch_unprocessed(self) -> list:
        """Retourne un batch de logs non traités sous forme de SimpleNamespace."""
        rows = self.db.execute(
            text("""
                SELECT id, session_id, user_id, user_message,
                       bot_response, user_correction
                FROM conversation_logs
                WHERE NOT is_processed
                ORDER BY created_at
                LIMIT :batch_size
            """),
            {"batch_size": self.config.batch_size},
        ).fetchall()

        return [
            SimpleNamespace(
                id=row[0],
                session_id=row[1],
                user_id=row[2],
                user_message=row[3],
                bot_response=row[4],
                user_correction=row[5],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Upsert des candidats
    # ------------------------------------------------------------------

    def _upsert_candidates(self, candidates: list) -> None:
        """Insère ou met à jour les candidats dans moderation_candidates.

        Règle de déduplication : même (candidate_type, word) avec status='pending'
        → incrémenter frequency + speaker_count + fusionner source_log_ids.
        Sinon : INSERT.
        """
        for cand in candidates:
            word = cand.get("word") or ""
            new_ids = cand.get("source_log_ids", [])

            existing = self.db.execute(
                text("""
                    SELECT id, frequency, speaker_count, source_log_ids
                    FROM moderation_candidates
                    WHERE candidate_type = :ctype
                      AND lower(word) = lower(:word)
                      AND status = 'pending'
                    LIMIT 1
                """),
                {"ctype": cand["candidate_type"], "word": word},
            ).fetchone()

            if existing:
                # Fusionner les log_ids (dédoublonnage stable)
                existing_ids = [str(i) for i in (existing[3] or [])]
                merged = list(dict.fromkeys(existing_ids + [str(i) for i in new_ids]))

                self.db.execute(
                    text("""
                        UPDATE moderation_candidates
                        SET frequency     = frequency + :freq,
                            speaker_count = GREATEST(speaker_count, :speakers),
                            source_log_ids = CAST(:log_ids AS UUID[]),
                            updated_at    = NOW()
                        WHERE id = :id
                    """),
                    {
                        "freq":     cand.get("frequency", 1),
                        "speakers": cand.get("speaker_count", 1),
                        "log_ids":  _uuid_array(merged),
                        "id":       existing[0],
                    },
                )
                logger.debug("Candidat mis à jour : %s '%s'", cand["candidate_type"], word)

            else:
                self.db.execute(
                    text("""
                        INSERT INTO moderation_candidates
                            (candidate_type, status, word, phonetic, context,
                             examples, variants, source_log_ids,
                             speaker_count, frequency)
                        VALUES
                            (:ctype, 'pending', :word, :phonetic, :context,
                             CAST(:examples AS jsonb), CAST(:variants AS jsonb), CAST(:log_ids AS UUID[]),
                             :speakers, :frequency)
                    """),
                    {
                        "ctype":     cand["candidate_type"],
                        "word":      word or None,
                        "phonetic":  cand.get("phonetic"),
                        "context":   cand.get("context"),
                        "examples":  json.dumps(cand.get("examples", []), ensure_ascii=False),
                        "variants":  json.dumps(cand.get("variants", []), ensure_ascii=False),
                        "log_ids":   _uuid_array(new_ids),
                        "speakers":  cand.get("speaker_count", 1),
                        "frequency": cand.get("frequency", 1),
                    },
                )
                logger.debug("Candidat inséré : %s '%s'", cand["candidate_type"], word)

        self.db.commit()

    # ------------------------------------------------------------------
    # Marquage des logs comme traités
    # ------------------------------------------------------------------

    def _mark_processed(self, logs: list) -> None:
        """Marque les logs traités (is_processed=TRUE, processed_at=NOW())."""
        if not logs:
            return
        self.db.execute(
            text("""
                UPDATE conversation_logs
                SET is_processed = TRUE,
                    processed_at = NOW()
                WHERE id = ANY(CAST(:ids AS UUID[]))
            """),
            {"ids": _uuid_array([log.id for log in logs])},
        )
        self.db.commit()

    # ------------------------------------------------------------------
    # Points d'entrée publics
    # ------------------------------------------------------------------

    async def run_once(self) -> int:
        """Traite un batch de logs. Retourne le nombre de candidats générés."""
        logs = self._fetch_unprocessed()
        if not logs:
            logger.info("Aucun log non traité.")
            return 0

        logger.info("%d logs récupérés.", len(logs))
        candidates = self.extractor.extract_batch(logs)
        logger.info("%d candidats extraits.", len(candidates))

        self._upsert_candidates(candidates)
        self._mark_processed(logs)

        return len(candidates)

    async def run_loop(self, interval_seconds: int = 21600) -> None:
        """Boucle infinie : traite, attend interval_seconds, recommence."""
        logger.info("Boucle démarrée (intervalle : %ds).", interval_seconds)
        while True:
            count = await self.run_once()
            print(
                f"[pipeline] {count} candidats extraits "
                f"à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await asyncio.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# Construction de la session DB depuis les variables d'environnement
# ---------------------------------------------------------------------------

def _build_session() -> Session:
    """Construit une session SQLAlchemy depuis les variables d'environnement."""
    user     = os.getenv("POSTGRES_USER",     "creole")
    password = os.getenv("POSTGRES_PASSWORD", "changeme")
    host     = os.getenv("POSTGRES_HOST",     "db")
    port     = os.getenv("POSTGRES_PORT",     "5432")
    db_name  = os.getenv("POSTGRES_DB",       "langmatinitje")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
    engine = create_engine(url, pool_pre_ping=True)
    Session_ = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session_()


# ---------------------------------------------------------------------------
# Point d'entrée CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline d'extraction linguistique — Lang Matinitjé"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Traiter un seul batch puis quitter",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=21600,
        help="Intervalle en secondes entre deux runs (défaut : 21600 = 6h)",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    pipeline_config = PipelineConfig()
    db = _build_session()

    try:
        worker = PipelineWorker(db, pipeline_config)
        if args.once:
            count = await worker.run_once()
            print(f"[pipeline] Terminé — {count} candidats générés.")
        else:
            await worker.run_loop(interval_seconds=args.interval)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(_main())
