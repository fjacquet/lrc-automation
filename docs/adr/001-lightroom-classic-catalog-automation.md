# ADR-001: Lightroom Classic Catalog Automation Approach

**Status:** Accepted
**Date:** 2026-02-17
**Decision Makers:** fjacquet

## Context

Photos in a Lightroom Classic catalog are organized in `YYYY/MM` folders on disk. Two problems exist:

1. **Misplaced photos**: Some photos were filed by file modification date instead of EXIF `DateTimeOriginal`, placing them in the wrong `YYYY/MM` folder.
2. **Duplicate date prefixes in filenames**: Files like `29122012-29122012-IMG_20121229_131334` have the date prefix duplicated and need cleaning to `29122012-IMG_131334`.

All operations must maintain Lightroom catalog link integrity -- files cannot be moved/renamed outside of Lightroom's awareness.

## Decision

Build a **Python CLI tool** that directly manipulates the `.lrcat` SQLite catalog file and moves/renames files on disk, with Lightroom closed.

### Why Not Lightroom Classic Lua SDK Plugin?

The Lua SDK was evaluated and **rejected** because:
- `LrPhoto` has **no `moveToFolder()` method** -- the SDK cannot move photos between folders programmatically
- `LrFileUtils` can rename/move files on disk, but Lightroom will then think the photo is missing, with no way to reconnect
- The SDK can only **read** metadata and **create collections**, not perform the file operations we need

### Why Not Lightroom CC (Cloud) MCP/API?

Existing MCP servers (Zapier, Pipedream) target **Lightroom CC** (cloud version), not **Lightroom Classic** (desktop). They operate through Adobe's cloud API and cannot interact with local `.lrcat` catalogs.

### Why Direct SQLite Manipulation?

The `.lrcat` catalog file is a SQLite database with well-documented tables:
- `AgLibraryRootFolder` - absolute root paths
- `AgLibraryFolder` - folder paths relative to root
- `AgLibraryFile` - filenames with folder FK
- `Adobe_images` - core image data including `captureTime`

Moving a photo requires only: `UPDATE AgLibraryFile SET folder = :new_folder_id WHERE id_local = :file_id`

