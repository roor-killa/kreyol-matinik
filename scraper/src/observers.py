"""Observateurs du pattern Observer — logs et statistiques de scraping."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ScraperObserver(ABC):
    """Interface abstraite pour les observateurs de scraping."""

    @abstractmethod
    def update(self, event: str, payload: dict[str, Any]) -> None:
        """Reçoit une notification d'événement.

        Args:
            event: Nom de l'événement ('fetch', 'parse', 'error', 'done').
            payload: Données associées à l'événement.
        """


class LogObserver(ScraperObserver):
    """Observateur qui journalise chaque événement via le module logging.

    Attributes:
        name: Identifiant de cet observateur dans les logs.
    """

    def __init__(self, name: str = "LogObserver") -> None:
        self.name = name

    def update(self, event: str, payload: dict[str, Any]) -> None:
        """Journalise l'événement reçu.

        Args:
            event: Nom de l'événement.
            payload: Données associées.
        """
        match event:
            case "fetch":
                logger.info("[%s] FETCH %s → %s", self.name, payload.get("url"), payload.get("status"))
            case "parse":
                logger.info("[%s] PARSE — %d item(s) extraits", self.name, payload.get("count", 0))
            case "error":
                logger.warning("[%s] ERREUR %s : %s", self.name, payload.get("url"), payload.get("error"))
            case "done":
                logger.info(
                    "[%s] TERMINÉ — %d item(s) total en %.1fs",
                    self.name,
                    payload.get("total", 0),
                    payload.get("duration", 0.0),
                )
            case _:
                logger.debug("[%s] EVENT %s : %s", self.name, event, payload)


class StatsObserver(ScraperObserver):
    """Observateur qui accumule des statistiques de progression.

    Attributes:
        fetches: Nombre de pages récupérées avec succès.
        errors: Nombre d'erreurs réseau ou HTTP.
        items_parsed: Nombre total d'items extraits.
        started_at: Horodatage du premier événement reçu.
    """

    def __init__(self) -> None:
        self.fetches: int = 0
        self.errors: int = 0
        self.items_parsed: int = 0
        self.started_at: datetime | None = None

    def update(self, event: str, payload: dict[str, Any]) -> None:
        """Met à jour les compteurs internes.

        Args:
            event: Nom de l'événement.
            payload: Données associées.
        """
        if self.started_at is None:
            self.started_at = datetime.now()

        match event:
            case "fetch":
                self.fetches += 1
            case "parse":
                self.items_parsed += payload.get("count", 0)
            case "error":
                self.errors += 1

    def summary(self) -> dict[str, Any]:
        """Retourne un résumé des statistiques collectées.

        Returns:
            Dictionnaire avec fetches, errors, items_parsed, duration_s.
        """
        duration = (
            (datetime.now() - self.started_at).total_seconds()
            if self.started_at
            else 0.0
        )
        return {
            "fetches": self.fetches,
            "errors": self.errors,
            "items_parsed": self.items_parsed,
            "duration_s": round(duration, 1),
        }

    def __repr__(self) -> str:
        s = self.summary()
        return (
            f"StatsObserver(fetches={s['fetches']}, errors={s['errors']}, "
            f"items={s['items_parsed']}, duration={s['duration_s']}s)"
        )
