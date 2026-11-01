"""Find and read Rainbow Six Siege's GameSettings.ini.

We only *read* the player's settings file to prefill their profile; we never write to it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WINDOW_MODES = {"0": "fullscreen", "1": "windowed", "2": "borderless"}


def _window_mode(raw: str) -> str:
    return WINDOW_MODES.get(raw.strip(), "unknown")


def _int(raw: str) -> int:
    return int(float(raw))


# ini key (lowercase) -> (profile field, ADS scope or None, converter)
KEY_MAP: dict[str, tuple[str, str | None, Callable[[str], Any]]] = {
    "mouseyawsensitivity": ("yaw_sensitivity", None, _int),
    "mousepitchsensitivity": ("pitch_sensitivity", None, _int),
    "mousesensitivitymultiplierunit": ("mouse_multiplier_unit", None, float),
    "xfactoraiming": ("x_factor_aiming", None, float),
    "adsmousesensitivity1x": ("ads_sensitivity", "1x", _int),
    "adsmousesensitivity2xhalf": ("ads_sensitivity", "2.5x", _int),
    "adsmousesensitivity3x": ("ads_sensitivity", "3x", _int),
    "adsmousesensitivity4x": ("ads_sensitivity", "4x", _int),
    "adsmousesensitivity5x": ("ads_sensitivity", "5x", _int),
    "adsmousesensitivity12x": ("ads_sensitivity", "12x", _int),
    "defaultfov": ("fov", None, float),
    "resolutionwidth": ("resolution_width", None, _int),
    "resolutionheight": ("resolution_height", None, _int),
    "windowmode": ("window_mode", None, _window_mode),
}
ALL_FIELDS: list[str] = list(dict.fromkeys(f for f, _, _ in KEY_MAP.values()))


@dataclass
class GameSettingsImport:
    values: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    source: str = ""


def _decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def parse_game_settings(path: Path) -> GameSettingsImport:
    text = _decode(Path(path).read_bytes())
    values: dict[str, Any] = {}
    ads: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in ";#[" or "=" not in line:
            continue
        key, raw = (part.strip() for part in line.split("=", 1))
        mapping = KEY_MAP.get(key.lower())
        if mapping is None:
            continue
        name, scope, convert = mapping
        if (scope and scope in ads) or (not scope and name in values):
            continue  # first match wins
        try:
            value = convert(raw)
        except ValueError:
            continue
        if scope:
            ads[scope] = value
        else:
            values[name] = value
    if ads:
        values["ads_sensitivity"] = ads
    missing = [f for f in ALL_FIELDS if f not in values]
    return GameSettingsImport(values=values, missing=missing, source=str(path))


def find_game_settings(documents_dirs: list[Path]) -> list[dict]:
    found: dict[str, float] = {}
    for doc in documents_dirs:
        base = Path(doc) / "My Games" / "Rainbow Six - Siege"
        if not base.is_dir():
            continue
        for f in base.glob("*/GameSettings.ini"):
            found[str(f)] = f.stat().st_mtime
    ordered = sorted(found.items(), key=lambda kv: kv[1], reverse=True)
    return [{"path": p, "modified": m} for p, m in ordered]


def default_documents_dirs() -> list[Path]:
    home = Path.home()
    dirs = [home / "Documents"]
    onedrive = home / "OneDrive" / "Documents"
    if onedrive.is_dir():
        dirs.append(onedrive)
    return dirs
