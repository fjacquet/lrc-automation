"""Utility functions for date parsing, path helpers, UUID generation."""

import re
import uuid
from datetime import datetime

from .constants import (
    DUPLICATE_PREFIX_PATTERN,
    FOLDER_YYYY_MM_PATTERN,
    IMG_DATE_PATTERN,
)


def parse_capture_time(value: str | None) -> datetime | None:
    """Parse Lightroom captureTime string to datetime.

    Lightroom stores captureTime as ISO 8601 strings like:
    - "2023-06-15T14:30:00"
    - "2023-06-15T14:30:00+02:00"
    - "2023:06:15 14:30:00" (EXIF-style)
    """
    if not value:
        return None

    # Try ISO 8601 format first
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    # Try parsing with timezone offset stripped
    cleaned = re.sub(r"[+-]\d{2}:\d{2}$", "", value)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    return None


def extract_yyyy_mm(path_from_root: str) -> tuple[int, int] | None:
    """Extract (year, month) from a pathFromRoot like '2023/06/'."""
    match = FOLDER_YYYY_MM_PATTERN.match(path_from_root)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1900 <= year <= 2100 and 1 <= month <= 12:
            return year, month
        return None

    # Try extracting from longer paths like "2023/06/subfolder/"
    parts = path_from_root.strip("/").split("/")
    if len(parts) >= 2:
        try:
            year = int(parts[0])
            month = int(parts[1])
            if 1900 <= year <= 2100 and 1 <= month <= 12:
                return year, month
        except ValueError:
            pass

    return None


def clean_duplicate_prefix(base_name: str) -> str | None:
    """Clean a filename with duplicated date prefix.

    Example: '29122012-29122012-IMG_20121229_131334' -> '29122012-IMG_131334'

    Returns the cleaned name, or None if no duplicate prefix found.
    """
    match = DUPLICATE_PREFIX_PATTERN.match(base_name)
    if not match:
        return None

    prefix = match.group(1)  # e.g. "29122012"
    rest = match.group(2)  # e.g. "IMG_20121229_131334"

    # Also strip redundant date from IMG_YYYYMMDD_NNNNNN -> IMG_NNNNNN
    img_match = IMG_DATE_PATTERN.match(rest)
    if img_match:
        rest = f"IMG_{img_match.group(2)}"

    return f"{prefix}-{rest}"


def generate_uuid() -> str:
    """Generate a UUID4 string in the format Lightroom uses."""
    return str(uuid.uuid4()).upper()


def build_full_path(
    root_absolute: str, path_from_root: str, base_name: str, extension: str
) -> str:
    """Reconstruct the full file path."""
    return f"{root_absolute}{path_from_root}{base_name}.{extension}"


def parse_sidecar_extensions(sidecar_str: str | None) -> list[str]:
    """Parse the sidecarExtensions column value.

    Example: "JPG,xmp" -> ["JPG", "xmp"]
    """
    if not sidecar_str:
        return []
    return [ext.strip() for ext in sidecar_str.split(",") if ext.strip()]
