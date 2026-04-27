"""
Tests — /api/v1/moderation (Phase 8)

Couvre :
- test_queue_requires_lingwis
- test_approve_creates_mot
- test_reject_sets_status
- test_merge_links_variant
- test_stats_counts
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.models.models import (
    CandidateStatus,
    Contributeur,
    LinguisticEntry,
    ModerationCandidate,
    Mot,
    User,
)


# ---------------------------------------------------------------------------
# Fixtures spécifiques à la modération
# ---------------------------------------------------------------------------

@pytest.fixture
def lingwis_token(db_session) -> str:
    """Crée un utilisateur lingwis et retourne son JWT."""
    user = User(
        email="lingwis@test.kreyol",
        hashed_password=hash_password("lingwis1234"),
        name="Lingwis Test",
        role="lingwis",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Contributeur(user_id=user.id, pseudo="Lingwis"))
    db_session.flush()
    return create_access_token(user.id, "lingwis")


@pytest.fixture
def contributeur_token(db_session) -> str:
    """Crée un utilisateur contributeur (rôle insuffisant) et retourne son JWT."""
    user = User(
        email="contrib@test.kreyol",
        hashed_password=hash_password("contrib1234"),
        name="Contrib Test",
        role="contributeur",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Contributeur(user_id=user.id, pseudo="Contrib"))
    db_session.flush()
    return create_access_token(user.id, "contributeur")


@pytest.fixture
def pending_candidate(db_session) -> ModerationCandidate:
    """Insère un candidat 'new_word' en attente."""
    candidate = ModerationCandidate(
        candidate_type="new_word",
        status="pending",
        word="zanmi",
        phonetic="Z500",
        context="zanmi ka alé lekòl",
        examples=[{"kr": "zanmi ka alé lekòl"}],
        variants=[],
        source_log_ids=[uuid.uuid4()],
        speaker_count=3,
        frequency=7,
    )
    db_session.add(candidate)
    db_session.flush()
    return candidate


@pytest.fixture
def known_mot(db_session) -> Mot:
    """Insère un mot existant pour les tests de fusion."""
    mot = Mot(mot_creole="zanmitay", valide=True)
    db_session.add(mot)
    db_session.flush()
    return mot


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# test_queue_requires_lingwis
# ---------------------------------------------------------------------------

class TestQueueAccess:
    def test_queue_anonymous_returns_401(self, client: TestClient):
        resp = client.get("/api/v1/moderation/queue")
        assert resp.status_code == 401

    def test_queue_contributeur_returns_403(self, client: TestClient, contributeur_token):
        resp = client.get("/api/v1/moderation/queue", headers=_auth(contributeur_token))
        assert resp.status_code == 403

    def test_queue_lingwis_allowed(self, client: TestClient, lingwis_token):
        resp = client.get("/api/v1/moderation/queue", headers=_auth(lingwis_token))
        assert resp.status_code == 200

    def test_queue_admin_allowed(self, client: TestClient, admin_token):
        resp = client.get("/api/v1/moderation/queue", headers=_auth(admin_token))
        assert resp.status_code == 200

    def test_queue_returns_pagination(self, client: TestClient, lingwis_token, pending_candidate):
        resp = client.get("/api/v1/moderation/queue", headers=_auth(lingwis_token))
        data = resp.json()
        assert "total" in data
        assert "results" in data
        assert "page" in data
        assert data["total"] >= 1

    def test_queue_filter_by_type(self, client: TestClient, lingwis_token, pending_candidate):
        resp = client.get(
            "/api/v1/moderation/queue",
            params={"candidate_type": "new_word"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 200
        for item in resp.json()["results"]:
            assert item["candidate_type"] == "new_word"

    def test_stats_requires_lingwis(self, client: TestClient):
        resp = client.get("/api/v1/moderation/stats")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# test_approve_creates_mot
# ---------------------------------------------------------------------------

class TestApprove:
    def test_approve_creates_mot(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        """Approuver un candidat doit créer un Mot dans la table mots."""
        mot_count_before = db_session.query(Mot).count()

        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "approved", "definition_kr": "moun ki zanmi'w"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["linked_mot_id"] is not None

        mot_count_after = db_session.query(Mot).count()
        assert mot_count_after == mot_count_before + 1

        # Le mot créé doit avoir le bon mot_creole
        mot = db_session.get(Mot, data["linked_mot_id"])
        assert mot.mot_creole == "zanmi"
        assert mot.valide is True

    def test_approve_creates_linguistic_entry(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        """L'approbation doit créer une LinguisticEntry pour la traçabilité."""
        entries_before = db_session.query(LinguisticEntry).count()

        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "approved"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 200

        entries_after = db_session.query(LinguisticEntry).count()
        assert entries_after == entries_before + 1

        entry = db_session.query(LinguisticEntry).order_by(LinguisticEntry.id.desc()).first()
        assert entry.candidate_id == pending_candidate.id
        assert entry.source == "conversation"

    def test_approve_with_word_override(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        """word_override doit être utilisé comme mot_creole."""
        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "approved", "word_override": "zanmi-a"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 200
        mot = db_session.get(Mot, resp.json()["linked_mot_id"])
        assert mot.mot_creole == "zanmi-a"

    def test_approve_sets_candidate_status(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "approved"},
            headers=_auth(lingwis_token),
        )
        db_session.refresh(pending_candidate)
        assert pending_candidate.status == CandidateStatus.approved

    def test_approve_twice_returns_409(self, client: TestClient, lingwis_token, pending_candidate):
        """Un candidat déjà traité ne peut pas être resoumis."""
        client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "approved"},
            headers=_auth(lingwis_token),
        )
        resp2 = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "approved"},
            headers=_auth(lingwis_token),
        )
        assert resp2.status_code == 409

    def test_approve_unknown_candidate_404(self, client: TestClient, lingwis_token):
        resp = client.patch(
            "/api/v1/moderation/99999",
            json={"status": "approved"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# test_reject_sets_status
# ---------------------------------------------------------------------------

class TestReject:
    def test_reject_sets_status(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "rejected", "reviewer_note": "mot déjà connu"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        db_session.refresh(pending_candidate)
        assert pending_candidate.status == CandidateStatus.rejected
        assert pending_candidate.reviewer_note == "mot déjà connu"

    def test_reject_does_not_create_mot(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        mot_before = db_session.query(Mot).count()
        client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "rejected"},
            headers=_auth(lingwis_token),
        )
        assert db_session.query(Mot).count() == mot_before

    def test_reject_sets_reviewer(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "rejected"},
            headers=_auth(lingwis_token),
        )
        db_session.refresh(pending_candidate)
        assert pending_candidate.reviewed_by is not None
        assert pending_candidate.reviewed_at is not None

    def test_invalid_status_returns_422(self, client: TestClient, lingwis_token, pending_candidate):
        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "inexistant"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# test_merge_links_variant
# ---------------------------------------------------------------------------

class TestMerge:
    def test_merge_links_variant(self, client: TestClient, db_session, lingwis_token, pending_candidate, known_mot):
        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "merged", "merge_with_mot_id": known_mot.id},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "merged"
        assert data["linked_mot_id"] == known_mot.id

    def test_merge_creates_linguistic_entry(self, client: TestClient, db_session, lingwis_token, pending_candidate, known_mot):
        entries_before = db_session.query(LinguisticEntry).count()
        client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "merged", "merge_with_mot_id": known_mot.id},
            headers=_auth(lingwis_token),
        )
        assert db_session.query(LinguisticEntry).count() == entries_before + 1

        entry = db_session.query(LinguisticEntry).order_by(LinguisticEntry.id.desc()).first()
        assert entry.mot_id == known_mot.id

    def test_merge_without_mot_id_returns_422(self, client: TestClient, lingwis_token, pending_candidate):
        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "merged"},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 422

    def test_merge_with_unknown_mot_returns_404(self, client: TestClient, lingwis_token, pending_candidate):
        resp = client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "merged", "merge_with_mot_id": 99999},
            headers=_auth(lingwis_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# test_stats_counts
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_returns_expected_keys(self, client: TestClient, lingwis_token):
        resp = client.get("/api/v1/moderation/stats", headers=_auth(lingwis_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "by_status" in data
        assert "by_type" in data
        assert "total" in data

    def test_stats_counts_pending(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        resp = client.get("/api/v1/moderation/stats", headers=_auth(lingwis_token))
        data = resp.json()
        assert data["by_status"].get("pending", 0) >= 1

    def test_stats_after_reject(self, client: TestClient, db_session, lingwis_token, pending_candidate):
        """Après un rejet, le compteur 'rejected' doit augmenter."""
        before = client.get("/api/v1/moderation/stats", headers=_auth(lingwis_token)).json()
        rejected_before = before["by_status"].get("rejected", 0)

        client.patch(
            f"/api/v1/moderation/{pending_candidate.id}",
            json={"status": "rejected"},
            headers=_auth(lingwis_token),
        )

        after = client.get("/api/v1/moderation/stats", headers=_auth(lingwis_token)).json()
        assert after["by_status"].get("rejected", 0) == rejected_before + 1

    def test_stats_total_matches_sum(self, client: TestClient, lingwis_token):
        resp = client.get("/api/v1/moderation/stats", headers=_auth(lingwis_token))
        data = resp.json()
        assert data["total"] == sum(data["by_status"].values())
