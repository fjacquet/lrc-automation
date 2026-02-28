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


def needs_location_test_data() -> dict:
    """Test data for scan_needs_location_folder: photos in date-only folder with GPS."""
    root_path = "/tmp/test_photos/"
    return {
        "roots": [
            (1, "ROOT-UUID-1", root_path, "test_photos", "../test_photos"),
        ],
        "folders": [
            # Date-only folder: photos that need a location subfolder
            (1, "FOLD-UUID-1", "2023/06/", 1),
            # Already in location subfolder
            (2, "FOLD-UUID-2", "2023/06/FR/Paris/", 1),
            # Date-only folder for no-GPS photo
            (3, "FOLD-UUID-3", "2023/07/", 1),
        ],
        "files": [
            # File 1: GPS, in date-only folder → should be returned
            (
                1,
                "FILE-UUID-1",
                "IMG_GPS_DATE",
                "JPG",
                1,
                "IMG_GPS_DATE",
                None,
                None,
                "IMG_GPS_DATE.JPG",
                None,
            ),
            # File 2: GPS, already in location subfolder → NOT returned
            (
                2,
                "FILE-UUID-2",
                "IMG_GPS_LOC",
                "JPG",
                2,
                "IMG_GPS_LOC",
                None,
                None,
                "IMG_GPS_LOC.JPG",
                None,
            ),
            # File 3: no GPS, in date-only folder → NOT returned
            (
                3,
                "FILE-UUID-3",
                "IMG_NOGPS",
                "JPG",
                3,
                "IMG_NOGPS",
                None,
                None,
                "IMG_NOGPS.JPG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-1", "2023-06-15T14:30:00", 1, "JPG", 0, 3, "AB", None, None),
            (2, "IMG-UUID-2", "2023-06-15T14:30:00", 2, "JPG", 0, 4, "AB", None, None),
            (3, "IMG-UUID-3", "2023-07-10T10:00:00", 3, "JPG", 0, 2, "AB", None, None),
        ],
        "exif": [
            (1, 1, "2023-06-15T14:30:00", None, None, None, 48.8566, 2.3522, 1),
            (2, 2, "2023-06-15T14:30:00", None, None, None, 48.8566, 2.3522, 1),
            (3, 3, "2023-07-10T10:00:00", None, None, None, None, None, 0),
        ],
    }


@pytest.fixture
def tmp_catalog_needs_location(tmp_path: Path) -> Path:
    """Catalog with GPS photos in date-only folder (candidates for location)."""
    db_path = tmp_path / "test_needs_location.lrcat"
    return create_test_catalog(db_path, needs_location_test_data())


def year_in_year_test_data() -> dict:
    """Test data for scan_year_in_year_photos: photos in wrong root year."""
    return {
        "roots": [
            (1, "ROOT-UUID-1", "/Lightroom/2022/", "2022", "../2022"),
        ],
        "folders": [
            # Wrong year in pathFromRoot (2003 vs root 2022)
            (1, "FOLD-UUID-1", "2003/12/", 1),
            # Correct year in pathFromRoot (2022)
            (2, "FOLD-UUID-2", "2022/06/", 1),
        ],
        "files": [
            # Year-in-year: root=2022, path=2003/12/
            (
                1,
                "FILE-UUID-1",
                "IMG_YIY",
                "JPG",
                1,
                "IMG_YIY",
                None,
                None,
                "IMG_YIY.JPG",
                None,
            ),
            # Correct: root=2022, path=2022/06/
            (
                2,
                "FILE-UUID-2",
                "IMG_OK",
                "JPG",
                2,
                "IMG_OK",
                None,
                None,
                "IMG_OK.JPG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-1", "2003-12-15T10:00:00", 1, "JPG", 0, 3, "AB", None, None),
            (2, "IMG-UUID-2", "2022-06-20T10:00:00", 2, "JPG", 0, 4, "AB", None, None),
        ],
    }


