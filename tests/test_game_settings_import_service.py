"""Tests for read-only GameSettings.ini import."""

from pathlib import Path

import pytest

from siegesense.services.game_settings_import_service import read_game_settings_ini


def test_imports_explicit_input_fields_and_reports_unmapped_scope_keys(tmp_path: Path) -> None:
    path = tmp_path / "GameSettings.ini"
    original = """[DISPLAY]
ResolutionWidth=1920

[INPUT]
MouseSensitivity=67
MouseYawSensitivity=6
MousePitchSensitivity=6
MouseSensitivityMultiplierUnit=0.020000
ADSMouseMultiplierUnit=0.020000
ADSMouseSensitivityGlobal=57
ADSMouseSensitivity1x=40
ADSMouseSensitivity1xHalf=44
ADSMouseSensitivity2x=45
ADSMouseSensitivity3x=36
"""
    path.write_text(original, encoding="utf-8")

    imported = read_game_settings_ini(path)

    assert imported.values == {
        "horizontal": 6,
        "vertical": 6,
        "sensitivity_multiplier": pytest.approx(0.02),
        "ads_sensitivity_multiplier": pytest.approx(0.02),
        "ads_global": 57,
        "ads_1x": 40,
    }
    assert imported.additional_ads_keys == (
        "adsmousesensitivity1xhalf",
        "adsmousesensitivity2x",
        "adsmousesensitivity3x",
    )
    assert path.read_text(encoding="utf-8") == original


def test_uses_legacy_global_mouse_sensitivity_only_as_axis_fallback(tmp_path: Path) -> None:
    path = tmp_path / "GameSettings.ini"
    path.write_text(
        "[INPUT]\nMouseSensitivity=54\nMouseSensitivityMultiplierUnit=0.020000\n",
        encoding="utf-8",
    )

    imported = read_game_settings_ini(path)

    assert imported.values["horizontal"] == 54
    assert imported.values["vertical"] == 54


def test_invalid_known_values_are_skipped_and_warned(tmp_path: Path) -> None:
    path = tmp_path / "GameSettings.ini"
    path.write_text(
        "[INPUT]\nMouseYawSensitivity=999\nMouseSensitivityMultiplierUnit=not-a-number\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No supported sensitivity entries"):
        read_game_settings_ini(path)


def test_missing_input_section_is_rejected_without_changes(tmp_path: Path) -> None:
    path = tmp_path / "GameSettings.ini"
    path.write_text("[DISPLAY]\nResolutionWidth=1920\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\[INPUT\]"):
        read_game_settings_ini(path)
