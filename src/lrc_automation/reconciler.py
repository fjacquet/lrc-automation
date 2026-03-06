"""Catalog reconciler — fixes AgLibraryFile.folder for found-elsewhere files."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .models import FileAuditResult, MissingFile, ReconcileChange, ReconcileReport
from .utils import generate_uuid
from .validators import CatalogValidator

logger = logging.getLogger(__name__)


class CatalogReconciler:
    """Update catalog folder pointers for files found at a different disk location.

    For each unambiguous ``found_elsewhere`` entry from an audit, the reconciler:

    1. Derives ``pathFromRoot`` from the file's actual disk path relative to its root.
    2. Finds or creates the ``AgLibraryFolder`` row for that path.
    3. Updates ``AgLibraryFile.folder`` to point at the new row.

    No files are moved on disk; only catalog metadata changes.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def reconcile(self) -> ReconcileReport:
        """Run a full audit then fix all unambiguous found-elsewhere files."""
        validator = CatalogValidator(self.conn)
        audit = validator.audit_files_on_disk()
        return self.reconcile_from_audit(audit)

    def reconcile_from_audit(self, audit: FileAuditResult) -> ReconcileReport:
        """Fix catalog pointers using a pre-computed FileAuditResult."""
        report = ReconcileReport()

        # Separate into buckets
        for mf in audit.missing:
            if not mf.found_at:
                report.truly_missing.append(mf)
            elif len(mf.found_at) > 1:
                logger.warning(
                    "SKIP (ambiguous, %d candidates): %s",
                    len(mf.found_at),
                    mf.expected_path,
                )
                report.skipped_ambiguous.append(mf)
            else:
                change = self._reconcile_one(mf)
                if change:
                    report.reconciled.append(change)

        logger.info(
            "Reconcile complete: %d fixed, %d skipped (ambiguous), %d truly missing",
            len(report.reconciled),
            len(report.skipped_ambiguous),
            len(report.truly_missing),
        )
        return report

    def _reconcile_one(self, mf: MissingFile) -> ReconcileChange | None:
        """Fix the catalog pointer for a single unambiguous found-elsewhere file."""
        actual_path = mf.found_at[0]

        # Find which known root contains the actual file
        cursor = self.conn.execute(
            "SELECT id_local, absolutePath FROM AgLibraryRootFolder"
        )
        matched_root_id: int | None = None
        matched_root_path: Path | None = None
        for row in cursor.fetchall():
            root_path = Path(row[1])
            try:
                actual_path.relative_to(root_path)
                matched_root_id = int(row[0])
                matched_root_path = root_path
                break
            except ValueError:
                continue

        if matched_root_id is None or matched_root_path is None:
            logger.warning(
                "Actual path %s is not under any known root; skipping",
                actual_path,
            )
            return None

        # Derive pathFromRoot: directory portion relative to the root
        rel = actual_path.relative_to(matched_root_path)
        path_from_root = rel.parent.as_posix() + "/"
        if path_from_root == "./":
            path_from_root = ""

        # Find or create the AgLibraryFolder row
        new_folder_id = self._find_or_create_folder(matched_root_id, path_from_root)

        # Get current folder id for reporting
        cur2 = self.conn.execute(
            "SELECT folder FROM AgLibraryFile WHERE id_local = ?",
            (mf.file_id,),
        )
        row2 = cur2.fetchone()
        old_folder_id: int = row2[0] if row2 else 0

        # Update the catalog pointer
        self.conn.execute(
            "UPDATE AgLibraryFile SET folder = ? WHERE id_local = ?",
            (new_folder_id, mf.file_id),
        )

        logger.info("RECONCILE %s  →  %s", mf.expected_path, actual_path)

        return ReconcileChange(
            file_id=mf.file_id,
            old_folder_id=old_folder_id,
            new_folder_id=new_folder_id,
            actual_path=actual_path,
            expected_path=mf.expected_path,
        )

    def _find_or_create_folder(self, root_folder_id: int, path_from_root: str) -> int:
        """Return id_local for (root_folder_id, path_from_root), creating if needed."""
        cursor = self.conn.execute(
            "SELECT id_local FROM AgLibraryFolder "
            "WHERE rootFolder = ? AND pathFromRoot = ?",
            (root_folder_id, path_from_root),
        )
        row = cursor.fetchone()
        if row:
            return int(row[0])

        # Create a new row
        cursor2 = self.conn.execute("SELECT MAX(id_local) FROM AgLibraryFolder")
        next_id = (cursor2.fetchone()[0] or 0) + 1
        folder_uuid = generate_uuid()
        self.conn.execute(
            "INSERT INTO AgLibraryFolder "
            "(id_local, id_global, pathFromRoot, rootFolder) "
            "VALUES (?, ?, ?, ?)",
            (next_id, folder_uuid, path_from_root, root_folder_id),
        )
        logger.debug("Created AgLibraryFolder id=%d path=%r", next_id, path_from_root)
        return next_id
