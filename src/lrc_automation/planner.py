"""Change planner - builds execution plans from scan results."""

from __future__ import annotations

import sqlite3

from .constants import (
    DEFAULT_TARGET_LAYOUT,
    QUERY_FILE_EXISTS_IN_FOLDER,
    QUERY_MAX_FOLDER_ID,
)
from .models import ChangePlan, ChangeType, FileChange
from .scanner import CatalogScanner

_MAX_COLLISION_TRIES = 9999


def _resolve_in_plan(base_name: str, extension: str, taken: set[str]) -> str:
    """Resolve a filename collision against already-planned renames (no DB needed)."""
    if f"{base_name}.{extension}" not in taken:
        return base_name
    for i in range(1, _MAX_COLLISION_TRIES + 1):
        candidate = f"{base_name}_{i}"
        if f"{candidate}.{extension}" not in taken:
            return candidate
    raise RuntimeError(f"Cannot resolve in-plan collision for '{base_name}'")


class ChangePlanner:
    """Builds a ChangePlan from scan results."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        scanner: CatalogScanner,
        target_layout: str = DEFAULT_TARGET_LAYOUT,
        location_folders: bool = False,
    ) -> None:
        self.conn = conn
        self.scanner = scanner
        self.target_layout = target_layout
        self.location_folders = location_folders
        self.existing_folders = scanner.get_all_folders()

    def build_plan(
        self, include_moves: bool = True, include_renames: bool = True
    ) -> ChangePlan:
        """Build a complete change plan."""
        plan = ChangePlan()

        if include_moves:
            self._plan_moves(plan)

        if include_renames:
            self._plan_renames(plan)

        return plan

    def _plan_moves(self, plan: ChangePlan) -> None:
        """Plan moves for misplaced photos."""
        misplaced = self.scanner.scan_misplaced_photos()

        # Batch-resolve GPS coordinates if location folders enabled
        location_map: dict[tuple[float, float], tuple[str, str]] = {}
        if self.location_folders:
            from .geocoder import LocationResolver

            resolver = LocationResolver()
            coords = [
                (p.gps_latitude, p.gps_longitude)
                for p in misplaced
                if p.gps_latitude is not None and p.gps_longitude is not None
            ]
            if coords:
                location_map = resolver.resolve_batch(coords)

        # Track basenames already planned for folders that don't exist yet
        in_plan: dict[tuple[int, str], set[str]] = {}

        for photo in misplaced:
            # Determine target path with optional location subfolder
            country: str | None = None
            city: str | None = None
            if (
                self.location_folders
                and photo.gps_latitude is not None
                and photo.gps_longitude is not None
            ):
                loc = location_map.get((photo.gps_latitude, photo.gps_longitude))
                if loc:
                    country, city = loc

            if self.location_folders and (country and city):
                target_path = photo.get_expected_folder_path_with_location(
                    self.target_layout, country, city
                )
            else:
                target_path = photo.get_expected_folder_path(self.target_layout)
            if target_path is None:
                continue

            # Check if target folder exists in catalog
            folder_key = (photo.root_folder_id, target_path)
            target_folder = self.existing_folders.get(folder_key)

            target_folder_id = None
            if target_folder:
                target_folder_id = target_folder.id_local
            else:
                # Need to create folder(s)
                self._ensure_folder_chain(plan, photo.root_folder_id, target_path)

            # Check for filename collision
            if target_folder_id is not None:
                # Folder exists in catalog — query the DB
                new_basename = self._resolve_collision(
                    target_folder_id, photo.base_name, photo.extension
                )
            else:
                # Folder to be created — resolve against other planned moves
                taken = in_plan.setdefault(folder_key, set())
                new_basename = _resolve_in_plan(photo.base_name, photo.extension, taken)
                taken.add(f"{new_basename}.{photo.extension}")

            change = FileChange(
                change_type=ChangeType.MOVE_PHOTO,
                photo=photo,
                source_folder_path=photo.current_folder_path,
                target_folder_path=target_path,
                target_folder_id=target_folder_id,
            )

            # If there's a collision, also rename
            if new_basename != photo.base_name:
                change.old_name = photo.base_name
                change.new_name = new_basename

            plan.changes.append(change)

    def _plan_renames(self, plan: ChangePlan) -> None:
        """Plan renames for files with duplicate prefixes."""
        duplicates = self.scanner.scan_duplicate_prefixes()

        for photo, cleaned_name in duplicates:
            # Check for collision with cleaned name
            final_name = self._resolve_collision(
                photo.folder_id, cleaned_name, photo.extension
            )

            plan.changes.append(
                FileChange(
                    change_type=ChangeType.RENAME_FILE,
                    photo=photo,
                    old_name=photo.base_name,
                    new_name=final_name,
                )
            )

    def _ensure_folder_chain(
        self, plan: ChangePlan, root_folder_id: int, target_path: str
    ) -> None:
        """Ensure all parent folders exist for the target path.

        For target_path "2023/06/", ensures both "2023/" and "2023/06/" exist.
        """
        parts = target_path.strip("/").split("/")
        for i in range(len(parts)):
            partial = "/".join(parts[: i + 1]) + "/"
            folder_key = (root_folder_id, partial)
            if (
                folder_key not in self.existing_folders
                and (root_folder_id, partial) not in plan.folders_to_create
            ):
                plan.folders_to_create.append((root_folder_id, partial))

    def _resolve_collision(self, folder_id: int, base_name: str, extension: str) -> str:
        """Resolve filename collision by appending _1, _2, etc."""
        cursor = self.conn.execute(
            QUERY_FILE_EXISTS_IN_FOLDER, (folder_id, base_name, extension)
        )
        if cursor.fetchone()[0] == 0:
            return base_name

        for counter in range(1, _MAX_COLLISION_TRIES + 1):
            candidate = f"{base_name}_{counter}"
            cursor = self.conn.execute(
                QUERY_FILE_EXISTS_IN_FOLDER, (folder_id, candidate, extension)
            )
            if cursor.fetchone()[0] == 0:
                return candidate

        raise RuntimeError(
            f"Cannot resolve collision for '{base_name}.{extension}' "
            f"after {_MAX_COLLISION_TRIES} tries"
        )

    def _get_next_folder_id(self) -> int:
        """Get the next available folder id_local."""
        cursor = self.conn.execute(QUERY_MAX_FOLDER_ID)
        max_id = cursor.fetchone()[0]
        return (max_id or 0) + 1
