"""Data models for Lightroom Classic catalog automation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ChangeType(Enum):
    MOVE_PHOTO = "move_photo"
    RENAME_FILE = "rename_file"


@dataclass
class RootFolder:
    id_local: int
    absolute_path: str


@dataclass
class Folder:
    id_local: int
    id_global: str
    path_from_root: str
    root_folder_id: int


@dataclass
class PhotoRecord:
    image_id: int
    file_id: int
    folder_id: int
    root_folder_id: int
    base_name: str
    extension: str
    sidecar_extensions: str | None
    capture_time: datetime | None
    current_folder_path: str
    root_absolute_path: str
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    original_filename: str | None = None

    @property
    def full_path(self) -> Path:
        return (
            Path(self.root_absolute_path)
            / self.current_folder_path
            / f"{self.base_name}.{self.extension}"
        )

    @property
    def expected_folder_path(self) -> str | None:
        """Derive target folder from capture_time using default layout."""
        from .constants import DEFAULT_TARGET_LAYOUT

        return self.get_expected_folder_path(DEFAULT_TARGET_LAYOUT)

    def get_expected_folder_path(self, layout: str) -> str | None:
        """Derive target folder from capture_time using given strftime layout."""
        if self.capture_time:
            path = self.capture_time.strftime(layout)
            if not path.endswith("/"):
                path += "/"
            return path
        return None

    def get_expected_folder_path_with_location(
        self,
        layout: str,
        country: str | None,
        city: str | None,
    ) -> str | None:
        """Derive target folder with optional Country/City subfolder.

        Returns date path + Country/City/ when both are available,
        otherwise falls back to date-only path.
        """
        base = self.get_expected_folder_path(layout)
        if base is None:
            return None
        if country and city:
            return f"{base}{country}/{city}/"
        return base


@dataclass
class FileChange:
    change_type: ChangeType
    photo: PhotoRecord
    # For MOVE_PHOTO
    source_folder_path: str | None = None
    target_folder_path: str | None = None
    target_folder_id: int | None = None
    # For RENAME_FILE
    old_name: str | None = None
    new_name: str | None = None


@dataclass
class ChangePlan:
    changes: list[FileChange] = field(default_factory=list)
    folders_to_create: list[tuple[int, str]] = field(
        default_factory=list
    )  # (root_id, pathFromRoot)

    @property
    def move_count(self) -> int:
        return sum(1 for c in self.changes if c.change_type == ChangeType.MOVE_PHOTO)

    @property
    def rename_count(self) -> int:
        return sum(1 for c in self.changes if c.change_type == ChangeType.RENAME_FILE)


@dataclass
class ExecutionReport:
    succeeded: list[FileChange] = field(default_factory=list)
    failed: list[tuple[FileChange, str]] = field(default_factory=list)
    rolled_back: bool = False
    folders_removed: int = 0

    def record_success(self, change: FileChange) -> None:
        self.succeeded.append(change)

    def record_error(self, change: FileChange, error: str) -> None:
        self.failed.append((change, error))

    def mark_rolled_back(self) -> None:
        """Called when a failure triggered a full rollback of all changes."""
        self.rolled_back = True
        self.succeeded.clear()

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)


@dataclass
class MissingFile:
    """A catalog file record whose expected disk path does not exist."""

    expected_path: Path
    base_name: str
    extension: str
    root_folder_id: int
    file_id: int
    found_at: list[Path]  # empty → truly missing; multiple → ambiguous match

    @property
    def status(self) -> str:
        if not self.found_at:
            return "truly_missing"
        if len(self.found_at) == 1:
            return "found_elsewhere"
        return "ambiguous"


@dataclass
class FileAuditResult:
    """Result of a full disk audit across all catalog records."""

    total_checked: int
    missing: list[MissingFile]

    @property
    def present_count(self) -> int:
        return self.total_checked - len(self.missing)

    @property
    def found_elsewhere_count(self) -> int:
        return sum(1 for m in self.missing if m.found_at)

    @property
    def truly_missing_count(self) -> int:
        return sum(1 for m in self.missing if not m.found_at)


@dataclass
class ReconcileChange:
    """A single catalog pointer fix: AgLibraryFile.folder updated to actual location."""

    file_id: int
    old_folder_id: int
    new_folder_id: int
    actual_path: Path
    expected_path: Path


@dataclass
class ReconcileReport:
    """Summary of a reconcile run."""

    reconciled: list[ReconcileChange] = field(default_factory=list)
    skipped_ambiguous: list[MissingFile] = field(default_factory=list)
    truly_missing: list[MissingFile] = field(default_factory=list)
