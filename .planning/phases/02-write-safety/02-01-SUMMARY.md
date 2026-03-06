---
phase: 02-write-safety
plan: "01"
subsystem: catalog
tags: [psutil, process-detection, cross-platform, windows, macos, safety]

# Dependency graph
requires: []
provides:
  - "psutil.process_iter replaces pgrep subprocess in check_lightroom_not_running"
  - "LR_PROCESS_NAME_WINDOWS constant in constants.py"
  - "psutil>=5.9 as core dependency"
  - "types-psutil in dev dependencies for mypy strict mode"
affects:
  - 02-write-safety
  - executor
  - catalog

# Tech tracking
tech-stack:
  added:
    - "psutil>=5.9 (core dependency)"
    - "types-psutil (dev dependency)"
  patterns:
    - "psutil.process_iter for cross-platform process detection — one caller in catalog.py"
    - "TDD RED-GREEN: commit failing tests before production code"

key-files:
  created: []
  modified:
    - "src/lrc_automation/catalog.py — replaced pgrep with psutil.process_iter"
    - "src/lrc_automation/constants.py — added LR_PROCESS_NAME_WINDOWS"
    - "pyproject.toml — added psutil>=5.9 to [project.dependencies] and types-psutil to dev"
    - "tests/test_catalog.py — added 3 PROC-01 tests (macOS, Windows, AccessDenied)"
    - "uv.lock — updated with psutil and types-psutil"

key-decisions:
  - "psutil.process_iter replaces pgrep subprocess: cross-platform, no external binary needed"
  - "types-psutil added as dev dependency to satisfy mypy strict mode"
  - "WAL mode is NOT enabled in check_lightroom_not_running (documented in method docstring) — Windows file-locking semantics prohibit it"

patterns-established:
  - "ClassVar[dict[str, str]] annotation required for mutable class-level dict in test FakeProc stubs (ruff RUF012)"

requirements-completed:
  - PROC-01

# Metrics
duration: 3min
completed: 2026-03-06
---

# Phase 02 Plan 01: psutil Cross-Platform Lightroom Process Detection Summary

**psutil.process_iter replaces pgrep subprocess in catalog.py, detecting both 'Adobe Lightroom Classic' (macOS) and 'Lightroom.exe' (Windows) as a core dependency**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-06T20:30:13Z
- **Completed:** 2026-03-06T20:33:00Z
- **Tasks:** 2 (RED + GREEN)
- **Files modified:** 5

## Accomplishments

- Replaced macOS-only `pgrep` subprocess with `psutil.process_iter` for cross-platform Lightroom detection
- Added `LR_PROCESS_NAME_WINDOWS = "Lightroom.exe"` constant to constants.py
- Added `psutil>=5.9` as a core dependency (binary wheels available for all target platforms)
- Added `types-psutil` as dev dependency to satisfy mypy strict mode
- All three PROC-01 tests pass: macOS detection, Windows detection, AccessDenied tolerance

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — add failing tests for psutil process detection** - `46b5c92` (test)
2. **Task 2: GREEN — implement psutil detection + add psutil to pyproject.toml** - `af0d2bb` (feat)

_Note: TDD tasks have separate commits (test RED → feat GREEN)_

## Files Created/Modified

- `src/lrc_automation/catalog.py` — replaced pgrep subprocess with psutil.process_iter; removed subprocess import; added psutil import and LR_PROCESS_NAME_WINDOWS import
- `src/lrc_automation/constants.py` — added `LR_PROCESS_NAME_WINDOWS = "Lightroom.exe"`
- `pyproject.toml` — added `psutil>=5.9` to core dependencies; `types-psutil` to dev dependencies
- `tests/test_catalog.py` — added 3 PROC-01 tests + LightroomRunningError import + ClassVar annotation + typing.ClassVar import
- `uv.lock` — updated with psutil 7.2.2 and types-psutil 7.2.2.20260130

## Decisions Made

- psutil.process_iter chosen over pgrep: cross-platform, no external binary dependency, AccessDenied handling built in
- types-psutil added to satisfy mypy strict mode (no `# type: ignore[import-untyped]` needed)
- WAL mode explicitly NOT enabled (documented in method docstring per STATE.md blocker note)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added types-psutil dev dependency for mypy strict mode**

- **Found during:** Task 2 (GREEN — run make check)
- **Issue:** `mypy src/` reported `error: Library stubs not installed for "psutil"` because strict mode requires type stubs
- **Fix:** `uv add --dev "types-psutil"` — installs official psutil type stubs
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Verification:** `uv run mypy src/` reports "Success: no issues found in 14 source files"
- **Committed in:** `af0d2bb` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added ClassVar annotation to FakeProc.info dict**

- **Found during:** Task 2 (GREEN — ruff check)
- **Issue:** `ruff check` reported RUF012 "Mutable default value for class attribute" on `info = {...}` in FakeProc stubs
- **Fix:** Added `ClassVar[dict[str, str]]` type annotation and `from typing import ClassVar` import to test file
- **Files modified:** `tests/test_catalog.py`
- **Verification:** `uv run ruff check tests/test_catalog.py` reports "All checks passed!"
- **Committed in:** `af0d2bb` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 2 — missing critical correctness for type checking and linting)
**Impact on plan:** Both auto-fixes necessary for mypy strict compliance and ruff clean pass. No scope creep.

## Issues Encountered

- Pre-existing `test_executor.py` lint errors (E501 lines too long) exist in the codebase from plan 02-02. These are out of scope for this plan — logged to deferred-items but not fixed. `make check` fails for these pre-existing reasons.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PROC-01 complete: Lightroom process detection is now cross-platform
- `psutil>=5.9` established as core dependency — available to PROC-02, PROC-03, PROC-04 if needed
- Pre-existing `test_executor.py` lint failures should be resolved before merging to maincd

---
_Phase: 02-write-safety_
_Completed: 2026-03-06_
