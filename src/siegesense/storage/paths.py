"""Resolve per-user storage locations without creating files at import time."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRECTORY_NAME = "SiegeSenseAI"


def default_data_directory(
    *,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    platform: str | None = None,
) -> Path:
    """Return a platform-appropriate user data directory without creating it.

    Parameters are injectable for tests. Merely importing this module never
    touches the filesystem; the directory is created when the database opens.
    """
    env = os.environ if environ is None else environ
    current_platform = sys.platform if platform is None else platform
    user_home = Path.home() if home is None else Path(home)

    if current_platform == "win32":
        root = env.get("LOCALAPPDATA") or env.get("APPDATA")
        base = Path(root) if root else user_home / "AppData" / "Local"
    elif current_platform == "darwin":
        base = user_home / "Library" / "Application Support"
    else:
        root = env.get("XDG_DATA_HOME")
        base = Path(root) if root else user_home / ".local" / "share"

    return base / APP_DIRECTORY_NAME


def default_database_path(**kwargs: object) -> Path:
    """Return the default SQLite file path without creating it."""
    return default_data_directory(**kwargs) / "siegesense.sqlite3"
