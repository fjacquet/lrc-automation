"""Constants - regex patterns, date formats, table names."""

import re

# Folder structure pattern: YYYY/MM/
FOLDER_YYYY_MM_PATTERN = re.compile(r"^(\d{4})/(\d{2})/$")

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
