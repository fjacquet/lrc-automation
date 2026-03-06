# lrc-automation

[![CI](https://github.com/fjacquet/lrc-automation/actions/workflows/ci.yml/badge.svg?branch=maincd)](https://github.com/fjacquet/lrc-automation/actions/workflows/ci.yml)
[![Docs](https://github.com/fjacquet/lrc-automation/actions/workflows/docs.yml/badge.svg)](https://github.com/fjacquet/lrc-automation/actions/workflows/docs.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.5.0-orange.svg)](https://github.com/fjacquet/lrc-automation/releases)

A Python CLI tool for automating Lightroom Classic catalog maintenance. It directly manipulates the `.lrcat` SQLite catalog and moves/renames files on disk, keeping Lightroom's catalog links intact.

## Why?

Lightroom Classic organizes photos in date-based folders, but sometimes files end up in the wrong folder (e.g. filed by file modification date instead of EXIF capture date). The Lightroom Classic Lua SDK cannot move photos between folders programmatically, so this tool works directly with the `.lrcat` SQLite database.

See [ADR-001](docs/adr/001-lightroom-classic-catalog-automation.md) for the full decision record.

## Features

- **Scan** (read-only): Identify misplaced photos, duplicate date prefixes, DDMMYYYY filename prefixes, and year-in-year folder anomalies
- **Plan** (read-only): Generate a change plan for moves, renames, or cross-root migrations; exportable to JSON or CSV
- **Apply** (write): Move and rename files on disk and update the catalog, with mandatory backup and rollback on error
- **Validate**: Run integrity checks, full disk audit (missing vs. found-elsewhere), exportable to JSON or CSV
- **Reconcile** (write): Fix catalog folder pointers for files found at a different path than recorded
- **Cleanup** (write): Remove empty directories and macOS AppleDouble (`._*`) files left by previous operations
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

### Windows

**Requirements:** Windows 10 or later, Python 3.12+ ([python.org](https://www.python.org/downloads/) or Windows Store), and `uv` or `pipx`.

**Install with uv:**

```powershell
pip install uv
uv tool install lrc-automation
```

**Install with pipx:**

```powershell
pip install pipx
pipx install lrc-automation
```

**MAX_PATH advisory:** Windows limits file paths to 260 characters by default. If your catalog root paths are deep, enable long-path support:

1. Open Group Policy Editor (`gpedit.msc`)
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

Or via PowerShell (requires admin):

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**First run:** The `--catalog` / `-c` flag is optional. The tool auto-discovers the default Lightroom catalog at `%USERPROFILE%\Pictures\Lightroom\`:

```powershell
# Auto-discover default Lightroom catalog
lrc-auto scan

# Or specify explicitly (both slash styles work)
lrc-auto -c "C:\Users\YourName\Pictures\Lightroom\Catalog.lrcat" scan
lrc-auto -c "C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat" scan
```

**.env file on Windows** — both forward slashes and escaped backslashes work:

```env
LRC_CATALOG_PATH=C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat
LRC_BACKUP_DIR=C:/Users/YourName/Documents/LightroomBackups
```

**Known limitations:** The `[geo]` extra (`reverse_geocoder`) has no Windows wheel on PyPI. Location-folder features (`--location-folders`) are macOS/Linux only.

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

# Preview cross-root year-in-year migrations (opt-in, not included in --fix all)
lrc-auto -c "/path/to/catalog.lrcat" plan --fix root-migrations

# Export plan for review
lrc-auto -c "/path/to/catalog.lrcat" plan -o plan.json
```

### Apply (modifies catalog + disk)

```bash
# Apply all fixes (moves + renames; creates backup)
lrc-auto -c "/path/to/catalog.lrcat" apply

# Apply only moves or only renames
lrc-auto -c "/path/to/catalog.lrcat" apply --fix moves
lrc-auto -c "/path/to/catalog.lrcat" apply --fix renames

# Apply cross-root year-in-year migrations (explicit opt-in required)
lrc-auto -c "/path/to/catalog.lrcat" apply --fix root-migrations

# Skip confirmation prompt
lrc-auto -c "/path/to/catalog.lrcat" apply -y
```

### Validate + Audit

```bash
# Integrity check + full disk audit
lrc-auto -c "/path/to/catalog.lrcat" validate

# Export audit results
lrc-auto -c "/path/to/catalog.lrcat" validate --output audit.json
```

### Reconcile

Fix catalog folder pointers for files found at a different path than recorded
(e.g. after the year-doubling bug or a manual file move outside Lightroom):

```bash
lrc-auto -c "/path/to/catalog.lrcat" reconcile
```

### Cleanup

Remove empty directories and macOS AppleDouble (`._*`) files left by previous operations:

```bash
lrc-auto -c "/path/to/catalog.lrcat" cleanup
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