@pytest.fixture
def tmp_catalog_year_in_year(tmp_path: Path) -> Path:
    """Catalog with a photo in a year-in-year folder (wrong root year)."""
    db_path = tmp_path / "test_yiy.lrcat"
    return create_test_catalog(db_path, year_in_year_test_data())


def per_year_root_test_data(root_dir: str) -> dict:
    """Test data: per-year root (year in absolutePath, month-only pathFromRoot)."""
    root_path = root_dir if root_dir.endswith("/") else root_dir + "/"
    return {
        "roots": [
            (1, "ROOT-UUID-1", root_path, "2023", "../2023"),
        ],
        "folders": [
            # Per-year root: pathFromRoot contains only the month
            (1, "FOLD-UUID-1", "06/", 1),
        ],
        "files": [
            (
                1,
                "FILE-UUID-1",
                "IMG_PYR_1",
                "JPG",
                1,
                "IMG_PYR_1",
                None,
                None,
                "IMG_PYR_1.JPG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-1", "2023-06-15T14:30:00", 1, "JPG", 0, 3, "AB", None, None),
        ],
        "exif": [
            # Paris GPS coordinates
            (1, 1, "2023-06-15T14:30:00", None, None, None, 48.8566, 2.3522, 1),
        ],
    }


@pytest.fixture
def tmp_catalog_per_year_root(tmp_path: Path) -> tuple[Path, Path]:
    """Catalog with a per-year root (year in absolutePath, month-only pathFromRoot)."""
    root_dir = tmp_path / "2023"
    root_dir.mkdir()
    (root_dir / "06").mkdir()
    (root_dir / "06" / "IMG_PYR_1.JPG").write_text("photo")

    db_path = tmp_path / "test_pyr.lrcat"
    create_test_catalog(db_path, per_year_root_test_data(str(root_dir)))
    return db_path, root_dir


def per_year_root_damaged_test_data(root_dir: str) -> dict:
    """Test data: per-year root where pathFromRoot incorrectly includes the year.

    Simulates the damaged state left by the year-doubling bug (ADR-003): the file
    was moved to root/2023/06/Switzerland/Saillon/ and the DB recorded pathFromRoot
    as "2023/06/Switzerland/Saillon/" instead of "06/Switzerland/Saillon/".
    """
    root_path = root_dir if root_dir.endswith("/") else root_dir + "/"
    return {
        "roots": [
            (1, "ROOT-UUID-D", root_path, "2023", "../2023"),
        ],
        "folders": [
            # pathFromRoot wrongly contains the year — the damaged state
            (1, "FOLD-UUID-D", "2023/06/Switzerland/Saillon/", 1),
        ],
        "files": [
            (
                1,
                "FILE-UUID-D",
                "IMG_DAMAGED_1",
                "JPG",
                1,
                "IMG_DAMAGED_1",
                None,
                None,
                "IMG_DAMAGED_1.JPG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-D", "2023-06-15T14:30:00", 1, "JPG", 0, 3, "AB", None, None),
        ],
        "exif": [
            # Paris GPS coordinates
            (1, 1, "2023-06-15T14:30:00", None, None, None, 48.8566, 2.3522, 1),
        ],
    }


@pytest.fixture
def tmp_catalog_per_year_root_damaged(tmp_path: Path) -> tuple[Path, Path]:
    """Catalog in the year-doubled-damage state: pathFromRoot includes the year."""
    root_dir = tmp_path / "2023"
    root_dir.mkdir()
    # File exists at the doubled path on disk
    damaged_dir = root_dir / "2023" / "06" / "Switzerland" / "Saillon"
    damaged_dir.mkdir(parents=True)
    (damaged_dir / "IMG_DAMAGED_1.JPG").write_text("photo")

    db_path = tmp_path / "test_pyr_damaged.lrcat"
    create_test_catalog(db_path, per_year_root_damaged_test_data(str(root_dir)))
    return db_path, root_dir


