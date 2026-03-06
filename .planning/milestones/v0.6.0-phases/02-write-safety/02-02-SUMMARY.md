---
phase: 02-write-safety
plan: "02"
subsystem: executor
tags: [pathlib, as_posix, darwin, sys.platform, retry, PermissionError, sqlite]

# Dependency graph
requires:
  - phase: 01-path-safety
    provides: SQLite URI fix, backslash normalisation enabling safe catalog opens on Windows
provides:
  - as_posix() forward-slash writes in cleanup_empty_folders (executor.py)
  - as_posix() forward-slash writes in _reconcile_one (reconciler.py)
  - sys.platform darwin guard in _is_effectively_empty and cleanup_empty_folders
  - _MOVE_RETRIES / _MOVE_RETRY_SLEEP constants with PermissionError retry loop in _apply_file_op
affects:
  - 03-ci-windows
  - any future executor or reconciler changes touching pathFromRoot derivation

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use rel.as_posix() (never str(rel)) when writing Path to SQLite pathFromRoot column"
    - "Guard AppleDouble ._* logic with sys.platform == 'darwin'"
    - "Retry loops on PermissionError: register rollback AFTER success, not before"

key-files:
  created: []
  modified:
    - src/lrc_automation/executor.py
    - src/lrc_automation/reconciler.py
    - tests/test_executor.py
    - tests/test_reconciler.py

key-decisions:
  - "sys.platform == 'darwin' is the guard for all AppleDouble logic — not os.name or platform.system()"
  - "Rollback action appended AFTER successful file op completes, not inside retry loop, to prevent ghost rollbacks"
  - "_MOVE_RETRY_SLEEP set to 0.0 in tests via monkeypatch to keep test suite fast"

patterns-established:
  - "as_posix() for any Path -> SQL column write: always produces forward slashes regardless of host OS"
  - "darwin guard pattern: if sys.platform == 'darwin': before any AppleDouble interaction"
  - "Retry loop pattern: last_err sentinel, break on success, raise last_err after loop"

requirements-completed: [PROC-02, PROC-03, PROC-04]

# Metrics
duration: 4min
completed: 2026-03-06
---

# Phase 02 Plan 02: Write Safety Summary

**Cross-platform SQL writes hardened: as_posix() pathFromRoot, darwin-gated AppleDouble cleanup, and 3-attempt PermissionError retry loop in executor and reconciler**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-06T20:30:18Z
- **Completed:** 2026-03-06T20:34:18Z
- **Tasks:** 2 (RED + GREEN TDD cycle)
- **Files modified:** 4

## Accomplishments

- PROC-02: `rel.as_posix()` used in both `cleanup_empty_folders` and `_reconcile_one` — forward slashes stored in SQLite pathFromRoot on all platforms
- PROC-03: `_is_effectively_empty` and `_delete_apple_double_files` call guarded by `sys.platform == "darwin"` — non-macOS platforms treat `._*` as real files and never delete them
- PROC-04: `_apply_file_op` wraps `shutil.move`/`os.rename` in a 3-attempt retry loop sleeping `_MOVE_RETRY_SLEEP` seconds on `PermissionError`, re-raising on exhaustion; rollback registered only after success

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Add failing tests for as_posix, darwin guard, and retry** - `a1ddfd4` (test)
2. **Task 2: GREEN — Fix as_posix writes, darwin guard, and retry loop** - `afc8d4d` (feat)

**Plan metadata:** `e1ff274` (docs: complete plan)

_Note: TDD tasks have two commits: test (RED) then feat (GREEN)_

## Files Created/Modified

- `src/lrc_automation/executor.py` — Added `sys`, `time` imports; `_MOVE_RETRIES`/`_MOVE_RETRY_SLEEP` constants; darwin guard in `_is_effectively_empty` and `cleanup_empty_folders`; `as_posix()` for pathFromRoot; retry loop in `_apply_file_op`
- `src/lrc_automation/reconciler.py` — `rel.parent.as_posix()` in `_reconcile_one` pathFromRoot derivation
- `tests/test_executor.py` — `TestWriteSafety` class: 5 new tests covering all three PROC requirements
- `tests/test_reconciler.py` — Source-inspection test verifying `as_posix()` in reconciler

## Decisions Made

- `sys.platform == "darwin"` chosen over `os.name == "nt"` negation because the guard protects a macOS-specific behaviour (AppleDouble), making darwin the positive assertion cleaner
- Rollback action registered after the retry loop succeeds — never inside the loop — so partial/failed attempts leave no ghost rollback entries
- `_MOVE_RETRY_SLEEP` is a module-level constant (not hardcoded) so tests can zero it out via `monkeypatch.setattr` without modifying production code

## Deviations from Plan

None — plan executed exactly as written. The only minor adjustment was shortening two docstrings by a few words to satisfy ruff E501 (88-char line limit), which is a formatting requirement, not a functional deviation.

## Issues Encountered

- `uv sync` (run before execution) removed geo extras (`reverse_geocoder`, `numpy`, etc.); `uv sync --all-extras` restored them so the full 207-test suite could run green.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- PROC-02, PROC-03, PROC-04 requirements fulfilled
- Phase 03 (CI Windows) can proceed: executor and reconciler write-safety fixes are in place
- No blockers

## Self-Check: PASSED

- executor.py: FOUND
- reconciler.py: FOUND
- 02-02-SUMMARY.md: FOUND
- RED commit a1ddfd4: FOUND
- GREEN commit afc8d4d: FOUND
- Metadata commit e1ff274: FOUND

---
_Phase: 02-write-safety_
_Completed: 2026-03-06_
