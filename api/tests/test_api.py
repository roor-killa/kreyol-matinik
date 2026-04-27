"""
Tests unitaires — Lang Matinitjé API (SQLite)

Tests pg_trgm marqués @pytest.mark.skip (func.similarity() indisponible en SQLite).
"""
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "service" in data


# ---------------------------------------------------------------------------
# /api/v1/corpus
# ---------------------------------------------------------------------------

def test_corpus_empty(client: TestClient):
    resp = client.get("/api/v1/corpus")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["results"] == []


# ---------------------------------------------------------------------------
# /api/v1/expressions
# ---------------------------------------------------------------------------

def test_expressions_empty(client: TestClient):
    resp = client.get("/api/v1/expressions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["results"] == []


# ---------------------------------------------------------------------------
# /api/v1/media
# ---------------------------------------------------------------------------

def test_media_empty(client: TestClient):
    resp = client.get("/api/v1/media")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_media_404(client: TestClient):
    resp = client.get("/api/v1/media/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/v1/dictionary — erreurs et cas limites
# ---------------------------------------------------------------------------

def test_dictionary_random_empty_db(client: TestClient):
    """Retourne 404 si la table mots est vide."""
    resp = client.get("/api/v1/dictionary/random")
    assert resp.status_code == 404


def test_dictionary_get_404(client: TestClient):
    resp = client.get("/api/v1/dictionary/9999")
    assert resp.status_code == 404
    assert "9999" in resp.json()["detail"]


def test_dictionary_post_no_auth(client: TestClient):
    """POST sans token Bearer → 401."""
    resp = client.post("/api/v1/dictionary", json={"mot_creole": "lanmou"})
    assert resp.status_code == 401


def test_dictionary_post_invalid_token(client: TestClient):
    """POST avec token invalide → 401."""
    resp = client.post(
        "/api/v1/dictionary",
        json={"mot_creole": "lanmou"},
        headers={"Authorization": "Bearer token-invalide"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api/v1/dictionary — CRUD complet (JWT admin requis)
# ---------------------------------------------------------------------------

def test_dictionary_crud(client: TestClient, admin_token: str):
    """POST → GET → PUT → GET avec token admin."""
    bearer = {"Authorization": f"Bearer {admin_token}"}

    # Création
    resp = client.post(
        "/api/v1/dictionary",
        json={"mot_creole": "lanmou", "phonetique": "la.mu"},
        headers=bearer,
    )
    assert resp.status_code == 201
    created = resp.json()
    mot_id = created["id"]
    assert created["mot_creole"] == "lanmou"
    assert created["phonetique"] == "la.mu"

    # Lecture
    resp = client.get(f"/api/v1/dictionary/{mot_id}")
    assert resp.status_code == 200
    assert resp.json()["mot_creole"] == "lanmou"

    # Mise à jour
    resp = client.put(
        f"/api/v1/dictionary/{mot_id}",
        json={"phonetique": "lã.mu"},
        headers=bearer,
    )
    assert resp.status_code == 200
    assert resp.json()["phonetique"] == "lã.mu"

    # Relecture
    resp = client.get(f"/api/v1/dictionary/{mot_id}")
    assert resp.status_code == 200
    assert resp.json()["phonetique"] == "lã.mu"


def test_dictionary_random_after_insert(client: TestClient, admin_token: str):
    """Après insertion, /random retourne 200."""
    client.post(
        "/api/v1/dictionary",
        json={"mot_creole": "annou"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = client.get("/api/v1/dictionary/random")
    assert resp.status_code == 200
    data = resp.json()
    assert "mot_creole" in data
    assert "traductions" in data


# ---------------------------------------------------------------------------
# /api/v1/dictionary/search — SKIP (pg_trgm requis)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="func.similarity() nécessite PostgreSQL + pg_trgm")
def test_dictionary_search(client: TestClient):
    resp = client.get("/api/v1/dictionary/search?q=annou")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/translate — SKIP (pg_trgm requis)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="func.similarity() nécessite PostgreSQL + pg_trgm")
def test_translate(client: TestClient):
    resp = client.post(
        "/api/v1/translate",
        json={"text": "Allons à la mer", "source": "fr", "target": "crm"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "corpus_match"


# ---------------------------------------------------------------------------
# POST /api/v1/chat
# ---------------------------------------------------------------------------

def test_chat_reply(client: TestClient):
    """Vérifie le contrat du endpoint /chat (réponse non-vide, session_id)."""
    msg = "Saw fè ?"
    resp = client.post("/api/v1/chat", json={"message": msg})
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert isinstance(data["reply"], str) and len(data["reply"]) > 0
    assert data["session_id"]
    assert data["model_version"] == "fèfèn-0.2-tfidf"

    # Un session_id UUID valide fourni doit être retourné tel quel
    import uuid as _uuid
    sid = str(_uuid.uuid4())
    resp2 = client.post("/api/v1/chat", json={"message": msg, "session_id": sid})
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == sid


def test_chat_reply_index():
    """_STUB_REPLIES contient 4 réponses — reply_index = len(message) % 4."""
    from app.routers.chat import _STUB_REPLIES
    assert len(_STUB_REPLIES) == 4


# ---------------------------------------------------------------------------
# Auth — POST /api/v1/auth/register + login + GET /auth/me
# ---------------------------------------------------------------------------

def test_auth_register(client: TestClient):
    """Inscription d'un nouvel utilisateur → 201, token + rôle contributeur."""
    resp = client.post("/api/v1/auth/register", json={
        "name": "Tibo Test",
        "email": "tibo@test.kr",
        "password": "motdepasse123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "tibo@test.kr"
    assert data["user"]["role"] == "contributeur"
    assert data["user"]["contributeur"] is not None


def test_auth_register_duplicate_email(client: TestClient):
    """Inscrire deux fois le même email → 409."""
    payload = {"name": "Dup", "email": "dup@test.kr", "password": "pass1234"}
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_auth_login(client: TestClient):
    """Login avec bon mot de passe → token."""
    client.post("/api/v1/auth/register", json={
        "name": "Login User",
        "email": "login@test.kr",
        "password": "motdepasse123",
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": "login@test.kr",
        "password": "motdepasse123",
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_auth_login_wrong_password(client: TestClient):
    """Mauvais mot de passe → 401."""
    resp = client.post("/api/v1/auth/login", json={
        "email": "inexistant@test.kr",
        "password": "mauvais",
    })
    assert resp.status_code == 401


def test_auth_me(client: TestClient):
    """GET /auth/me avec token valide → profil utilisateur."""
    reg = client.post("/api/v1/auth/register", json={
        "name": "Me User",
        "email": "me@test.kr",
        "password": "motdepasse123",
    })
    token = reg.json()["token"]
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@test.kr"
    assert data["role"] == "contributeur"
    assert data["contributeur"] is not None


def test_auth_me_no_token(client: TestClient):
    """GET /auth/me sans token → 401."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