This is the approach used by community tools like [LightroomClassicCatalogReader](https://github.com/thatlarrypearson/LightroomClassicCatalogReader) and documented by [camerahacks/lightroom-database](https://github.com/camerahacks/lightroom-database).

## Architecture

### Project Structure

```
lrc-automation/
├── pyproject.toml
├── .env                 # LRC_CATALOG_PATH, LRC_BACKUP_DIR
├── docs/adr/
├── src/lrc_automation/
│   ├── __init__.py
│   ├── cli.py           # Click CLI: scan, plan, apply, validate, restore
│   ├── catalog.py       # CatalogConnection: open, backup, lock check
│   ├── models.py        # PhotoRecord, Folder, FileChange, ChangePlan
│   ├── scanner.py       # Scan for misplaced photos + duplicate filenames
│   ├── planner.py       # Build ChangePlan (folder creation, collision handling)
│   ├── executor.py      # Apply: move files on disk + update SQLite
│   ├── reporter.py      # Rich terminal output, CSV/JSON export
│   ├── validators.py    # Pre-flight and post-flight integrity checks
│   ├── utils.py         # Date parsing, path helpers
│   └── constants.py     # Regex patterns, table names
└── tests/
```

### Key SQLite Operations

**Move photo to different folder:**
```sql
UPDATE AgLibraryFile SET folder = :new_folder_id WHERE id_local = :file_id;
```

**Rename file:**
```sql
UPDATE AgLibraryFile SET baseName = :new_name, idx_filename = :new_idx WHERE id_local = :file_id;
```

**Create folder:**
```sql
INSERT INTO AgLibraryFolder (id_local, id_global, pathFromRoot, rootFolder) VALUES (...);
```

**Path reconstruction:**
```
full_path = AgLibraryRootFolder.absolutePath + AgLibraryFolder.pathFromRoot + AgLibraryFile.baseName + "." + extension
```

### Rename Logic

`29122012-29122012-IMG_20121229_131334` -> `29122012-IMG_131334`

1. Detect duplicated date prefix: `(\d{8})-\1-(.+)` -> keep one prefix
2. Strip redundant date from `IMG_YYYYMMDD_NNNNNN` -> `IMG_NNNNNN`

### Safety Measures

1. **Lightroom must be closed** - enforced by checking `.lrcat-lock` file + process check
2. **Mandatory backup** of `.lrcat` before any write
3. **Single SQLite transaction** (`BEGIN IMMEDIATE ... COMMIT`) for all SQL changes
4. **Disk rollback stack** - every file move records an undo operation, reversed on error
5. **SQLite `integrity_check`** before and after modifications
6. **Post-flight validation** - verify all files exist at new paths, no broken FKs

### CLI Commands

```bash
lrc-auto scan -c ~/Pictures/MyCatalog.lrcat        # Read-only scan
lrc-auto plan -c ~/Pictures/MyCatalog.lrcat -o plan.json  # Generate plan
lrc-auto apply -c ~/Pictures/MyCatalog.lrcat        # Apply changes
lrc-auto validate -c ~/Pictures/MyCatalog.lrcat     # Integrity check
lrc-auto restore -c ~/Pictures/MyCatalog.lrcat --backup-path ...  # Restore
```

### Dependencies

- `click` - CLI framework
- `rich` - Terminal tables and progress bars
- `python-dotenv` - `.env` configuration
- `sqlite3` (stdlib) - Catalog database access
- `shutil` (stdlib) - File move operations
- `pytest` - Testing

### Edge Cases

| Case | Handling |
|------|----------|
| No `captureTime` (NULL) | Skip with warning |
| Target folder not in catalog | Create `AgLibraryFolder` row + mkdir |
| Filename collision in target | Append `_1`, `_2`, etc. |
| RAW+JPG sidecar pairs | Move together (parse `sidecarExtensions`) |
| XMP sidecars | Move `.xmp` alongside main file |
| Virtual copies | Skip (share master's physical file) |
| Cross-filesystem moves | Copy+delete instead of rename |

## Implementation Phases

| Phase | Deliverable |
|-------|------------|
| 1 | Foundation: `models.py`, `constants.py`, `utils.py`, `catalog.py` |
| 2 | Scanner: `scanner.py` + `reporter.py` + `cli.py scan` |
| 3 | Planner: `planner.py` + `cli.py plan` with export |
| 4 | Executor: `validators.py` + `executor.py` + `cli.py apply/validate/restore` |
| 5 | Tests: unit + integration tests |
| 6 | Optional: MCP server wrapper |

## Consequences

**Positive:**
- Full automation of photo organization fixes
- Safe with mandatory backup and rollback
- Read-only scan mode for review before changes
- No dependency on Lightroom's limited SDK

**Negative:**
- Requires Lightroom to be closed during apply
- Risk of catalog corruption if SQLite schema changes between LR versions (mitigated by schema version check)
- Not officially supported by Adobe

**Risks:**
- Adobe could change the SQLite schema in future LR updates -> check `Adobe_variablesTable` for version
- Partial disk failure during move -> rollback stack + backup restoration

## References

- [Lightroom Classic SDK](https://developer.adobe.com/lightroom-classic/) - evaluated and rejected for this use case
- [camerahacks/lightroom-database](https://github.com/camerahacks/lightroom-database) - unofficial schema documentation
- [LightroomClassicCatalogReader](https://github.com/thatlarrypearson/LightroomClassicCatalogReader) - Python catalog reader
- [Lightroom Queen Forums - Database schema](https://www.lightroomqueen.com/community/threads/lightroom-classic-catalog-database-schema.44883/)
- [Seachess - Dive into Lightroom catalogues](https://www.seachess.net/notes/dive-into-lightroom-catalogues/)
- [Jeffrey Friedl - Accessing LR SQLite directly](https://regex.info/blog/2006-07-29/221)