def multi_root_test_data(root_2012: str, root_2013: str) -> dict:
    """Test data: two year-based roots; Photo 1 is cross-root (wrong year root).

    - Root 1 (id=1): root_2012 path, last segment '2012'
    - Root 2 (id=2): root_2013 path, last segment '2013'
    - Folder 1: pathFromRoot='2012/08/', rootFolder=2 → year-in-year
    - Folder 2: pathFromRoot='2013/06/', rootFolder=2 → well-placed
    - Photo 1 (IMG_CROSS): folder=1, capture=2012-08-15 → cross-root candidate
    - Photo 2 (IMG_OK): folder=2, capture=2013-06-20 → well-placed, not moved
    """
    r2012 = root_2012 if root_2012.endswith("/") else root_2012 + "/"
    r2013 = root_2013 if root_2013.endswith("/") else root_2013 + "/"
    return {
        "roots": [
            (1, "ROOT-UUID-2012", r2012, "2012", "../2012"),
            (2, "ROOT-UUID-2013", r2013, "2013", "../2013"),
        ],
        "folders": [
            (1, "FOLD-UUID-1", "2012/08/", 2),
            (2, "FOLD-UUID-2", "2013/06/", 2),
        ],
        "files": [
            (
                1,
                "FILE-UUID-1",
                "IMG_CROSS",
                "JPG",
                1,
                "IMG_CROSS",
                None,
                None,
                "IMG_CROSS.JPG",
                None,
            ),
            (
                2,
                "FILE-UUID-2",
                "IMG_OK",
                "JPG",
                2,
                "IMG_OK",
                None,
                None,
                "IMG_OK.JPG",
                None,
            ),
        ],
        "images": [
            (1, "IMG-UUID-1", "2012-08-15T10:00:00", 1, "JPG", 0, 3, "AB", None, None),
            (2, "IMG-UUID-2", "2013-06-20T10:00:00", 2, "JPG", 0, 4, "AB", None, None),
        ],
    }


@pytest.fixture
def tmp_catalog_multi_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Catalog with two year-roots; Photo 1 is cross-root (wrong year root).

    Both root directories are created on disk so the planner's disk-existence
    check passes for cross-root moves.
    Returns (db_path, root_2012_dir, root_2013_dir).
    """
    root_2012_dir = tmp_path / "2012"
    root_2013_dir = tmp_path / "2013"
    root_2012_dir.mkdir()
    root_2013_dir.mkdir()

    db_path = tmp_path / "test_multi_root.lrcat"
    create_test_catalog(
        db_path, multi_root_test_data(str(root_2012_dir), str(root_2013_dir))
    )
    return db_path, root_2012_dir, root_2013_dir


@pytest.fixture
def tmp_catalog_multi_root_with_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Same as tmp_catalog_multi_root but with actual files on disk.

    IMG_CROSS.JPG is at the wrong location (root_2013/2012/08/IMG_CROSS.JPG).
    IMG_OK.JPG is at its correct location (root_2013/2013/06/IMG_OK.JPG).
    Returns (db_path, root_2012_dir, root_2013_dir).
    """
    root_2012_dir = tmp_path / "2012"
    root_2013_dir = tmp_path / "2013"
    root_2012_dir.mkdir()
    root_2013_dir.mkdir()

    cross_dir = root_2013_dir / "2012" / "08"
    cross_dir.mkdir(parents=True)
    (cross_dir / "IMG_CROSS.JPG").write_text("photo")

    ok_dir = root_2013_dir / "2013" / "06"
    ok_dir.mkdir(parents=True)
    (ok_dir / "IMG_OK.JPG").write_text("photo")

    db_path = tmp_path / "test_multi_root.lrcat"
    create_test_catalog(
        db_path, multi_root_test_data(str(root_2012_dir), str(root_2013_dir))
    )
    return db_path, root_2012_dir, root_2013_dir
