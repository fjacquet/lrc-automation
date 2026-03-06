---
phase: 01-path-safety
plan: 02
subsystem: scanner
tags: [sqlite, path-safety, windows, backslash, tdd]

# Dependency graph
requires:
  - phase: 01-path-safety
    provides: PATH-01 SQLite URI fix ensuring catalog opens on Windows
provides:
  - Backslash-normalised full_folder at scan_misplaced_photos() line 125
  - Backslash-normalised full_folder at scan_needs_location_folder() line 224
  - Backslash-normalised root_year_str at scan_year_in_year_photos() line 244
  - Four new PATH-02 regression tests for Windows catalog paths
affects:
  - planner.py (uses PhotoRecord.root_absolute_path — may also need normalisation if it builds paths)
  - executor.py (moves files using root path — already uses pathlib so less risk)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backslash normalisation: always call .replace('\\\\', '/') on root_absolute_path before any '/' split or concatenation"

key-files:
  created: []
  modified:
    - src/lrc_automation/scanner.py
    - tests/test_scanner.py

key-decisions:
  - "Normalise per call-site with a local norm_root variable rather than at PhotoRecord construction to keep the fix surgical and avoid breaking other callers"
  - "Use no-op behaviour on already-forward-slash paths so existing Mac/Linux tests remain unchanged"

patterns-established:
  - "TDD RED-GREEN: commit failing tests first, then fix code in a second commit"
  - "norm_root pattern: assign photo.root_absolute_path.replace('\\\\', '/') to norm_root before any path operations"

requirements-completed: [PATH-02]

# Metrics
duration: 12min
completed: 2026-03-06
---

# Phase 01 Plan 02: Path Safety — Windows Backslash Normalisation Summary

**Three one-line `.replace("\\", "/")` fixes in scanner.py make Windows-catalog backslash root paths visible to date-detection, backed by four new regression tests.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-06T00:00:00Z
- **Completed:** 2026-03-06T00:12:00Z
- **Tasks:** 2 (TDD RED + TDD GREEN)
- **Files modified:** 2

## Accomplishments

- Added four failing tests for Windows-style `absolutePath` (e.g. `C:\Users\Photos\`) before the fix
- Fixed `scan_misplaced_photos()` so Windows-root catalogs correctly detect misplaced photos
- Fixed `scan_needs_location_folder()` so GPS location candidates are found under Windows roots
- Fixed `scan_year_in_year_photos()` so root-year extraction works on backslash paths
- All 198 tests pass; ruff and mypy both clean on `src/`

## Task Commits

1. **Task 1: Write failing tests for PATH-02 Windows backslash absolutePath (RED)** - `1e8a6f5` (test)
2. **Task 2: Fix backslash normalisation in scanner.py (GREEN)** - `c18224b` (feat)

## Exact Lines Changed in scanner.py

### Site 1 — scan_misplaced_photos() (~line 124)

Before:
```python
full_folder = photo.root_absolute_path + photo.current_folder_path
```

After:
```python
norm_root = photo.root_absolute_path.replace("\\", "/")
full_folder = norm_root + photo.current_folder_path
```

### Site 2 — scan_needs_location_folder() (~line 223)

Before:
```python
full_folder = photo.root_absolute_path + photo.current_folder_path
```

After:
```python
norm_root = photo.root_absolute_path.replace("\\", "/")
full_folder = norm_root + photo.current_folder_path
```

### Site 3 — scan_year_in_year_photos() (~line 243)

Before:
```python
root_year_str = photo.root_absolute_path.rstrip("/").split("/")[-1]
```

After:
```python
norm_root = photo.root_absolute_path.replace("\\", "/")
root_year_str = norm_root.rstrip("/").split("/")[-1]
```

## Tests Added and What Each Proves

| Test name | What it proves |
|-----------|---------------|
| `test_scan_misplaced_windows_backslash_root` | Correctly placed photo under `C:\Users\Photos\` root is NOT returned as misplaced |
| `test_scan_misplaced_windows_backslash_root_detects_mismatch` | Photo in wrong month under Windows root IS returned as misplaced (main regression) |
| `test_scan_year_in_year_windows_backslash_root` | Root year extraction works on `C:\Lightroom\2022\` (backslash root) |
| `test_scan_needs_location_folder_windows_backslash_root` | GPS photo in date-matching folder under Windows root is returned as location candidate |

## Files Created/Modified

- `/Users/fjacquet/Projects/lrc-automation/src/lrc_automation/scanner.py` — Three one-line normalisation fixes at call sites (using local `norm_root` variable)
- `/Users/fjacquet/Projects/lrc-automation/tests/test_scanner.py` — Added `SCHEMA_SQL` import + four new PATH-02 test methods to `TestCatalogScanner`

## Decisions Made

- Normalise at the call site (assign to `norm_root`) rather than at `PhotoRecord` construction, keeping the fix surgical and limited to scanner.py
- Extract to a named variable (`norm_root`) rather than chaining inline to stay within ruff's 88-character line limit

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Style] Fixed E501 line-length violations from inline `.replace()` chains**
- **Found during:** Task 2 (GREEN phase), ruff check after edits
- **Issue:** Inlining `.replace("\\", "/")` directly in the long concatenation expressions pushed lines over 88 chars
- **Fix:** Extracted each normalisation to a `norm_root` local variable; shortened test docstrings and split long tuple literals
- **Files modified:** `src/lrc_automation/scanner.py`, `tests/test_scanner.py`
- **Verification:** `uv run ruff check src/lrc_automation/scanner.py && uv run ruff check tests/test_scanner.py` both exit 0
- **Committed in:** c18224b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - style/correctness to pass CI)
**Impact on plan:** The `norm_root` pattern is strictly cleaner than the inline approach anyway. No scope creep.

## Issues Encountered

None — plan executed as specified once the line-length constraint was addressed.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- PATH-02 fix complete; Windows-catalog scanning now reliable
- planner.py also uses `root_absolute_path` to build paths — recommend checking those sites for the same backslash pattern (PATH-03 or a follow-on plan)
- All scanner tests passing; ready to proceed to remaining Phase 1 plans

---
*Phase: 01-path-safety*
*Completed: 2026-03-06*
