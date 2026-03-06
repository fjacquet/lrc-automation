# lrc-automation

## What This Is

A Python CLI tool that automates Lightroom Classic catalog maintenance by directly manipulating the `.lrcat` SQLite database and moving/renaming files on disk. It detects misplaced photos (folder date ≠ EXIF capture time), renames files with bad date prefixes, audits missing files, and reconciles catalog folder pointers — without requiring Lightroom to be open.

## Core Value

Photos stay at the path their EXIF capture date dictates, so the Lightroom catalog folder tree always reflects reality.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ CLI with scan, plan, apply, validate, restore commands — v0.1.0
- ✓ Misplaced photo detection (folder date vs EXIF captureTime) — v0.1.0
- ✓ Duplicate date-prefix filename detection — v0.1.0
- ✓ Single-transaction SQLite + disk moves with full rollback — v0.1.0
- ✓ Pre/post-flight catalog integrity checks — v0.1.0
- ✓ Rich terminal output + JSON/CSV export — v0.1.0
- ✓ Configurable target folder layout (`LRC_TARGET_LAYOUT`) — v0.2.0
- ✓ Optional GPS-based location subfolders (`--location-folders`) — v0.3.0
- ✓ Broadened scanner: ISO YYYY-MM-DD, French date folders, year-in-root patterns — v0.4.0
- ✓ Cross-root migration (`--fix root-migrations`) — v0.5.0
- ✓ DDMMYYYY→YYMMDD prefix renames wired into apply — v0.5.0
- ✓ Cleanup command (empty dirs + AppleDouble files) — v0.5.0
- ✓ Reconcile command (fix folder pointers for found-elsewhere files) — v0.5.0
- ✓ Full disk audit (`validate`) with JSON/CSV output — v0.5.0
- ✓ `--log-file` debug logging — v0.5.0
- ✓ Windows catalog open via SQLite URI (`_path_to_sqlite_uri`) — v0.6.0
- ✓ Windows backslash normalisation in scanner (`norm_root`) — v0.6.0
- ✓ `geo` extra decoupled from core install — v0.6.0
- ✓ Cross-platform process detection via `psutil` — v0.6.0
- ✓ `path.as_posix()` SQL writes for `pathFromRoot` — v0.6.0
- ✓ `sys.platform` guard for AppleDouble cleanup — v0.6.0
- ✓ `PermissionError` retry loop for transient Windows locks — v0.6.0
- ✓ 3-OS CI matrix (ubuntu/macos/windows) + `.gitattributes` LF enforcement — v0.6.0
- ✓ SBOM artifact attached to every GitHub release — v0.6.0
- ✓ Zero-config catalog discovery (`_discover_default_catalog`) — v0.6.0
- ✓ Windows onboarding docs (README + docs/usage.md) + ADR-007 — v0.6.0
- ✓ `docs/prd.md` updated for macOS/Windows targets — v0.6.0
- ✓ Complete v0.6.0 CHANGELOG entry — v0.6.0

### Active

<!-- Current scope for next milestone. Planning in progress. -->

*(No active requirements — planning next milestone)*

### Out of Scope

- Lightroom Lua SDK integration — SQLite direct access is the only viable approach (ADR-001)
- Real-time sync / daemon mode — safety requires explicit user invocation
- GUI — CLI tool for power users

## Constraints

- **Safety**: Never write to catalog while Lightroom is open (lock file check + process detection)
- **Atomicity**: All writes in a single SQLite transaction with disk rollback on failure
- **Compatibility**: Must support Lightroom Classic catalog schema (AgLibraryFile, AgLibraryFolder, AgLibraryRootFolder, Adobe_images)
- **Python**: 3.12+ only; uv for dependency management

## Context

- Real catalog: `~/Pictures/Lightroom/Lightroom Catalog-v13-3.lrcat` (1 GB, ~92K photos)
- NAS at `/Volumes/photo/` not always mounted — operations must handle offline root gracefully
- 20,178 photos (22%) have GPS coordinates
- Photo library spans decades with mixed folder naming conventions (YYYY/MM, YYYY-MM-DD, French dates, topical)
- Python 3.12/3.13, uv, ruff, mypy strict, pytest; no `unittest.mock`
- 215 tests using in-memory SQLite catalogs; 7,815 lines Python (src + tests)
- Shipped v0.6.0 with full Windows + macOS support; Linux CI-only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Direct SQLite over Lua SDK | LR SDK cannot move photos between folders | ✓ Good |
| Optional `[geo]` extra for reverse geocoding | `reverse_geocoder` is large; not needed for basic use | ✓ Good |
| Single transaction for all writes | Ensures atomicity; any failure rolls back completely | ✓ Good |
| Target layout `YYYY/MM/` as default | Matches existing majority of catalog structure | ✓ Good |
| Strip bogus 1904 Lightroom epoch dates | Avoids misdetecting old imports as misplaced | ✓ Good |
| `psutil` for process detection (v0.6.0) | Cross-platform hard dependency; replaces macOS-only pgrep | ✓ Good |
| `path.as_posix()` for SQL path writes (v0.6.0) | Lightroom expects forward slashes on all platforms | ✓ Good |
| `sys.platform == 'darwin'` guard for AppleDouble (v0.6.0) | AppleDouble files only exist on macOS | ✓ Good |
| SQLite URI via `_path_to_sqlite_uri()` (v0.6.0) | Windows drive-letter paths need `file:///C:/...` format | ✓ Good |
| `home_dir` param on `_discover_default_catalog` (v0.6.0) | Testability without patching `Path.home()` | ✓ Good |
| Linux as CI-only target (v0.6.0) | `reverse_geocoder` has no Windows wheel; Linux servers don't use LR | ✓ Good |

---
*Last updated: 2026-03-06 after v0.6.0 Multiplatform milestone*
