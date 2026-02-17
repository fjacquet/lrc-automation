# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`lrc-automation` is a Python CLI tool that automates Lightroom Classic catalog maintenance by directly manipulating the `.lrcat` SQLite database and moving/renaming files on disk. The LR Classic Lua SDK cannot move photos between folders, so direct SQLite is the only viable approach (see `docs/adr/001-lightroom-classic-catalog-automation.md`).

## Commands

```bash
uv sync                              # Install deps
uv run pytest -v                     # Run all tests
uv run pytest tests/test_scanner.py  # Run single test file
uv run pytest -k "test_name"         # Run specific test
uv run ruff check .                  # Lint
uv run ruff format .                 # Format
uv run mypy src/                     # Type check
uv run lrc-auto -c <path> scan       # Run CLI scan
```

### Makefile targets

```bash
make install     # uv sync
make lint        # ruff check
make format      # ruff format
make typecheck   # mypy src/
make test        # pytest -v
make check       # lint + format-check + typecheck + test (CI target)
make docs        # mkdocs build
make docs-serve  # mkdocs serve (local preview)
make clean       # remove build artifacts
```

## Architecture

Pipeline: **scan** (read-only) -> **plan** (read-only) -> **apply** (writes) -> **validate**

- `cli.py` — Click entry point with 5 commands: scan, plan, apply, validate, restore
- `catalog.py` — `CatalogConnection`: open/close/backup/lock-check (context manager)
- `scanner.py` — `CatalogScanner`: queries catalog, detects misplaced photos + duplicate filenames
- `planner.py` — `ChangePlanner`: builds `ChangePlan` from scan results, resolves target folders
- `executor.py` — `ChangeExecutor`: applies plan (disk moves + SQL updates) in single transaction with rollback
- `validators.py` — Pre/post-flight integrity checks (PRAGMA integrity_check, orphan detection)
- `reporter.py` — Rich terminal output + JSON/CSV export
- `models.py` — Dataclasses: `PhotoRecord`, `FileChange`, `ChangePlan`, `ExecutionReport`
- `utils.py` — Date parsing (captureTime formats), path helpers, UUID generation
- `constants.py` — Regex patterns, SQL queries, table names

### Key Data Flow

1. `CatalogScanner._fetch_all_photos()` joins `Adobe_images` + `AgLibraryFile` + `AgLibraryFolder` + `AgLibraryRootFolder` to build `PhotoRecord` list
2. Full file path = `AgLibraryRootFolder.absolutePath` + `AgLibraryFolder.pathFromRoot` + `AgLibraryFile.baseName` + `.` + `extension`
3. **Target layout is configurable** via `LRC_TARGET_LAYOUT` env var (default `%Y/%m/` = `YYYY/MM/`). Photos are moved to match their `captureTime`
4. Moving a photo in the catalog = `UPDATE AgLibraryFile SET folder = :new_folder_id`
5. The executor moves the physical file + sidecars on disk to match

### Safety Invariants

- All writes use `BEGIN IMMEDIATE ... COMMIT` (single transaction)
- Every disk move is tracked in `_rollback_actions` and reversed on any error
- Lock file (`.lrcat-lock`) + process check prevent writes while LR is open
- Mandatory backup before any write operation

### Test Setup

Tests use in-memory SQLite catalogs via `tests/conftest.py:create_test_catalog()`. The `SCHEMA_SQL` constant defines a minimal catalog schema. Fixtures: `tmp_catalog` (DB only), `tmp_catalog_with_files` (DB + actual files on disk for executor tests).

## Code Style

- Type hints on all function signatures
- Module docstrings required
- snake_case functions, PascalCase classes
- ruff config: line-length 88, select E/F/I/N/W/UP/B/SIM/RUF, target py312
- mypy strict mode enabled

## Known Issue: Scanner Date Detection

The scanner currently only matches `YYYY/MM/` in `pathFromRoot`. The real catalog (92K photos, 4K folders) also uses:
- `YYYY-MM-DD` date subfolders (1,663 folders)
- French date folders like `1 avril 2016` (978 folders)
- Dates in root folder paths, not just pathFromRoot

Scanner must parse dates from **full path** (root + pathFromRoot) and filter bogus dates (1904-01-01). Target layout `YYYY/MM/` is correct — the source detection needs broadening.