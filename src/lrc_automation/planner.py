"""Change planner - builds execution plans from scan results."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .constants import (
    DEFAULT_TARGET_LAYOUT,
    QUERY_FILE_EXISTS_IN_FOLDER,
    QUERY_MAX_FOLDER_ID,
)
from .models import ChangePlan, ChangeType, FileChange, PhotoRecord
from .scanner import CatalogScanner
from .utils import date_portion_of_path

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
            if self.location_folders:
                self._plan_location_moves(plan)

        if include_renames:
            self._plan_renames(plan)

        return plan

    def _plan_moves(self, plan: ChangePlan) -> None:
        """Plan moves for misplaced photos."""
        misplaced = self.scanner.scan_misplaced_photos()
        location_map = self._build_location_map(misplaced)
        in_plan: dict[tuple[int, str], set[str]] = {}

        for photo in misplaced:
            target_path = self._compute_target_path(photo, location_map)
            if target_path is None:
                continue
            self._add_move_change(plan, photo, target_path, in_plan)

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

    def _plan_location_moves(self, plan: ChangePlan) -> None:
        """Plan location-subfolder moves for GPS photos in date-correct folders."""
        candidates = self.scanner.scan_needs_location_folder()
        if not candidates:
            return
        location_map = self._build_location_map(candidates)
        in_plan: dict[tuple[int, str], set[str]] = {}

        for photo in candidates:
            loc = location_map.get((photo.gps_latitude, photo.gps_longitude))  # type: ignore[arg-type]
            if not loc:
                continue
            country, city = loc
            if photo.capture_time is None:
                continue
            date_pfx = date_portion_of_path(
                photo.current_folder_path,
                photo.capture_time.year,
                photo.capture_time.month,
            )
            # In per-year roots the year lives in absolutePath, not in pathFromRoot.
            # A previous bad run may have stored pathFromRoot with the year prefix
            # (e.g. "2025/12/Switzerland/...").  date_portion_of_path then returns
            # "2025/12/" which, joined to the root, doubles the year.  Strip it.
            year_str = str(photo.capture_time.year)
            root_tail = Path(photo.root_absolute_path.rstrip("/")).name
            if root_tail == year_str and date_pfx.startswith(year_str + "/"):
                date_pfx = date_pfx[len(year_str) + 1 :]
            target_path = f"{date_pfx}{country}/{city}/"
            if target_path == photo.current_folder_path:
                continue
            self._add_move_change(plan, photo, target_path, in_plan)

    def _build_location_map(
        self, photos: list[PhotoRecord]
    ) -> dict[tuple[float, float], tuple[str, str]]:
        """Batch-resolve GPS coordinates to (country, city) via LocationResolver."""
        if not self.location_folders:
            return {}
        from .geocoder import LocationResolver

        resolver = LocationResolver()
        coords = [
            (p.gps_latitude, p.gps_longitude)
            for p in photos
            if p.gps_latitude is not None and p.gps_longitude is not None
        ]
        if not coords:
            return {}
        return resolver.resolve_batch(coords)

    def _compute_target_path(
        self,
        photo: PhotoRecord,
        location_map: dict[tuple[float, float], tuple[str, str]],
    ) -> str | None:
        """Compute target folder path, including optional location subfolder."""
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

        if self.location_folders and country and city:
            return photo.get_expected_folder_path_with_location(
                self.target_layout, country, city
            )
        return photo.get_expected_folder_path(self.target_layout)

    def _add_move_change(
        self,
        plan: ChangePlan,
        photo: PhotoRecord,
        target_path: str,
        in_plan: dict[tuple[int, str], set[str]],
    ) -> None:
        """Add a MOVE_PHOTO change, handling folder creation and name collision."""
        folder_key = (photo.root_folder_id, target_path)
        target_folder = self.existing_folders.get(folder_key)

        target_folder_id = None
        if target_folder:
            target_folder_id = target_folder.id_local
        else:
            self._ensure_folder_chain(plan, photo.root_folder_id, target_path)

        if target_folder_id is not None:
            new_basename = self._resolve_collision(
                target_folder_id, photo.base_name, photo.extension
            )
        else:
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
        if new_basename != photo.base_name:
            change.old_name = photo.base_name
            change.new_name = new_basename
        plan.changes.append(change)

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
