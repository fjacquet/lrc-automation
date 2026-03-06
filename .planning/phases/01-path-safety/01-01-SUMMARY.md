---
phase: 01-path-safety
plan: "01"
subsystem: catalog
tags: [path-safety, sqlite-uri, windows, cross-platform, tdd]
dependency_graph:
  requires: []
  provides: [_path_to_sqlite_uri, PATH-01-fix, PATH-03-fix]
  affects: [catalog.py, tests/test_catalog.py]
tech_stack:
  added: []
  patterns: [sqlite-file-uri, sys.platform-guard, tdd-red-green]
key_files:
  created:
    - tests/test_catalog.py
  modified:
    - src/lrc_automation/catalog.py
decisions:
  - "_path_to_sqlite_uri detects Windows drive-letter paths via posix string check (len>=3 and posix[1]==':' and posix[2]=='/') because Path.is_absolute() is platform-dependent — on macOS, Path('C:/...').is_absolute() returns False"
metrics:
  duration: "4 minutes"
  completed: "2026-03-06"
  tasks_completed: 2
  files_modified: 2
requirements_satisfied:
  - PATH-01
  - PATH-03
---

# Phase 1 Plan 01: Path Safety - SQLite URI and Mac-Origin Catalog Summary

**One-liner:** SQLite URI fix via `_path_to_sqlite_uri()` helper using `file:///` prefix + Windows drive detection; macOS-to-Windows catalog guard via `sys.platform == "win32"` check on `AgLibraryRootFolder.absolutePath`.

## What Was Implemented

### `_path_to_sqlite_uri(path: Path, readonly: bool = False) -> str`

Added as a module-level function at lines 13-32 in `src/lrc_automation/catalog.py` (before `CatalogError`).

**Signature:**
```python
def _path_to_sqlite_uri(path: Path, readonly: bool = False) -> str:
```

**Behavior:**
- Converts `path.as_posix()` to a SQLite URI with `file:///` prefix for any absolute path
- Detects absolute paths via `path.is_absolute()` (POSIX) OR checking if posix string looks like `X:/...` (Windows drive letter — needed because `Path.is_absolute()` is platform-dependent)
- Appends `?mode=ro` only when `readonly=True`
- Examples:
  - `Path("C:/Users/foo/bar.lrcat"), readonly=True` → `"file:///C:/Users/foo/bar.lrcat?mode=ro"`
  - `Path("/Volumes/photo/bar.lrcat"), readonly=False` → `"file:////Volumes/photo/bar.lrcat"`

### Changes to `validate_is_lrcat()` (lines 49-80)

1. **Suffix check** (line 49): `self.catalog_path.suffix.lower() != ".lrcat"` — accepts `.LRCAT`, `.Lrcat`, etc.
2. **URI fix** (lines 53-55): Replaced `sqlite3.connect(f"file:{self.catalog_path}?mode=ro", uri=True)` with `sqlite3.connect(_path_to_sqlite_uri(self.catalog_path, readonly=True), uri=True)`
3. **PATH-03 guard** (lines 66-78): After the `Adobe_images` table check, queries `AgLibraryRootFolder.absolutePath LIMIT 10`. If `sys.platform == "win32"` and any path contains `/Volumes/`, raises `CatalogError` with a human-readable message explaining the macOS-origin catalog issue and remediation steps.

### Changes to `open(readonly=True)` (lines 138-141)

Replaced:
```python
uri = f"file:{self.catalog_path}?mode=ro"
self.conn = sqlite3.connect(uri, uri=True)
```
With:
```python
self.conn = sqlite3.connect(
    _path_to_sqlite_uri(self.catalog_path, readonly=True), uri=True
)
```

### `import sys` added to imports (line 6)

## Test Coverage Added

`tests/test_catalog.py` — 7 new tests, all passing:

| Test | Coverage |
|------|----------|
| `test_path_to_sqlite_uri_windows_style` | URI has no backslash, `file:///` prefix, `?mode=ro` suffix for Windows-style path |
| `test_path_to_sqlite_uri_posix_absolute` | POSIX `/Volumes/...` → `file:///` prefix + `?mode=ro` |
| `test_path_to_sqlite_uri_readonly_false` | `readonly=False` → no `?mode=ro` |
| `test_path_to_sqlite_uri_is_absolute_prefix` | All absolute paths → `file:///` prefix |
| `test_validate_is_lrcat_accepts_uppercase_extension` | `.LRCAT` file accepted without raising |
| `test_mac_origin_catalog_warns_monkeypatched` | `sys.platform="win32"` + `/Volumes/` → `CatalogError` with `/Volumes/` in message |
| `test_mac_origin_catalog_ok_on_non_windows` | Native platform (darwin/linux) → no raise for `/Volumes/` paths |

**Full test suite: 198 tests, 0 failures.**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cross-platform detection of Windows drive-letter paths**

- **Found during:** Task 2 (GREEN phase)
- **Issue:** `Path("C:/Users/foo/bar.lrcat").is_absolute()` returns `False` on macOS/Linux because POSIX doesn't recognize drive letters. The plan used `path.is_absolute()` as the sole absolute-path check, which caused the Windows-style path test to fail — URI produced was `file:C:/...` instead of `file:///C:/...`.
- **Fix:** Added `has_drive = len(posix) >= 3 and posix[1] == ":" and posix[2] == "/"` as an additional check alongside `path.is_absolute()`. Uses `is_abs = path.is_absolute() or has_drive` so the function works correctly on all platforms for both path styles.
- **Files modified:** `src/lrc_automation/catalog.py` (lines 27-30)
- **Commit:** 24d3f05

## Self-Check: PASSED

- [x] `src/lrc_automation/catalog.py` exists and contains `_path_to_sqlite_uri`
- [x] `tests/test_catalog.py` exists and has 7 tests
- [x] Commit `29eadbe` (RED phase) exists
- [x] Commit `24d3f05` (GREEN phase) exists
- [x] `uv run pytest -v` → 198 passed
- [x] `uv run ruff check src/lrc_automation/catalog.py tests/test_catalog.py` → clean
- [x] `uv run mypy src/lrc_automation/catalog.py` → no issues
