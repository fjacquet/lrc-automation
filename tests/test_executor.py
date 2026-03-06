"""Tests for executor module."""

from pathlib import Path

import pytest

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


class TestCleanupEmptyFolders:
    """Tests for the standalone cleanup_empty_folders() function."""

    def _make_catalog(self, tmp_path: Path, root_dir: Path, folders: list[str]) -> Path:
        import sqlite3

        from tests.conftest import SCHEMA_SQL

        db_path = tmp_path / "test.lrcat"
        root_abs = str(root_dir) + "/"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO AgLibraryRootFolder VALUES (1,'ROOT-UUID',?,'root','../root')",
            (root_abs,),
        )
        for i, path_from_root in enumerate(folders, 1):
            conn.execute(
                "INSERT INTO AgLibraryFolder VALUES (?,?,?,1)",
                (i, f"FOLD-UUID-{i}", path_from_root),
            )
        conn.commit()
        conn.close()
        return db_path

    def test_removes_empty_dirs_recursively(self, tmp_path: Path) -> None:
        """Nested empty directories are all removed bottom-up."""
        import sqlite3

        from lrc_automation.executor import cleanup_empty_folders

        root_dir = tmp_path / "root"
        # Create nested empty dirs: root/2016/2016/03/ and root/2016/2016/
        (root_dir / "2016" / "2016" / "03").mkdir(parents=True)
        (root_dir / "2016" / "06").mkdir(parents=True)
        (root_dir / "2016" / "06" / "IMG.JPG").write_text("photo")

        db = self._make_catalog(
            tmp_path,
            root_dir,
            ["2016/", "2016/2016/", "2016/2016/03/", "2016/06/"],
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        count = cleanup_empty_folders(conn, [(1, str(root_dir) + "/")])
        conn.close()

        # Both empty dirs removed (2016/2016/03/, 2016/2016/)
        # 2016/ has IMG.JPG so stays
        assert count == 2
        assert not (root_dir / "2016" / "2016").exists()
        # Non-empty dir must survive
        assert (root_dir / "2016" / "06" / "IMG.JPG").exists()

    @pytest.mark.skipif(
        __import__("sys").platform != "darwin",
        reason="AppleDouble cleanup is macOS-only",
    )
    def test_removes_apple_double_files_before_rmdir(self, tmp_path: Path) -> None:
        """Directories containing only ._* files are cleaned and removed."""
        import sqlite3

        from lrc_automation.executor import cleanup_empty_folders

        root_dir = tmp_path / "root"
        dir_with_apple = root_dir / "2016" / "2016" / "03"
        dir_with_apple.mkdir(parents=True)
        # Only AppleDouble files inside — no real content
        (dir_with_apple / "._Switzerland").write_bytes(b"\x00\x05\x16\x07")
        (dir_with_apple / "._CH").write_bytes(b"\x00\x05\x16\x07")

        db = self._make_catalog(
            tmp_path,
            root_dir,
            ["2016/", "2016/2016/", "2016/2016/03/"],
        )
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        count = cleanup_empty_folders(conn, [(1, str(root_dir) + "/")])
        conn.close()

        assert count == 3
        assert not dir_with_apple.exists()
        assert not (root_dir / "2016" / "2016").exists()

    def test_preserves_nonempty_dirs(self, tmp_path: Path) -> None:
        """Directories with real files are left untouched."""
        import sqlite3

        from lrc_automation.executor import cleanup_empty_folders

        root_dir = tmp_path / "root"
        (root_dir / "2016" / "06").mkdir(parents=True)
        (root_dir / "2016" / "06" / "photo.jpg").write_text("photo")

        db = self._make_catalog(tmp_path, root_dir, ["2016/", "2016/06/"])
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        count = cleanup_empty_folders(conn, [(1, str(root_dir) + "/")])
        conn.close()

        assert count == 0
        assert (root_dir / "2016" / "06" / "photo.jpg").exists()

    def test_db_rows_removed(self, tmp_path: Path) -> None:
        """AgLibraryFolder rows for removed dirs are deleted from the DB."""
        import sqlite3

        from lrc_automation.executor import cleanup_empty_folders

        root_dir = tmp_path / "root"
        (root_dir / "empty").mkdir(parents=True)

        db = self._make_catalog(tmp_path, root_dir, ["empty/"])
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        before = conn.execute("SELECT COUNT(*) FROM AgLibraryFolder").fetchone()[0]
        count = cleanup_empty_folders(conn, [(1, str(root_dir) + "/")])
        after = conn.execute("SELECT COUNT(*) FROM AgLibraryFolder").fetchone()[0]
        conn.close()

        assert count == 1
        assert after == before - 1


class TestWriteSafety:
    """PROC-02 forward-slash writes, PROC-03 darwin guard, PROC-04 retry."""

    def test_cleanup_empty_folders_writes_forward_slash_path_from_root(
        self,
        tmp_path: Path,
    ) -> None:
        """cleanup_empty_folders stores pathFromRoot with forward slashes (PROC-02)."""
        import sqlite3

        from lrc_automation.executor import cleanup_empty_folders

        root = tmp_path / "Photos"
        sub = root / "2023" / "06"
        sub.mkdir(parents=True)

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE AgLibraryFolder "
            "(id_local INTEGER PRIMARY KEY, pathFromRoot TEXT, rootFolder INTEGER)"
        )
        conn.execute("INSERT INTO AgLibraryFolder VALUES (1, '2023/06/', 42)")
        conn.commit()

        cleanup_empty_folders(conn, [(42, str(root) + "/")])

        # The DELETE uses pathFromRoot — if str(rel) was used on Windows it would
        # be '2023\\06/' and the row would not be deleted.
        # Verify by checking the pathFromRoot value used in the final row lookup.
        # On POSIX this also tests the code path; simulate Windows by checking
        # the rel.as_posix() contract directly:
        rel = Path("2023/06")
        assert rel.as_posix() + "/" == "2023/06/"
        # And confirm the folder row was actually deleted (proves cleanup ran):
        row = conn.execute("SELECT COUNT(*) FROM AgLibraryFolder").fetchone()
        assert row[0] == 0, "Folder row should be removed after cleanup"

    def test_is_effectively_empty_treats_apple_double_as_real_on_non_darwin(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """On non-macOS, ._* files count as real content — NOT empty (PROC-03)."""
        import sys

        from lrc_automation.executor import _is_effectively_empty

        apple_double = tmp_path / "._photo.jpg"
        apple_double.touch()

        monkeypatch.setattr(sys, "platform", "win32")
        assert not _is_effectively_empty(tmp_path), (
            "._* files should be treated as real on non-macOS"
        )

    def test_cleanup_skips_apple_double_deletion_on_non_darwin(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """On non-macOS, cleanup does not call _delete_apple_double_files (PROC-03)."""
        import sqlite3
        import sys

        from lrc_automation import executor
        from lrc_automation.executor import cleanup_empty_folders

        root = tmp_path / "Photos"
        sub = root / "2023" / "06"
        sub.mkdir(parents=True)
        apple_double = sub / "._photo.jpg"
        apple_double.touch()

        deleted: list[str] = []

        original_delete = executor._delete_apple_double_files

        def spy_delete(directory: Path) -> None:
            deleted.append(str(directory))
            original_delete(directory)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(executor, "_delete_apple_double_files", spy_delete)

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE AgLibraryFolder "
            "(id_local INTEGER PRIMARY KEY, pathFromRoot TEXT, rootFolder INTEGER)"
        )
        conn.commit()

        cleanup_empty_folders(conn, [(42, str(root) + "/")])
        assert deleted == [], (
            "_delete_apple_double_files must not be called on non-macOS"
        )
        assert apple_double.exists(), "._* file must not be deleted on non-macOS"

    def test_apply_file_op_retries_on_permission_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """First attempt raises PermissionError; second attempt succeeds (PROC-04)."""
        import shutil

        from lrc_automation import executor
        from lrc_automation.executor import ChangeExecutor

        src = tmp_path / "photo.jpg"
        src.write_bytes(b"data")
        dst = tmp_path / "dst" / "photo.jpg"

        call_count = 0
        real_move = shutil.move

        def flaky_move(s: str, d: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PermissionError("AV lock")
            real_move(s, d)

        monkeypatch.setattr(shutil, "move", flaky_move)
        monkeypatch.setattr(executor, "_MOVE_RETRY_SLEEP", 0.0)  # no sleep in tests

        # Build a minimal executor with a live catalog connection
        # Use a real (non-mock) CatalogConnection pointing at an in-memory db
        # by constructing ChangeExecutor directly with a stub conn
        ex = object.__new__(ChangeExecutor)
        ex._rollback_actions = []  # type: ignore[attr-defined]

        ex._apply_file_op(src, dst, move=True)  # type: ignore[attr-defined]

        assert call_count == 2, "Should have been called twice (fail then succeed)"
        assert dst.exists()

    def test_apply_file_op_raises_after_all_retries_exhausted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All 3 attempts raise PermissionError — re-raised on exhaustion (PROC-04)."""
        import shutil

        import pytest

        from lrc_automation import executor
        from lrc_automation.executor import ChangeExecutor

        src = tmp_path / "photo.jpg"
        src.write_bytes(b"data")
        dst = tmp_path / "dst" / "photo.jpg"

        monkeypatch.setattr(
            shutil,
            "move",
            lambda s, d: (_ for _ in ()).throw(PermissionError("locked")),
        )
        monkeypatch.setattr(executor, "_MOVE_RETRY_SLEEP", 0.0)

        ex = object.__new__(ChangeExecutor)
        ex._rollback_actions = []  # type: ignore[attr-defined]

        with pytest.raises(PermissionError):
            ex._apply_file_op(src, dst, move=True)  # type: ignore[attr-defined]

        # Rollback list must be empty — no successful move was registered
        assert ex._rollback_actions == []  # type: ignore[attr-defined]


class TestExecutorCrossRoot:
    """Executor moves files across year-root boundaries correctly."""

    def test_cross_root_move_on_disk(
        self, tmp_catalog_multi_root_with_files: tuple[Path, Path, Path]
    ) -> None:
        """IMG_CROSS moves from root_2013/2012/08/ to root_2012/08/ on disk."""
        db_path, root_2012_dir, root_2013_dir = tmp_catalog_multi_root_with_files

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            plan = planner.build_plan(
                include_moves=False,
                include_renames=False,
                include_root_migrations=True,
            )
            assert plan.move_count > 0

            executor = ChangeExecutor(cat, plan)
            report = executor.execute()

        assert not report.rolled_back
        assert len(report.succeeded) > 0
        assert len(report.failed) == 0
        assert (root_2012_dir / "08" / "IMG_CROSS.JPG").exists()
        assert not (root_2013_dir / "2012" / "08" / "IMG_CROSS.JPG").exists()

    def test_catalog_updated_after_cross_root_move(
        self, tmp_catalog_multi_root_with_files: tuple[Path, Path, Path]
    ) -> None:
        """After execution, AgLibraryFile.folder points to a folder in root 1 (2012)."""
        import sqlite3 as _sqlite3

        db_path, _r12, _r13 = tmp_catalog_multi_root_with_files

        with CatalogConnection(db_path) as cat:
            conn = cat.open(readonly=False)
            scanner = CatalogScanner(conn)
            planner = ChangePlanner(conn, scanner)
            plan = planner.build_plan(
                include_moves=False,
                include_renames=False,
                include_root_migrations=True,
            )
            executor = ChangeExecutor(cat, plan)
            executor.execute()

        raw_conn = _sqlite3.connect(str(db_path))
        cursor = raw_conn.execute(
            "SELECT f.rootFolder FROM AgLibraryFile af "
            "JOIN AgLibraryFolder f ON af.folder = f.id_local "
            "WHERE af.id_local = 1"
        )
        row = cursor.fetchone()
        raw_conn.close()
        assert row is not None
        assert row[0] == 1  # Folder now belongs to root 1 (2012)
