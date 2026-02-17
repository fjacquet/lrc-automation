# Architecture

## Pipeline

```
scan (read-only) → plan (read-only) → apply (writes) → validate
```

## Modules

| Module | Description |
|--------|-------------|
| `cli.py` | Click CLI entry point with 5 commands: scan, plan, apply, validate, restore |
| `catalog.py` | `CatalogConnection`: open, backup, lock check (context manager) |
| `scanner.py` | `CatalogScanner`: query catalog, detect misplaced photos + duplicate filenames |
| `planner.py` | `ChangePlanner`: build `ChangePlan` from scan results, resolve target folders |
| `executor.py` | `ChangeExecutor`: apply plan (disk moves + SQL updates) in single transaction with rollback |
| `validators.py` | Pre/post-flight integrity checks (PRAGMA integrity_check, orphan detection) |
| `reporter.py` | Rich terminal output + JSON/CSV export |
| `models.py` | Dataclasses: `PhotoRecord`, `FileChange`, `ChangePlan`, `ExecutionReport` |
| `geocoder.py` | `LocationResolver`: offline reverse geocoding (GPS to Country/City), optional `[geo]` extra |
| `utils.py` | Date parsing (captureTime formats), folder date extraction, path helpers, UUID generation |
| `constants.py` | Regex patterns (including ISO/French date folders), SQL queries, table names |

## Key data flow

1. `CatalogScanner._fetch_all_photos()` joins `Adobe_images` + `AgLibraryFile` + `AgLibraryFolder` + `AgLibraryRootFolder` to build a `PhotoRecord` list
2. Full file path = `AgLibraryRootFolder.absolutePath` + `AgLibraryFolder.pathFromRoot` + `AgLibraryFile.baseName` + `.` + `extension`
3. **Target layout is configurable** via `LRC_TARGET_LAYOUT` (default `%Y/%m/`) — photos are moved to match their `captureTime`
4. **Date detection** uses `extract_date_from_path()` which scans the full path (root + pathFromRoot) right-to-left, recognizing `YYYY/MM/`, `YYYY-MM-DD`, French dates (`1 avril 2016`), and year-in-root patterns. The Lightroom epoch year 1904 is filtered as bogus.
5. **Optional location folders**: when `--location-folders` is enabled, GPS coordinates are reverse-geocoded to `Country/City/` subfolders appended to the date path
6. Moving a photo in the catalog = `UPDATE AgLibraryFile SET folder = :new_folder_id`
7. The executor moves the physical file + sidecars on disk to match

## Database tables

The Lightroom Classic `.lrcat` catalog is a SQLite database. Key tables:

- `AgLibraryRootFolder` — absolute root paths (e.g. `/Volumes/photo/Weekends/`)
- `AgLibraryFolder` — subfolder paths relative to root (e.g. `2023/2023-12-24/`)
- `AgLibraryFile` — filenames with a foreign key to their folder
- `Adobe_images` — image metadata including `captureTime`
- `AgHarvestedExifMetadata` — EXIF data including GPS coordinates (`gpsLatitude`, `gpsLongitude`, `hasGPS`)

## Safety invariants

- All writes use `BEGIN IMMEDIATE ... COMMIT` (single transaction)
- Every disk move is tracked in `_rollback_actions` and reversed on any error
- Lock file (`.lrcat-lock`) + process check prevent writes while LR is open
- Mandatory backup before any write operation
- SQLite `PRAGMA integrity_check` runs before and after modifications
