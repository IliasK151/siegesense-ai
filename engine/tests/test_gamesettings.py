import os

from conftest import TEST_FIXTURES

from siegesense_engine.gamesettings import find_game_settings, parse_game_settings

FULL = {
    "yaw_sensitivity": 12,
    "pitch_sensitivity": 11,
    "mouse_multiplier_unit": 0.02,
    "x_factor_aiming": 0.02,
    "ads_sensitivity": {"1x": 55, "2.5x": 60, "3x": 65, "4x": 70, "5x": 75, "12x": 80},
    "fov": 84.0,
    "resolution_width": 2560,
    "resolution_height": 1440,
    "window_mode": "borderless",
}


def test_full_file():
    result = parse_game_settings(TEST_FIXTURES / "GameSettings_utf8.ini")
    assert result.values == FULL
    assert result.missing == []
    assert result.source.endswith("GameSettings_utf8.ini")


def test_utf16_file():
    assert parse_game_settings(TEST_FIXTURES / "GameSettings_utf16.ini").values == FULL


def test_missing_keys_reported():
    result = parse_game_settings(TEST_FIXTURES / "GameSettings_partial.ini")
    assert result.values == {"yaw_sensitivity": 12, "window_mode": "borderless"}
    assert "pitch_sensitivity" in result.missing
    assert "fov" in result.missing
    assert "ads_sensitivity" in result.missing


def test_case_insensitive_keys(tmp_path):
    f = tmp_path / "GameSettings.ini"
    f.write_text("[input]\nmouseyawsensitivity = 5\n")
    assert parse_game_settings(f).values["yaw_sensitivity"] == 5


def test_bad_value_goes_to_missing(tmp_path):
    f = tmp_path / "GameSettings.ini"
    f.write_text("DefaultFOV=abc\nWindowMode=7\n")
    result = parse_game_settings(f)
    assert "fov" not in result.values
    assert "fov" in result.missing
    assert result.values["window_mode"] == "unknown"


def test_duplicate_keys_first_wins(tmp_path):
    f = tmp_path / "GameSettings.ini"
    f.write_text("[A]\nMouseYawSensitivity=7\n[B]\nMouseYawSensitivity=9\n")
    assert parse_game_settings(f).values["yaw_sensitivity"] == 7


def test_find_game_settings(tmp_path):
    base = tmp_path / "Documents" / "My Games" / "Rainbow Six - Siege"
    old, new = base / "old-id" / "GameSettings.ini", base / "new-id" / "GameSettings.ini"
    for f in (old, new):
        f.parent.mkdir(parents=True)
        f.write_text("x=1")
    os.utime(old, (1_000, 1_000))
    os.utime(new, (2_000, 2_000))
    found = find_game_settings([tmp_path / "Documents", tmp_path / "missing"])
    assert [f["path"] for f in found] == [str(new), str(old)]
    assert found[0]["modified"] == 2_000


def test_find_game_settings_none(tmp_path):
    assert find_game_settings([tmp_path / "nothing"]) == []


def test_inf_and_nan_go_to_missing(tmp_path):
    f = tmp_path / "GameSettings.ini"
    f.write_text("DefaultFOV=nan\nMouseYawSensitivity=inf\nResolutionWidth=1e400\n")
    result = parse_game_settings(f)
    assert result.values == {}
    for field in ("fov", "yaw_sensitivity", "resolution_width"):
        assert field in result.missing


def test_onedrive_variants_found(tmp_path, monkeypatch):
    from pathlib import Path

    from siegesense_engine import gamesettings

    (tmp_path / "Documents").mkdir()
    (tmp_path / "OneDrive - Contoso" / "Documents").mkdir(parents=True)
    (tmp_path / "OneDrive" / "Documents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(gamesettings, "_known_documents_folder", lambda: None)
    dirs = gamesettings.default_documents_dirs()
    assert tmp_path / "Documents" in dirs
    assert tmp_path / "OneDrive - Contoso" / "Documents" in dirs
    assert tmp_path / "OneDrive" / "Documents" in dirs
    assert len(dirs) == len(set(dirs))


def test_known_folder_comes_first(tmp_path, monkeypatch):
    from pathlib import Path

    from siegesense_engine import gamesettings

    redirected = tmp_path / "D" / "Docs"
    redirected.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(gamesettings, "_known_documents_folder", lambda: redirected)
    assert gamesettings.default_documents_dirs()[0] == redirected
