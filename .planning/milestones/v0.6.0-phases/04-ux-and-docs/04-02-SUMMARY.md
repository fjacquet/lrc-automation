---
phase: 04-ux-and-docs
plan: "02"
subsystem: documentation
tags: [windows, docs, adr, onboarding]
dependency_graph:
  requires: [04-01]
  provides: [UX-02, UX-04]
  affects: [README.md, docs/usage.md, docs/adr/007-multiplatform-windows-support.md]
tech_stack:
  added: []
  patterns: [ADR-format, Windows-onboarding, cross-platform-docs]
key_files:
  created:
    - docs/adr/007-multiplatform-windows-support.md
  modified:
    - README.md
    - docs/usage.md
decisions:
  - "ADR-007 follows the same Status/Date/Context/Decisions/Consequences/Alternatives format established by ADR-001 through ADR-006"
  - "Windows docs placed as subsection of existing Installation in README (not a separate top-level section) to preserve document flow"
  - "docs/usage.md Windows section placed before Configuration so Windows users see install steps before usage details"
metrics:
  duration_minutes: 2
  completed_date: "2026-03-06"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 4 Plan 2: Windows Documentation and ADR-007 Summary

**One-liner:** Windows onboarding docs (README + usage.md) and ADR-007 documenting all 8 v0.6.0 multiplatform decisions with rationale.

## What Was Built

### Task 1: Windows Installation Sections (README.md + docs/usage.md)

**README.md** — New `### Windows` subsection under `## Installation` covering:
- Requirements: Windows 10+, Python 3.12+, uv or pipx
- Install with `uv tool install lrc-automation` and `pipx install lrc-automation`
- MAX_PATH advisory with both Group Policy and PowerShell registry command
- First-run examples with both `C:\` and `C:/` path styles
- `.env` file syntax showing forward-slash paths (recommended) and escaped backslashes
- Known limitation: `[geo]` extra not available on Windows

**docs/usage.md** — New `## Windows Installation and First Run` section at the top (before Configuration) with the same content plus:
- More detailed MAX_PATH explanation with two fix options
- Auto-discovery behavior and the exact error message when discovery fails
- `.env` examples for both slash styles with explanatory comments
- Explicit known-limitations subsection (geo extra, AppleDouble cleanup)

### Task 2: ADR-007 (docs/adr/007-multiplatform-windows-support.md)

Documents all 8 decisions from the v0.6.0 multiplatform work:

| ID | Decision |
|----|----------|
| PATH-01 | SQLite URI forward-slash fix via `path.as_posix()` in `_path_to_sqlite_uri()` |
| PROC-01 | psutil replaces `pgrep` subprocess for cross-platform process detection |
| PROC-02 | `path.as_posix()` for all SQL `pathFromRoot` writes |
| PROC-03 | `sys.platform == 'darwin'` guard for AppleDouble cleanup |
| PROC-04 | `PermissionError` retry loop for Windows antivirus scan locks |
| CI-04 | `anchore/sbom-action@v0` for SPDX SBOM on releases |
| CI-02 | `.gitattributes` with `* text=auto eol=lf` for Windows CI checkouts |
| UX-01 | Catalog auto-discovery at OS-default Lightroom path |

ADR format matches ADR-006 exactly: Status, Date, Decision Makers, Context, Decisions (numbered subsections), Consequences (Positive/Negative/Neutral), Alternatives Considered.

## Verification

- `grep -ic "windows" README.md` → 5 (passes)
- `grep -ic "windows" docs/usage.md` → 9 (passes)
- `test -f docs/adr/007-multiplatform-windows-support.md` → EXISTS (passes)
- `grep "psutil" docs/adr/007-multiplatform-windows-support.md` → 11 lines (passes)
- `uv run ruff check .` → All checks passed
- `uv run pytest -x -q` → 215 passed

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 0cd14dd | docs(04-02): add Windows installation and first-run sections |
| Task 2 | 54b387f | docs(04-02): add ADR-007 multiplatform Windows support decisions |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `README.md` exists and contains Windows section: FOUND
- `docs/usage.md` exists and contains Windows section: FOUND
- `docs/adr/007-multiplatform-windows-support.md` exists: FOUND
- Commits 0cd14dd and 54b387f verified in git log: FOUND
