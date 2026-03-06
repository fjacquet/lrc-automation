"""Tests for CatalogReconciler."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.conftest import SCHEMA_SQL


def _make_catalog(
    tmp_path: Path,
    root_abs: str,
    folder_path: str,
    filename: str,
) -> Path:
    """Create a minimal catalog with one photo record."""
    db_path = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        "INSERT INTO AgLibraryRootFolder VALUES (1,'ROOT-UUID',?,'root','../root')",
        (root_abs,),
    )
    conn.execute(
        "INSERT INTO AgLibraryFolder VALUES (1,'FOLD-UUID',?,1)",
        (folder_path,),
    )
    base, ext = filename.rsplit(".", 1)
    conn.execute(
        "INSERT INTO AgLibraryFile VALUES (1,'FILE-UUID',?,?,1,?,NULL,NULL,?,NULL)",
        (base, ext, base, filename),
    )
    conn.execute(
        "INSERT INTO Adobe_images VALUES (1,'IMG-UUID','2023-06-15T10:00:00',"
        "1,'JPG',0,0,'AB',NULL,NULL)"
    )
    conn.commit()
    conn.close()
    return db_path


class TestCatalogReconciler:
    """Tests for CatalogReconciler.reconcile_from_audit()."""

    def test_reconcile_found_elsewhere(self, tmp_path: Path) -> None:
        """Single found_elsewhere entry → folder pointer updated in DB.

        The file was moved from root/06/ to root/07/ (same root, different month),
        which is the common case after a wrong-location apply run.
        """
        from lrc_automation.models import FileAuditResult, MissingFile
        from lrc_automation.reconciler import CatalogReconciler

        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)
        # File actually lives in a different subfolder of the same root
        actual_dir = root_dir / "07"
        actual_dir.mkdir(parents=True)
        actual_file = actual_dir / "IMG_MOVED.JPG"
        actual_file.write_text("photo")

        db = _make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder_path="06/",
            filename="IMG_MOVED.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        expected_path = root_dir / "06" / "IMG_MOVED.JPG"
        mf = MissingFile(
            expected_path=expected_path,
            base_name="IMG_MOVED",
            extension="JPG",
            root_folder_id=1,
            file_id=1,
            found_at=[actual_file],
        )
        audit = FileAuditResult(total_checked=1, missing=[mf])

        reconciler = CatalogReconciler(conn)
        conn.execute("BEGIN IMMEDIATE")
        report = reconciler.reconcile_from_audit(audit)
        conn.commit()

        assert len(report.reconciled) == 1
        assert len(report.skipped_ambiguous) == 0
        assert len(report.truly_missing) == 0

        # Verify DB was updated: AgLibraryFile.folder points to the new folder row
        row = conn.execute(
            "SELECT folder FROM AgLibraryFile WHERE id_local = 1"
        ).fetchone()
        assert row is not None
        new_folder_id = row[0]
        folder_row = conn.execute(
            "SELECT pathFromRoot FROM AgLibraryFolder WHERE id_local = ?",
            (new_folder_id,),
        ).fetchone()
        assert folder_row is not None
        assert folder_row[0] == "07/"
        conn.close()

    def test_reconcile_ambiguous_skipped(self, tmp_path: Path) -> None:
        """Multiple found_at candidates → entry goes into skipped_ambiguous."""
        from lrc_automation.models import FileAuditResult, MissingFile
        from lrc_automation.reconciler import CatalogReconciler

        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)
        actual1 = tmp_path / "2022" / "06" / "IMG_AMB.JPG"
        actual2 = tmp_path / "2021" / "06" / "IMG_AMB.JPG"
        actual1.parent.mkdir(parents=True)
        actual2.parent.mkdir(parents=True)
        actual1.write_text("copy1")
        actual2.write_text("copy2")

        db = _make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder_path="06/",
            filename="IMG_AMB.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        mf = MissingFile(
            expected_path=root_dir / "06" / "IMG_AMB.JPG",
            base_name="IMG_AMB",
            extension="JPG",
            root_folder_id=1,
            file_id=1,
            found_at=[actual1, actual2],
        )
        audit = FileAuditResult(total_checked=1, missing=[mf])

        reconciler = CatalogReconciler(conn)
        conn.execute("BEGIN IMMEDIATE")
        report = reconciler.reconcile_from_audit(audit)
        conn.commit()

        assert len(report.reconciled) == 0
        assert len(report.skipped_ambiguous) == 1
        assert len(report.truly_missing) == 0

        # DB must NOT have been changed
        row = conn.execute(
            "SELECT folder FROM AgLibraryFile WHERE id_local = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 1  # still original folder id
        conn.close()

    def test_reconcile_truly_missing_untouched(self, tmp_path: Path) -> None:
        """Truly missing file → nothing in DB changes, ends in truly_missing."""
        from lrc_automation.models import FileAuditResult, MissingFile
        from lrc_automation.reconciler import CatalogReconciler

        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)

        db = _make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder_path="06/",
            filename="GONE.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        mf = MissingFile(
            expected_path=root_dir / "06" / "GONE.JPG",
            base_name="GONE",
            extension="JPG",
            root_folder_id=1,
            file_id=1,
            found_at=[],
        )
        audit = FileAuditResult(total_checked=1, missing=[mf])

        reconciler = CatalogReconciler(conn)
        conn.execute("BEGIN IMMEDIATE")
        report = reconciler.reconcile_from_audit(audit)
        conn.commit()

        assert len(report.reconciled) == 0
        assert len(report.skipped_ambiguous) == 0
        assert len(report.truly_missing) == 1

        row = conn.execute(
            "SELECT folder FROM AgLibraryFile WHERE id_local = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 1  # unchanged
        conn.close()

    def test_reconcile_one_writes_forward_slash_path_from_root(
        self,
        tmp_path: Path,
    ) -> None:
        """_reconcile_one stores pathFromRoot with forward slashes (PROC-02)."""
        # Verify contract: rel.parent.as_posix() always yields forward slashes
        rel = Path("2023/06/photo.jpg")
        assert rel.parent.as_posix() + "/" == "2023/06/"
        # Negative: str() on Windows would yield backslashes
        # (on POSIX str == as_posix, but the code must use as_posix explicitly)
        from lrc_automation import reconciler as rec_mod
        import inspect

        src = inspect.getsource(rec_mod)
        assert "as_posix()" in src, (
            "reconciler.py must use .as_posix() for pathFromRoot, not str()"
        )

    def test_reconcile_creates_new_folder_row(self, tmp_path: Path) -> None:
        """Actual path maps to a folder not in AgLibraryFolder → new row created."""
        from lrc_automation.models import FileAuditResult, MissingFile
        from lrc_automation.reconciler import CatalogReconciler

        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)
        # Actual file is in an entirely new subfolder not yet in the catalog
        new_dir = root_dir / "07"
        new_dir.mkdir(parents=True)
        actual_file = new_dir / "IMG_NEW_FOLDER.JPG"
        actual_file.write_text("photo")

        db = _make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder_path="06/",
            filename="IMG_NEW_FOLDER.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        # Confirm only one folder row before reconcile
        before = conn.execute("SELECT COUNT(*) FROM AgLibraryFolder").fetchone()[0]
        assert before == 1

        mf = MissingFile(
            expected_path=root_dir / "06" / "IMG_NEW_FOLDER.JPG",
            base_name="IMG_NEW_FOLDER",
            extension="JPG",
            root_folder_id=1,
            file_id=1,
            found_at=[actual_file],
        )
        audit = FileAuditResult(total_checked=1, missing=[mf])

        reconciler = CatalogReconciler(conn)
        conn.execute("BEGIN IMMEDIATE")
        report = reconciler.reconcile_from_audit(audit)
        conn.commit()

        assert len(report.reconciled) == 1

        # A new AgLibraryFolder row must have been created
        after = conn.execute("SELECT COUNT(*) FROM AgLibraryFolder").fetchone()[0]
        assert after == 2

        # The new folder row should have pathFromRoot = "07/"
        new_row = conn.execute(
            "SELECT pathFromRoot FROM AgLibraryFolder WHERE id_local != 1"
        ).fetchone()
        assert new_row is not None
        assert new_row[0] == "07/"
        conn.close()
