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
