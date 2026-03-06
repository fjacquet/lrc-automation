---
phase: 04-ux-and-docs
plan: "01"
subsystem: ui
tags: [click, cli, auto-discovery, ux, lightroom]

# Dependency graph
requires: []
provides:
  - _discover_default_catalog() function in cli.py
  - --catalog option made optional (required=False)
  - UsageError when no catalog found with clear guidance message
  - BadParameter when explicit catalog path does not exist
affects: [all phases that invoke cli.py]

# Tech tracking
tech-stack:
  added: []
  patterns: [monkeypatch + CliRunner for Click integration tests, home_dir injection for testable path discovery]

key-files:
  created: [tests/test_cli.py]
  modified: [src/lrc_automation/cli.py]

key-decisions:
  - "home_dir parameter on _discover_default_catalog() for testability rather than monkeypatching Path.home()"
  - "envvar LRC_CATALOG_PATH still takes priority via Click --catalog option's envvar= binding (not special-cased in code)"
  - "type=click.Path() (no exists=True) to allow None path through to manual existence check in cli() body"
  - "monkeypatch.delenv('LRC_CATALOG_PATH') needed in no-catalog tests since dev machine has env var set"

patterns-established:
  - "CLI integration tests: monkeypatch module-level function + delenv to isolate from environment"
  - "Discovery functions accept home_dir=None override for hermetic testing without filesystem mocks"

requirements-completed: [UX-01]

# Metrics
duration: 2min
completed: 2026-03-06
---

# Phase 4 Plan 01: Catalog Auto-Discovery Summary

**`--catalog` made optional via `_discover_default_catalog()` checking `~/Pictures/Lightroom/*.lrcat` with clear UsageError when no catalog is found**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-06T21:33:37Z
- **Completed:** 2026-03-06T21:36:09Z
- **Tasks:** 2 (RED + GREEN TDD cycle)
- **Files modified:** 2

## Accomplishments

- Added `_discover_default_catalog(home_dir=None)` at module level in `cli.py`: globs `~/Pictures/Lightroom/*.lrcat`, returns first sorted match or `None`
- Changed `--catalog` option from `required=True, type=click.Path(exists=True)` to `required=False, default=None, type=click.Path()`
- Updated `cli()` body: calls discovery when `catalog is None`, raises `UsageError` if still `None`, raises `BadParameter` for explicit non-existent paths
- Created `tests/test_cli.py` with 8 tests covering all discovery and CLI integration behaviors

## Task Commits

Each task was committed atomically:

1. **RED: Failing auto-discovery tests** - `940f4bc` (test)
2. **GREEN: Implement auto-discovery in cli.py** - `a3ae264` (feat)

## Files Created/Modified

- `src/lrc_automation/cli.py` - Added `_discover_default_catalog()`, updated `--catalog` option and `cli()` body
- `tests/test_cli.py` - New file with 8 tests for discovery unit and CLI integration

## Decisions Made

- `home_dir` parameter on `_discover_default_catalog()` for testability — avoids monkeypatching `Path.home()`
- `envvar="LRC_CATALOG_PATH"` on `--catalog` still takes priority automatically via Click option binding
- `type=click.Path()` (no `exists=True`) allows `None` through to the manual existence check in the `cli()` body
- `monkeypatch.delenv("LRC_CATALOG_PATH")` required in no-catalog tests because the developer's machine has the env var set to a real catalog path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test failed due to LRC_CATALOG_PATH env var on developer machine**

- **Found during:** GREEN phase (first test run)
- **Issue:** `test_cli_errors_when_no_catalog` expected "No catalog specified" but got "Catalog not found: /Volumes/T7 Shield/LRC2026/LRC2026.lrcat" because `LRC_CATALOG_PATH` env var was set and took precedence
- **Fix:** Added `monkeypatch.delenv("LRC_CATALOG_PATH", raising=False)` to both env-sensitive tests
- **Files modified:** `tests/test_cli.py`
- **Verification:** 8 tests pass, including on CI where env var is absent
- **Committed in:** `a3ae264` (GREEN commit)

**2. [Rule 1 - Bug] Unused `sys` import and long lines**

- **Found during:** GREEN phase ruff lint
- **Issue:** `import sys` added per plan spec but not used; several test lines exceeded 88 chars
- **Fix:** Removed `sys` import; rewrapped long function signatures and docstrings; ran `ruff check --fix` for import sort
- **Files modified:** `src/lrc_automation/cli.py`, `tests/test_cli.py`
- **Verification:** `ruff check .` passes with zero errors
- **Committed in:** `a3ae264` (GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 bugs found during green phase verification)
**Impact on plan:** Both fixes necessary for lint compliance and CI correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `--catalog` is now optional for zero-config first run on standard Lightroom installations
- `_discover_default_catalog()` is importable and testable for future enhancements (e.g., searching additional paths)
- All 215 tests pass; mypy strict and ruff clean

---
*Phase: 04-ux-and-docs*
*Completed: 2026-03-06*
