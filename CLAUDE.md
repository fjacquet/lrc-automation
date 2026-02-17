# CLAUDE.md - Project Instructions

## Project Overview

`lrc-automation` is a Python CLI tool that automates Lightroom Classic catalog maintenance by directly manipulating the `.lrcat` SQLite database and moving/renaming files on disk.

## Tech Stack

- Python 3.13+, uv package manager, uv_build
- click (CLI), rich (terminal output), python-dotenv (.env config)
- sqlite3 (stdlib) for catalog access
- pytest for testing, ruff for linting/formatting

## Commands

```bash
uv sync                          # Install deps
uv run pytest -v                 # Run tests (37 tests)
uv run ruff check . && uv run ruff format .  # Lint + format
uv run lrc-auto -c <path> scan   # Run the CLI
```

## Key Architecture Decisions

- See `docs/adr/001-lightroom-classic-catalog-automation.md`
- Lua SDK was rejected (can't move photos between folders)
- Direct SQLite manipulation is the only viable approach
- All writes require LR closed + mandatory backup + single transaction

## Current Status (2026-02-17)

### Working
- Full CLI with scan/plan/apply/validate/restore commands
- Scanner, planner, executor, validators, reporter all implemented
- 37 tests passing

### Needs Updating
- **Scanner doesn't match real catalog structure**. The initial design assumed `YYYY/MM/` subfolders in `pathFromRoot`. The real catalog uses:
  - `YYYY-MM-DD` date folders (1,663 folders)
  - French date folders like `1 avril 2016` (978 folders)
  - Dates in root folder paths, not just pathFromRoot
  - Topical folders with no dates (should be skipped)
- Scanner must parse dates from **full path** (root + pathFromRoot)
- Bogus dates (1904-01-01) need filtering
- No duplicate prefix files found in real catalog (pattern may need broadening)

## Catalog Structure

Main storage: `/Volumes/photo/` (NAS, not always mounted)
Local: `/Users/fjacquet/Pictures/2024/`, `/Users/fjacquet/Pictures/2025/`

Real catalog: `/Users/fjacquet/Pictures/Lightroom/Lightroom Catalog-v13-3.lrcat`
- Schema v1400000 (LR Classic v14)
- 92,717 photos, 4,180 folders, 42 root folders
- 1,175 misplaced photos detected

## Code Style

- Type hints on all function signatures
- Module docstrings required
- snake_case functions, PascalCase classes
- Line length 88 (ruff default)
- ruff select: E, F, I, N, W, UP
