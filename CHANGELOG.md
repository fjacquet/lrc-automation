# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] - 2026-02-28

### Added
- **Cross-root migration** (`--fix root-migrations`): detect and fix 406 "year-in-year"
  photos (e.g. root=2013, pathFromRoot=2012/08/) that live in the wrong year root.
  Strips the spurious leading year from `pathFromRoot` and moves the file to the correct
  year root (cross-root) or corrects the folder path within the same root (intra-root).
  Disabled by default; not triggered by `--fix all`. (ADR-006)
- `FileChange` gains two optional fields: `target_root_id` and
  `target_root_absolute_path` for cross-root move support
- `ChangePlanner._find_root_for_year()` static helper: finds the catalog root whose
  `absolutePath` ends with a given year
- `ChangePlanner._plan_root_migrations()`: builds cross-root and intra-root fixes
- `Reporter.print_root_migration_summary()`: prints cross-root vs intra-root split table
- **DDMMYYYY → YYMMDD prefix renames** wired into `apply --fix renames` and `--fix all`.
  Previously detected by `scan` and `plan` but never applied.
- `cleanup` command: removes empty directories and AppleDouble (`._*`) files left behind
  by previous operations
- `reconcile` command: fixes `AgLibraryFile.folder` pointers for files found at a
  different path than the catalog records (repairs damage from year-doubling bug). (ADR-005)
- `validate --output`: export audit results to JSON or CSV
- `--log-file` option on the top-level group: write DEBUG-level logs to file while
  keeping terminal output at WARNING level
- Full disk audit (`validate`): `audit_files_on_disk()` finds truly-missing vs
  found-elsewhere files using one rglob per unique root. (ADR-004)
- 12 new tests for cross-root migration (models, planner, executor)

### Fixed
- `Reporter.print_prefix_format_summary()`: target folder no longer doubles CC/City
  segments (e.g. `CH/Aubonne/CH/Aubonne/`) — now uses `get_expected_folder_path_with_location()`
- `executor._execute_move()`: uses `target_root_absolute_path` when set, so cross-root
  moves write to the correct directory instead of the source root
- `validators.postflight_check()`: verifies file existence in the correct destination root
- Per-year-root year-doubling bug in `_plan_location_moves()`: a previous bad run could
  leave `pathFromRoot` starting with the year (e.g. `2025/12/CH/…`); the planner now
  strips the doubled year before computing the target path

## [0.4.0] - 2026-02-17

### Added
- Broadened scanner date detection: ISO `YYYY-MM-DD` folders, French date folders (`1 avril 2016`), and year-in-root + month-in-path patterns now recognized
- New `extract_date_from_path()` function scans full path (root + pathFromRoot) right-to-left for date segments
- `FOLDER_ISO_DATE_PATTERN`, `FOLDER_FRENCH_DATE_PATTERN`, `FOLDER_BARE_YEAR_PATTERN` regex constants
- `FRENCH_MONTH_MAP` for French month name lookup (with and without accents)
- Lightroom epoch year 1904 filtered as bogus date
- 23 new tests: `extract_date_from_path` (18), scanner broadened detection (5)

### Changed
- `scan_misplaced_photos()` now uses `extract_date_from_path(root + pathFromRoot)` instead of `extract_yyyy_mm(pathFromRoot)`, detecting ~2,600 additional date folder patterns from real catalogs

## [0.3.0] - 2026-02-17

### Added
- Optional GPS-based location subfolders via `--location-folders` flag or `LRC_LOCATION_FOLDERS` env var
- New `geocoder.py` module with `LocationResolver` class for offline reverse geocoding (uses `reverse_geocoder` K-D tree)
- Optional `[geo]` dependency group: `pip install lrc-automation[geo]`
- `PhotoRecord` gains `gps_latitude`/`gps_longitude` fields and `get_expected_folder_path_with_location()` method
- GPS-joined SQL query (`QUERY_ALL_PHOTOS_WITH_GPS`) with LEFT JOIN on `AgHarvestedExifMetadata`
- Batch coordinate resolution with in-memory caching for efficient lookups
- Folder name sanitization for filesystem-safe Country/City names (unicode, special chars)
- GPS column and count in scan summary when `--location-folders` is enabled
- 34 new tests: geocoder (12), models (9), scanner GPS (4), planner location (5), sanitization (8)
- Documentation for location folders in `docs/usage.md` and `CLAUDE.md`

### Changed
- `CatalogScanner`, `ChangePlanner` now accept `location_folders` parameter (default `False`)
- `AgHarvestedExifMetadata` test schema updated with GPS columns (`gpsLatitude`, `gpsLongitude`, `hasGPS`)
- `Reporter.print_scan_summary()` accepts `location_folders` flag to show GPS info
- CLAUDE.md updated with Environment section, test conventions, and geo dependency docs

## [0.2.0] - 2026-02-17

### Added
- Configurable target folder layout via `LRC_TARGET_LAYOUT` env var or `--target-layout` CLI option
- `layout_to_regex()` helper to convert strftime layouts to regex patterns
- `PhotoRecord.get_expected_folder_path(layout)` method for layout-aware path computation
- 10 new tests covering custom layouts, regex generation, and backward compatibility
- Documentation for target layout configuration in `docs/usage.md`

### Changed
- `CatalogScanner`, `ChangePlanner` now accept `target_layout` parameter (default `%Y/%m/`)
- `extract_yyyy_mm()` accepts optional `layout` parameter for pattern matching
- `Reporter.print_scan_summary()` displays configured target layout

## [0.1.0] - 2026-02-17

### Added
- CLI with 5 commands: `scan`, `plan`, `apply`, `validate`, `restore`
- `CatalogScanner`: detect misplaced photos (folder date vs EXIF captureTime) and duplicate date prefixes in filenames
- `ChangePlanner`: build change plans with target folder resolution and collision handling
- `ChangeExecutor`: apply plans with disk moves + SQLite updates in a single transaction, with full rollback on error
- `CatalogValidator`: pre-flight and post-flight integrity checks (PRAGMA integrity_check, orphan detection)
- `Reporter`: Rich terminal output with scan summaries, change plan tables, and execution reports; JSON/CSV export
- `CatalogConnection`: context manager with backup, lock-file detection, and LR process check
- Date parsing for multiple captureTime formats (ISO 8601, EXIF-style, timezone offsets)
- Sidecar file handling (.xmp and sidecarExtensions) for moves and renames
- 37 tests with in-memory SQLite test catalogs
- ADR documenting why direct SQLite was chosen over Lua SDK
- README with usage examples and safety documentation
- Makefile with install/lint/format/typecheck/test/check/docs/clean targets
- GitHub Actions CI (Python 3.12/3.13 matrix) and docs deployment to GH Pages
- MkDocs Material documentation site (index, usage, architecture pages)
- mypy strict mode type checking
- Expanded ruff lint rules (bugbear, simplify, ruff-specific)
