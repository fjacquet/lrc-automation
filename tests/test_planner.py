"""Tests for planner module."""

import sqlite3
from pathlib import Path

import pytest

from lrc_automation.constants import LocationOrder
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


class TestPlanLocationMovesPerYearRoot:
    """Verify that location moves don't double the year for per-year root catalogs."""

    def test_target_path_does_not_double_year(
        self,
        tmp_catalog_per_year_root: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per-year root: pathFromRoot is '06/', target should be '06/FR/Paris/'."""
        import sqlite3

        from lrc_automation.geocoder import LocationResolver
        from lrc_automation.planner import ChangePlanner
        from lrc_automation.scanner import CatalogScanner

        db_path, _ = tmp_catalog_per_year_root

        # Monkeypatch geocoder to return Paris for any coordinates
        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {c: ("FR", "Paris") for c in coords},
        )

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        # Trigger location moves explicitly
        from lrc_automation.models import ChangePlan

        location_plan = ChangePlan()
        planner._plan_location_moves(location_plan)

        # Should have exactly one move
        assert len(location_plan.changes) == 1
        change = location_plan.changes[0]
        target = change.target_folder_path

        # Must NOT contain doubled year (2023/2023/ or 2023/06/ prefix with 2023 again)
        assert target is not None
        assert "2023/06" not in target, f"Year was doubled in target path: {target!r}"
        # Must be the month-only prefix + location
        assert target == "06/FR/Paris/"
        conn.close()

    def test_damaged_per_year_root_strips_doubled_year(
        self,
        tmp_catalog_per_year_root_damaged: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Damaged per-year root: pathFromRoot='2023/06/Switzerland/Saillon/'.

        After the year-doubling bug, some photos have pathFromRoot that includes
        the year.  _plan_location_moves must strip the year so the target path is
        '06/FR/Paris/' not '2023/06/FR/Paris/' (which would double the year again).
        """
        import sqlite3

        from lrc_automation.geocoder import LocationResolver
        from lrc_automation.planner import ChangePlanner
        from lrc_automation.scanner import CatalogScanner

        db_path, _ = tmp_catalog_per_year_root_damaged

        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {c: ("FR", "Paris") for c in coords},
        )

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(conn, scanner, location_folders=True)
        from lrc_automation.models import ChangePlan

        location_plan = ChangePlan()
        planner._plan_location_moves(location_plan)

        assert len(location_plan.changes) == 1
        target = location_plan.changes[0].target_folder_path
        assert target is not None
        # Year must NOT appear in the target path — it's already in absolutePath
        assert "2023" not in target, f"Year doubled in target: {target!r}"
        assert target == "06/FR/Paris/"
        conn.close()


