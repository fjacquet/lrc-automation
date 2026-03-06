---
phase: 03-ci-matrix
plan: 01
subsystem: infra
tags: [ci, github-actions, uv, ruff, mypy, pytest, windows, macos, gitattributes]

# Dependency graph
requires:
  - phase: 02-write-safety
    provides: "Cross-platform executor and process check completed"
provides:
  - ".gitattributes with LF enforcement for all text files"
  - "3-OS x 2-Python CI matrix using uv run commands and setup-uv@v7"
affects: [04-scanner-date]

# Tech tracking
tech-stack:
  added: []
  patterns: [uv run for all CI steps (no make), gitattributes eol=lf for cross-platform line endings]

key-files:
  created: [.gitattributes]
  modified: [.github/workflows/ci.yml]

key-decisions:
  - "gitattributes eol=lf prevents CRLF failures on Windows runners — ruff format --check sees consistent line endings"
  - "setup-uv@v7 with enable-cache: true replaces v4 for OS-aware cache keys in multi-OS matrix"
  - "uv sync (no --all-extras) on all platforms — reverse_geocoder has no Windows wheel, so geo extra is CI-excluded"
  - "fail-fast: false so a failure on one platform does not cancel other platform runs"
  - "Individual uv run steps replace make check — make is unavailable on Windows runners"

patterns-established:
  - "All CI steps use uv run <tool> rather than make targets for cross-platform compatibility"
  - "Binary file types explicitly excluded from LF normalisation in .gitattributes"

requirements-completed: [CI-01, CI-02, CI-03]

# Metrics
duration: 5min
completed: 2026-03-06
---

# Phase 3 Plan 01: CI Matrix Summary

**3-OS x 2-Python GitHub Actions matrix with LF enforcement via .gitattributes and setup-uv@v7, replacing ubuntu-only make check CI**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-06T20:49:00Z
- **Completed:** 2026-03-06T20:54:25Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `.gitattributes` enforcing LF on all text files at checkout — prevents CRLF failures on Windows runners
- Rewrote `ci.yml` with 3-OS matrix (ubuntu, macos, windows) x 2 Python versions (3.12, 3.13)
- Upgraded `setup-uv@v4` to `setup-uv@v7` with `enable-cache: true` for OS-aware cache keys
- Replaced `make check` with four individual `uv run` steps that work on all three platforms
- All 207 tests pass locally

## Task Commits

Each task was committed atomically:

1. **Task 1: Create .gitattributes with LF enforcement** - `437145c` (chore)
2. **Task 2: Rewrite ci.yml — 3-OS matrix, uv run commands, setup-uv@v7** - `6d6407d` (feat)

## Files Created/Modified

- `.gitattributes` - LF enforcement for all text files; binary exclusions for whl, images, lrcat, db, sqlite
- `.github/workflows/ci.yml` - 3x2 matrix (os x python-version), fail-fast: false, setup-uv@v7 with cache, four uv run steps

## Decisions Made

- Used `* text=auto eol=lf` as the top-level rule — applies to all text files before specific binary overrides
- Omitted `uv sync --all-extras` because `reverse_geocoder` lacks a Windows wheel; geo extra tests are not part of the core CI gate
- `fail-fast: false` keeps all runners running independently so failures on one OS don't mask failures on another
- `setup-uv@v7` chosen (current stable) over v4 for proper multi-OS cache key handling

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CI infrastructure is complete for Phase 4 (scanner date detection)
- Windows runner will now enforce LF checkout before ruff runs
- Geo extra exclusion from CI is documented — Phase 4 plans that add geo tests should use a separate job with `uv sync --all-extras` on ubuntu only

---
*Phase: 03-ci-matrix*
*Completed: 2026-03-06*
