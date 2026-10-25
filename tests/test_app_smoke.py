"""End-to-end source startup smoke test for the desktop entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import siegesense.app as app_module


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



def test_packaged_smoke_failure_writes_diagnostics(
    tmp_path: Path, monkeypatch,
) -> None:
    log_path = tmp_path / "smoke-error.txt"

    def fail_startup(smoke_test: bool) -> int:
        assert smoke_test
        raise RuntimeError("synthetic startup failure")

    monkeypatch.setattr(app_module, "_run_application", fail_startup)
    monkeypatch.setattr(sys, "argv", ["main.py", "--smoke-test"])
    monkeypatch.setenv("SIEGESENSE_SMOKE_LOG", str(log_path))

    assert app_module.main() == 1
    assert "synthetic startup failure" in log_path.read_text(encoding="utf-8")
