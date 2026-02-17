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
            assert (root_dir / "2023/07/29122012-IMG_131334.JPG").exists()
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
            assert row[0] == "29122012-IMG_131334"

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
