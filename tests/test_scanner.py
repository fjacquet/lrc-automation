"""Tests for scanner module."""

import sqlite3
from pathlib import Path

from lrc_automation.scanner import CatalogScanner


class TestCatalogScanner:
    def test_get_total_photo_count(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        assert scanner.get_total_photo_count() == 4
        conn.close()

    def test_scan_misplaced_photos(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        # Photos 2 and 4 are in 2023/07/ but captured in 2023/06
        # Photo 3 is in 2022/12/ but captured in 2012/12
        assert len(misplaced) == 3
        conn.close()

    def test_scan_duplicate_prefixes(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        duplicates = scanner.scan_duplicate_prefixes()
        assert len(duplicates) == 1
        photo, cleaned = duplicates[0]
        assert photo.base_name == "29122012-29122012-IMG_20121229_131334"
        assert cleaned == "121229-IMG_131334"
        conn.close()

    def test_correctly_placed_not_in_misplaced(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        file_ids = [p.file_id for p in misplaced]
        # File 1 is correctly placed in 2023/06/
        assert 1 not in file_ids
        conn.close()

    def test_get_all_folders(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        folders = scanner.get_all_folders()
        assert len(folders) == 3
        assert (1, "2023/06/") in folders
        assert (1, "2023/07/") in folders
        conn.close()

    def test_get_root_folders(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        roots = scanner.get_root_folders()
        assert len(roots) == 1
        assert roots[0].absolute_path == "/tmp/test_photos/"
        conn.close()

    def test_scan_without_location_flag(self, tmp_catalog_with_gps: Path) -> None:
        """Without location_folders, photos should not have GPS data."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=False)
        photos = scanner._fetch_all_photos()
        for photo in photos:
            assert photo.gps_latitude is None
            assert photo.gps_longitude is None
        conn.close()

    def test_scan_with_location_flag(self, tmp_catalog_with_gps: Path) -> None:
        """With location_folders, GPS photos should have lat/lon populated."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        photos = scanner._fetch_all_photos()
        gps_photos = [p for p in photos if p.gps_latitude is not None]
        assert len(gps_photos) == 2
        # Check Zurich coords
        zurich = [p for p in gps_photos if p.base_name == "IMG_GPS_1"]
        assert len(zurich) == 1
        assert abs(zurich[0].gps_latitude - 47.3769) < 0.01  # type: ignore[operator]
        conn.close()

    def test_scan_photo_without_gps_has_none(self, tmp_catalog_with_gps: Path) -> None:
        """Photos without GPS have None even when location flag is on."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        photos = scanner._fetch_all_photos()
        nogps = [p for p in photos if p.base_name == "IMG_NOGPS_1"]
        assert len(nogps) == 1
        assert nogps[0].gps_latitude is None
        assert nogps[0].gps_longitude is None
        conn.close()

    def test_scan_misplaced_with_location(self, tmp_catalog_with_gps: Path) -> None:
        """Misplaced photos include GPS data when flag is on."""
        conn = sqlite3.connect(str(tmp_catalog_with_gps))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        misplaced = scanner.scan_misplaced_photos()
        gps_misplaced = [p for p in misplaced if p.gps_latitude is not None]
        # Photos 1 and 2 are misplaced (in 2023/07/ but captured 2023-06)
        assert len(gps_misplaced) == 2
        conn.close()


class TestScannerBroadenedDetection:
    """Tests for broadened date detection (ISO, French, year-in-root)."""

    def test_iso_date_correctly_placed(self, diverse_folder_catalog: Path) -> None:
        """Photo in 2023-12-24/ captured 2023-12 should NOT be misplaced."""
        conn = sqlite3.connect(str(diverse_folder_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        file_ids = [p.file_id for p in misplaced]
        assert 10 not in file_ids
        conn.close()

    def test_french_date_correctly_placed(self, diverse_folder_catalog: Path) -> None:
        """Photo in '1 avril 2016/' captured 2016-04 should NOT be misplaced."""
        conn = sqlite3.connect(str(diverse_folder_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        file_ids = [p.file_id for p in misplaced]
        assert 11 not in file_ids
        conn.close()

    def test_topical_folder_skipped(self, diverse_folder_catalog: Path) -> None:
        """Photo in 'Vacances/' should be skipped (no date detected)."""
        conn = sqlite3.connect(str(diverse_folder_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        file_ids = [p.file_id for p in misplaced]
        assert 13 not in file_ids
        conn.close()

    def test_standard_yyyy_mm_mismatch_detected(
        self, diverse_folder_catalog: Path
    ) -> None:
        """Photo in 2022/03/ captured 2022-05 should be detected as misplaced."""
        conn = sqlite3.connect(str(diverse_folder_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        file_ids = [p.file_id for p in misplaced]
        assert 14 in file_ids
        conn.close()

    def test_year_in_root_month_in_path_correctly_placed(
        self, diverse_folder_catalog: Path
    ) -> None:
        """Photo with root=2021/ path=06/ captured 2021-06 should NOT be misplaced."""
        conn = sqlite3.connect(str(diverse_folder_catalog))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        misplaced = scanner.scan_misplaced_photos()
        file_ids = [p.file_id for p in misplaced]
        assert 12 not in file_ids
        conn.close()


class TestScanNeedsLocationFolder:
    """Tests for CatalogScanner.scan_needs_location_folder()."""

    def test_returns_gps_photos_in_date_only_folder(
        self, tmp_catalog_needs_location: Path
    ) -> None:
        """GPS photo in date-only folder (2023/06/) is a candidate."""
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        candidates = scanner.scan_needs_location_folder()
        file_ids = [p.file_id for p in candidates]
        assert 1 in file_ids
        conn.close()

    def test_skips_photos_already_in_location_subfolder(
        self, tmp_catalog_needs_location: Path
    ) -> None:
        """GPS photo already in 2023/06/FR/Paris/ is NOT a candidate."""
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        candidates = scanner.scan_needs_location_folder()
        file_ids = [p.file_id for p in candidates]
        assert 2 not in file_ids
        conn.close()

    def test_skips_photos_without_gps(self, tmp_catalog_needs_location: Path) -> None:
        """Photo without GPS is NOT a candidate even if in date-only folder."""
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=True)
        candidates = scanner.scan_needs_location_folder()
        file_ids = [p.file_id for p in candidates]
        assert 3 not in file_ids
        conn.close()

    def test_returns_empty_when_flag_off(
        self, tmp_catalog_needs_location: Path
    ) -> None:
        """Returns [] when location_folders=False regardless of GPS data."""
        conn = sqlite3.connect(str(tmp_catalog_needs_location))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn, location_folders=False)
        assert scanner.scan_needs_location_folder() == []
        conn.close()


class TestScanYearInYear:
    """Tests for CatalogScanner.scan_year_in_year_photos()."""

    def test_detects_photo_in_wrong_root_year(
        self, tmp_catalog_year_in_year: Path
    ) -> None:
        """Photo with root 2022 but pathFromRoot 2003/12/ is detected."""
        conn = sqlite3.connect(str(tmp_catalog_year_in_year))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        yiy = scanner.scan_year_in_year_photos()
        file_ids = [p.file_id for p in yiy]
        assert 1 in file_ids
        conn.close()

    def test_skips_correct_year_photo(self, tmp_catalog_year_in_year: Path) -> None:
        """Photo with root 2022 and pathFromRoot 2022/06/ is NOT detected."""
        conn = sqlite3.connect(str(tmp_catalog_year_in_year))
        conn.row_factory = sqlite3.Row
        scanner = CatalogScanner(conn)
        yiy = scanner.scan_year_in_year_photos()
        file_ids = [p.file_id for p in yiy]
        assert 2 not in file_ids
        conn.close()
