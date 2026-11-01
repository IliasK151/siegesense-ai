"""Find and read Rainbow Six Siege's GameSettings.ini.

We only *read* the player's settings file to prefill their profile; we never write to it.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WINDOW_MODES = {"0": "fullscreen", "1": "windowed", "2": "borderless"}


def _window_mode(raw: str) -> str:
    return WINDOW_MODES.get(raw.strip(), "unknown")


def _float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"not a finite number: {raw}")
    return value


def _int(raw: str) -> int:
    return int(_float(raw))


# ini key (lowercase) -> (profile field, ADS scope or None, converter)
KEY_MAP: dict[str, tuple[str, str | None, Callable[[str], Any]]] = {
    "mouseyawsensitivity": ("yaw_sensitivity", None, _int),
    "mousepitchsensitivity": ("pitch_sensitivity", None, _int),
    "mousesensitivitymultiplierunit": ("mouse_multiplier_unit", None, _float),
    "xfactoraiming": ("x_factor_aiming", None, _float),
    "adsmousesensitivity1x": ("ads_sensitivity", "1x", _int),
    "adsmousesensitivity2xhalf": ("ads_sensitivity", "2.5x", _int),
    "adsmousesensitivity3x": ("ads_sensitivity", "3x", _int),
    "adsmousesensitivity4x": ("ads_sensitivity", "4x", _int),
    "adsmousesensitivity5x": ("ads_sensitivity", "5x", _int),
    "adsmousesensitivity12x": ("ads_sensitivity", "12x", _int),
    "defaultfov": ("fov", None, _float),
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
        except (ValueError, OverflowError):
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


def _known_documents_folder() -> Path | None:
    """The real Documents folder on Windows (handles redirection to other drives)."""
    if sys.platform != "win32":
        return None
    import ctypes
    import uuid
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    raw = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}").bytes_le
    guid = GUID.from_buffer_copy(raw)
    path_ptr = ctypes.c_wchar_p()
    try:
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)
        )
        if result != 0 or not path_ptr.value:
            return None
        return Path(path_ptr.value)
    except OSError:
        return None
    finally:
        if path_ptr:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)


def default_documents_dirs() -> list[Path]:
    home = Path.home()
    candidates: list[Path] = []
    known = _known_documents_folder()
    if known is not None:
        candidates.append(known)
    candidates.append(home / "Documents")
    if home.is_dir():
        candidates += sorted(p / "Documents" for p in home.glob("OneDrive*") if p.is_dir())
    seen: set[Path] = set()
    dirs: list[Path] = []
    for d in candidates:
        if d not in seen:
            seen.add(d)
            dirs.append(d)
    return dirs
