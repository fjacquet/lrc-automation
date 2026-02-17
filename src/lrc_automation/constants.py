"""Constants - regex patterns, date formats, table names."""

import re

# Default target layout (strftime format)
DEFAULT_TARGET_LAYOUT = "%Y/%m/"

# Folder structure pattern: YYYY/MM/
FOLDER_YYYY_MM_PATTERN = re.compile(r"^(\d{4})/(\d{2})/$")

# Mapping of strftime directives to regex fragments
_STRFTIME_TO_REGEX: dict[str, str] = {
    "%Y": r"\d{4}",
    "%m": r"\d{2}",
    "%d": r"\d{2}",
    "%H": r"\d{2}",
    "%M": r"\d{2}",
    "%S": r"\d{2}",
}


def layout_to_regex(layout: str) -> re.Pattern[str]:
    """Convert a strftime layout string to a compiled regex pattern.

    Example: "%Y/%m/" → re.compile(r"^\\d{4}/\\d{2}/$")
    """
    pattern = re.escape(layout)
    for directive, regex_frag in _STRFTIME_TO_REGEX.items():
        pattern = pattern.replace(re.escape(directive), regex_frag)
    return re.compile(f"^{pattern}$")


# ISO date folder pattern: YYYY-MM-DD
FOLDER_ISO_DATE_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

# French date folder pattern: D month YYYY (e.g. "1 avril 2016")
FOLDER_FRENCH_DATE_PATTERN = re.compile(
    r"^(\d{1,2})\s+"
    r"(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|"
    r"septembre|octobre|novembre|d[eé]cembre)"
    r"\s+(\d{4})$",
    re.IGNORECASE,
)

# Bare year folder pattern: YYYY
FOLDER_BARE_YEAR_PATTERN = re.compile(r"^(\d{4})$")

# French month name to integer mapping
FRENCH_MONTH_MAP: dict[str, int] = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

# Duplicate date prefix patterns
# Matches: DDMMYYYY-DDMMYYYY-rest (e.g. 29122012-29122012-IMG_20121229_131334)
DUPLICATE_PREFIX_PATTERN = re.compile(r"^(\d{8})-\1-(.+)$")

# IMG with embedded date: IMG_YYYYMMDD_NNNNNN
IMG_DATE_PATTERN = re.compile(r"^IMG_(\d{8})_(\d+.*)$")

# Lightroom catalog tables
TABLE_ROOT_FOLDER = "AgLibraryRootFolder"
TABLE_FOLDER = "AgLibraryFolder"
TABLE_FILE = "AgLibraryFile"
TABLE_IMAGES = "Adobe_images"
TABLE_EXIF = "AgHarvestedExifMetadata"
TABLE_VARIABLES = "Adobe_variablesTable"

# Lock file suffix
LOCK_FILE_SUFFIX = "-lock"

# Lightroom process name on macOS
LR_PROCESS_NAME = "Adobe Lightroom Classic"

# Backup file suffix format
BACKUP_SUFFIX_FORMAT = ".bak-{timestamp}"

# Query to get all photos with their paths and capture times
QUERY_ALL_PHOTOS = """
    SELECT
        img.id_local AS image_id,
        f.id_local AS file_id,
        fld.id_local AS folder_id,
        rf.id_local AS root_folder_id,
        f.baseName,
        f.extension,
        f.sidecarExtensions,
        img.captureTime,
        fld.pathFromRoot,
        rf.absolutePath
    FROM Adobe_images AS img
    JOIN AgLibraryFile AS f ON img.rootFile = f.id_local
    JOIN AgLibraryFolder AS fld ON f.folder = fld.id_local
    JOIN AgLibraryRootFolder AS rf ON fld.rootFolder = rf.id_local
    WHERE img.masterImage IS NULL
"""

QUERY_ALL_PHOTOS_WITH_GPS = """
    SELECT
        img.id_local AS image_id,
        f.id_local AS file_id,
        fld.id_local AS folder_id,
        rf.id_local AS root_folder_id,
        f.baseName,
        f.extension,
        f.sidecarExtensions,
        img.captureTime,
        fld.pathFromRoot,
        rf.absolutePath,
        exif.gpsLatitude,
        exif.gpsLongitude,
        exif.hasGPS
    FROM Adobe_images AS img
    JOIN AgLibraryFile AS f ON img.rootFile = f.id_local
    JOIN AgLibraryFolder AS fld ON f.folder = fld.id_local
    JOIN AgLibraryRootFolder AS rf ON fld.rootFolder = rf.id_local
    LEFT JOIN AgHarvestedExifMetadata AS exif ON exif.image = img.id_local
    WHERE img.masterImage IS NULL
"""

QUERY_ALL_FOLDERS = """
    SELECT
        fld.id_local,
        fld.id_global,
        fld.pathFromRoot,
        fld.rootFolder
    FROM AgLibraryFolder AS fld
"""

QUERY_ROOT_FOLDERS = """
    SELECT
        id_local,
        absolutePath
    FROM AgLibraryRootFolder
"""

QUERY_MAX_FOLDER_ID = "SELECT MAX(id_local) FROM AgLibraryFolder"

QUERY_FILE_EXISTS_IN_FOLDER = """
    SELECT COUNT(*) FROM AgLibraryFile
    WHERE folder = ? AND baseName = ? AND extension = ?
"""
