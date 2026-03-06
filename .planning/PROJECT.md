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

## Current Milestone: v0.6.0 Multiplatform

**Goal:** Make lrc-automation run on Windows, Linux, and macOS without platform-specific assumptions in the code.

**Target features:**

- Cross-platform process detection (replace macOS-only `pgrep` with `psutil`)
- Windows catalog path handling (backslash paths, drive letters in `absolutePath`)
- Platform-aware AppleDouble cleanup (no-op or skip on non-macOS)
- Default catalog path discovery per platform
- CI matrix expanded to Windows + Linux runners
- Documentation updated for all platforms

### Active

<!-- Current scope. Building toward these. -->

- [ ] Cross-platform Lightroom process detection
- [ ] Windows path handling in catalog absolutePath
- [ ] Platform-aware cleanup (AppleDouble is macOS-only)
- [ ] Default catalog path per OS
- [ ] CI: Windows + Linux in GitHub Actions matrix
- [ ] Docs: multiplatform install and usage

### Out of Scope

- Lightroom Lua SDK integration — SQLite direct access is the only viable approach (ADR-001)
- Real-time sync / daemon mode — safety requires explicit user invocation
- GUI — CLI tool for power users

## Context

- Real catalog: `~/Pictures/Lightroom/Lightroom Catalog-v13-3.lrcat` (1 GB, ~92K photos)
- NAS at `/Volumes/photo/` not always mounted — operations must handle offline root gracefully
- 20,178 photos (22%) have GPS coordinates
- Photo library spans decades with mixed folder naming conventions (YYYY/MM, YYYY-MM-DD, French dates, topical)
- Python 3.12/3.13, uv, ruff, mypy strict, pytest; no `unittest.mock`
- 83+ tests using in-memory SQLite catalogs

## Constraints

- **Safety**: Never write to catalog while Lightroom is open (lock file check + process detection)
- **Atomicity**: All writes in a single SQLite transaction with disk rollback on failure
- **Compatibility**: Must support Lightroom Classic catalog schema (AgLibraryFile, AgLibraryFolder, AgLibraryRootFolder, Adobe_images)
- **Python**: 3.12+ only; uv for dependency management

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Direct SQLite over Lua SDK | LR SDK cannot move photos between folders | ✓ Good |
| Optional `[geo]` extra for reverse geocoding | `reverse_geocoder` is large; not needed for basic use | ✓ Good |
| Single transaction for all writes | Ensures atomicity; any failure rolls back completely | ✓ Good |
| Target layout `YYYY/MM/` as default | Matches existing majority of catalog structure | ✓ Good |
| Strip bogus 1904 Lightroom epoch dates | Avoids misdetecting old imports as misplaced | ✓ Good |

---
*Last updated: 2026-03-06 after bootstrapping .planning from CHANGELOG (v0.5.0 shipped)*
