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

    @property
    def full_path(self) -> Path:
        return (
            Path(self.root_absolute_path)
            / self.current_folder_path
            / f"{self.base_name}.{self.extension}"
        )

    @property
    def expected_folder_path(self) -> str | None:
        """Derive YYYY/MM/ from capture_time."""
        if self.capture_time:
            return f"{self.capture_time.year}/{self.capture_time.month:02d}/"
        return None


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

    def record_success(self, change: FileChange) -> None:
        self.succeeded.append(change)

    def record_error(self, change: FileChange, error: str) -> None:
        self.failed.append((change, error))

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)
