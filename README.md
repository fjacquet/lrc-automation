# lrc-automation

A Python CLI tool for automating Lightroom Classic catalog maintenance. It directly manipulates the `.lrcat` SQLite catalog and moves/renames files on disk, keeping Lightroom's catalog links intact.

## Why?

Lightroom Classic organizes photos in date-based folders, but sometimes files end up in the wrong folder (e.g. filed by file modification date instead of EXIF capture date). The Lightroom Classic Lua SDK cannot move photos between folders programmatically, so this tool works directly with the `.lrcat` SQLite database.

See [ADR-001](docs/adr/001-lightroom-classic-catalog-automation.md) for the full decision record.

## Features

- **Scan** (read-only): Identify misplaced photos and files with duplicate date prefixes
- **Plan** (read-only): Generate a change plan, exportable to JSON or CSV for review
- **Apply** (write): Move files on disk and update the catalog, with mandatory backup and rollback on error
- **Validate**: Run integrity checks on the catalog
- **Restore**: Restore catalog from a backup

## Supported Folder Structures

The scanner detects dates in folder paths using multiple patterns:

| Pattern | Example | Source |
|---------|---------|--------|
| `YYYY-MM-DD` | `/Volumes/photo/Weekends/2023/2023-12-24/` | ISO date folders |
| French dates | `/Volumes/photo/iphone/1 avril 2016/` | Apple Photos / iPhoto exports |
| `YYYY/MM/` | `2023/06/` | Classic date hierarchy |

Dates are extracted from both the root folder path and the `pathFromRoot` in the catalog.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Lightroom Classic **must be closed** during `apply` operations

## Installation

```bash
git clone <this-repo>
cd lrc-automation
uv sync
```

## Configuration

Copy `.env.example` to `.env` and set your catalog path:

```bash
cp .env.example .env
```

```env
LRC_CATALOG_PATH=/path/to/your/Lightroom Catalog.lrcat
LRC_BACKUP_DIR=                # optional, defaults to catalog directory
```

## Usage

### Scan (read-only, always safe)

```bash
# Scan for issues
lrc-auto -c "/path/to/catalog.lrcat" scan

# Export results to JSON or CSV
lrc-auto -c "/path/to/catalog.lrcat" scan -o results.json
lrc-auto -c "/path/to/catalog.lrcat" scan -o results.csv
```

### Plan (read-only)

```bash
# Preview all planned changes
lrc-auto -c "/path/to/catalog.lrcat" plan

# Plan only moves or only renames
lrc-auto -c "/path/to/catalog.lrcat" plan --fix moves
lrc-auto -c "/path/to/catalog.lrcat" plan --fix renames

# Export plan for review
lrc-auto -c "/path/to/catalog.lrcat" plan -o plan.json
```

### Apply (modifies catalog + disk)

```bash
# Apply all fixes (prompts for confirmation, creates backup)
lrc-auto -c "/path/to/catalog.lrcat" apply

# Apply only moves
lrc-auto -c "/path/to/catalog.lrcat" apply --fix moves

# Skip confirmation prompt
lrc-auto -c "/path/to/catalog.lrcat" apply -y
```

### Validate

```bash
lrc-auto -c "/path/to/catalog.lrcat" validate
```

### Restore from Backup

```bash
lrc-auto -c "/path/to/catalog.lrcat" restore --backup-path /path/to/backup.lrcat.bak-20260217
```

## Safety

The tool enforces multiple safety layers:

1. **Lock check**: Refuses to modify the catalog if Lightroom is running (`.lrcat-lock` file detection + process check)
2. **Mandatory backup**: Creates a timestamped backup before any write operation
3. **Single transaction**: All SQL changes happen in one `BEGIN IMMEDIATE ... COMMIT`
4. **Disk rollback**: Every file move is tracked; all moves are reversed on any error
5. **Integrity checks**: SQLite `PRAGMA integrity_check` runs before and after modifications
6. **Post-flight validation**: Verifies all files exist at their new paths after changes

## Architecture

```
src/lrc_automation/
  cli.py           Click CLI entry point
  catalog.py       CatalogConnection: open, backup, lock check
  scanner.py       Scan for misplaced photos + duplicate filenames
  planner.py       Build change plans (folder creation, collision handling)
  executor.py      Apply plans: disk moves + SQLite updates + rollback
  validators.py    Pre-flight and post-flight integrity checks
  reporter.py      Rich terminal output, CSV/JSON export
  models.py        Data classes (PhotoRecord, ChangePlan, etc.)
  utils.py         Date parsing, path helpers
  constants.py     Regex patterns, SQL queries
```

### How It Works

The Lightroom Classic `.lrcat` catalog is a SQLite database. Key tables:

- `AgLibraryRootFolder` -- absolute root paths (e.g. `/Volumes/photo/Weekends/`)
- `AgLibraryFolder` -- subfolder paths relative to root (e.g. `2023/2023-12-24/`)
- `AgLibraryFile` -- filenames with a foreign key to their folder
- `Adobe_images` -- image metadata including `captureTime`

Full file path = `AgLibraryRootFolder.absolutePath` + `AgLibraryFolder.pathFromRoot` + `AgLibraryFile.baseName` + `.` + `extension`

**Moving a photo** only requires updating one column:
```sql
UPDATE AgLibraryFile SET folder = :new_folder_id WHERE id_local = :file_id;
```

The tool also moves the physical file (and sidecars) on disk to match.

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest -v

# Lint and format
uv run ruff check .
uv run ruff format .
```

## Catalog Stats (reference)

Tested against a real catalog with:
- 92,717 photos across 4,180 folders and 42 root folders
- Schema version 1400000 (Lightroom Classic v14)
- File types: JPG (64k), DNG (11k), CR2 (7k), MOV (2.8k), RAF (1.9k), and more
- 1,175 misplaced photos detected (capture date != folder date)

## License

MIT
