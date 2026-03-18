"""Tests d'intégration — nécessite Docker (PostgreSQL + pgvector actif).

Ces tests écrivent de vraies données dans la table `documents`.
Ils sont marqués @pytest.mark.integration et skippés par défaut.

Lancer UNIQUEMENT si le docker-compose est up :
    docker compose up -d db
    cd kreyol-matinik/scraper
    python -m pytest tests/test_db_integration.py -v -m integration

Variables d'environnement requises (lues depuis .env) :
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()  # charge le .env du projet

# Skip automatique si la DB est inaccessible ou si le marker n'est pas demandé
pytestmark = pytest.mark.integration


# =============================================================================
# Fixture : connexion réelle (skippée si DB inaccessible)
# =============================================================================

@pytest.fixture(scope="module")
def db_conn():
    """Connexion psycopg2 réelle. Skip le module si la DB est inaccessible."""
    psycopg2 = pytest.importorskip("psycopg2")
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5433")),
            dbname=os.getenv("POSTGRES_DB", "langmatinitje"),
            user=os.getenv("POSTGRES_USER", "creole"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
    except Exception as e:
        pytest.skip(f"PostgreSQL inaccessible : {e}")

    yield conn

    # Nettoyage : supprime les documents de test insérés
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE url LIKE 'https://test.integration/%'")
    conn.commit()
    conn.close()


# =============================================================================
# Tests
# =============================================================================

class TestDBIntegration:

    def test_pgvector_extension_active(self, db_conn):
        """Vérifie que l'extension vector est bien installée."""
        with db_conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            row = cur.fetchone()
        assert row is not None, "Extension pgvector non installée — relancer docker-compose"

    def test_table_documents_existe(self, db_conn):
        """Vérifie que la table documents a bien été créée."""
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'documents'
            """)
            row = cur.fetchone()
        assert row is not None, "Table 'documents' introuvable — vérifier 02_documents.sql"

    def test_upsert_insert(self, db_conn):
        """Insère un document et vérifie qu'il est bien en base."""
        from src.db_loader import DocumentLoader

        loader = DocumentLoader(db_conn)
        items = [{
            "titre":       "Événement test intégration",
            "description": "Description du test d'intégration.",
            "prix":        "gratuit",
            "localisation":"Fort-de-France",
            "date":        "2026-03-01",
            "url":         "https://test.integration/bizouk/1",
        }]
        from src.scrapers.bizouk_scraper import BizoukScraper
        scraper = BizoukScraper(delay=0)

        n = loader.upsert_many(items, scraper.to_document)
        assert n == 1

        with db_conn.cursor() as cur:
            cur.execute("SELECT title, source FROM documents WHERE url = %s",
                        ("https://test.integration/bizouk/1",))
            row = cur.fetchone()

        assert row is not None
        assert row[0] == "Événement test intégration"
        assert row[1] == "bizouk"

    def test_upsert_idempotent(self, db_conn):
        """Réinsérer le même URL deux fois ne crée pas de doublon."""
        from src.db_loader import DocumentLoader
        from src.scrapers.rci_scraper import RCIScraper

        scraper = RCIScraper(delay=0)
        loader = DocumentLoader(db_conn)
        item = {
            "titre":   "Article idempotence",
            "resume":  "Test idempotence.",
            "categorie":"Tech",
            "date":    "2026-03-01",
            "url":     "https://test.integration/rci/idempotent",
        }

        loader.upsert_many([item], scraper.to_document)
        loader.upsert_many([item], scraper.to_document)  # 2e fois

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE url = %s",
                ("https://test.integration/rci/idempotent",)
            )
            count = cur.fetchone()[0]

        assert count == 1, "UPSERT non idempotent : doublon détecté"

    def test_source_invalide_rejetee(self, db_conn):
        """Un document avec une source inconnue doit être rejeté."""
        from src.db_loader import DocumentLoader

        loader = DocumentLoader(db_conn)

        def bad_to_document(item):
            return {"source": "inconnu", "doc_type": "annonce",
                    "title": "T", "content": "C"}

        n = loader.upsert_many([{"x": 1}], bad_to_document)
        assert n == 0   # rejeté par _validate_and_prepare

    def test_insert_tous_les_scrapers(self, db_conn):
        """Chaque scraper peut écrire dans documents sans erreur."""
        from src.db_loader import DocumentLoader
        from src.scrapers.bizouk_scraper import BizoukScraper
        from src.scrapers.kiprix_scraper import KiprixScraper
        from src.scrapers.madiana_scraper import MadianaScraper
        from src.scrapers.rci_scraper import RCIScraper
        from src.scrapers.kreyol_scraper import KreyolScraper

        loader = DocumentLoader(db_conn)

        cases = [
            (BizoukScraper(delay=0), {
                "titre": "Test Bizouk", "description": "desc",
                "prix": "10€", "localisation": "FDF", "date": None,
                "url": "https://test.integration/bizouk/all",
            }),
            (KiprixScraper(delay=0), {
                "nom": "Test Kiprix", "prix": "2€", "magasin": "Carrefour",
                "disponibilite": "En stock", "categorie": "Épicerie",
                "url": "https://test.integration/kiprix/all",
            }),
            (MadianaScraper(delay=0), {
                "titre": "Test Film", "description": "synopsis",
                "genre": "Action", "seances": "20h", "prix_place": "10€",
                "images": None, "url": "https://test.integration/madiana/all",
            }),
            (RCIScraper(delay=0), {
                "titre": "Test RCI", "resume": "résumé actu",
                "categorie": "Société", "date": "2026-03-01",
                "url": "https://test.integration/rci/all",
            }),
            (KreyolScraper(delay=0), {
                "mot": "tèstmot", "definition": "Definisyon tès.",
                "traduction_fr": "mot test", "categorie_gram": "nom",
                "exemple": "Sa sé yon tès.", "phonetique": "tɛstmo",
                "url": "https://test.integration/kreyol/all",
            }),
        ]

        for scraper, item in cases:
            n = loader.upsert_many([item], scraper.to_document)
            assert n == 1, f"{scraper.__class__.__name__} : upsert a échoué"
