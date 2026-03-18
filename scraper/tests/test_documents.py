"""Tests unitaires pour to_document() et DocumentLoader.

Ces tests ne nécessitent PAS de base de données.
Ils vérifient que chaque scraper produit des documents
conformes au schéma attendu par la table `documents`.

Lancer :
    cd kreyol-matinik/scraper
    python -m pytest tests/test_documents.py -v
"""

import json
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from src.db_loader import DocumentLoader, _validate_and_prepare


# =============================================================================
# Données factices représentatives de chaque scraper
# =============================================================================

BIZOUK_ITEM: dict[str, Any] = {
    "titre":        "Vélo électrique Decathlon",
    "description":  "Vélo électrique très bon état, peu utilisé.",
    "prix":         "450 €",
    "categorie":    "Sport & Loisirs",
    "localisation": "Fort-de-France",
    "date":         "2026-02-20",
    "url":          "https://www.bizouk.com/annonces/velo-42",
}

KIPRIX_ITEM: dict[str, Any] = {
    "nom":           "Lait entier 1L Lactel",
    "prix":          "1.89 €",
    "magasin":       "Leader Price Martinique",
    "disponibilite": "En stock",
    "categorie":     "Épicerie",
    "url":           "https://www.kiprix.com/produits/lait-lactel-1L",
}

MADIANA_ITEM: dict[str, Any] = {
    "titre":      "Vaiana 2",
    "description":"La suite des aventures de Vaiana et Maui.",
    "genre":      "Animation",
    "seances":    "14h00, 17h30, 20h00",
    "prix_place": "10.50 €",
    "images":     "https://madiana.com/img/vaiana2.jpg",
    "url":        "https://www.madiana.com/films/vaiana-2",
}

RCI_ITEM: dict[str, Any] = {
    "titre":     "Grève aux transports : perturbations en Martinique",
    "resume":    "Les chauffeurs de bus ont entamé un mouvement de grève.",
    "categorie": "Société",
    "date":      "2026-03-01",
    "url":       "https://www.rci.fm/actualites/greve-transports-2026",
}

KREYOL_ITEM: dict[str, Any] = {
    "mot":           "annou",
    "definition":    "Ekspresyon pou ankourajé kèk moun pou fè kichòy ansanm.",
    "traduction_fr": "allons",
    "categorie_gram":"vèb",
    "exemple":       "Annou alé laplaj !",
    "phonetique":    "annu",
    "url":           "https://pawolotek.com/mo/annou",
}


# =============================================================================
# Helpers de validation réutilisables
# =============================================================================

REQUIRED_FIELDS = ("source", "doc_type", "title", "content")
VALID_SOURCES   = {"bizouk", "kiprix", "madiana", "rci", "kreyol"}
VALID_DOC_TYPES = {"annonce", "produit", "film", "actualite", "mot"}


def assert_valid_document(doc: dict[str, Any]) -> None:
    """Vérifie qu'un document respecte le schéma commun."""
    for field in REQUIRED_FIELDS:
        assert field in doc, f"Champ obligatoire manquant : '{field}'"
        assert doc[field], f"Champ obligatoire vide : '{field}'"

    assert doc["source"] in VALID_SOURCES, \
        f"source invalide : {doc['source']!r}"
    assert doc["doc_type"] in VALID_DOC_TYPES, \
        f"doc_type invalide : {doc['doc_type']!r}"

    # Les champs optionnels, s'ils sont présents, doivent avoir le bon type
    if doc.get("metadata") is not None:
        assert isinstance(doc["metadata"], dict), \
            "metadata doit être un dict (pas une str)"
    if doc.get("url") is not None:
        assert isinstance(doc["url"], str), "url doit être une str"


# =============================================================================
# Tests BizoukScraper.to_document()
# =============================================================================

class TestBizoukToDocument:
    @pytest.fixture()
    def scraper(self):
        from src.scrapers.bizouk_scraper import BizoukScraper
        return BizoukScraper(delay=0)

    def test_schema_valide(self, scraper):
        doc = scraper.to_document(BIZOUK_ITEM)
        assert_valid_document(doc)

    def test_source_et_doc_type(self, scraper):
        doc = scraper.to_document(BIZOUK_ITEM)
        assert doc["source"] == "bizouk"
        assert doc["doc_type"] == "annonce"

    def test_title_est_le_titre(self, scraper):
        doc = scraper.to_document(BIZOUK_ITEM)
        assert doc["title"] == BIZOUK_ITEM["titre"]

    def test_content_contient_la_description(self, scraper):
        doc = scraper.to_document(BIZOUK_ITEM)
        assert BIZOUK_ITEM["description"] in doc["content"]

    def test_metadata_contient_prix_et_localisation(self, scraper):
        doc = scraper.to_document(BIZOUK_ITEM)
        assert doc["metadata"]["prix"] == BIZOUK_ITEM["prix"]
        assert doc["metadata"]["localisation"] == BIZOUK_ITEM["localisation"]

    def test_url_transmise(self, scraper):
        doc = scraper.to_document(BIZOUK_ITEM)
        assert doc["url"] == BIZOUK_ITEM["url"]

    def test_item_vide_ne_crash_pas(self, scraper):
        """Un item avec seulement un titre ne doit pas lever d'exception."""
        doc = scraper.to_document({"titre": "Annonce test"})
        assert_valid_document(doc)


