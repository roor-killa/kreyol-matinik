"""
Tests — POST /chat (logging Phase 8) et POST /chat/correct
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.models.models import ConversationLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chat(client: TestClient, message: str, session_id: str | None = None, token: str | None = None):
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/v1/chat", json=body, headers=headers)


# ---------------------------------------------------------------------------
# test_chat_creates_log
# ---------------------------------------------------------------------------

def test_chat_creates_log(client: TestClient, db_session):
    """Chaque appel /chat doit créer une entrée dans conversation_logs."""
    before = db_session.query(ConversationLog).count()

    resp = _chat(client, "Bonjou Fèfèn !")
    assert resp.status_code == 200

    after = db_session.query(ConversationLog).count()
    assert after == before + 1


def test_chat_log_stores_message_and_reply(client: TestClient, db_session):
    """Le log doit contenir le message utilisateur et la réponse du bot."""
    resp = _chat(client, "Ka manjé ou ?"  )
    assert resp.status_code == 200

    log = (
        db_session.query(ConversationLog)
        .order_by(ConversationLog.created_at.desc())
        .first()
    )
    assert log is not None
    assert log.user_message == "Ka manjé ou ?"
    assert log.bot_response  # non vide
    assert log.is_processed is False


def test_chat_session_id_returned(client: TestClient):
    """La réponse doit inclure un session_id UUID valide."""
    resp = _chat(client, "Bonjou !")
    data = resp.json()
    assert "session_id" in data
    # Vérifier que c'est un UUID valide
    uuid.UUID(data["session_id"])


def test_chat_session_id_reused(client: TestClient, db_session):
    """Si un session_id UUID valide est fourni, il doit être conservé dans le log."""
    sid = str(uuid.uuid4())
    resp = _chat(client, "Mwen ka palé", session_id=sid)
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid

    log = (
        db_session.query(ConversationLog)
        .filter(ConversationLog.session_id == uuid.UUID(sid))
        .first()
    )
    assert log is not None


def test_chat_detects_creole_language(client: TestClient, db_session):
    """Un message créole doit avoir detected_lang='crm'."""
    _chat(client, "mwen ka manjé poul la")

    log = (
        db_session.query(ConversationLog)
        .order_by(ConversationLog.created_at.desc())
        .first()
    )
    assert log.detected_lang == "crm"
    assert log.lang_confidence > 0.0


# ---------------------------------------------------------------------------
# test_chat_anonymous_user
# ---------------------------------------------------------------------------

def test_chat_anonymous_user(client: TestClient, db_session):
    """Sans token JWT, user_id doit être NULL dans le log."""
    _chat(client, "Bonjou sans token")

    log = (
        db_session.query(ConversationLog)
        .order_by(ConversationLog.created_at.desc())
        .first()
    )
    assert log.user_id is None


def test_chat_authenticated_user(client: TestClient, db_session, admin_token: str):
    """Avec un token JWT valide, user_id doit être renseigné."""
    _chat(client, "Bonjou admin", token=admin_token)

    log = (
        db_session.query(ConversationLog)
        .order_by(ConversationLog.created_at.desc())
        .first()
    )
    assert log.user_id is not None


# ---------------------------------------------------------------------------
# test_chat_correction
# ---------------------------------------------------------------------------

def test_chat_correction(client: TestClient, db_session):
    """POST /chat/correct doit écrire user_correction dans le log."""
    # 1. Créer un log via /chat
    resp = _chat(client, "Ki sa yé sa ?")
    assert resp.status_code == 200
    sid = resp.json()["session_id"]

    # Récupérer l'id du log créé
    log = (
        db_session.query(ConversationLog)
        .filter(ConversationLog.session_id == uuid.UUID(sid))
        .first()
    )
    assert log is not None
    assert log.user_correction is None

    # 2. Soumettre la correction (log_id en query param, correction en body JSON)
    resp2 = client.post(
        "/api/v1/chat/correct",
        params={"log_id": str(log.id)},
        json="sa vle di : c'est quoi ça",
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "correction enregistrée"

    # 3. Vérifier la persistance
    db_session.refresh(log)
    assert log.user_correction == "sa vle di : c'est quoi ça"


def test_chat_correction_404(client: TestClient):
    """Corriger un log inexistant doit retourner 404."""
    fake_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/chat/correct",
        params={"log_id": fake_id},
        json="test correction",
    )
    assert resp.status_code == 404


def test_chat_correction_requires_body(client: TestClient, db_session):
    """Une correction vide (min_length=1) doit retourner 422."""
    resp = _chat(client, "test")
    sid = resp.json()["session_id"]
    log = (
        db_session.query(ConversationLog)
        .filter(ConversationLog.session_id == uuid.UUID(sid))
        .first()
    )
    resp2 = client.post(
        "/api/v1/chat/correct",
        params={"log_id": str(log.id)},
        json="",   # chaîne vide → min_length=1 → 422
    )
    assert resp2.status_code == 422
