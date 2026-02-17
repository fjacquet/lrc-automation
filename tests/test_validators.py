"""Tests for validators module."""

import sqlite3
from pathlib import Path

from lrc_automation.validators import CatalogValidator


class TestCatalogValidator:
    def test_preflight_clean_catalog(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        validator = CatalogValidator(conn)
        warnings = validator.preflight_check()
        assert len(warnings) == 0
        conn.close()

    def test_preflight_detects_broken_folder_ref(self, tmp_path: Path) -> None:
        from tests.conftest import create_test_catalog

        db_path = tmp_path / "broken.lrcat"
        create_test_catalog(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Insert a file with a broken folder reference
        conn.execute(
            "INSERT INTO AgLibraryFile VALUES "
            "(99, 'BROKEN', 'broken', 'JPG', 999, 'broken', "
            "NULL, NULL, 'broken.JPG', NULL)"
        )
        conn.commit()

        validator = CatalogValidator(conn)
        warnings = validator.preflight_check()
        assert any("broken folder" in w for w in warnings)
        conn.close()

    def test_check_files_exist_detects_missing(self, tmp_catalog: Path) -> None:
        conn = sqlite3.connect(str(tmp_catalog))
        conn.row_factory = sqlite3.Row
        validator = CatalogValidator(conn)
        # All files in test catalog point to /tmp/test_photos/ which
        # doesn't exist, so all should be missing
        warnings = validator.check_files_exist_on_disk()
        assert any("missing" in w.lower() for w in warnings)
        conn.close()
