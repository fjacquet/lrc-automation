# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`lrc-automation` is a Python CLI tool that automates Lightroom Classic catalog maintenance by directly manipulating the `.lrcat` SQLite database and moving/renaming files on disk. The LR Classic Lua SDK cannot move photos between folders, so direct SQLite is the only viable approach (see `docs/adr/001-lightroom-classic-catalog-automation.md`).

## Commands

```bash
uv sync                              # Install deps
uv sync --all-extras                 # Install deps + optional geo extra
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
- `geocoder.py` — `LocationResolver`: offline reverse geocoding (GPS → Country/City), optional `[geo]` extra
- `reporter.py` — Rich terminal output + JSON/CSV export
- `models.py` — Dataclasses: `PhotoRecord`, `FileChange`, `ChangePlan`, `ExecutionReport`
- `utils.py` — Date parsing (captureTime formats), path helpers, UUID generation
- `constants.py` — Regex patterns, SQL queries, table names

### Key Data Flow

1. `CatalogScanner._fetch_all_photos()` joins `Adobe_images` + `AgLibraryFile` + `AgLibraryFolder` + `AgLibraryRootFolder` to build `PhotoRecord` list
2. Full file path = `AgLibraryRootFolder.absolutePath` + `AgLibraryFolder.pathFromRoot` + `AgLibraryFile.baseName` + `.` + `extension`
3. **Target layout is configurable** via `LRC_TARGET_LAYOUT` env var (default `%Y/%m/` = `YYYY/MM/`). Photos are moved to match their `captureTime`
4. **Optional location folders**: `--location-folders` / `LRC_LOCATION_FOLDERS` appends `Country/City/` subfolders using GPS coordinates from `AgHarvestedExifMetadata`. Requires optional `[geo]` extra (`reverse_geocoder`)
5. Moving a photo in the catalog = `UPDATE AgLibraryFile SET folder = :new_folder_id`
6. The executor moves the physical file + sidecars on disk to match

### Safety Invariants

- All writes use `BEGIN IMMEDIATE ... COMMIT` (single transaction)
- Every disk move is tracked in `_rollback_actions` and reversed on any error
- Lock file (`.lrcat-lock`) + process check prevent writes while LR is open
- Mandatory backup before any write operation

### Test Setup

Tests use in-memory SQLite catalogs via `tests/conftest.py:create_test_catalog()`. The `SCHEMA_SQL` constant defines a minimal catalog schema. Fixtures: `tmp_catalog` (DB only), `tmp_catalog_with_files` (DB + actual files on disk for executor tests), `tmp_catalog_with_gps` (DB with GPS EXIF data for geocoder/location tests).

## Environment

Copy `.env.example` to `.env`. Key variables: `LRC_CATALOG_PATH`, `LRC_BACKUP_DIR`, `LRC_TARGET_LAYOUT`, `LRC_LOCATION_FOLDERS`.

## Code Style

- Type hints on all function signatures
- Module docstrings required
- snake_case functions, PascalCase classes
- ruff config: line-length 88, select E/F/I/N/W/UP/B/SIM/RUF, target py312
- mypy strict mode enabled
- **Never use `unittest.mock`** — use `pytest.MonkeyPatch` (via `monkeypatch` fixture) instead

## Known Issue: Scanner Date Detection

The scanner currently only matches `YYYY/MM/` in `pathFromRoot`. The real catalog (92K photos, 4K folders) also uses:

- `YYYY-MM-DD` date subfolders (1,663 folders)
- French date folders like `1 avril 2016` (978 folders)
- Dates in root folder paths, not just pathFromRoot

Scanner must parse dates from **full path** (root + pathFromRoot) and filter bogus dates (1904-01-01). Target layout `YYYY/MM/` is correct — the source detection needs broadening.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->