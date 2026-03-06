"""Tests for catalog.py path-safety fixes (PATH-01 and PATH-03)."""

import sqlite3
import sys
from pathlib import Path
from typing import ClassVar

import pytest

from lrc_automation.catalog import (
    CatalogConnection,
    CatalogError,
    LightroomRunningError,
    _path_to_sqlite_uri,
)
from tests.conftest import create_test_catalog

# ---------------------------------------------------------------------------
# PATH-01: _path_to_sqlite_uri correctness
# ---------------------------------------------------------------------------


def test_path_to_sqlite_uri_windows_style() -> None:
    """Windows path: URI has no backslash, file:/// prefix, ends with ?mode=ro."""
    path = Path("C:/Users/Photos/Catalog.lrcat")
    uri = _path_to_sqlite_uri(path, readonly=True)
    assert "\\" not in uri
    assert uri.startswith("file:///")
    assert uri.endswith("?mode=ro")


def test_path_to_sqlite_uri_posix_absolute() -> None:
    """POSIX absolute path must start with file:/// and contain ?mode=ro."""
    path = Path("/Volumes/photo/Catalog.lrcat")
    uri = _path_to_sqlite_uri(path, readonly=True)
    assert uri.startswith("file:///")
    assert "?mode=ro" in uri


def test_path_to_sqlite_uri_readonly_false() -> None:
    """When readonly=False, the URI must NOT contain ?mode=ro."""
    path = Path("/tmp/test.lrcat")
    uri = _path_to_sqlite_uri(path, readonly=False)
    assert "?mode=ro" not in uri


def test_path_to_sqlite_uri_is_absolute_prefix() -> None:
    """Any absolute path must produce a URI that starts with file:///."""
    path = Path("/some/absolute/path/catalog.lrcat")
    assert path.is_absolute()
    uri = _path_to_sqlite_uri(path, readonly=False)
    assert uri.startswith("file:///")


# ---------------------------------------------------------------------------
# Suffix case-insensitivity fix (PATH-01 sub-requirement)
# ---------------------------------------------------------------------------


def test_validate_is_lrcat_accepts_uppercase_extension(tmp_path: Path) -> None:
    """.LRCAT (uppercase) must be accepted by validate_is_lrcat() without raising."""
    # Create a valid catalog with lowercase extension first
    lower_path = tmp_path / "test.lrcat"
    create_test_catalog(lower_path)

    # Rename to uppercase extension
    upper_path = tmp_path / "test.LRCAT"
    lower_path.rename(upper_path)

    cc = CatalogConnection(upper_path)
    # Must NOT raise — .suffix.lower() check must accept .LRCAT
    cc.validate_is_lrcat()


# ---------------------------------------------------------------------------
# PATH-03: Mac-origin catalog detection on Windows
# ---------------------------------------------------------------------------


def test_mac_origin_catalog_warns_monkeypatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On win32, validate_is_lrcat() raises CatalogError for /Volumes/ absolutePath."""
    db_path = tmp_path / "mac_catalog.lrcat"
    create_test_catalog(db_path)

    # Update the root folder path to simulate a Mac-origin catalog
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE AgLibraryRootFolder SET absolutePath = '/Volumes/photo/2023/'")
    conn.commit()
    conn.close()

    # Simulate running on Windows
    monkeypatch.setattr(sys, "platform", "win32")

    cc = CatalogConnection(db_path)
    with pytest.raises(CatalogError, match="/Volumes/"):
        cc.validate_is_lrcat()


def test_mac_origin_catalog_ok_on_non_windows(tmp_path: Path) -> None:
    """On non-Windows, validate_is_lrcat() must NOT raise for Mac-origin catalogs."""
    db_path = tmp_path / "mac_catalog_ok.lrcat"
    create_test_catalog(db_path)

    # Update the root folder path to simulate a Mac-origin catalog
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE AgLibraryRootFolder SET absolutePath = '/Volumes/photo/2023/'")
    conn.commit()
    conn.close()

    # Do NOT monkeypatch sys.platform — leave it as darwin/linux
    cc = CatalogConnection(db_path)
    # Must NOT raise on non-Windows
    cc.validate_is_lrcat()


# ---------------------------------------------------------------------------
# PROC-01: psutil cross-platform Lightroom process detection
# ---------------------------------------------------------------------------


def test_check_lightroom_running_detects_macos_process(
    tmp_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """psutil finds 'Adobe Lightroom Classic' — raises LightroomRunningError."""
    import psutil

    class FakeProc:
        info: ClassVar[dict[str, str]] = {"name": "Adobe Lightroom Classic"}

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([FakeProc()]))
    conn = CatalogConnection(tmp_catalog)
    with pytest.raises(LightroomRunningError):
        conn.check_lightroom_not_running()


def test_check_lightroom_running_detects_windows_process(
    tmp_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """psutil finds 'Lightroom.exe' — raises LightroomRunningError."""
    import psutil

    class FakeProc:
        info: ClassVar[dict[str, str]] = {"name": "Lightroom.exe"}

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([FakeProc()]))
    conn = CatalogConnection(tmp_catalog)
    with pytest.raises(LightroomRunningError):
        conn.check_lightroom_not_running()


def test_check_lightroom_running_tolerates_access_denied(
    tmp_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AccessDenied during process_iter is silently skipped — no crash."""
    import psutil

    class DeniedProc:
        @property
        def info(self) -> dict[str, str]:
            raise psutil.AccessDenied(pid=99)

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([DeniedProc()]))
    conn = CatalogConnection(tmp_catalog)
    conn.check_lightroom_not_running()  # must not raise
