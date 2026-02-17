"""Catalog scanner for misplaced photos and duplicate filenames."""

import sqlite3

from .constants import (
    DEFAULT_TARGET_LAYOUT,
    QUERY_ALL_FOLDERS,
    QUERY_ALL_PHOTOS,
    QUERY_ALL_PHOTOS_WITH_GPS,
    QUERY_ROOT_FOLDERS,
)
from .models import Folder, PhotoRecord, RootFolder
from .utils import clean_duplicate_prefix, extract_yyyy_mm, parse_capture_time


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
                )
            )
        return photos

    def _fetch_all_photos_with_gps(self) -> list[PhotoRecord]:
        """Fetch all photos with GPS data from LEFT JOIN."""
        cursor = self.conn.execute(QUERY_ALL_PHOTOS_WITH_GPS)
        photos = []
        for row in cursor:
            has_gps = row["hasGPS"] == 1 if row["hasGPS"] is not None else False
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
                    if has_gps and row["gpsLatitude"] is not None
                    else None,
                    gps_longitude=float(row["gpsLongitude"])
                    if has_gps and row["gpsLongitude"] is not None
                    else None,
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

            # Extract YYYY/MM from actual folder path
            actual_ym = extract_yyyy_mm(photo.current_folder_path, self.target_layout)
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

    def get_total_photo_count(self) -> int:
        """Return total number of non-virtual-copy photos."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM Adobe_images WHERE masterImage IS NULL"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
