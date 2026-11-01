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


def test_schema_version_is_1(tmp_path):
    s = Store(tmp_path / "s.db")
    assert s.schema_version() == 1
    s.close()
    assert Store(tmp_path / "s.db").schema_version() == 1
