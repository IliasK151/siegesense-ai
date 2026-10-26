"""Read-only import of known Rainbow Six Siege input settings.

This module never writes or modifies GameSettings.ini. Scope keys whose naming does
not exactly match the current UI are reported for review instead of guessed mappings.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GameSettingsImport:
    """Recognized input values plus unmodified scope keys requiring manual review."""

    source_path: str
    values: dict[str, int | float]
    additional_ads_keys: tuple[str, ...]
    warnings: tuple[str, ...]


def read_game_settings_ini(path: str | Path) -> GameSettingsImport:
    """Read selected GameSettings.ini and return only values with explicit mappings."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"GameSettings.ini was not found: {source}")
    try:
        raw_text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(
            "This GameSettings.ini could not be decoded as UTF-8. No settings were changed."
        ) from error
    except OSError as error:
        raise ValueError(f"Could not read GameSettings.ini: {error}") from error

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read_string(raw_text)
    except configparser.Error as error:
        raise ValueError(f"GameSettings.ini could not be parsed: {error}") from error

    input_section = next(
        (section for section in parser.sections() if section.casefold() == "input"),
        None,
    )
    if input_section is None:
        raise ValueError("GameSettings.ini does not contain an [INPUT] section.")

    options = {
        key.casefold(): value.strip()
        for key, value in parser.items(input_section)
    }
    values: dict[str, int | float] = {}
    warnings: list[str] = []

    def read_integer(key: str, field: str, *, minimum: int, maximum: int) -> None:
        raw_value = options.get(key.casefold())
        if raw_value is None:
            return
        try:
            value = int(raw_value)
        except ValueError:
            warnings.append(f"{key} was not a valid integer and was skipped.")
            return
        if not minimum <= value <= maximum:
            warnings.append(
                f"{key}={raw_value} is outside the supported {minimum}–{maximum} range and was skipped."
            )
            return
        values[field] = value

    def read_multiplier(key: str, field: str) -> None:
        raw_value = options.get(key.casefold())
        if raw_value is None:
            return
        try:
            value = float(raw_value)
        except ValueError:
            warnings.append(f"{key} was not a valid number and was skipped.")
            return
        if not 0.000001 <= value <= 1.0:
            warnings.append(
                f"{key}={raw_value} is outside the supported multiplier range and was skipped."
            )
            return
        values[field] = value

    # Prefer explicit horizontal/vertical keys. The older global key is a fallback
    # only where the matching axis-specific key is absent.
    read_integer("MouseYawSensitivity", "horizontal", minimum=1, maximum=100)
    read_integer("MousePitchSensitivity", "vertical", minimum=1, maximum=100)
    if "horizontal" not in values:
        read_integer("MouseSensitivity", "horizontal", minimum=1, maximum=100)
    if "vertical" not in values:
        read_integer("MouseSensitivity", "vertical", minimum=1, maximum=100)

    read_multiplier("MouseSensitivityMultiplierUnit", "sensitivity_multiplier")
    read_multiplier("ADSMouseMultiplierUnit", "ads_sensitivity_multiplier")
    read_integer("ADSMouseSensitivityGlobal", "ads_global", minimum=1, maximum=200)
    read_integer("ADSMouseSensitivity1x", "ads_1x", minimum=1, maximum=200)

    if not values:
        raise ValueError(
            "No supported sensitivity entries were found in [INPUT]. "
            "No Settings Lab values were changed."
        )

    additional_ads_keys = tuple(
        sorted(
            key
            for key in options
            if key.startswith("adsmousesensitivity")
            and key not in {"adsmousesensitivityglobal", "adsmousesensitivity1x"}
        )
    )
    return GameSettingsImport(
        source_path=str(source),
        values=values,
        additional_ads_keys=additional_ads_keys,
        warnings=tuple(warnings),
    )
