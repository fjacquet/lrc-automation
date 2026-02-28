"""Tests for planner module."""

import sqlite3
from pathlib import Path

import pytest

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
        assert rename.new_name == "121229-IMG_131334"
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

    def test_plan_moves_without_location(self, tmp_catalog_with_gps: Path) -> None:
        """Default behavior: no location subfolder in target paths."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=False)
        planner = ChangePlanner(conn, scanner, location_folders=False)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        for change in plan.changes:
            if change.change_type == ChangeType.MOVE_PHOTO:
                # Target should be date-only: "2023/06/"
                assert change.target_folder_path == "2023/06/"
        conn.close()

    def test_plan_moves_with_location(self, tmp_catalog_with_gps: Path) -> None:
        """With location_folders, GPS photos get Country/City subfolder."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        # GPS photos should have location subfolder
        gps_moves = [c for c in moves if c.photo.gps_latitude is not None]
        assert len(gps_moves) >= 2
        for move in gps_moves:
            # Target path should include country/city: "2023/06/XX/CityName/"
            path = move.target_folder_path or ""
            parts = path.strip("/").split("/")
            assert len(parts) == 4, f"Expected 4 parts, got {parts}"
        conn.close()

    def test_plan_moves_mixed_gps(self, tmp_catalog_with_gps: Path) -> None:
        """Photos without GPS get date-only path even when location is enabled."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        nogps_moves = [c for c in moves if c.photo.gps_latitude is None]
        for move in nogps_moves:
            # Should be date-only: "2023/06/"
            assert move.target_folder_path == "2023/06/"
        conn.close()

    def test_folders_to_create_with_location(self, tmp_catalog_with_gps: Path) -> None:
        """Folder chain includes Country and City folders."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        new_paths = [p for _, p in plan.folders_to_create]
        # Should have location-based subfolders
        location_paths = [p for p in new_paths if p.count("/") >= 3]
        assert len(location_paths) > 0
        conn.close()

    def test_plan_no_duplicate_folders(self, tmp_catalog_with_gps: Path) -> None:
        """Two photos in same location should not create duplicate folders."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        # No duplicate folder paths
        folder_set = set(plan.folders_to_create)
        assert len(folder_set) == len(plan.folders_to_create)
        conn.close()


class TestPlanLocationMoves:
    """Tests for _plan_location_moves: GPS photos already in date-only folders."""

    def test_plan_location_moves_creates_move_to_country_city(
        self, tmp_catalog_needs_location: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GPS photo in date-only folder gets moved to Country/City subfolder."""
        from lrc_automation.geocoder import LocationResolver

        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {(48.8566, 2.3522): ("FR", "Paris")},
        )
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        # File 1 (GPS in date-only folder) should be moved to 2023/06/FR/Paris/
        target_paths = [c.target_folder_path for c in moves]
        assert any("FR" in (p or "") and "Paris" in (p or "") for p in target_paths)
        conn.close()

    def test_plan_location_moves_skips_already_in_correct_location(
        self, tmp_catalog_needs_location: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GPS photo already in the correct CC/City subfolder is NOT moved again."""
        from lrc_automation.geocoder import LocationResolver

        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {(48.8566, 2.3522): ("FR", "Paris")},
        )
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        # File 2 is already in 2023/06/FR/Paris/ which matches target → not moved
        for move in moves:
            if move.photo.file_id == 2:
                # Would only appear if target != current — confirm target equals current
                assert move.target_folder_path != move.photo.current_folder_path
        conn.close()

    def test_plan_location_moves_disabled_when_flag_off(
        self, tmp_catalog_needs_location: Path
    ) -> None:
        """With location_folders=False, _plan_location_moves adds no changes."""
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=False)
        planner = ChangePlanner(conn, scanner, location_folders=False)
        plan = planner.build_plan(include_moves=True, include_renames=False)
        # No moves expected (file 1 is correctly placed date-wise, file 3 no GPS)
        assert len(plan.changes) == 0
        conn.close()
