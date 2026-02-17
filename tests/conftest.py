"""Test fixtures for lrc-automation tests."""

import sqlite3
from pathlib import Path

import pytest

SCHEMA_SQL = """
CREATE TABLE AgLibraryRootFolder (
    id_local INTEGER PRIMARY KEY,
    id_global TEXT,
    absolutePath TEXT,
    name TEXT,
    relativePathFromCatalog TEXT
);

CREATE TABLE AgLibraryFolder (
    id_local INTEGER PRIMARY KEY,
    id_global TEXT,
    pathFromRoot TEXT,
    rootFolder INTEGER
);

CREATE TABLE AgLibraryFile (
    id_local INTEGER PRIMARY KEY,
    id_global TEXT,
    baseName TEXT,
    extension TEXT,
    folder INTEGER,
    idx_filename TEXT,
    importHash TEXT,
    md5 TEXT,
    originalFilename TEXT,
    sidecarExtensions TEXT
);

CREATE TABLE Adobe_images (
    id_local INTEGER PRIMARY KEY,
    id_global TEXT,
    captureTime TEXT,
    rootFile INTEGER,
    fileFormat TEXT,
    pick INTEGER,
    rating INTEGER,
    orientation TEXT,
    masterImage INTEGER,
    copyName TEXT
);

CREATE TABLE AgHarvestedExifMetadata (
    image INTEGER,
    dateTimeOriginal TEXT,
    focalLength REAL,
    aperture REAL,
    isoSpeedRating INTEGER
);

CREATE TABLE Adobe_variablesTable (
    id_local INTEGER PRIMARY KEY,
    name TEXT,
    value TEXT
);

INSERT INTO Adobe_variablesTable (id_local, name, value)
VALUES (1, 'Adobe_DBVersion', '1700');
"""


def create_test_catalog(db_path: Path, data: dict | None = None) -> Path:
    """Create a minimal test .lrcat catalog."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)

    if data is None:
        data = default_test_data()

    for root in data.get("roots", []):
        conn.execute(
            "INSERT INTO AgLibraryRootFolder VALUES (?, ?, ?, ?, ?)",
            root,
        )
    for folder in data.get("folders", []):
        conn.execute(
            "INSERT INTO AgLibraryFolder VALUES (?, ?, ?, ?)",
            folder,
        )
    for file in data.get("files", []):
        conn.execute(
            "INSERT INTO AgLibraryFile VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            file,
        )
    for image in data.get("images", []):
        conn.execute(
            "INSERT INTO Adobe_images VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            image,
        )

    conn.commit()
    conn.close()
    return db_path


def default_test_data() -> dict:
    """Default test data with some misplaced photos and duplicates."""
    root_path = "/tmp/test_photos/"
    return {
        "roots": [
            (1, "ROOT-UUID-1", root_path, "test_photos", "../test_photos"),
        ],
        "folders": [
            (1, "FOLD-UUID-1", "2023/06/", 1),
            (2, "FOLD-UUID-2", "2023/07/", 1),
            (3, "FOLD-UUID-3", "2022/12/", 1),
        ],
        "files": [
            # Correctly placed photo
            (
                1,
                "FILE-UUID-1",
                "IMG_1001",
                "CR2",
                1,
                "IMG_1001",
                None,
                None,
                "IMG_1001.CR2",
                "xmp",
            ),
            # Misplaced photo: in 2023/07 but captured in 2023/06
            (
                2,
                "FILE-UUID-2",
                "IMG_1002",
                "JPG",
                2,
                "IMG_1002",
                None,
                None,
                "IMG_1002.JPG",
                None,
            ),
            # Duplicate prefix photo
            (
                3,
                "FILE-UUID-3",
                "29122012-29122012-IMG_20121229_131334",
                "JPG",
                3,
                "29122012-29122012-IMG_20121229_131334",
                None,
                None,
                "IMG_20121229_131334.JPG",
                None,
            ),
            # Another misplaced photo
            (
                4,
                "FILE-UUID-4",
                "IMG_1003",
                "DNG",
                2,
                "IMG_1003",
                None,
                None,
                "IMG_1003.DNG",
                None,
            ),
        ],
        "images": [
            # Correctly placed: captured 2023-06, in folder 2023/06/
            (1, "IMG-UUID-1", "2023-06-15T14:30:00", 1, "RAW", 0, 3, "AB", None, None),
            # Misplaced: captured 2023-06, in folder 2023/07/
            (2, "IMG-UUID-2", "2023-06-20T10:00:00", 2, "JPG", 0, 4, "AB", None, None),
            # Duplicate prefix: captured 2012-12-29, in folder 2022/12/
            (3, "IMG-UUID-3", "2012-12-29T13:13:34", 3, "JPG", 0, 0, "AB", None, None),
            # Misplaced: captured 2023-06, in folder 2023/07/
            (4, "IMG-UUID-4", "2023-06-25T08:00:00", 4, "DNG", 0, 5, "AB", None, None),
        ],
    }


@pytest.fixture
def tmp_catalog(tmp_path: Path) -> Path:
    """Create a temporary test catalog."""
    db_path = tmp_path / "test.lrcat"
    return create_test_catalog(db_path)


@pytest.fixture
def tmp_catalog_with_files(tmp_path: Path) -> tuple[Path, Path]:
    """Create a test catalog with actual files on disk."""
    root_dir = tmp_path / "photos"
    root_path = str(root_dir) + "/"

    data = {
        "roots": [
            (1, "ROOT-UUID-1", root_path, "photos", "../photos"),
        ],
        "folders": [
            (1, "FOLD-UUID-1", "2023/06/", 1),
            (2, "FOLD-UUID-2", "2023/07/", 1),
        ],
        "files": [
            (
                1,
                "FILE-UUID-1",
                "IMG_1001",
                "JPG",
                1,
                "IMG_1001",
                None,
                None,
                "IMG_1001.JPG",
                None,
            ),
            (
                2,
                "FILE-UUID-2",
                "IMG_1002",
                "JPG",
                2,
                "IMG_1002",
                None,
                None,
                "IMG_1002.JPG",
                None,
            ),
            (
                3,
                "FILE-UUID-3",
                "29122012-29122012-IMG_20121229_131334",
                "JPG",
                2,
                "29122012-29122012-IMG_20121229_131334",
                None,
                None,
                "original.JPG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-1", "2023-06-15T14:30:00", 1, "JPG", 0, 3, "AB", None, None),
            (2, "IMG-UUID-2", "2023-06-20T10:00:00", 2, "JPG", 0, 4, "AB", None, None),
            (3, "IMG-UUID-3", "2023-07-01T12:00:00", 3, "JPG", 0, 0, "AB", None, None),
        ],
    }

    db_path = tmp_path / "test.lrcat"
    create_test_catalog(db_path, data)

    # Create actual files on disk
    for folder_path in ["2023/06/", "2023/07/"]:
        (root_dir / folder_path).mkdir(parents=True, exist_ok=True)

    (root_dir / "2023/06/IMG_1001.JPG").write_text("photo1")
    (root_dir / "2023/07/IMG_1002.JPG").write_text("photo2")
    (root_dir / "2023/07/29122012-29122012-IMG_20121229_131334.JPG").write_text(
        "photo3"
    )

    return db_path, root_dir
