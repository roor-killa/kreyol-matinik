"""Tests unitaires pour BaseScraper, observers et pipeline."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from src.base_scraper import BaseScraper
from src.observers import LogObserver, StatsObserver
from src.pipeline import DataPipeline


# ---------------------------------------------------------------------------
# Fixture : implémentation minimale de BaseScraper pour les tests
# ---------------------------------------------------------------------------

class DummyScraper(BaseScraper):
    """Scraper minimal pour tester la classe abstraite."""

    def scrape(self, max_pages: int = 0) -> list[dict]:
        return self.data

    def parse(self, soup: BeautifulSoup) -> list[dict]:
        return [{"titre": soup.title.string if soup.title else ""}]

    def to_document(self, item: dict) -> dict:
        return {
            "source":   "kreyol",
            "doc_type": "mot",
            "title":    item.get("titre", ""),
            "content":  item.get("titre", ""),
        }


@pytest.fixture()
def scraper() -> DummyScraper:
    return DummyScraper("https://example.com", delay=0)


# ---------------------------------------------------------------------------
# Tests BaseScraper
# ---------------------------------------------------------------------------

class TestBaseScraper:
    def test_init(self, scraper: DummyScraper) -> None:
        assert scraper.base_url == "https://example.com"
        assert scraper.delay == 0
        assert scraper.data == []

    def test_trailing_slash_stripped(self) -> None:
        s = DummyScraper("https://example.com/", delay=0)
        assert not s.base_url.endswith("/")

    def test_fetch_page_success(self, scraper: DummyScraper) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html><title>Test</title></html>"
        mock_resp.raise_for_status = MagicMock()

        with patch("src.base_scraper.requests.get", return_value=mock_resp):
            soup = scraper.fetch_page("https://example.com/page")

        assert soup is not None
        assert soup.title.string == "Test"

    def test_fetch_page_http_error(self, scraper: DummyScraper) -> None:
        import requests

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_resp
        )

        with patch("src.base_scraper.requests.get", return_value=mock_resp):
            result = scraper.fetch_page("https://example.com/404")

        assert result is None

    def test_fetch_page_network_error(self, scraper: DummyScraper) -> None:
        import requests

        with patch(
            "src.base_scraper.requests.get",
            side_effect=requests.exceptions.ConnectionError("timeout"),
        ):
            result = scraper.fetch_page("https://example.com")

        assert result is None

    def test_save_to_json(self, scraper: DummyScraper) -> None:
        scraper.data = [{"mot": "annou", "traduction": "allons"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.json"
            scraper.save_to_json(path)
            data = json.loads(path.read_text(encoding="utf-8"))
        assert data == scraper.data

    def test_save_to_csv(self, scraper: DummyScraper) -> None:
        scraper.data = [{"mot": "annou", "traduction": "allons"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "out.csv"
            scraper.save_to_csv(path)
            assert path.exists()
            assert path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Tests Observer Pattern
# ---------------------------------------------------------------------------

class TestObservers:
    def test_log_observer_attach(self, scraper: DummyScraper) -> None:
        obs = LogObserver("test")
        scraper.attach(obs)
        assert obs in scraper._observers

    def test_log_observer_detach(self, scraper: DummyScraper) -> None:
        obs = LogObserver()
        scraper.attach(obs)
        scraper.detach(obs)
        assert obs not in scraper._observers

    def test_stats_observer_counts(self, scraper: DummyScraper) -> None:
        stats = StatsObserver()
        scraper.attach(stats)

        scraper._notify("fetch", {"url": "https://x.com", "status": 200})
        scraper._notify("fetch", {"url": "https://x.com/2", "status": 200})
        scraper._notify("parse", {"count": 5})
        scraper._notify("error", {"url": "https://x.com/err", "error": "404"})

        summary = stats.summary()
        assert summary["fetches"] == 2
        assert summary["items_parsed"] == 5
        assert summary["errors"] == 1

    def test_stats_summary_has_duration(self) -> None:
        stats = StatsObserver()
        stats.update("fetch", {"url": "x", "status": 200})
        summary = stats.summary()
        assert "duration_s" in summary
        assert summary["duration_s"] >= 0


# ---------------------------------------------------------------------------
# Tests DataPipeline
# ---------------------------------------------------------------------------

class TestDataPipeline:
    @pytest.fixture()
    def pipeline(self) -> DataPipeline:
        return DataPipeline()

    def test_clean_removes_empty_entries(self, pipeline: DataPipeline) -> None:
        raw = [
            {"url": "https://a.com/1", "titre": "", "texte_creole": "", "texte_fr": ""},
            {"url": "https://a.com/2", "titre": "annou", "texte_creole": "ann alé", "texte_fr": "allons"},
        ]
        cleaned = pipeline.clean(raw)
        assert len(cleaned) == 1
        assert cleaned[0]["titre"] == "annou"

    def test_clean_deduplication(self, pipeline: DataPipeline) -> None:
        raw = [
            {"url": "https://a.com/1", "titre": "annou", "texte_creole": "ann alé", "texte_fr": ""},
            {"url": "https://a.com/1", "titre": "annou", "texte_creole": "ann alé", "texte_fr": ""},
        ]
        cleaned = pipeline.clean(raw)
        assert len(cleaned) == 1

    def test_clean_normalizes_whitespace(self, pipeline: DataPipeline) -> None:
        raw = [{"url": "u", "titre": "  an  nou  ", "texte_creole": "ann\t\talé", "texte_fr": ""}]
        cleaned = pipeline.clean(raw)
        assert cleaned[0]["titre"] == "an nou"
        assert cleaned[0]["texte_creole"] == "ann alé"

    def test_detect_language_creole(self, pipeline: DataPipeline) -> None:
        text = "nou ka alé la man pou sa té jouk fò nou"
        assert pipeline.detect_language(text) == "crm"

    def test_detect_language_short_text(self, pipeline: DataPipeline) -> None:
        assert pipeline.detect_language("hi") == "unknown"

    def test_detect_language_empty(self, pipeline: DataPipeline) -> None:
        assert pipeline.detect_language("") == "unknown"

    def test_import_requires_db_url(self, pipeline: DataPipeline) -> None:
        with pytest.raises(RuntimeError, match="db_url non configurée"):
            pipeline.import_to_db([{"titre": "test"}])
