"""Change executor - applies plans to disk and SQLite catalog."""

import contextlib
import os
import shutil
import sqlite3
from collections.abc import Callable
from functools import partial
from pathlib import Path

from .catalog import CatalogConnection
from .models import ChangePlan, ChangeType, ExecutionReport, FileChange, PhotoRecord
from .utils import generate_uuid, parse_sidecar_extensions


class ExecutionError(Exception):
    """Error during plan execution."""


class SkippableError(ExecutionError):
    """Pre-disk-op validation failure — nothing was touched, safe to skip."""


class ChangeExecutor:
    """Executes a ChangePlan: moves files on disk and updates SQLite catalog."""

    def __init__(
        self,
        catalog: CatalogConnection,
        plan: ChangePlan,
        on_progress: Callable[[FileChange, bool], None] | None = None,
    ) -> None:
        self.catalog = catalog
        self.plan = plan
        self._on_progress = on_progress
        self._rollback_actions: list[Callable[..., object]] = []

    def execute(self) -> ExecutionReport:
        """Execute the full plan.

        Order:
        1. Create any new folders (on disk + in SQLite)
        2. For each change: move/rename file on disk, update SQLite
        3. Commit transaction
        """
        report = ExecutionReport()
        conn = self.catalog.conn
        if conn is None:
            conn = self.catalog.open(readonly=False)

        try:
            conn.execute("BEGIN IMMEDIATE")

            # Phase 1: Create folders
            folder_id_map = self._create_folders(conn)

            # Phase 2: Apply changes
            for change in self.plan.changes:
                try:
                    if change.change_type == ChangeType.MOVE_PHOTO:
                        self._execute_move(conn, change, folder_id_map)
                    elif change.change_type == ChangeType.RENAME_FILE:
                        self._execute_rename(conn, change)
                    report.record_success(change)
                    if self._on_progress:
                        self._on_progress(change, True)
                except SkippableError as e:
                    # Pre-disk-op failure: nothing was touched, safe to skip
                    report.record_error(change, str(e))
                    if self._on_progress:
                        self._on_progress(change, False)
                except Exception as e:
                    # Mid-operation failure: disk partially modified, rollback all
                    report.record_error(change, str(e))
                    conn.rollback()
                    self._rollback_disk_changes()
                    report.mark_rolled_back()
                    return report

            conn.commit()

        except Exception as e:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
            self._rollback_disk_changes()
            raise ExecutionError(f"Execution failed: {e}") from e

        return report

    def _create_folders(self, conn: sqlite3.Connection) -> dict[tuple[int, str], int]:
        """Create new folders on disk and in SQLite.

        Returns mapping of (root_id, pathFromRoot) -> new folder id_local.
        """
        folder_id_map: dict[tuple[int, str], int] = {}

        # Get root folder paths
        root_paths: dict[int, str] = {}
        cursor = conn.execute("SELECT id_local, absolutePath FROM AgLibraryRootFolder")
        for row in cursor:
            root_paths[row[0]] = row[1]

        # Get next available id
        cursor = conn.execute("SELECT MAX(id_local) FROM AgLibraryFolder")
        next_id = (cursor.fetchone()[0] or 0) + 1

        for root_id, path_from_root in self.plan.folders_to_create:
            root_path = root_paths.get(root_id)
            if root_path is None:
                raise ExecutionError(f"Root folder {root_id} not found")

            # Create on disk
            full_dir = Path(root_path) / path_from_root
            full_dir.mkdir(parents=True, exist_ok=True)

            # Create in catalog
            folder_uuid = generate_uuid()
            conn.execute(
                "INSERT INTO AgLibraryFolder "
                "(id_local, id_global, pathFromRoot, rootFolder) "
                "VALUES (?, ?, ?, ?)",
                (next_id, folder_uuid, path_from_root, root_id),
            )

            folder_id_map[(root_id, path_from_root)] = next_id
            next_id += 1

        return folder_id_map

    def _execute_move(
        self,
        conn: sqlite3.Connection,
        change: FileChange,
        folder_id_map: dict[tuple[int, str], int],
    ) -> None:
        """Move a single photo to a new folder."""
        photo = change.photo
        target_path = change.target_folder_path
        if target_path is None:
            raise ExecutionError("No target folder path")

        # Determine target folder ID
        target_folder_id = change.target_folder_id
        if target_folder_id is None:
            key = (photo.root_folder_id, target_path)
            target_folder_id = folder_id_map.get(key)
            if target_folder_id is None:
                # Try to find it in existing folders
                cursor = conn.execute(
                    "SELECT id_local FROM AgLibraryFolder "
                    "WHERE rootFolder = ? AND pathFromRoot = ?",
                    (photo.root_folder_id, target_path),
                )
                row = cursor.fetchone()
                if row:
                    target_folder_id = row[0]
                else:
                    raise ExecutionError(f"Target folder not found: {target_path}")

        # Build source and destination paths
        src = photo.full_path
        base_name = change.new_name or photo.base_name
        dst_dir = Path(photo.root_absolute_path) / target_path
        dst = dst_dir / f"{base_name}.{photo.extension}"

        self._apply_file_op(src, dst, move=True)
        self._handle_sidecars(
            photo, src.parent, dst_dir, photo.base_name, base_name, move=True
        )

        # Update catalog
        if change.new_name:
            conn.execute(
                "UPDATE AgLibraryFile SET folder = ?, "
                "baseName = ?, idx_filename = ? "
                "WHERE id_local = ?",
                (target_folder_id, base_name, base_name, photo.file_id),
            )
        else:
            conn.execute(
                "UPDATE AgLibraryFile SET folder = ? WHERE id_local = ?",
                (target_folder_id, photo.file_id),
            )

    def _execute_rename(self, conn: sqlite3.Connection, change: FileChange) -> None:
        """Rename a single file."""
        photo = change.photo
        old_name = change.old_name
        new_name = change.new_name
        if not old_name or not new_name:
            raise ExecutionError("Missing old or new name")

        folder_path = Path(photo.root_absolute_path) / photo.current_folder_path
        src = folder_path / f"{old_name}.{photo.extension}"
        dst = folder_path / f"{new_name}.{photo.extension}"

        self._apply_file_op(src, dst, move=False)
        self._handle_sidecars(
            photo, folder_path, folder_path, old_name, new_name, move=False
        )

        conn.execute(
            "UPDATE AgLibraryFile SET baseName = ?, "
            "idx_filename = ? WHERE id_local = ?",
            (new_name, new_name, photo.file_id),
        )

    def _apply_file_op(self, src: Path, dst: Path, move: bool) -> None:
        """Move or rename a file and record the rollback action."""
        if not src.exists():
            raise SkippableError(f"Source file not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise SkippableError(f"Destination already exists: {dst}")
        op = shutil.move if move else os.rename
        op(str(src), str(dst))
        self._rollback_actions.append(partial(op, str(dst), str(src)))

    def _handle_sidecars(
        self,
        photo: PhotoRecord,
        src_dir: Path,
        dst_dir: Path,
        old_base: str,
        new_base: str,
        move: bool,
    ) -> None:
        """Move or rename sidecar files alongside the main file."""
        op = shutil.move if move else os.rename
        for ext in parse_sidecar_extensions(photo.sidecar_extensions):
            src = src_dir / f"{old_base}.{ext}"
            dst = dst_dir / f"{new_base}.{ext}"
            if src.exists():
                op(str(src), str(dst))
                self._rollback_actions.append(partial(op, str(dst), str(src)))
        # XMP sidecar (may not be listed in sidecarExtensions)
        xmp_src = src_dir / f"{old_base}.xmp"
        xmp_dst = dst_dir / f"{new_base}.xmp"
        if xmp_src.exists() and not xmp_dst.exists():
            op(str(xmp_src), str(xmp_dst))
            self._rollback_actions.append(partial(op, str(xmp_dst), str(xmp_src)))

    def _rollback_disk_changes(self) -> None:
        """Undo all disk changes in reverse order."""
        for undo in reversed(self._rollback_actions):
            with contextlib.suppress(OSError):
                undo()
        self._rollback_actions.clear()
