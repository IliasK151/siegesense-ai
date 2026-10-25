"""Resolve the default local data directory without creating it at import time."""

from __future__ import annotations

import os
from pathlib import Path


def default_data_directory() -> Path:
    """Return a platform-appropriate user data directory."""
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "SiegeSenseAI"
    return Path.home() / ".siegesense_ai"
