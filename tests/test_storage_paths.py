"""Platform data-path resolution tests."""

from pathlib import Path

from siegesense.storage.paths import default_data_directory, default_database_path


def test_windows_prefers_local_app_data() -> None:
    result = default_data_directory(
        environ={"LOCALAPPDATA": "C:/Users/Test/AppData/Local", "APPDATA": "C:/Users/Test/AppData/Roaming"},
        home=Path("C:/Users/Test"),
        platform="win32",
    )
    assert result == Path("C:/Users/Test/AppData/Local/SiegeSenseAI")


def test_windows_falls_back_to_home_when_environment_is_missing() -> None:
    result = default_data_directory(environ={}, home=Path("C:/Users/Test"), platform="win32")
    assert result == Path("C:/Users/Test/AppData/Local/SiegeSenseAI")


def test_macos_uses_application_support() -> None:
    result = default_data_directory(environ={}, home=Path("/Users/test"), platform="darwin")
    assert result == Path("/Users/test/Library/Application Support/SiegeSenseAI")


def test_linux_respects_xdg_data_home() -> None:
    result = default_data_directory(environ={"XDG_DATA_HOME": "/tmp/test-data"}, home=Path("/home/test"), platform="linux")
    assert result == Path("/tmp/test-data/SiegeSenseAI")


def test_linux_uses_xdg_default_when_unset() -> None:
    result = default_data_directory(environ={}, home=Path("/home/test"), platform="linux")
    assert result == Path("/home/test/.local/share/SiegeSenseAI")


def test_default_database_path_does_not_create_files(tmp_path: Path) -> None:
    target = default_database_path(environ={"XDG_DATA_HOME": str(tmp_path / "data")}, home=tmp_path, platform="linux")
    assert target == tmp_path / "data" / "SiegeSenseAI" / "siegesense.sqlite3"
    assert not target.parent.exists()
