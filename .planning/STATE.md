# State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-06)

**Core value:** Photos stay at the path their EXIF capture date dictates, so the Lightroom catalog folder tree always reflects reality.
**Current focus:** Defining v0.6.0 milestone

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-06 — Milestone v0.6.0 Multiplatform started

## Accumulated Context

- Real catalog has ~92K photos across mixed folder naming conventions
- Previous runs may have left year-doubling artifacts (year-in-year paths); `reconcile` command fixes these
- NAS at `/Volumes/photo/` not always mounted — offline handling needed
- Tests use in-memory SQLite; never `unittest.mock`, use `monkeypatch`
- `make check` must pass before commits
- `insert_after_symbol` can inject inside method body — prefer `replace_content` for tail-of-class edits
