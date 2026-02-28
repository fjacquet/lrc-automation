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


class TestAuditFilesOnDisk:
    """Tests for CatalogValidator.audit_files_on_disk()."""

    def _make_catalog(
        self, tmp_path: Path, root_abs: str, folder: str, filename: str
    ) -> Path:
        """Create a minimal catalog with one photo record."""
        import sqlite3

        from tests.conftest import SCHEMA_SQL

        db_path = tmp_path / "test.lrcat"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO AgLibraryRootFolder VALUES (1,'ROOT-UUID',?,'root','../root')",
            (root_abs,),
        )
        conn.execute(
            "INSERT INTO AgLibraryFolder VALUES (1,'FOLD-UUID',?,1)",
            (folder,),
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

    def test_all_present(self, tmp_path: Path) -> None:
        """All files exist on disk → no missing entries."""
        import sqlite3

        from lrc_automation.validators import CatalogValidator

        root_dir = tmp_path / "2023"
        folder_dir = root_dir / "06"
        folder_dir.mkdir(parents=True)
        (folder_dir / "IMG_001.JPG").write_text("photo")

        db = self._make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder="06/",
            filename="IMG_001.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        result = CatalogValidator(conn).audit_files_on_disk()
        conn.close()

        assert result.total_checked == 1
        assert result.missing == []
        assert result.truly_missing_count == 0

    def test_missing_truly_gone(self, tmp_path: Path) -> None:
        """File recorded in DB but absent from disk and parent → truly missing."""
        import sqlite3

        from lrc_automation.validators import CatalogValidator

        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)
        # File NOT created on disk

        db = self._make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder="06/",
            filename="GONE.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        result = CatalogValidator(conn).audit_files_on_disk()
        conn.close()

        assert result.total_checked == 1
        assert len(result.missing) == 1
        assert result.missing[0].found_at == []
        assert result.truly_missing_count == 1
        assert result.found_elsewhere_count == 0

    def test_missing_found_in_parent(self, tmp_path: Path) -> None:
        """File missing at catalog path but present in sibling year-root."""
        import sqlite3

        from lrc_automation.validators import CatalogValidator

        # Root recorded in catalog: tmp_path/2023/
        # File actually at: tmp_path/2022/06/IMG_MOVED.JPG
        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)
        sibling_dir = tmp_path / "2022" / "06"
        sibling_dir.mkdir(parents=True)
        (sibling_dir / "IMG_MOVED.JPG").write_text("photo moved here")

        db = self._make_catalog(
            tmp_path,
            root_abs=str(root_dir) + "/",
            folder="06/",
            filename="IMG_MOVED.JPG",
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        result = CatalogValidator(conn).audit_files_on_disk()
        conn.close()

        assert result.total_checked == 1
        assert len(result.missing) == 1
        assert result.found_elsewhere_count == 1
        assert result.truly_missing_count == 0
        found = result.missing[0].found_at
        assert len(found) == 1
        assert found[0].name == "IMG_MOVED.JPG"

    def test_result_counts(self, tmp_path: Path) -> None:
        """Mixed: one present, one truly gone, one found-elsewhere → correct counts."""
        import sqlite3

        from lrc_automation.validators import CatalogValidator
        from tests.conftest import SCHEMA_SQL

        root_dir = tmp_path / "2023"
        (root_dir / "06").mkdir(parents=True)
        (root_dir / "06" / "PRESENT.JPG").write_text("here")
        # GONE.JPG: not on disk at all
        # MOVED.JPG: in sibling year root
        sibling = tmp_path / "2022" / "06"
        sibling.mkdir(parents=True)
        (sibling / "MOVED.JPG").write_text("moved")

        root_abs = str(root_dir) + "/"
        db_path = tmp_path / "multi.lrcat"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO AgLibraryRootFolder VALUES (1,'R1',?,'root','../root')",
            (root_abs,),
        )
        conn.execute("INSERT INTO AgLibraryFolder VALUES (1,'F1','06/',1)")
        files = [(1, "PRESENT", "JPG"), (2, "GONE", "JPG"), (3, "MOVED", "JPG")]
        for fid, base, ext in files:
            conn.execute(
                "INSERT INTO AgLibraryFile VALUES (?,?,?,?,1,?,NULL,NULL,?,NULL)",
                (fid, f"F-UUID-{fid}", base, ext, base, f"{base}.{ext}"),
            )
            conn.execute(
                "INSERT INTO Adobe_images VALUES (?,?,?,?,?,0,0,'AB',NULL,NULL)",
                (fid, f"I-UUID-{fid}", "2023-06-15T10:00:00", fid, "JPG"),
            )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        result = CatalogValidator(conn).audit_files_on_disk()
        conn.close()

        assert result.total_checked == 3
        assert result.present_count == 1
        assert len(result.missing) == 2
        assert result.found_elsewhere_count == 1
        assert result.truly_missing_count == 1