# =============================================================================
# Tests KiprixScraper.to_document()
# =============================================================================

class TestKiprixToDocument:
    @pytest.fixture()
    def scraper(self):
        from src.scrapers.kiprix_scraper import KiprixScraper
        return KiprixScraper(delay=0)

    def test_schema_valide(self, scraper):
        doc = scraper.to_document(KIPRIX_ITEM)
        assert_valid_document(doc)

    def test_source_et_doc_type(self, scraper):
        doc = scraper.to_document(KIPRIX_ITEM)
        assert doc["source"] == "kiprix"
        assert doc["doc_type"] == "produit"

    def test_content_contient_magasin_et_prix(self, scraper):
        doc = scraper.to_document(KIPRIX_ITEM)
        assert KIPRIX_ITEM["magasin"] in doc["content"]
        assert KIPRIX_ITEM["prix"] in doc["content"]

    def test_published_at_est_none(self, scraper):
        """Kiprix n'a pas de date de publication."""
        doc = scraper.to_document(KIPRIX_ITEM)
        assert doc.get("published_at") is None

    def test_metadata_contient_disponibilite(self, scraper):
        doc = scraper.to_document(KIPRIX_ITEM)
        assert doc["metadata"]["disponibilite"] == KIPRIX_ITEM["disponibilite"]


# =============================================================================
# Tests MadianaScraper.to_document()
# =============================================================================

class TestMadianaToDocument:
    @pytest.fixture()
    def scraper(self):
        from src.scrapers.madiana_scraper import MadianaScraper
        return MadianaScraper(delay=0)

    def test_schema_valide(self, scraper):
        doc = scraper.to_document(MADIANA_ITEM)
        assert_valid_document(doc)

    def test_source_et_doc_type(self, scraper):
        doc = scraper.to_document(MADIANA_ITEM)
        assert doc["source"] == "madiana"
        assert doc["doc_type"] == "film"

    def test_content_contient_seances(self, scraper):
        doc = scraper.to_document(MADIANA_ITEM)
        assert MADIANA_ITEM["seances"] in doc["content"]

    def test_metadata_contient_images(self, scraper):
        doc = scraper.to_document(MADIANA_ITEM)
        assert doc["metadata"]["images"] == MADIANA_ITEM["images"]


# =============================================================================
# Tests RCIScraper.to_document()
# =============================================================================

class TestRCIToDocument:
    @pytest.fixture()
    def scraper(self):
        from src.scrapers.rci_scraper import RCIScraper
        return RCIScraper(delay=0)

    def test_schema_valide(self, scraper):
        doc = scraper.to_document(RCI_ITEM)
        assert_valid_document(doc)

    def test_source_et_doc_type(self, scraper):
        doc = scraper.to_document(RCI_ITEM)
        assert doc["source"] == "rci"
        assert doc["doc_type"] == "actualite"

    def test_content_contient_resume(self, scraper):
        doc = scraper.to_document(RCI_ITEM)
        assert RCI_ITEM["resume"] in doc["content"]

    def test_published_at_transmis(self, scraper):
        doc = scraper.to_document(RCI_ITEM)
        assert doc["published_at"] == RCI_ITEM["date"]


# =============================================================================
# Tests KreyolScraper.to_document()
# =============================================================================

class TestKreyolToDocument:
    @pytest.fixture()
    def scraper(self):
        from src.scrapers.kreyol_scraper import KreyolScraper
        return KreyolScraper(delay=0)

    def test_schema_valide(self, scraper):
        doc = scraper.to_document(KREYOL_ITEM)
        assert_valid_document(doc)

    def test_source_et_doc_type(self, scraper):
        doc = scraper.to_document(KREYOL_ITEM)
        assert doc["source"] == "kreyol"
        assert doc["doc_type"] == "mot"

    def test_title_est_le_mot_creole(self, scraper):
        doc = scraper.to_document(KREYOL_ITEM)
        assert doc["title"] == KREYOL_ITEM["mot"]

    def test_content_contient_traduction(self, scraper):
        doc = scraper.to_document(KREYOL_ITEM)
        assert KREYOL_ITEM["traduction_fr"] in doc["content"]

    def test_metadata_contient_categorie_gram(self, scraper):
        doc = scraper.to_document(KREYOL_ITEM)
        assert doc["metadata"]["categorie_gram"] == KREYOL_ITEM["categorie_gram"]


