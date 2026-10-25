"""End-to-end source startup smoke test for the desktop entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_application_smoke_test_initializes_window_and_local_database(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["LOCALAPPDATA"] = str(tmp_path / "local-app-data")
    environment["APPDATA"] = str(tmp_path / "roaming-app-data")
    environment["XDG_DATA_HOME"] = str(tmp_path / "xdg-data")
    environment["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        [sys.executable, str(repository_root / "main.py"), "--smoke-test"],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        "Application smoke test failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
