"""Pre-flight and post-flight catalog integrity validators."""

import logging
import sqlite3
from collections import defaultdict
from pathlib import Path

from .models import ChangePlan, ChangeType, FileAuditResult, FileChange, MissingFile


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

    def preflight_plan_check(self, plan: ChangePlan) -> list[str]:
        """Verify all source files in the plan exist on disk before execution.

        Returns missing source paths. Callers should show these to the user
        and decide whether to abort or proceed (the executor will skip them
        via SkippableError, but this surfaces all issues upfront).
        """
        missing: list[str] = []
        for change in plan.changes:
            photo = change.photo
            if change.change_type == ChangeType.MOVE_PHOTO:
                src = photo.full_path
            else:
                folder = Path(photo.root_absolute_path) / photo.current_folder_path
                src = folder / f"{change.old_name}.{photo.extension}"
            if not src.exists():
                missing.append(str(src))
        return missing

    def postflight_check(self, succeeded: list["FileChange"]) -> list[str]:
        """Run after changes. Verify committed moves/renames exist on disk."""
        warnings: list[str] = []

        # Verify all committed changes exist at new locations
        for change in succeeded:
            if change.change_type == ChangeType.MOVE_PHOTO:
                base = change.new_name or change.photo.base_name
                dest_root = (
                    change.target_root_absolute_path
                    or change.photo.root_absolute_path
                )
                new_path = (
                    Path(dest_root)
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

    def check_year_in_year(self) -> list[str]:
        """Find photos whose root folder year differs from the year in pathFromRoot.

        Example: a 2003 photo imported in 2022 may reside at
          absolutePath = '/Lightroom/2022/'  pathFromRoot = '2003/12/'
        These are physically in the wrong yearly root folder on disk.
        """
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
        count = 0
        for row in cursor:
            root_absolute_path: str = row[0]
            path_from_root: str = row[1]
            root_year_str = root_absolute_path.rstrip("/").split("/")[-1]
            if not root_year_str.isdigit():
                continue
            path_year_str = path_from_root.split("/")[0]
            if not path_year_str.isdigit():
                continue
            if root_year_str != path_year_str and 1900 <= int(path_year_str) <= 2100:
                count += 1
                if count <= 20:
                    full_path = f"{root_absolute_path}{path_from_root}{row[2]}.{row[3]}"
                    warnings.append(f"Year-in-year: {full_path}")

        if count > 20:
            warnings.append(f"... and {count - 20} more year-in-year files")
        if count > 0:
            warnings.insert(0, f"Total year-in-year files: {count}")
        return warnings

    def audit_files_on_disk(self) -> FileAuditResult:
        """Full disk audit: check every catalog record, search parent for missing files.

        Algorithm:
        1. Fetch all (absolutePath, pathFromRoot, baseName, extension) from DB.
        2. Check each expected full path on disk — collect missing rows.
        3. For each unique parent of missing root folders, run ONE rglob pass to
           build a filename → [paths] index. This avoids O(N²) searches.
        4. Look up each missing file in the index; record where it was found.
        """
        logger = logging.getLogger(__name__)

        rows = self.conn.execute(
            """
            SELECT
                rf.id_local  AS root_id,
                f.id_local   AS file_id,
                rf.absolutePath,
                fld.pathFromRoot,
                f.baseName,
                f.extension
            FROM AgLibraryFile f
            JOIN AgLibraryFolder fld ON f.folder = fld.id_local
            JOIN AgLibraryRootFolder rf ON fld.rootFolder = rf.id_local
            """
        ).fetchall()

        logger.info("Auditing %d catalog records against disk", len(rows))

        missing_rows = [
            row
            for row in rows
            if not (Path(row[2]) / row[3] / f"{row[4]}.{row[5]}").exists()
        ]
        logger.info(
            "%d files present, %d missing",
            len(rows) - len(missing_rows),
            len(missing_rows),
        )

        if not missing_rows:
            return FileAuditResult(total_checked=len(rows), missing=[])

        # Build one rglob index per unique parent search directory
        parent_index: dict[Path, dict[str, list[Path]]] = {}
        unique_parents = {_search_parent(Path(r[2])) for r in missing_rows}
        for parent in sorted(unique_parents):
            if not parent.exists():
                logger.warning(
                    "Search root not accessible (volume unmounted?): %s", parent
                )
                parent_index[parent] = {}
                continue
            logger.info("Indexing %s for missing-file search …", parent)
            idx: dict[str, list[Path]] = defaultdict(list)
            for p in parent.rglob("*"):
                if p.is_file():
                    idx[p.name].append(p)
            parent_index[parent] = idx
            total = sum(len(v) for v in idx.values())
            logger.info("Indexed %d files under %s", total, parent)

        missing_files: list[MissingFile] = []
        for row in missing_rows:
            filename = f"{row[4]}.{row[5]}"
            parent = _search_parent(Path(row[2]))
            found_at = list(parent_index.get(parent, {}).get(filename, []))
            mf = MissingFile(
                expected_path=Path(row[2]) / row[3] / filename,
                base_name=row[4],
                extension=row[5],
                root_folder_id=row[0],
                file_id=row[1],
                found_at=found_at,
            )
            if found_at:
                logger.warning(
                    "MISSING (found at %s): %s",
                    found_at[0] if len(found_at) == 1 else f"{len(found_at)} locations",
                    mf.expected_path,
                )
            else:
                logger.warning("MISSING (not found anywhere): %s", mf.expected_path)
            missing_files.append(mf)

        return FileAuditResult(total_checked=len(rows), missing=missing_files)


def _search_parent(root_path: Path) -> Path:
    """Return the directory to rglob when searching for a missing file.

    For a per-year root like ``/Volumes/photo/2023/`` this returns
    ``/Volumes/photo/`` so sibling year-roots are also searched.
    Falls back to the root itself when it has no parent (filesystem root).
    """
    parent = root_path.parent
    return parent if parent != root_path else root_path
