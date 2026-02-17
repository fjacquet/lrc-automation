"""Lightroom Classic catalog connection and safety management."""

import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from .constants import LOCK_FILE_SUFFIX, LR_PROCESS_NAME


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
        if self.catalog_path.suffix != ".lrcat":
            raise CatalogError(f"Not a .lrcat file: {self.catalog_path}")

        # Quick check: try to open and verify expected tables exist
        conn = sqlite3.connect(f"file:{self.catalog_path}?mode=ro", uri=True)
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
        finally:
            conn.close()

    def check_lightroom_not_running(self) -> None:
        """Verify Lightroom is not running and catalog is not locked."""
        lock_path = Path(str(self.catalog_path) + LOCK_FILE_SUFFIX)
        if lock_path.exists():
            raise LightroomRunningError(
                f"Catalog is locked (found {lock_path.name}). Close Lightroom first."
            )

        # Check for running Lightroom process on macOS
        try:
            result = subprocess.run(
                ["pgrep", "-f", LR_PROCESS_NAME],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                raise LightroomRunningError(
                    "Lightroom Classic appears to be running. "
                    "Close it before modifying the catalog."
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # pgrep not available or timed out, skip process check

    def backup(self, backup_dir: Path | None = None) -> Path:
        """Create a timestamped backup of the catalog.

        Returns the path to the backup file.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target_dir = backup_dir or self.catalog_path.parent
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
            uri = f"file:{self.catalog_path}?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True)
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
