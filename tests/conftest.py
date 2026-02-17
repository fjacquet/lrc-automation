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
    id_local INTEGER PRIMARY KEY,
    image INTEGER,
    dateTimeOriginal TEXT,
    focalLength REAL,
    aperture REAL,
    isoSpeedRating INTEGER,
    gpsLatitude REAL,
    gpsLongitude REAL,
    hasGPS INTEGER DEFAULT 0
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
    for exif in data.get("exif", []):
        conn.execute(
            "INSERT INTO AgHarvestedExifMetadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            exif,
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


def gps_test_data() -> dict:
    """Test data with GPS coordinates on some photos."""
    root_path = "/tmp/test_photos/"
    return {
        "roots": [
            (1, "ROOT-UUID-1", root_path, "test_photos", "../test_photos"),
        ],
        "folders": [
            (1, "FOLD-UUID-1", "2023/06/", 1),
            (2, "FOLD-UUID-2", "2023/07/", 1),
        ],
        "files": [
            # Photo 1: has GPS (Zurich), misplaced in 2023/07/
            (
                1,
                "FILE-UUID-1",
                "IMG_GPS_1",
                "JPG",
                2,
                "IMG_GPS_1",
                None,
                None,
                "IMG_GPS_1.JPG",
                None,
            ),
            # Photo 2: has GPS (Paris), misplaced in 2023/07/
            (
                2,
                "FILE-UUID-2",
                "IMG_GPS_2",
                "JPG",
                2,
                "IMG_GPS_2",
                None,
                None,
                "IMG_GPS_2.JPG",
                None,
            ),
            # Photo 3: no GPS, correctly placed
            (
                3,
                "FILE-UUID-3",
                "IMG_NOGPS_1",
                "JPG",
                1,
                "IMG_NOGPS_1",
                None,
                None,
                "IMG_NOGPS_1.JPG",
                None,
            ),
            # Photo 4: no GPS, misplaced in 2023/07/
            (
                4,
                "FILE-UUID-4",
                "IMG_NOGPS_2",
                "DNG",
                2,
                "IMG_NOGPS_2",
                None,
                None,
                "IMG_NOGPS_2.DNG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-1", "2023-06-15T14:30:00", 1, "JPG", 0, 3, "AB", None, None),
            (2, "IMG-UUID-2", "2023-06-20T10:00:00", 2, "JPG", 0, 4, "AB", None, None),
            (3, "IMG-UUID-3", "2023-06-10T08:00:00", 3, "JPG", 0, 5, "AB", None, None),
            (4, "IMG-UUID-4", "2023-06-25T12:00:00", 4, "DNG", 0, 2, "AB", None, None),
        ],
        "exif": [
            # Photo 1: Zurich GPS
            (1, 1, "2023-06-15T14:30:00", None, None, None, 47.3769, 8.5417, 1),
            # Photo 2: Paris GPS
            (2, 2, "2023-06-20T10:00:00", None, None, None, 48.8566, 2.3522, 1),
            # Photo 3: no GPS
            (3, 3, "2023-06-10T08:00:00", None, None, None, None, None, 0),
            # Photo 4: no GPS
            (4, 4, "2023-06-25T12:00:00", None, None, None, None, None, 0),
        ],
    }


@pytest.fixture
def tmp_catalog_with_gps(tmp_path: Path) -> Path:
    """Create a temporary test catalog with GPS EXIF data."""
    db_path = tmp_path / "test_gps.lrcat"
    return create_test_catalog(db_path, gps_test_data())


def diverse_folder_test_data() -> dict:
    """Test data with ISO-date, French-date, year-in-root, and topical folders."""
    # Root path contains a year: /tmp/test_photos/2021/
    root_path = "/tmp/test_photos/2021/"
    return {
        "roots": [
            (1, "ROOT-UUID-1", root_path, "2021", "../test_photos/2021"),
        ],
        "folders": [
            # ISO date folder: 2023-12-24
            (10, "FOLD-UUID-10", "2023-12-24/", 1),
            # French date folder: 1 avril 2016
            (11, "FOLD-UUID-11", "1 avril 2016/", 1),
            # Bare month under year-in-root: 06/
            (12, "FOLD-UUID-12", "06/", 1),
            # Topical folder (no date)
            (13, "FOLD-UUID-13", "Vacances/", 1),
            # Standard YYYY/MM folder
            (14, "FOLD-UUID-14", "2022/03/", 1),
        ],
        "files": [
            # file_id 10: ISO date folder, correctly placed (same year+month)
            (
                10,
                "FILE-UUID-10",
                "IMG_2010",
                "JPG",
                10,
                "IMG_2010",
                None,
                None,
                "IMG_2010.JPG",
                None,
            ),
            # file_id 11: French date folder, correctly placed
            (
                11,
                "FILE-UUID-11",
                "IMG_2011",
                "JPG",
                11,
                "IMG_2011",
                None,
                None,
                "IMG_2011.JPG",
                None,
            ),
            # file_id 12: year-in-root + month folder, correctly placed
            (
                12,
                "FILE-UUID-12",
                "IMG_2012",
                "CR2",
                12,
                "IMG_2012",
                None,
                None,
                "IMG_2012.CR2",
                None,
            ),
            # file_id 13: topical folder, no date detectable
            (
                13,
                "FILE-UUID-13",
                "IMG_2013",
                "DNG",
                13,
                "IMG_2013",
                None,
                None,
                "IMG_2013.DNG",
                None,
            ),
            # file_id 14: standard YYYY/MM, misplaced (03 != 05)
            (
                14,
                "FILE-UUID-14",
                "IMG_2014",
                "JPG",
                14,
                "IMG_2014",
                None,
                None,
                "IMG_2014.JPG",
                None,
            ),
        ],
        "images": [
            # 10: captured 2023-12-15, in 2023-12-24/ → same year+month
            (
                10,
                "IMG-UUID-10",
                "2023-12-15T10:00:00",
                10,
                "JPG",
                0,
                3,
                "AB",
                None,
                None,
            ),
            # 11: captured 2016-04-01, in "1 avril 2016/" → correct
            (
                11,
                "IMG-UUID-11",
                "2016-04-01T12:00:00",
                11,
                "JPG",
                0,
                4,
                "AB",
                None,
                None,
            ),
            # 12: captured 2021-06-10, root=2021/, path=06/ → correct
            (
                12,
                "IMG-UUID-12",
                "2021-06-10T08:00:00",
                12,
                "RAW",
                0,
                5,
                "AB",
                None,
                None,
            ),
            # 13: captured 2020-08-15, in Vacances/ → no date → skipped
            (
                13,
                "IMG-UUID-13",
                "2020-08-15T14:00:00",
                13,
                "DNG",
                0,
                2,
                "AB",
                None,
                None,
            ),
            # 14: captured 2022-05-20, in 2022/03/ → misplaced (03 != 05)
            (
                14,
                "IMG-UUID-14",
                "2022-05-20T09:00:00",
                14,
                "JPG",
                0,
                1,
                "AB",
                None,
                None,
            ),
        ],
    }


@pytest.fixture
def diverse_folder_catalog(tmp_path: Path) -> Path:
    """Create a test catalog with diverse folder naming patterns."""
    db_path = tmp_path / "test_diverse.lrcat"
    return create_test_catalog(db_path, diverse_folder_test_data())
