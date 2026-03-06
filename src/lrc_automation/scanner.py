"""Catalog scanner for misplaced photos and duplicate filenames."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .geocoder import LocationResolver

from .constants import (
    DEFAULT_TARGET_LAYOUT,
    QUERY_ALL_FOLDERS,
    QUERY_ALL_PHOTOS,
    QUERY_ALL_PHOTOS_WITH_GPS,
    QUERY_ROOT_FOLDERS,
)
from .models import Folder, PhotoRecord, RootFolder
from .utils import (
    clean_duplicate_prefix,
    convert_prefix_format,
    extract_date_from_path,
    parse_capture_time,
)


class CatalogScanner:
    """Scans a Lightroom Classic catalog for problems."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        target_layout: str = DEFAULT_TARGET_LAYOUT,
        location_folders: bool = False,
    ) -> None:
        self.conn = conn
        self.target_layout = target_layout
        self.location_folders = location_folders

    def get_root_folders(self) -> list[RootFolder]:
        """Return all root folders."""
        cursor = self.conn.execute(QUERY_ROOT_FOLDERS)
        return [
            RootFolder(id_local=row["id_local"], absolute_path=row["absolutePath"])
            for row in cursor
        ]

    def get_all_folders(self) -> dict[tuple[int, str], Folder]:
        """Return dict keyed by (root_folder_id, pathFromRoot) -> Folder."""
        cursor = self.conn.execute(QUERY_ALL_FOLDERS)
        return {
            (row["rootFolder"], row["pathFromRoot"]): Folder(
                id_local=row["id_local"],
                id_global=row["id_global"],
                path_from_root=row["pathFromRoot"],
                root_folder_id=row["rootFolder"],
            )
            for row in cursor
        }

    def _fetch_all_photos(self) -> list[PhotoRecord]:
        """Fetch all non-virtual-copy photos from the catalog."""
        if self.location_folders:
            return self._fetch_all_photos_with_gps()
        cursor = self.conn.execute(QUERY_ALL_PHOTOS)
        photos = []
        for row in cursor:
            photos.append(
                PhotoRecord(
                    image_id=row["image_id"],
                    file_id=row["file_id"],
                    folder_id=row["folder_id"],
                    root_folder_id=row["root_folder_id"],
                    base_name=row["baseName"],
                    extension=row["extension"],
                    sidecar_extensions=row["sidecarExtensions"],
                    capture_time=parse_capture_time(row["captureTime"]),
                    current_folder_path=row["pathFromRoot"],
                    root_absolute_path=row["absolutePath"],
                    original_filename=row["originalFilename"],
                )
            )
        return photos

    def _fetch_all_photos_with_gps(self) -> list[PhotoRecord]:
        """Fetch all photos with GPS data from LEFT JOIN."""
        cursor = self.conn.execute(QUERY_ALL_PHOTOS_WITH_GPS)
        photos = []
        for row in cursor:
            photos.append(
                PhotoRecord(
                    image_id=row["image_id"],
                    file_id=row["file_id"],
                    folder_id=row["folder_id"],
                    root_folder_id=row["root_folder_id"],
                    base_name=row["baseName"],
                    extension=row["extension"],
                    sidecar_extensions=row["sidecarExtensions"],
                    capture_time=parse_capture_time(row["captureTime"]),
                    current_folder_path=row["pathFromRoot"],
                    root_absolute_path=row["absolutePath"],
                    gps_latitude=float(row["gpsLatitude"])
                    if row["gpsLatitude"] is not None
                    else None,
                    gps_longitude=float(row["gpsLongitude"])
                    if row["gpsLongitude"] is not None
                    else None,
                    original_filename=row["originalFilename"],
                )
            )
        return photos

    def scan_misplaced_photos(self) -> list[PhotoRecord]:
        """Return photos whose current folder doesn't match captureTime."""
        misplaced = []
        for photo in self._fetch_all_photos():
            if photo.capture_time is None:
                continue

            expected = photo.get_expected_folder_path(self.target_layout)
            if expected is None:
                continue

            # Extract year/month from full folder path (root + pathFromRoot)
            norm_root = photo.root_absolute_path.replace("\\", "/")
            full_folder = norm_root + photo.current_folder_path
            actual_ym = extract_date_from_path(full_folder)
            expected_ym = (photo.capture_time.year, photo.capture_time.month)

            if actual_ym is None:
                # Folder doesn't follow target layout pattern, skip
                continue

            if actual_ym != expected_ym:
                misplaced.append(photo)

        return misplaced

    def scan_duplicate_prefixes(self) -> list[tuple[PhotoRecord, str]]:
        """Return photos with duplicated date prefix and their cleaned names.

        Returns list of (photo, cleaned_name) tuples.
        """
        duplicates = []
        for photo in self._fetch_all_photos():
            cleaned = clean_duplicate_prefix(photo.base_name)
            if cleaned is not None:
                duplicates.append((photo, cleaned))
        return duplicates

    def scan_prefix_format(
        self,
        resolver: LocationResolver | None = None,
    ) -> list[tuple[PhotoRecord, str, tuple[str, str] | None]]:
        """Return photos with DDMMYYYY prefix that should be YYMMDD.

        Returns (photo, proposed_name, location) tuples where:
        - proposed_name is YYMMDD-rest (Country/City goes in the folder, not the name)
        - location is (country, city) from GPS, or None

        Results are sorted so GPS-tagged photos come first.
        """
        # First pass: collect candidates and GPS coords for batch resolution
        candidates: list[tuple[PhotoRecord, str]] = []
        gps_coords: list[tuple[float, float]] = []

        for photo in self._fetch_all_photos():
            converted = convert_prefix_format(photo.base_name)
            if converted is None:
                continue
            candidates.append((photo, converted))
            if (
                resolver is not None
                and photo.gps_latitude is not None
                and photo.gps_longitude is not None
            ):
                gps_coords.append((photo.gps_latitude, photo.gps_longitude))

        # Batch-resolve all GPS coordinates in a single K-D tree query
        location_map: dict[tuple[float, float], tuple[str, str]] = {}
        if gps_coords and resolver is not None:
            location_map = resolver.resolve_batch(gps_coords)

        # Second pass: assemble results with resolved locations
        results: list[tuple[PhotoRecord, str, tuple[str, str] | None]] = []
        for photo, converted in candidates:
            location: tuple[str, str] | None = None
            if photo.gps_latitude is not None and photo.gps_longitude is not None:
                location = location_map.get((photo.gps_latitude, photo.gps_longitude))
            results.append((photo, converted, location))

        # GPS-tagged photos first so the report is immediately useful
        results.sort(key=lambda x: x[2] is None)
        return results

    def get_total_photo_count(self) -> int:
        """Return total number of non-virtual-copy photos."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM Adobe_images WHERE masterImage IS NULL"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def scan_needs_location_folder(self) -> list[PhotoRecord]:
        """Return GPS photos in a date-recognized folder needing a location folder.

        Returns every GPS photo whose current folder contains a date matching its
        capture time, regardless of whether it already has a location subfolder.
        The planner resolves GPS and skips photos whose computed target path
        already equals the current path (i.e. already in the correct CC/City folder).

        This means photos in wrong-format location folders (e.g. "Switzerland/Saillon/"
        instead of "CH/Saillon/") are returned so the planner can re-move them.
        Only meaningful when location_folders=True.
        """
        if not self.location_folders:
            return []
        result = []
        for photo in self._fetch_all_photos():
            if photo.gps_latitude is None or photo.gps_longitude is None:
                continue
            if photo.capture_time is None:
                continue
            # Check the current folder contains a date matching capture time
            norm_root = photo.root_absolute_path.replace("\\", "/")
            full_folder = norm_root + photo.current_folder_path
            actual_ym = extract_date_from_path(full_folder)
            expected_ym = (photo.capture_time.year, photo.capture_time.month)
            if actual_ym is None or actual_ym != expected_ym:
                # No recognised date, or date mismatch — handled by scan_misplaced
                continue
            result.append(photo)
        return result

    def scan_year_in_year_photos(self) -> list[PhotoRecord]:
        """Return photos whose root folder year differs from the year in pathFromRoot.

        Example: a 2003 photo imported in 2022 may live at:
          root absolutePath = "/Lightroom/2022/"
          pathFromRoot      = "2003/12/"
        These photos are physically in the wrong yearly root folder.
        """
        result = []
        for photo in self._fetch_all_photos():
            # Extract root year from last component of root_absolute_path
            norm_root = photo.root_absolute_path.replace("\\", "/")
            root_year_str = norm_root.rstrip("/").split("/")[-1]
            if not root_year_str.isdigit():
                continue
            root_year = int(root_year_str)
            # Extract path year from first component of current_folder_path
            path_year_str = photo.current_folder_path.split("/")[0]
            if not path_year_str.isdigit():
                continue
            path_year = int(path_year_str)
            if root_year != path_year and 1900 <= path_year <= 2100:
                result.append(photo)
        return result
