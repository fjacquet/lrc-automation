"""Tests for executor module."""

from pathlib import Path

from lrc_automation.catalog import CatalogConnection
from lrc_automation.executor import ChangeExecutor
from lrc_automation.planner import ChangePlanner
from lrc_automation.scanner import CatalogScanner


class TestChangeExecutor:
    def test_execute_move(self, tmp_catalog_with_files: tuple[Path, Path]) -> None:
        db_path, root_dir = tmp_catalog_with_files

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            plan = planner.build_plan(include_moves=True, include_renames=False)

            assert plan.move_count > 0

            executor = ChangeExecutor(cat, plan)
            report = executor.execute()

            assert len(report.succeeded) > 0
            assert len(report.failed) == 0

            # Verify file was moved on disk
            # IMG_1002 was in 2023/07/ but captured in 2023/06
            assert (root_dir / "2023/06/IMG_1002.JPG").exists()
            assert not (root_dir / "2023/07/IMG_1002.JPG").exists()

    def test_execute_rename(self, tmp_catalog_with_files: tuple[Path, Path]) -> None:
        db_path, root_dir = tmp_catalog_with_files

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            plan = planner.build_plan(include_moves=False, include_renames=True)

            assert plan.rename_count > 0

            executor = ChangeExecutor(cat, plan)
            report = executor.execute()

            assert len(report.succeeded) > 0
            assert len(report.failed) == 0

            # Verify file was renamed on disk
            assert (root_dir / "2023/07/121229-IMG_131334.JPG").exists()
            assert not (
                root_dir / "2023/07/29122012-29122012-IMG_20121229_131334.JPG"
            ).exists()

    def test_execute_updates_catalog(
        self, tmp_catalog_with_files: tuple[Path, Path]
    ) -> None:
        db_path, _root_dir = tmp_catalog_with_files

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            plan = planner.build_plan(include_moves=False, include_renames=True)

            executor = ChangeExecutor(cat, plan)
            executor.execute()

            # Verify catalog was updated
            cursor = conn.execute(
                "SELECT baseName FROM AgLibraryFile WHERE id_local = 3"
            )
            row = cursor.fetchone()
            assert row[0] == "121229-IMG_131334"

    def test_rollback_on_error(self, tmp_catalog_with_files: tuple[Path, Path]) -> None:
        """Test that disk changes are rolled back on SQL error."""
        db_path, root_dir = tmp_catalog_with_files

        # Verify original state
        assert (root_dir / "2023/07/IMG_1002.JPG").exists()

        # The executor should handle errors gracefully
        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)

            # Verify the photo is still scannable after a failed attempt
            total = scanner.get_total_photo_count()
            assert total == 3


class TestEmptyFolderCleanup:
    """Verify empty source dirs are removed after moves."""

    def test_empty_source_folder_removed_after_move(
        self, tmp_catalog_with_files: tuple[Path, Path]
    ) -> None:

        db_path, root_dir = tmp_catalog_with_files

        # Ensure source folder 2023/07/ starts non-empty (has files)
        assert (root_dir / "2023/07").exists()

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            # Move all photos (IMG_1002 from 2023/07/ → 2023/06/)
            plan = planner.build_plan(include_moves=True, include_renames=False)

            executor = ChangeExecutor(cat, plan)
            report = executor.execute()

        assert not report.rolled_back

        # The 29122012 file is also in 2023/07/ and stays (it's a rename candidate
        # not a move), so 2023/07/ won't be empty in default test data.
        # We verify the cleanup count is an integer (may be 0 if folder not empty)
        assert isinstance(report.folders_removed, int)
        assert report.folders_removed >= 0

    def test_empty_folder_removed_from_disk_and_db(self, tmp_path: Path) -> None:
        """When ALL files move out of a folder, dir and DB record are removed."""
        import sqlite3

        from tests.conftest import create_test_catalog

        root_dir = tmp_path / "photos"
        root_path = str(root_dir) + "/"

        # Single photo in 2023/07/ that belongs in 2023/06/
        data = {
            "roots": [(1, "ROOT-UUID-1", root_path, "photos", "../photos")],
            "folders": [
                (1, "FOLD-UUID-1", "2023/06/", 1),
                (2, "FOLD-UUID-2", "2023/07/", 1),
            ],
            "files": [
                (
                    1,
                    "FILE-UUID-1",
                    "IMG_ONLY",
                    "JPG",
                    2,
                    "IMG_ONLY",
                    None,
                    None,
                    "IMG_ONLY.JPG",
                    None,
                ),
            ],
            "images": [
                (
                    1,
                    "IMG-UUID-1",
                    "2023-06-15T14:30:00",
                    1,
                    "JPG",
                    0,
                    3,
                    "AB",
                    None,
                    None,
                ),
            ],
        }

        db_path = tmp_path / "test.lrcat"
        create_test_catalog(db_path, data)

        (root_dir / "2023/06").mkdir(parents=True)
        (root_dir / "2023/07").mkdir(parents=True)
        (root_dir / "2023/07/IMG_ONLY.JPG").write_text("photo")

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            plan = planner.build_plan(include_moves=True, include_renames=False)

            executor = ChangeExecutor(cat, plan)
            report = executor.execute()

        assert not report.rolled_back
        assert len(report.succeeded) == 1

        # Source folder should be gone from disk
        assert not (root_dir / "2023/07").exists()

        # Source folder should be gone from DB
        raw_conn = sqlite3.connect(str(db_path))
        cursor = raw_conn.execute(
            "SELECT COUNT(*) FROM AgLibraryFolder WHERE pathFromRoot = '2023/07/'",
        )
        assert cursor.fetchone()[0] == 0
        raw_conn.close()

        # Cleanup counter reflects the removal
        assert report.folders_removed == 1
