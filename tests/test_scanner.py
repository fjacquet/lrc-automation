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
        assert cleaned == "29122012-IMG_131334"
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
