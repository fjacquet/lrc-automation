---
phase: 01-path-safety
plan: 03
subsystem: packaging
tags: [pyproject.toml, uv, reverse-geocoder, optional-dependencies, import-guard]

# Dependency graph
requires: []
provides:
  - reverse-geocoder removed from core and dev deps, kept only in [geo] optional extra
  - tests/test_packaging.py with 4 import-guard tests validating lazy-load behaviour
affects: [02-platform-compat, 03-crossplatform-ci]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional geo extra: reverse_geocoder and pycountry only in [project.optional-dependencies].geo"
    - "Lazy import guard: reverse_geocoder loaded on first use inside LocationResolver._ensure_loaded()"

key-files:
  created:
    - tests/test_packaging.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Remove pycountry from dev group alongside reverse_geocoder: both are geo-only, neither belongs in core dev"
  - "Test lazy-load pattern with sentinel module to catch any future eager import regressions"

patterns-established:
  - "Packaging test pattern: use monkeypatch.setitem(sys.modules, name, None) to simulate absent optional dep"
  - "Sentinel module pattern: subclass types.ModuleType to detect unexpected attribute accesses at import time"

requirements-completed: [UX-03]

# Metrics
duration: 12min
completed: 2026-03-06
---

# Phase 1 Plan 03: Geo Extra Packaging Fix Summary

**reverse-geocoder removed from core pyproject.toml deps and dev group; 4 import-guard tests confirm lazy-load works without the library installed**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-06T20:03:55Z
- **Completed:** 2026-03-06T20:15:30Z
- **Tasks:** 2
- **Files modified:** 3 (pyproject.toml, uv.lock, tests/test_packaging.py)

## Accomplishments
- Removed `pycountry>=24.6.1` and `reverse_geocoder>=1.5.1` from `[dependency-groups].dev` in pyproject.toml
- Regenerated uv.lock with `uv sync --all-extras` so geo tests still pass in dev environment
- Created tests/test_packaging.py with 4 tests verifying the lazy import guard works correctly
- All 198 tests pass (0 failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove reverse-geocoder from core and dev deps** - `2d6ec0a` (fix)
2. **Task 2: Add packaging guard test confirming core import works without reverse-geocoder** - `c1f1746` (test)

## Files Created/Modified
- `pyproject.toml` - Removed pycountry and reverse_geocoder from [dependency-groups].dev
- `uv.lock` - Regenerated after dep removal (--all-extras keeps geo packages in dev env)
- `tests/test_packaging.py` - 4 tests: cli import guard, resolve() guard, resolve_batch() guard, lazy-load sentinel

## Exact Diff Applied to pyproject.toml

```diff
 dev = [
     "mkdocs>=1.6",
     "mkdocs-material>=9.6",
     "mypy>=1.14",
     "pytest>=9.0.2",
     "pytest-cov>=6.0",
-    "pycountry>=24.6.1",
-    "reverse_geocoder>=1.5.1",
     "ruff>=0.15.1",
 ]
```

`[project.optional-dependencies].geo` unchanged:
```toml
geo = ["reverse_geocoder>=1.5.1", "pycountry>=24.6.1"]
```

## Tests Added in test_packaging.py

| Test | Class | What it verifies |
|------|-------|-----------------|
| `test_cli_import_succeeds_without_reverse_geocoder` | `TestCliImportWithoutReverseGeocoder` | `lrc_automation.cli` imports cleanly with reverse_geocoder absent |
| `test_geocoder_import_raises_without_geo_extra` | `TestGeocoderImportGuard` | `resolve()` raises ImportError mentioning `lrc-automation[geo]` |
| `test_geocoder_batch_raises_without_geo_extra` | `TestGeocoderImportGuard` | `resolve_batch()` raises ImportError mentioning `lrc-automation[geo]` |
| `test_geocoder_lazy_load_not_triggered_at_import` | `TestGeocoderImportGuard` | Importing geocoder module does not touch reverse_geocoder at all |

## uv.lock Changes Summary

- reverse_geocoder and pycountry removed from dev group markers in lock file
- Both packages retained as geo extra dependencies
- `uv sync --all-extras` resolves 48 packages (same count — geo extra still installed in dev venv)

## Decisions Made
- Removed pycountry from dev group alongside reverse_geocoder: both are geo-only concerns and neither belongs in the baseline dev environment that a contributor gets with plain `uv sync`
- Used sentinel module pattern (subclass of types.ModuleType) rather than simple None to detect eager imports at module load time

## Deviations from Plan

None - plan executed exactly as written. The pyproject.toml already had reverse-geocoder removed from `[project].dependencies` (that line was gone before this plan ran), so Task 1 only needed to remove the two dev-group lines.

## Issues Encountered

None - all tests passed on first run after implementation.

## Next Phase Readiness
- Packaging is now correct: plain install gets no geo library, `[geo]` extra opt-in is explicit
- Phase 1 remaining plans (01, 02) cover SQLite URI and Windows path safety
- geo extra import guard pattern documented in test_packaging.py for future reference

---
*Phase: 01-path-safety*
*Completed: 2026-03-06*
