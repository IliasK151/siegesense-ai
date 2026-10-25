"""Tests for the UI-independent session workflow service."""

import hashlib

import pytest

from siegesense.domain.models import ObservationKind
from siegesense.services.session_service import SessionService
from siegesense.storage.database import Database


@pytest.fixture
def service() -> SessionService:
    database = Database(":memory:")
    yield SessionService(database)
    database.close()


def test_create_session_and_list_excludes_demo_by_default(service: SessionService) -> None:
    real = service.create_session("Ranked review")
    demo = service.create_session("Example", is_demo=True)

    assert [item.id for item in service.list_sessions()] == [real.id]
    assert {item.id for item in service.list_sessions(include_demo=True)} == {real.id, demo.id}


def test_observation_inherits_parent_demo_flag(service: SessionService) -> None:
    session = service.create_session("Example", is_demo=True)
    observation = service.add_observation(session.id, 1250, "Example note", kind=ObservationKind.AIM)

    assert observation.is_demo is True
    assert service.list_observations(session.id) == []
    assert service.list_observations(session.id, include_demo=True) == [observation]


def test_observations_are_sorted_by_timestamp(service: SessionService) -> None:
    session = service.create_session("Review", duration_ms=10000)
    service.add_observation(session.id, 5000, "Second")
    service.add_observation(session.id, 1000, "First")

    assert [item.text for item in service.list_observations(session.id)] == ["First", "Second"]


def test_missing_session_is_reported(service: SessionService) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        service.add_observation("unknown", 0, "Note")


def test_invalid_timestamp_is_rejected(service: SessionService) -> None:
    session = service.create_session("Review", duration_ms=1000)
    with pytest.raises(ValueError, match="exceeds"):
        service.add_observation(session.id, 1001, "Outside clip")


def test_fingerprint_session_media_hashes_and_persists_recording(service: SessionService, tmp_path) -> None:
    media = tmp_path / "match.mp4"
    media.write_bytes(b"first chunk and second chunk")
    session = service.create_session("Fingerprint test", media_path=str(media))

    fingerprint = service.fingerprint_session_media(session.id, chunk_size=5)

    assert fingerprint == hashlib.sha256(media.read_bytes()).hexdigest()
    stored = service.list_sessions()[0]
    assert stored.media_sha256 == fingerprint


def test_fingerprint_session_media_rejects_missing_recording(service: SessionService) -> None:
    session = service.create_session("Missing file", media_path="/definitely/not/a/recording.mp4")
    with pytest.raises(ValueError, match="does not exist"):
        service.fingerprint_session_media(session.id)


def test_fingerprint_session_media_rejects_missing_path(service: SessionService) -> None:
    session = service.create_session("No media")
    with pytest.raises(ValueError, match="no recording path"):
        service.fingerprint_session_media(session.id)
