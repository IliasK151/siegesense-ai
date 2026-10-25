"""Tests for default local database startup behaviour."""

from pathlib import Path

from siegesense.storage.database import Database


def test_default_database_uses_resolved_path_and_creates_parent_on_open(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "profile" / "siegesense.sqlite3"
    monkeypatch.setattr("siegesense.storage.database.default_database_path", lambda: target)

    assert not target.parent.exists()
    database = Database()
    try:
        assert target.exists()
        assert database.path == target
        assert database.list_sessions() == []
    finally:
        database.close()
