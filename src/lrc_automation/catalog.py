"""Lightroom Classic catalog connection and safety management."""

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import psutil

from .constants import LOCK_FILE_SUFFIX, LR_PROCESS_NAME, LR_PROCESS_NAME_WINDOWS


def _path_to_sqlite_uri(path: Path, readonly: bool = False) -> str:
    """Build a SQLite URI that works on Windows and macOS.

    Windows: Path("C:/Users/foo/bar.lrcat").as_posix() -> "C:/Users/foo/bar.lrcat"
    URI:     file:///C:/Users/foo/bar.lrcat?mode=ro

    macOS:   Path("/Volumes/photo/bar.lrcat").as_posix() -> "/Volumes/photo/bar.lrcat"
    URI:     file:////Volumes/photo/bar.lrcat?mode=ro
    SQLite URI spec s.3.1: extra leading slashes after file: are valid.

    The is_absolute() check is cross-platform: on Windows a drive-letter path is
    absolute; POSIX-style paths (/...) and Windows drive letters (X:/...) are also
    detected so that macOS-origin absolutePaths work correctly on all platforms.
    """
    posix = path.as_posix()
    # Detect absolute paths: POSIX absolute (/...) or Windows drive letter (X:/...)
    has_drive = len(posix) >= 3 and posix[1] == ":" and posix[2] == "/"
    is_abs = path.is_absolute() or has_drive or posix.startswith("/")
    uri = f"file:///{posix}" if is_abs else f"file:{posix}"
    if readonly:
        uri += "?mode=ro"
    return uri


class CatalogError(Exception):
    """Base exception for catalog errors."""


class LightroomRunningError(CatalogError):
    """Raised when Lightroom is running and catalog is locked."""


class CatalogConnection:
    """Manages connection to a Lightroom Classic .lrcat catalog."""

    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path.resolve()
        self.conn: sqlite3.Connection | None = None

    def validate_is_lrcat(self) -> None:
        """Verify the file exists and is a valid .lrcat catalog."""
        if not self.catalog_path.exists():
            raise CatalogError(f"Catalog not found: {self.catalog_path}")
        if self.catalog_path.suffix.lower() != ".lrcat":
            raise CatalogError(f"Not a .lrcat file: {self.catalog_path}")

        # Quick check: try to open and verify expected tables exist
        conn = sqlite3.connect(
            _path_to_sqlite_uri(self.catalog_path, readonly=True), uri=True
        )
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='Adobe_images'"
            )
            if cursor.fetchone() is None:
                raise CatalogError(
                    "Not a valid Lightroom catalog "
                    f"(missing Adobe_images): {self.catalog_path}"
                )
            if sys.platform == "win32":
                cursor2 = conn.execute(
                    "SELECT absolutePath FROM AgLibraryRootFolder LIMIT 10"
                )
                for row in cursor2:
                    abs_path = row[0] or ""
                    if "/Volumes/" in abs_path:
                        raise CatalogError(
                            f"This catalog was created on macOS "
                            f"(root folder path '{abs_path}' contains '/Volumes/').\n"
                            "Open the catalog in Lightroom Classic on Windows first "
                            "so it can update all folder paths, then retry."
                        )
        finally:
            conn.close()

    def check_lightroom_not_running(self) -> None:
        """Verify Lightroom is not running and catalog is not locked.

        Uses psutil.process_iter for cross-platform process detection.
        Detects 'Adobe Lightroom Classic' (macOS) and 'Lightroom.exe' (Windows).

        Note: WAL mode is NOT enabled here. WAL mode must NOT be enabled on
        Windows (file-locking semantics differ); the lock-file + process check
        is the correct write-safety mechanism on all platforms.
        """
        lock_path = Path(str(self.catalog_path) + LOCK_FILE_SUFFIX)
        if lock_path.exists():
            raise LightroomRunningError(
                f"Catalog is locked (found {lock_path.name}). Close Lightroom first."
            )

        lr_names = {LR_PROCESS_NAME, LR_PROCESS_NAME_WINDOWS}
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.info["name"] in lr_names:
                        raise LightroomRunningError(
                            "Lightroom Classic appears to be running. "
                            "Close it before modifying the catalog."
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except LightroomRunningError:
            raise
        except Exception:
            pass  # psutil unavailable or OS error — fall through

    def backup(self, backup_dir: Path | None = None) -> Path:
        """Create a timestamped backup of the catalog.

        Returns the path to the backup file.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target_dir = backup_dir or self.catalog_path.parent

        if not target_dir.exists():
            raise CatalogError(f"Backup directory does not exist: {target_dir}")
        if not target_dir.is_dir():
            raise CatalogError(f"Backup path is not a directory: {target_dir}")

        backup_name = f"{self.catalog_path.stem}.lrcat.bak-{timestamp}"
        backup_path = target_dir / backup_name

        shutil.copy2(self.catalog_path, backup_path)

        # Also backup .lrcat-data if it exists (previews/smart previews DB)
        data_path = Path(str(self.catalog_path) + "-data")
        if data_path.exists():
            shutil.copytree(
                data_path, target_dir / f"{backup_name}-data", dirs_exist_ok=True
            )

        return backup_path

    def open(self, readonly: bool = False) -> sqlite3.Connection:
        """Open SQLite connection to the catalog."""
        if self.conn is not None:
            return self.conn

        if readonly:
            self.conn = sqlite3.connect(
                _path_to_sqlite_uri(self.catalog_path, readonly=True), uri=True
            )
        else:
            self.conn = sqlite3.connect(str(self.catalog_path))

        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self) -> None:
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def get_schema_version(self) -> str | None:
        """Read schema version from Adobe_variablesTable."""
        conn = self.open(readonly=True)
        try:
            cursor = conn.execute(
                "SELECT value FROM Adobe_variablesTable WHERE name = 'Adobe_DBVersion'"
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.OperationalError:
            return None

    def __enter__(self) -> "CatalogConnection":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
