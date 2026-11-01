from siegesense_engine.profile import Profile
from siegesense_engine.store import Store


def make_profile(name="Ash.Main", dpi=800) -> Profile:
    return Profile(in_game_name=name, dpi=dpi, yaw_sensitivity=10, pitch_sensitivity=10)


def test_store_empty_returns_none(tmp_path):
    assert Store(tmp_path / "s.db").get_profile() is None


def test_store_creates_parent_dirs(tmp_path):
    Store(tmp_path / "a" / "b" / "s.db").close()
    assert (tmp_path / "a" / "b" / "s.db").exists()


def test_store_roundtrip(tmp_path):
    s = Store(tmp_path / "s.db")
    s.save_profile(make_profile())
    s.close()
    assert Store(tmp_path / "s.db").get_profile() == make_profile()


def test_store_overwrite(tmp_path):
    s = Store(tmp_path / "s.db")
    s.save_profile(make_profile(dpi=800))
    s.save_profile(make_profile(dpi=1600))
    assert s.get_profile().dpi == 1600


def test_schema_version_is_current(tmp_path):
    s = Store(tmp_path / "s.db")
    assert s.schema_version() == 4
    s.close()
    assert Store(tmp_path / "s.db").schema_version() == 4


def _summary(started: str, score):
    from siegesense_engine.warmup import WarmupMetrics, WarmupSummary

    metrics = WarmupMetrics.empty("estimated").model_copy(update={"score": score})
    return WarmupSummary(
        id=None,
        started_at=started,
        duration_s=60.0,
        metrics=metrics,
        drill=None,
        message="",
        history=[],
    )


def test_store_warmup_history_order(tmp_path):
    s = Store(tmp_path / "s.db")
    for i in range(9):
        s.add_warmup(_summary(f"2026-11-0{i + 1}T10:00:00+00:00", 50 + i))
    hist = s.recent_warmups(7)
    assert [h.score for h in hist] == [52, 53, 54, 55, 56, 57, 58]
    assert hist[-1].started_at.startswith("2026-11-09")


def test_migration_2_from_v1_db(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO meta VALUES ('schema_version', '1');
        CREATE TABLE profiles (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL,
                               updated_at TEXT NOT NULL);
        """
    )
    db.execute(
        "INSERT INTO profiles VALUES (1, ?, 'x')",
        (make_profile().model_dump_json(),),
    )
    db.commit()
    db.close()
    s = Store(path)
    assert s.schema_version() == 4
    assert s.get_profile() == make_profile()
    assert s.recent_warmups() == []


def test_store_matches(tmp_path):
    s = Store(tmp_path / "s.db")
    assert s.schema_version() == 4
    mid = s.add_match("2026-11-01T20:00:00+00:00", "2026-11-01T20:30:00+00:00", {"rounds": []},
                      [{"t": 1.0, "kind": "death", "data": {}}])  # fmt: skip
    assert mid == 1
    [m] = s.recent_matches()
    assert m["id"] == 1 and m["summary"] == {"rounds": []}