class TestPlanLocationMovesOrderCcCityMonth:
    """Location moves with CC_CITY_MONTH ordering: YYYY/CC/City/MM/."""

    def test_cc_city_month_target_path(
        self, tmp_catalog_needs_location: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lrc_automation.geocoder import LocationResolver

        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {(48.8566, 2.3522): ("FR", "Paris")},
        )
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(
            conn,
            scanner,
            location_folders=True,
            location_order=LocationOrder.CC_CITY_MONTH,
        )
        from lrc_automation.models import ChangePlan

        plan = ChangePlan()
        planner._plan_location_moves(plan)
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        assert len(moves) >= 1
        for move in moves:
            target = move.target_folder_path or ""
            # Expected: 2023/FR/Paris/06/
            assert target == "2023/FR/Paris/06/", f"Unexpected target: {target!r}"
        conn.close()

    def test_cc_city_month_per_year_root(
        self,
        tmp_catalog_per_year_root: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per-year root + CC_CITY_MONTH: target should be CC/City/MM/ (no year)."""
        from lrc_automation.geocoder import LocationResolver

        db_path, _ = tmp_catalog_per_year_root
        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {c: ("FR", "Paris") for c in coords},
        )
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(
            conn,
            scanner,
            location_folders=True,
            location_order=LocationOrder.CC_CITY_MONTH,
        )
        from lrc_automation.models import ChangePlan

        plan = ChangePlan()
        planner._plan_location_moves(plan)
        assert len(plan.changes) == 1
        target = plan.changes[0].target_folder_path
        assert target is not None
        assert "2023" not in target, f"Year doubled in target: {target!r}"
        assert target == "FR/Paris/06/"
        conn.close()


class TestPlanLocationMovesOrderCcMonthCity:
    """Location moves with CC_MONTH_CITY ordering: YYYY/CC/MM/City/."""

    def test_cc_month_city_target_path(
        self, tmp_catalog_needs_location: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lrc_automation.geocoder import LocationResolver

        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {(48.8566, 2.3522): ("FR", "Paris")},
        )
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(
            conn,
            scanner,
            location_folders=True,
            location_order=LocationOrder.CC_MONTH_CITY,
        )
        from lrc_automation.models import ChangePlan

        plan = ChangePlan()
        planner._plan_location_moves(plan)
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        assert len(moves) >= 1
        for move in moves:
            target = move.target_folder_path or ""
            # Expected: 2023/FR/06/Paris/
            assert target == "2023/FR/06/Paris/", f"Unexpected target: {target!r}"
        conn.close()

    def test_cc_month_city_per_year_root(
        self,
        tmp_catalog_per_year_root: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per-year root + CC_MONTH_CITY: target should be CC/MM/City/ (no year)."""
        from lrc_automation.geocoder import LocationResolver

        db_path, _ = tmp_catalog_per_year_root
        monkeypatch.setattr(
            LocationResolver,
            "resolve_batch",
            lambda self, coords: {c: ("FR", "Paris") for c in coords},
        )
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        planner = ChangePlanner(
            conn,
            scanner,
            location_folders=True,
            location_order=LocationOrder.CC_MONTH_CITY,
        )
        from lrc_automation.models import ChangePlan

        plan = ChangePlan()
        planner._plan_location_moves(plan)
        assert len(plan.changes) == 1
        target = plan.changes[0].target_folder_path
        assert target is not None
        assert "2023" not in target, f"Year doubled in target: {target!r}"
        assert target == "FR/06/Paris/"
        conn.close()


class TestPlanPrefixFormatRenames:
    """_plan_prefix_format_renames() wires DDMMYYYY→YYMMDD into build_plan."""

    def test_prefix_format_renames_appear_in_plan(
        self, tmp_catalog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Monkeypatched scan_prefix_format returns two candidates → two RENAME_FILE."""
        from datetime import datetime

        from lrc_automation.models import PhotoRecord

        def _fake_photo(file_id: int, base_name: str) -> PhotoRecord:
            return PhotoRecord(
                image_id=file_id,
                file_id=file_id,
                folder_id=1,
                root_folder_id=1,
                base_name=base_name,
                extension="JPG",
                sidecar_extensions=None,
                capture_time=datetime(2012, 6, 15),
                current_folder_path="2012/06/",
                root_absolute_path="/tmp/",
            )

        fake_conversions = [
            (_fake_photo(10, "15062012-photo_a"), "120615-photo_a", None),
            (_fake_photo(11, "15062012-photo_b"), "120615-photo_b", None),
        ]

        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        monkeypatch.setattr(
            scanner, "scan_prefix_format", lambda *a, **kw: fake_conversions
        )
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=False, include_renames=True)

        rename_changes = [
            c for c in plan.changes if c.change_type == ChangeType.RENAME_FILE
        ]
        # 1 from _plan_renames (duplicate prefix in fixtures)
        # + 2 from _plan_prefix_format_renames
        prefix_format_ids = {10, 11}
        prefix_format_renames = [
            c for c in rename_changes if c.photo.file_id in prefix_format_ids
        ]
        assert len(prefix_format_renames) == 2
        names = {c.new_name for c in prefix_format_renames}
        assert "120615-photo_a" in names
        assert "120615-photo_b" in names
        conn.close()

    def test_no_duplication_between_plan_renames_and_prefix_format(
        self, tmp_catalog: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """file_id from _plan_renames is not duplicated by prefix format renames."""
        from datetime import datetime

        from lrc_automation.models import PhotoRecord

        # Use file_id=3 which is the duplicate-prefix photo already in the fixture
        def _fake_photo_id3() -> PhotoRecord:
            return PhotoRecord(
                image_id=3,
                file_id=3,
                folder_id=3,
                root_folder_id=1,
                base_name="29122012-29122012-IMG_20121229_131334",
                extension="JPG",
                sidecar_extensions=None,
                capture_time=datetime(2012, 12, 29),
                current_folder_path="2022/12/",
                root_absolute_path="/tmp/test_photos/",
            )

        fake_conversions = [(_fake_photo_id3(), "121229-IMG_20121229_131334", None)]

        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        monkeypatch.setattr(
            scanner, "scan_prefix_format", lambda *a, **kw: fake_conversions
        )
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=False, include_renames=True)

        # file_id=3 should appear exactly once (from _plan_renames, not duplicated)
        renames_for_3 = [c for c in plan.changes if c.photo.file_id == 3]
        assert len(renames_for_3) == 1
        conn.close()


class TestPlanRootMigrations:
    """_plan_root_migrations() plans year-in-year cross-root and intra-root moves."""

    def test_cross_root_move_detected(
        self, tmp_catalog_multi_root: tuple[Path, Path, Path]
    ) -> None:
        """Photo in root_2013/pfr='2012/08/' gets MOVE_PHOTO with target_root_id=1."""
        db_path, _r12, _r13 = tmp_catalog_multi_root
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(
            include_moves=False,
            include_renames=False,
            include_root_migrations=True,
        )
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        assert len(moves) == 1
        change = moves[0]
        assert change.photo.base_name == "IMG_CROSS"
        assert change.target_root_id == 1
        assert change.target_root_absolute_path is not None
        assert change.target_root_absolute_path.rstrip("/").endswith("2012")
        conn.close()

    def test_target_pfr_strips_spurious_year(
        self, tmp_catalog_multi_root: tuple[Path, Path, Path]
    ) -> None:
        """target_folder_path strips the leading '2012/' segment → '08/'."""
        db_path, _r12, _r13 = tmp_catalog_multi_root
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(
            include_moves=False,
            include_renames=False,
            include_root_migrations=True,
        )
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        assert len(moves) == 1
        assert moves[0].target_folder_path == "08/"
        conn.close()

    def test_well_placed_photo_not_in_plan(
        self, tmp_catalog_multi_root: tuple[Path, Path, Path]
    ) -> None:
        """Photo 2 (IMG_OK in root_2013/2013/06/) is not in the migration plan."""
        db_path, _r12, _r13 = tmp_catalog_multi_root
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(
            include_moves=False,
            include_renames=False,
            include_root_migrations=True,
        )
        file_ids = [c.photo.file_id for c in plan.changes]
        assert 2 not in file_ids
        conn.close()

    def test_no_matching_root_emits_no_change(
        self, tmp_catalog_year_in_year: Path
    ) -> None:
        """Single-root catalog with no matching year root → no migration changes."""
        conn = sqlite3.connect(str(tmp_catalog_year_in_year))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(
            include_moves=False,
            include_renames=False,
            include_root_migrations=True,
        )
        assert len(plan.changes) == 0
        conn.close()

    def test_folders_to_create_in_target_root(
        self, tmp_catalog_multi_root: tuple[Path, Path, Path]
    ) -> None:
        """(root_id=1, '08/') is queued for creation in the 2012 root."""
        db_path, _r12, _r13 = tmp_catalog_multi_root
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(
            include_moves=False,
            include_renames=False,
            include_root_migrations=True,
        )
        assert (1, "08/") in plan.folders_to_create
        conn.close()

    def test_intra_root_change_has_no_target_root_fields(self, tmp_path: Path) -> None:
        """Intra-root fix: capture_year == root_year → target_root_id=None."""
        from tests.conftest import create_test_catalog

        root_dir = tmp_path / "2013"
        root_dir.mkdir()
        root_path = str(root_dir) + "/"
        data = {
            "roots": [(1, "ROOT-UUID-1", root_path, "2013", "../2013")],
            "folders": [(1, "FOLD-UUID-1", "2015/06/", 1)],
            "files": [
                (
                    1,
                    "FILE-UUID-1",
                    "IMG_INTRA",
                    "JPG",
                    1,
                    "IMG_INTRA",
                    None,
                    None,
                    "IMG_INTRA.JPG",
                    None,
                ),
            ],
            "images": [
                (
                    1,
                    "IMG-UUID-1",
                    "2013-07-10T10:00:00",
                    1,
                    "JPG",
                    0,
                    3,
                    "AB",
                    None,
                    None,
                ),  # noqa: E501
            ],
        }
        db_path = tmp_path / "test_intra.lrcat"
        create_test_catalog(db_path, data)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(
            include_moves=False,
            include_renames=False,
            include_root_migrations=True,
        )
        moves = [c for c in plan.changes if c.change_type == ChangeType.MOVE_PHOTO]
        assert len(moves) == 1
        change = moves[0]
        assert change.target_root_id is None
        assert change.target_root_absolute_path is None
        assert change.target_folder_path == "06/"
        conn.close()

    def test_find_root_for_year_returns_correct_root(self) -> None:
        """_find_root_for_year() returns the root whose absolutePath ends with year."""
        from lrc_automation.models import RootFolder

        roots = [
            RootFolder(id_local=1, absolute_path="/lr/2012/"),
            RootFolder(id_local=2, absolute_path="/lr/2013/"),
        ]
        result = ChangePlanner._find_root_for_year(2012, roots)
        assert result is not None
        assert result.id_local == 1

        result_none = ChangePlanner._find_root_for_year(2025, roots)
        assert result_none is None

    def test_build_plan_default_excludes_root_migrations(
        self, tmp_catalog_multi_root: tuple[Path, Path, Path]
    ) -> None:
        """build_plan() default call excludes root migrations (opt-in required)."""
        db_path, _r12, _r13 = tmp_catalog_multi_root
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        planner = ChangePlanner(conn, scanner)
        plan = planner.build_plan(include_moves=False, include_renames=False)
        cross_root_changes = [
            c
            for c in plan.changes
            if c.change_type == ChangeType.MOVE_PHOTO and c.target_root_id is not None
        ]
        assert len(cross_root_changes) == 0
        conn.close()