# =============================================================================
# Tests DocumentLoader (avec mock psycopg2 — sans DB)
# =============================================================================

class TestDocumentLoader:
    @pytest.fixture()
    def mock_conn(self):
        """Fausse connexion psycopg2 — aucune base de données requise."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn, cursor

    def _make_to_document(self, source: str, doc_type: str):
        def to_document(item):
            return {
                "source":   source,
                "doc_type": doc_type,
                "title":    item["title"],
                "content":  item["content"],
                "url":      item.get("url"),
            }
        return to_document

    def test_upsert_many_appelle_execute_batch(self, mock_conn):
        conn, cursor = mock_conn
        loader = DocumentLoader(conn)
        items = [{"title": "Test", "content": "Contenu test", "url": "https://x.com/1"}]
        to_doc = self._make_to_document("rci", "actualite")

        with patch("src.db_loader.psycopg2.extras.execute_batch") as mock_batch:
            loader.upsert_many(items, to_doc)
            assert mock_batch.called
            conn.commit.assert_called_once()

    def test_upsert_many_liste_vide_retourne_zero(self, mock_conn):
        conn, _ = mock_conn
        loader = DocumentLoader(conn)
        n = loader.upsert_many([], lambda x: x)
        assert n == 0
        conn.commit.assert_not_called()

    def test_metadata_serialise_en_json(self, mock_conn):
        conn, _ = mock_conn
        loader = DocumentLoader(conn)

        def to_doc(item):
            return {
                "source": "kiprix", "doc_type": "produit",
                "title": "Lait", "content": "Lait entier",
                "metadata": {"prix": "1.89 €", "magasin": "Leader Price"},
            }

        captured = []
        def fake_batch(cur, sql, docs, **kwargs):
            captured.extend(docs)

        with patch("src.db_loader.psycopg2.extras.execute_batch", side_effect=fake_batch):
            loader.upsert_many([{"x": 1}], to_doc)

        assert isinstance(captured[0]["metadata"], str)
        parsed = json.loads(captured[0]["metadata"])
        assert parsed["prix"] == "1.89 €"

    def test_item_invalide_est_ignore(self, mock_conn):
        """Un item qui fait planter to_document() est ignoré sans stopper le batch."""
        conn, _ = mock_conn
        loader = DocumentLoader(conn)

        def to_doc_fragile(item):
            if item.get("bad"):
                raise KeyError("champ manquant")
            return {"source": "rci", "doc_type": "actualite",
                    "title": "OK", "content": "Contenu OK"}

        items = [{"bad": True}, {"ok": True}]
        with patch("src.db_loader.psycopg2.extras.execute_batch"):
            n = loader.upsert_many(items, to_doc_fragile)
        assert n == 1   # seul l'item valide est compté


# =============================================================================
# Tests _validate_and_prepare (validation du schéma)
# =============================================================================

class TestValidateAndPrepare:
    def _base(self) -> dict:
        return {"source": "rci", "doc_type": "actualite",
                "title": "Titre", "content": "Contenu"}

    def test_doc_valide_passe(self):
        doc = _validate_and_prepare(self._base())
        assert doc["source"] == "rci"

    def test_source_invalide_leve_erreur(self):
        d = {**self._base(), "source": "inconnu"}
        with pytest.raises(ValueError, match="source"):
            _validate_and_prepare(d)

    def test_doc_type_invalide_leve_erreur(self):
        d = {**self._base(), "doc_type": "truc"}
        with pytest.raises(ValueError, match="doc_type"):
            _validate_and_prepare(d)

    def test_title_vide_leve_erreur(self):
        d = {**self._base(), "title": ""}
        with pytest.raises(ValueError, match="title"):
            _validate_and_prepare(d)

    def test_title_trop_long_est_tronque(self):
        d = {**self._base(), "title": "A" * 600}
        doc = _validate_and_prepare(d)
        assert len(doc["title"]) == 500

    def test_metadata_dict_serialise(self):
        d = {**self._base(), "metadata": {"prix": "10 €"}}
        doc = _validate_and_prepare(d)
        assert isinstance(doc["metadata"], str)
        assert json.loads(doc["metadata"])["prix"] == "10 €"

    def test_metadata_none_reste_none(self):
        d = {**self._base(), "metadata": None}
        doc = _validate_and_prepare(d)
        assert doc["metadata"] is None
