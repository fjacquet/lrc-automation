"""Tests for planner module."""

import sqlite3
from pathlib import Path

from lrc_automation.models import ChangeType
from lrc_automation.planner import ChangePlanner
from lrc_automation.scanner import CatalogScanner


class TestChangePlanner:
    def test_build_plan_moves(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        assert plan.move_count > 0
        assert plan.rename_count == 0
        conn.close()

    def test_build_plan_renames(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=False, include_renames=True)
        assert plan.move_count == 0
        assert plan.rename_count == 1
        # Verify the rename
        rename = plan.changes[0]
        assert rename.change_type == ChangeType.RENAME_FILE
        assert rename.new_name == "29122012-IMG_131334"
        conn.close()

    def test_build_plan_all(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=True, include_renames=True)
        assert plan.move_count > 0
        assert plan.rename_count > 0
        conn.close()

    def test_folders_to_create(self, tmp_catalog: Path) -> None:
        """Moving photo 3 from 2022/12/ to 2012/12/ requires new folder."""
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        # Should need to create 2012/ and 2012/12/ folders
        new_paths = [p for _, p in plan.folders_to_create]
        assert "2012/" in new_paths
        assert "2012/12/" in new_paths
        conn.close()

    def test_no_changes_for_correct_photos(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan()
        # File 1 (correctly placed) should not appear
        move_file_ids = [
            c.photo.file_id
            for c in plan.changes
            if c.change_type == ChangeType.MOVE_PHOTO
        ]
        assert 1 not in move_file_ids
        conn.close()
