"""Pre-flight and post-flight catalog integrity validators."""

import sqlite3
from pathlib import Path

from .models import ChangeType, FileChange


class CatalogValidator:
    """Validates catalog integrity before and after changes."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def preflight_check(self) -> list[str]:
        """Run before any changes. Returns list of warnings."""
        warnings: list[str] = []

        # SQLite integrity check
        cursor = self.conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result != "ok":
            warnings.append(f"SQLite integrity check failed: {result}")

        # Check for orphan file records (files with no image)
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM AgLibraryFile f
            LEFT JOIN Adobe_images img ON img.rootFile = f.id_local
            WHERE img.id_local IS NULL
        """)
        orphan_count = cursor.fetchone()[0]
        if orphan_count > 0:
            warnings.append(
                f"Found {orphan_count} orphan file records (no image reference)"
            )

        # Check for broken folder references
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM AgLibraryFile f
            LEFT JOIN AgLibraryFolder fld ON f.folder = fld.id_local
            WHERE fld.id_local IS NULL
        """)
        broken_folder_refs = cursor.fetchone()[0]
        if broken_folder_refs > 0:
            warnings.append(
                f"Found {broken_folder_refs} files with broken folder references"
            )

        return warnings

    def postflight_check(self, succeeded: list["FileChange"]) -> list[str]:
        """Run after changes. Verify committed moves/renames exist on disk."""
        warnings: list[str] = []

        # Verify all committed changes exist at new locations
        for change in succeeded:
            if change.change_type == ChangeType.MOVE_PHOTO:
                base = change.new_name or change.photo.base_name
                new_path = (
                    Path(change.photo.root_absolute_path)
                    / (change.target_folder_path or "")
                    / f"{base}.{change.photo.extension}"
                )
                if not new_path.exists():
                    warnings.append(f"Moved file not found at: {new_path}")

            elif change.change_type == ChangeType.RENAME_FILE:
                new_path = (
                    Path(change.photo.root_absolute_path)
                    / change.photo.current_folder_path
                    / f"{change.new_name}.{change.photo.extension}"
                )
                if not new_path.exists():
                    warnings.append(f"Renamed file not found at: {new_path}")

        # Check for duplicate files in same folder
        cursor = self.conn.execute("""
            SELECT baseName, extension, folder, COUNT(*) as cnt
            FROM AgLibraryFile
            GROUP BY baseName, extension, folder
            HAVING cnt > 1
        """)
        for row in cursor:
            warnings.append(
                f"Duplicate in folder {row[2]}: {row[0]}.{row[1]} ({row[3]} copies)"
            )

        # SQLite integrity check
        cursor = self.conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result != "ok":
            warnings.append(f"Post-flight SQLite integrity check failed: {result}")

        return warnings

    def check_files_exist_on_disk(self) -> list[str]:
        """Verify every catalog file actually exists at its computed path."""
        warnings: list[str] = []
        cursor = self.conn.execute("""
            SELECT
                rf.absolutePath,
                fld.pathFromRoot,
                f.baseName,
                f.extension
            FROM AgLibraryFile f
            JOIN AgLibraryFolder fld ON f.folder = fld.id_local
            JOIN AgLibraryRootFolder rf ON fld.rootFolder = rf.id_local
        """)
        missing = 0
        for row in cursor:
            full_path = Path(row[0]) / row[1] / f"{row[2]}.{row[3]}"
            if not full_path.exists():
                missing += 1
                if missing <= 20:
                    warnings.append(f"Missing file: {full_path}")

        if missing > 20:
            warnings.append(f"... and {missing - 20} more missing files")

        if missing > 0:
            warnings.insert(0, f"Total missing files: {missing}")

        return warnings
