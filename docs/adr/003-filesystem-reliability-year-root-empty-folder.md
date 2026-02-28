# ADR-003: Filesystem Reliability — Per-Year-Root Path Fix and Empty Folder Cleanup

**Status:** Accepted
**Date:** 2026-02-28
**Decision Makers:** fjacquet

## Context

Three concrete problems were discovered after a Switzerland validation run that produced
19,127 moves to wrong country folders:

### Problem 1 — Year-doubling in per-year root catalogs

The catalog uses per-year root folders: `/Volumes/T7 Shield/Lightroom/2012/` is one root,
`/Volumes/T7 Shield/Lightroom/2022/` is another. For these roots,
`AgLibraryFolder.pathFromRoot` contains only the month/day portion, e.g. `"10/13/"` — not
`"2012/10/13/"`.

`_plan_location_moves()` was calling `photo.get_expected_folder_path_with_location()` which
runs `strftime("%Y/%m/")` and returns `"2012/10/CH/Saillon/"`. When the executor built
`dst_dir`:

```
dst_dir = Path("/Volumes/.../2012/") / "2012/10/CH/Saillon/"
        = /Volumes/.../2012/2012/10/CH/Saillon/   ← year DOUBLED
```

The move succeeded (mkdir + shutil.move both work on the wrong doubled path), the DB was
updated with the doubled pathFromRoot, and postflight_check passed because it used the same
path. The plan output showed `10/13/ → 2012/10/Switzerland/Saillon/` — the year doubling
was visible but unnoticed.

This caused 19,127 photos to be moved to paths like
`/Volumes/T7 Shield/Lightroom/2012/2012/10/CH/Saillon/` — which Lightroom would treat as
missing files.

### Problem 2 — `check_files_exist_on_disk()` not wired into `validate`

`CatalogValidator.check_files_exist_on_disk()` existed and queried every photo's full path,
but the `validate` CLI command only called `preflight_check()` and `check_year_in_year()`.
Users had no CLI way to audit "does every DB record have a real file on disk?"

### Problem 3 — Empty source directories not cleaned up

After moving all files out of a folder, the now-empty directory remained on disk and as an
`AgLibraryFolder` record in the DB. This created orphaned directories and confusing
Lightroom UI entries showing empty folders.

---

## Decisions

### Decision 1: `date_portion_of_path()` utility

**Decision:** Add a module-level utility function `date_portion_of_path(path_from_root, year, month) -> str` to `utils.py` that extracts only the date portion of a `pathFromRoot` string, stripping any trailing location subfolders.

```python
date_portion_of_path("10/Switzerland/Saillon/", 2012, 10)  # → "10/"
date_portion_of_path("2023/06/FR/Paris/",       2023, 6)   # → "2023/06/"
date_portion_of_path("2023-06-15/CH/Saillon/",  2023, 6)   # → "2023-06-15/"
```

The function handles all three folder formats used in the real catalog:
- `YYYY/MM/` — standard layout
- `MM/` — per-year root (year lives in `absolutePath`)
- `YYYY-MM-DD/` — ISO date folders

**Rationale:** The root cause of the year-doubling was that `_plan_location_moves()` derived the target path from the photo's `capture_time` via `strftime`, discarding the existing `pathFromRoot`. For per-year roots the year must not be repeated. Using the existing `pathFromRoot` as the date prefix is the correct approach — it was already correct before any location suffix was added.

### Decision 2: `_plan_location_moves()` uses `date_portion_of_path`

**Decision:** Replace the `get_expected_folder_path_with_location()` call in `_plan_location_moves()` with:

```python
date_pfx = date_portion_of_path(
    photo.current_folder_path,
    photo.capture_time.year,
    photo.capture_time.month,
)
target_path = f"{date_pfx}{country}/{city}/"
```

**Rationale:** This preserves the existing date representation in the path (whether `YYYY/MM/`, `MM/`, or `YYYY-MM-DD/`) and appends only the location suffix. The year is never recomputed from `capture_time`, so it cannot be doubled.

### Decision 3: Empty folder cleanup in `ChangeExecutor`

**Decision:** After the main `COMMIT`, sweep through source directories from which all files were moved. For each directory that is now empty on disk: `rmdir()` the directory and delete the corresponding `AgLibraryFolder` DB row. Each deletion is its own `COMMIT`.

```python
def _cleanup_empty_folders(
    self, conn, source_dirs: set[tuple[int, str, str]]
) -> int:
```

Add `folders_removed: int = 0` to `ExecutionReport` and display in the reporter.

**Rationale:** Leaving empty directories creates confusing Lightroom UI entries (empty folder nodes). The cleanup is non-critical (non-fatal `OSError` is suppressed) and runs only after the main transaction commits successfully, so it cannot corrupt the main operation.

**Alternative considered:** Remove empty folders via a separate `cleanup` CLI command. Rejected — it requires a second pass over the same data and leaves a window where the DB and disk are inconsistent.

---

## Affected Files

| File | Change |
|------|--------|
| `src/lrc_automation/utils.py` | Added `date_portion_of_path()` |
| `src/lrc_automation/planner.py` | `_plan_location_moves()` now uses `date_portion_of_path` |
| `src/lrc_automation/executor.py` | Added `_cleanup_empty_folders()`, collects source dirs in `execute()` |
| `src/lrc_automation/models.py` | Added `folders_removed: int = 0` to `ExecutionReport` |
| `src/lrc_automation/reporter.py` | Shows `folders_removed` in execution summary |

## Tests

- `tests/test_utils.py` — `TestDatePortionOfPath` (8 cases covering all folder formats)
- `tests/conftest.py` — `tmp_catalog_per_year_root` fixture
- `tests/test_planner.py` — `TestPlanLocationMovesPerYearRoot.test_target_path_does_not_double_year`
- `tests/test_executor.py` — `TestEmptyFolderCleanup` (2 cases)

---

## Consequences

**Positive:**
- Location moves are now correct for all root folder types (flat and per-year).
- Lightroom's folder panel no longer shows empty ghost folders after a run.
- `ExecutionReport` accurately counts folders removed.

**Negative:**
- `_cleanup_empty_folders` issues one DB `COMMIT` per removed folder outside the main
  transaction. A crash between removals would leave some empty DB rows without their disk
  directories, but this is non-critical (no data is lost).

**Risk mitigation:** The main transaction commits before cleanup begins. A cleanup failure
leaves empty folders on disk and in the DB — a cosmetic problem, not a data-loss problem.
Users can re-run `apply` (cleanup is idempotent) or manually delete the empty folders.
