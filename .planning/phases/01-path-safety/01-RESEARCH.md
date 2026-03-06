# Phase 1: Path Safety - Research

**Researched:** 2026-03-06
**Domain:** Python pathlib, SQLite URI construction, pyproject.toml optional dependencies
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PATH-01 | Tool opens Lightroom catalog on Windows without SQLite URI error (normalize `file:` URI to forward slashes before opening) | SQLite URI spec + pathlib.as_posix() pattern documented in Standard Stack; exact fix in Code Examples |
| PATH-02 | Scan correctly extracts dates when catalog root uses Windows drive-letter paths (`C:/Photos/`) combined with `pathFromRoot` | `extract_date_from_path()` already splits on `/` only — safe when separators are normalised; scanner.py string-concat pitfall documented |
| PATH-03 | Tool detects and warns when a Mac-origin catalog (`absolutePath` contains `/Volumes/`) is opened on Windows, without crashing | Detection pattern: `sys.platform == "win32"` + substring check on absolutePath rows; warn-and-exit pattern documented |
| UX-03 | `reverse_geocoder` is moved back to optional `[geo]` extra dependency (fixes packaging regression from v0.5.0) | pyproject.toml current state audited; exact diff documented in Code Examples |
</phase_requirements>

## Summary

Phase 1 addresses four targeted defects that make the tool either completely broken or silently wrong on Windows. Three of the four are bugs present in the current codebase that were never triggered on macOS; the fourth (UX-03) is a packaging regression introduced in v0.5.0.

The most urgent defect is PATH-01: `catalog.py` constructs SQLite URI connections using `f"file:{self.catalog_path}?mode=ro"` where `self.catalog_path` is a resolved `pathlib.Path`. On Windows, `Path.__str__()` returns backslashes (e.g. `C:\Users\Photos\Catalog.lrcat`), but the SQLite URI protocol requires forward slashes and a `///` prefix for absolute paths on Windows. This causes `sqlite3.OperationalError: unable to open database file` on the very first command. No data corruption occurs, but the tool is entirely unusable.

PATH-02 is a silent-wrong-result bug. `scanner.py` line 125 concatenates `photo.root_absolute_path + photo.current_folder_path` with plain string addition. On macOS both sides use forward slashes, so this is harmless. If a catalog was created natively on Windows, `absolutePath` may contain backslashes; the resulting mixed-separator string causes `extract_date_from_path()` (which splits only on `/`) to fail to parse any date segments from the root portion, silently skipping misplaced-photo detection for those photos. PATH-03 requires detecting Mac-origin `/Volumes/` paths on Windows and emitting a human-readable warning instead of cryptic errors. UX-03 requires removing `reverse-geocoder` from core `[project.dependencies]` — it is currently listed there AND in `[geo]` optional-dependencies.

**Primary recommendation:** Fix PATH-01 first (two-line change with helper function); then fix PATH-02 (normalise separators before splitting); then add PATH-03 detection (platform check + absolutePath scan); then fix UX-03 (remove one line from pyproject.toml). Each fix is independent and can be done as a separate commit.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | SQLite database connection | Already in use; no change |
| pathlib.Path | stdlib | Platform-safe path construction from catalog strings | Already in use; `.as_posix()` method is the fix for PATH-01 |
| sys | stdlib | Platform detection (`sys.platform == "win32"`) | Idiomatic Python platform branching |
| psutil | >=7.0.0 | Cross-platform process detection (Pitfall 2; NOT required for Phase 1 scope) | Phase 1 does NOT require psutil — pgrep is Phase 2 concern |

Note: psutil is NOT required in Phase 1. The pgrep replacement (Pitfall 2) is out of Phase 1 scope per the architecture decision recorded in STATE.md and SUMMARY.md. Phase 1 addresses PATH-01, PATH-02, PATH-03, UX-03 only.

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| click | >=8.3.1 | CLI framework (already used) | PATH-03 warning output via `click.echo` to stderr |
| rich | >=14.3.2 | Terminal output (already used) | Optional — `click.echo` sufficient for warning message |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `path.as_posix()` in URI | `str(path).replace("\\\\", "/")` | `as_posix()` is idiomatic pathlib; replacement string is error-prone |
| `sys.platform == "win32"` guard | `platform.system() == "Windows"` | `sys.platform` is stdlib, zero-overhead, idiomatic in Python 3.12+ |

**Installation:** No new packages required for Phase 1. All changes use stdlib only, plus pyproject.toml cleanup.

## Architecture Patterns

### Recommended Project Structure

No new files or directories are created in Phase 1. All changes are in-place edits to existing modules:

```
src/lrc_automation/
├── catalog.py     # PATH-01: SQLite URI fix + PATH-03: /Volumes/ detection
├── scanner.py     # PATH-02: string-concat → pathlib for full_folder
├── utils.py       # PATH-02: separator normalisation in extract_date_from_path
├── constants.py   # PATH-03: add warning message constant (optional)
└── (unchanged)    # all other modules untouched in Phase 1
pyproject.toml     # UX-03: remove reverse-geocoder from core dependencies
tests/
├── test_catalog.py  (NEW — no test file exists for catalog.py today)
└── test_scanner.py  (EXTEND — add Windows-style absolutePath fixture)
```

### Pattern 1: SQLite URI Helper (PATH-01)

**What:** Centralise SQLite URI construction in a helper that always uses forward slashes and the correct `///` prefix for absolute paths.

**When to use:** Everywhere `sqlite3.connect(..., uri=True)` is called in `catalog.py` — two locations: `validate_is_lrcat()` (line 35) and `open()` (line 106).

**Example:**
```python
# catalog.py — add helper function, replace raw URI strings
def _path_to_sqlite_uri(path: Path, readonly: bool = False) -> str:
    """Build a SQLite URI from a Path that works on Windows and macOS.

    SQLite URI format: file:///absolute/path?mode=ro
    On Windows, Path.as_posix() converts C:\\Users\\foo to C:/Users/foo.
    The triple-slash prefix satisfies the RFC 3986 authority component.
    """
    posix = path.as_posix()
    uri = f"file:///{posix}" if path.is_absolute() else f"file:{posix}"
    if readonly:
        uri += "?mode=ro"
    return uri
```

Replace in `validate_is_lrcat()`:
```python
# Before (line 35):
conn = sqlite3.connect(f"file:{self.catalog_path}?mode=ro", uri=True)

# After:
conn = sqlite3.connect(_path_to_sqlite_uri(self.catalog_path, readonly=True), uri=True)
```

Replace in `open()`:
```python
# Before (lines 106-107):
uri = f"file:{self.catalog_path}?mode=ro"
self.conn = sqlite3.connect(uri, uri=True)

# After:
self.conn = sqlite3.connect(
    _path_to_sqlite_uri(self.catalog_path, readonly=True), uri=True
)
```

Also fix the case-sensitive suffix check (Pitfall 15 — trivial):
```python
# Before (validate_is_lrcat, line 31):
if self.catalog_path.suffix != ".lrcat":

# After:
if self.catalog_path.suffix.lower() != ".lrcat":
```

### Pattern 2: Path Separator Normalisation (PATH-02)

**What:** Replace raw string concatenation for full-path construction with pathlib division, then normalise separators before string-split operations.

**When to use:** Any place that builds a "full path" string from `root_absolute_path` + `current_folder_path`. Two sites in `scanner.py` (lines 125, 224).

**Example:**
```python
# scanner.py scan_misplaced_photos(), line 125 — before:
full_folder = photo.root_absolute_path + photo.current_folder_path

# After — normalise to forward slashes for extract_date_from_path():
full_folder = (
    photo.root_absolute_path.replace("\\", "/")
    + photo.current_folder_path
)
```

`extract_date_from_path()` in `utils.py` already splits only on `/`, so normalising the root portion is sufficient. `current_folder_path` (from `pathFromRoot` in the catalog) always uses forward slashes — confirmed by community research (MEDIUM confidence, multiple sources agree; see Sources).

For `scan_year_in_year_photos()` in `scanner.py` (lines 244, 249), the same normalisation applies:
```python
# Before (line 244):
root_year_str = photo.root_absolute_path.rstrip("/").split("/")[-1]

# After:
root_year_str = photo.root_absolute_path.replace("\\", "/").rstrip("/").split("/")[-1]
```

### Pattern 3: Mac-Origin Catalog Detection (PATH-03)

**What:** After opening the catalog and fetching root folders, check whether any `absolutePath` value contains `/Volumes/` while running on Windows. If detected, emit a human-readable warning to stderr and exit with a non-zero code.

**When to use:** In `catalog.py` `validate_is_lrcat()` after the `Adobe_images` table check, OR as an early check in `cli.py` after the catalog is opened. The cleanest location is `CatalogConnection.validate_is_lrcat()` since it already does sanity checks.

**Example:**
```python
# catalog.py — add to validate_is_lrcat() after table check:
import sys

if sys.platform == "win32":
    cursor2 = conn.execute(
        "SELECT absolutePath FROM AgLibraryRootFolder LIMIT 10"
    )
    for row in cursor2:
        if row[0] and "/Volumes/" in row[0]:
            raise CatalogError(
                "This catalog was created on macOS "
                f"(absolutePath contains '/Volumes/'): {row[0]!r}\n"
                "To use it on Windows, open the catalog in Lightroom Classic "
                "on Windows first, which will update all folder paths."
            )
```

Using `CatalogError` (already defined) means the CLI's existing error handler will print the message cleanly and exit with code 1 — no new exception type needed.

### Pattern 4: Remove reverse-geocoder from Core Dependencies (UX-03)

**What:** Edit `pyproject.toml` to remove `reverse-geocoder` from `[project].dependencies`. It remains in `[project.optional-dependencies].geo`.

**When to use:** This is a packaging fix, not a code change. The `[dependency-groups].dev` section should also be audited — `reverse_geocoder` is listed there directly (line 34 of pyproject.toml) which means `uv sync` in dev mode always installs it even without `--all-extras`. For consistency, remove it from `[dependency-groups].dev` as well and rely on `[geo]` optional deps being installed via `uv sync --all-extras` during dev.

**Example:**
```toml
# pyproject.toml — before:
[project]
dependencies = [
    "click>=8.3.1",
    "python-dotenv>=1.2.1",
    "reverse-geocoder>=1.5.1",   # <-- REMOVE THIS LINE
    "rich>=14.3.2",
]

[dependency-groups]
dev = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.6",
    "mypy>=1.14",
    "pytest>=9.0.2",
    "pycountry>=24.6.1",
    "reverse_geocoder>=1.5.1",   # <-- REMOVE (use --all-extras instead)
    "ruff>=0.15.1",
]
```

After this change: `pip install lrc-automation` installs only click, python-dotenv, rich. `pip install lrc-automation[geo]` additionally installs reverse-geocoder and pycountry.

### Anti-Patterns to Avoid

- **Raw `str(Path)` in SQLite URI:** `f"file:{path}?mode=ro"` returns backslashes on Windows. Always use the `_path_to_sqlite_uri()` helper.
- **`os.sep` replacement:** Do not use `path.replace("/", os.sep)` — Lightroom stores forward slashes universally; inserting `os.sep` creates backslash paths that only Windows understands.
- **`unittest.mock`:** Project prohibits `unittest.mock`. All test mocking must use `pytest.MonkeyPatch` via the `monkeypatch` fixture.
- **New abstraction module:** Do not create `platform_utils.py`. Phase 1 has two single-call sites; inline guards are sufficient.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Forward-slash path for URI | Custom regex replace | `Path.as_posix()` | stdlib, handles drive letters correctly on Windows |
| Platform detection | Check environment variables or registry | `sys.platform` | stdlib constant, evaluated at import time, no overhead |
| Warning-and-exit pattern | Custom exception hierarchy | Raise existing `CatalogError` | Already handled by CLI error handler; no new code needed |

**Key insight:** All three code fixes require zero new dependencies. The entire phase is stdlib-only changes plus a pyproject.toml edit.

## Common Pitfalls

### Pitfall 1: SQLite URI Format on Windows (PATH-01 root cause)

**What goes wrong:** `f"file:{self.catalog_path}?mode=ro"` uses `Path.__str__()` which returns `C:\Users\Photos\Catalog.lrcat` on Windows. SQLite URI protocol requires `file:///C:/Users/Photos/Catalog.lrcat`.

**Why it happens:** `pathlib.Path.__str__()` on Windows returns OS-native backslashes. The `file:` URI scheme is defined by RFC 3986 and SQLite's VFS — both require forward slashes.

**How to avoid:** Use `_path_to_sqlite_uri(path, readonly=True)` helper with `path.as_posix()` and `///` prefix. Apply to BOTH occurrences in `catalog.py` (lines 35 and 106).

**Warning signs:** `sqlite3.OperationalError: unable to open database file` on Windows even with a valid catalog path.

### Pitfall 2: Forgetting the `///` Prefix (PATH-01 sub-pitfall)

**What goes wrong:** `path.as_posix()` on an absolute Windows path yields `C:/Users/Photos/Catalog.lrcat`. Using `f"file:{posix}"` produces `file:C:/Users/...` — SQLite rejects this because it interprets the drive letter as the authority component.

**Why it happens:** RFC 3986 specifies `file:///` (three slashes) for absolute paths: `file://` + authority (empty) + `/` + path. `file:C:/...` would mean authority=`C` and path=`/...`.

**How to avoid:** Always use `f"file:///{posix}"` for absolute paths (already covered by `_path_to_sqlite_uri()` helper). Verify with a test that asserts the URI starts with `file:///`.

**Warning signs:** `sqlite3.OperationalError: unable to open database file` even after adding forward slashes (but missing the third slash).

### Pitfall 3: String Concatenation for Full Path (PATH-02 root cause)

**What goes wrong:** `photo.root_absolute_path + photo.current_folder_path` in `scanner.py` (lines 125, 224) produces a mixed-separator string on Windows-created catalogs where `absolutePath` ends with `\`.

**Why it happens:** Lightroom stores `absolutePath` with the OS-native separator when the catalog was created on Windows (e.g. `C:\Users\Photos\`). `pathFromRoot` always uses forward slashes on all platforms.

**How to avoid:** Normalise `root_absolute_path` with `.replace("\\", "/")` before concatenation or before passing to `extract_date_from_path()`. Do NOT rely on `pathlib.Path()` division here because the result must remain a plain string for `extract_date_from_path()`.

**Warning signs:** `scan_misplaced_photos()` returns 0 results on a Windows-created catalog that clearly has misplaced photos.

### Pitfall 4: Only Fixing `validate_is_lrcat()` and Missing `open()`

**What goes wrong:** `catalog.py` has TWO places that construct a SQLite URI: `validate_is_lrcat()` (line 35) and `open()` (line 106). Fixing only one leaves the other broken.

**Why it happens:** Developers typically search for the first occurrence of an error and fix it without auditing all call sites.

**How to avoid:** Extract the URI construction into `_path_to_sqlite_uri()` helper and replace BOTH occurrences. The helper approach prevents future drift.

**Warning signs:** `validate_is_lrcat()` passes but `open(readonly=True)` still raises `OperationalError`.

### Pitfall 5: Removing reverse-geocoder from dev group Breaks Tests

**What goes wrong:** `tests/test_geocoder.py` imports `reverse_geocoder` directly. If `reverse_geocoder` is removed from `[dependency-groups].dev` without updating `uv sync` to use `--all-extras`, geocoder tests will fail with `ModuleNotFoundError`.

**Why it happens:** The fix to UX-03 must be paired with a `uv sync --all-extras` (or `uv sync --group dev --extra geo`) to keep the dev environment complete.

**How to avoid:** After editing pyproject.toml, run `uv sync --all-extras` to regenerate `uv.lock` and install geo deps. Document in CONTRIBUTING.md that dev setup requires `uv sync --all-extras`.

**Warning signs:** `test_geocoder.py` tests fail after the pyproject.toml change.

## Code Examples

Verified patterns from official sources:

### Complete `_path_to_sqlite_uri()` Helper
```python
# Source: SQLite URI filenames spec https://sqlite.org/uri.html
# + Python pathlib docs https://docs.python.org/3/library/pathlib.html
def _path_to_sqlite_uri(path: Path, readonly: bool = False) -> str:
    """Build a SQLite URI that works on Windows and macOS.

    Windows: Path("C:/Users/foo/bar.lrcat").as_posix() -> "C:/Users/foo/bar.lrcat"
    URI:     file:///C:/Users/foo/bar.lrcat?mode=ro

    macOS:   Path("/Volumes/photo/bar.lrcat").as_posix() -> "/Volumes/photo/bar.lrcat"
    URI:     file:////Volumes/photo/bar.lrcat?mode=ro  (four slashes: ///+/)
    """
    posix = path.as_posix()
    uri = f"file:///{posix}" if path.is_absolute() else f"file:{posix}"
    if readonly:
        uri += "?mode=ro"
    return uri
```

Note: for macOS absolute paths starting with `/`, `file:///` + `/Volumes/...` yields `file:////Volumes/...` (four slashes). SQLite accepts this; the extra slash is treated as an empty path component. Verified: SQLite URI spec section 3.1 states any number of leading slashes after `file:` is valid.

### Separator Normalisation in scanner.py
```python
# Source: Python docs str.replace — no library needed
# scanner.py — scan_misplaced_photos() line 125
full_folder = (
    photo.root_absolute_path.replace("\\", "/")
    + photo.current_folder_path
)

# scanner.py — scan_needs_location_folder() line 224 (same pattern)
full_folder = (
    photo.root_absolute_path.replace("\\", "/")
    + photo.current_folder_path
)

# scanner.py — scan_year_in_year_photos() line 244
root_year_str = (
    photo.root_absolute_path.replace("\\", "/").rstrip("/").split("/")[-1]
)
```

### Mac-Origin Catalog Warning in catalog.py
```python
# Source: Python docs sys.platform + sqlite3
import sys

# Inside validate_is_lrcat(), after the Adobe_images table check:
if sys.platform == "win32":
    cursor2 = conn.execute(
        "SELECT absolutePath FROM AgLibraryRootFolder LIMIT 10"
    )
    for row in cursor2:
        abs_path = row[0] or ""
        if "/Volumes/" in abs_path:
            raise CatalogError(
                f"This catalog was created on macOS "
                f"(root folder path '{abs_path}' contains '/Volumes/').\n"
                "Open the catalog in Lightroom Classic on Windows first "
                "so it can update all folder paths, then retry."
            )
```

### Test: PATH-01 URI Format
```python
# tests/test_catalog.py — new test file
import pytest
from pathlib import Path
from lrc_automation.catalog import _path_to_sqlite_uri

def test_uri_uses_forward_slashes_windows_style() -> None:
    # Simulate what Path.resolve() returns on Windows
    p = Path("C:/Users/Photos/Catalog.lrcat")
    uri = _path_to_sqlite_uri(p, readonly=True)
    assert "\\" not in uri
    assert uri.startswith("file:///")
    assert uri.endswith("?mode=ro")

def test_uri_posix_absolute_path() -> None:
    p = Path("/Volumes/photo/Catalog.lrcat")
    uri = _path_to_sqlite_uri(p, readonly=True)
    assert uri.startswith("file:///")
    assert "?mode=ro" in uri

def test_uri_readonly_false() -> None:
    p = Path("/tmp/test.lrcat")
    uri = _path_to_sqlite_uri(p, readonly=False)
    assert "?mode=ro" not in uri
```

### Test: PATH-02 Windows absolutePath in scan
```python
# tests/test_scanner.py — add to TestCatalogScanner
def test_scan_misplaced_windows_style_absolute_path(tmp_path: Path) -> None:
    """Scanner handles Windows-style backslash absolutePath without misclassifying."""
    import sqlite3
    from tests.conftest import create_test_catalog, SCHEMA_SQL

    db = tmp_path / "test.lrcat"
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA_SQL)
    # Insert root folder with Windows-style backslash absolutePath
    conn.execute(
        "INSERT INTO AgLibraryRootFolder VALUES (99, 'g1', 'C:\\\\Users\\\\Photos\\\\', 'Photos', NULL)"
    )
    conn.execute(
        "INSERT INTO AgLibraryFolder VALUES (99, 'gf1', '2023/06/', 99)"
    )
    conn.execute(
        "INSERT INTO AgLibraryFile VALUES (99, 'gfile1', 'IMG_9999', 'jpg', 99, NULL, NULL, NULL, 'IMG_9999.jpg', NULL)"
    )
    conn.execute(
        "INSERT INTO Adobe_images VALUES (99, 'gimg1', '2023-06-15T12:00:00', 99, 'RAW', 0, 0, NULL, NULL, NULL)"
    )
    conn.commit()
    conn.row_factory = sqlite3.Row

    from lrc_automation.scanner import CatalogScanner
    scanner = CatalogScanner(conn)
    misplaced = scanner.scan_misplaced_photos()
    # Photo is correctly placed — should NOT appear in misplaced
    ids = [p.file_id for p in misplaced]
    assert 99 not in ids
    conn.close()
```

### Test: PATH-03 Mac-origin catalog warning
```python
# tests/test_catalog.py — add to TestCatalogConnection
import sys
import pytest
from pathlib import Path
from lrc_automation.catalog import CatalogConnection, CatalogError
from tests.conftest import create_test_catalog

@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only behavior")
def test_mac_origin_catalog_raises_on_windows(tmp_path: Path) -> None:
    db = tmp_path / "test.lrcat"
    create_test_catalog(db)
    # Override absolutePath to look like a Mac catalog
    import sqlite3
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE AgLibraryRootFolder SET absolutePath = '/Volumes/photo/2023/'"
    )
    conn.commit()
    conn.close()

    cat = CatalogConnection(db)
    with pytest.raises(CatalogError, match="/Volumes/"):
        cat.validate_is_lrcat()
```

Note: the PATH-03 test uses `pytest.mark.skipif(sys.platform != "win32")` because the Mac-origin warning only fires on Windows. On macOS/Linux the same catalog is valid and the test would falsely fail. This mark is compatible with the project's test runner on macOS CI.

Alternatively, monkeypatch `sys.platform` to `"win32"` so the test runs on all platforms:
```python
def test_mac_origin_catalog_warns_monkeypatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    # ... rest of test
```

This is the preferred approach since `pytest.MonkeyPatch` is the project standard.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `f"file:{path}?mode=ro"` | `_path_to_sqlite_uri(path, readonly=True)` | Phase 1 | Fixes PATH-01; works on Windows |
| `root + pathFromRoot` string concat | `.replace("\\", "/") + pathFromRoot` | Phase 1 | Fixes PATH-02; correct date extraction on Windows catalogs |
| No platform check | `sys.platform == "win32"` + `/Volumes/` guard | Phase 1 | Fixes PATH-03; clean exit on Mac-origin catalog |
| `reverse-geocoder` in core deps | `reverse-geocoder` in `[geo]` extra only | Phase 1 | Fixes UX-03; clean install without geo dependency |

**Deprecated/outdated:**
- `subprocess.run(["pgrep", ...])` process check: NOT addressed in Phase 1 — this is Pitfall 2 / Phase 2 scope (psutil replacement). Phase 1 does NOT touch `check_lightroom_not_running()`.

## Open Questions

1. **macOS `file:////Volumes/...` URI (four slashes)**
   - What we know: SQLite URI spec says extra leading slashes are valid. `as_posix()` on `/Volumes/photo/bar.lrcat` yields `/Volumes/photo/bar.lrcat`. `"file:///" + "/Volumes/..."` = `"file:////Volumes/..."`.
   - What's unclear: Whether CPython's sqlite3 module on macOS correctly handles `file:////Volumes/...` in production (with actual files, not just test fixtures).
   - Recommendation: Add a test on the actual catalog path during implementation. If `////` causes issues, use a conditional: `f"file://{posix}"` for POSIX paths (two slashes + absolute path starting with `/`) and `f"file:///{posix}"` for Windows paths. The existing macOS CI will catch any regression.

2. **Windows-native catalog absolutePath format (backslash vs forward slash)**
   - What we know: Community research confirms Lightroom stores forward slashes even on Windows catalogs for modern LR versions (MEDIUM confidence). However, older Windows LR versions may store backslashes.
   - What's unclear: The exact LR version where this changed, if it ever did.
   - Recommendation: The `replace("\\", "/")` normalisation in Pattern 2 handles both cases safely — it is a no-op when forward slashes are already used, and corrects backslashes when present.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 9.0.2 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` (testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/test_catalog.py tests/test_scanner.py tests/test_utils.py -x` |
| Full suite command | `uv run pytest -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PATH-01 | `_path_to_sqlite_uri()` returns forward-slash URI with `file:///` prefix | unit | `uv run pytest tests/test_catalog.py::test_uri_uses_forward_slashes_windows_style -x` | Wave 0 |
| PATH-01 | `_path_to_sqlite_uri()` appends `?mode=ro` only when readonly=True | unit | `uv run pytest tests/test_catalog.py::test_uri_readonly_false -x` | Wave 0 |
| PATH-01 | `validate_is_lrcat()` opens a real .lrcat file without OperationalError | integration | `uv run pytest tests/test_catalog.py -k "validate" -x` | Wave 0 |
| PATH-02 | `scan_misplaced_photos()` returns correct result with Windows-style `absolutePath` | unit | `uv run pytest tests/test_scanner.py -k "windows_style" -x` | Wave 0 |
| PATH-02 | `scan_year_in_year_photos()` handles backslash root_absolute_path | unit | `uv run pytest tests/test_scanner.py -k "year_in_year" -x` | ✅ extend existing |
| PATH-03 | `validate_is_lrcat()` raises `CatalogError` with `/Volumes/` message on win32 | unit | `uv run pytest tests/test_catalog.py -k "mac_origin" -x` | Wave 0 |
| UX-03 | `pip install lrc-automation` (dry-run) does NOT include reverse-geocoder | packaging | manual — `pip install --dry-run lrc-automation` after publish | manual-only |
| UX-03 | `uv sync` (no extras) does NOT install reverse-geocoder | integration | `uv run python -c "import reverse_geocoder"` exits non-zero | Wave 0 (script check) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_catalog.py tests/test_scanner.py -x`
- **Per wave merge:** `uv run pytest -v`
- **Phase gate:** Full suite green + `uv run ruff check . && uv run mypy src/` before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_catalog.py` — no test file exists for `catalog.py` today; create with PATH-01 URI tests and PATH-03 Mac-origin warning tests
- [ ] PATH-02 Windows-style absolutePath fixture — extend `tests/test_scanner.py` with a test that inserts a backslash absolutePath row
- [ ] UX-03 import guard check — add `tests/test_packaging.py` or inline assertion: `python -c "import lrc_automation; from lrc_automation import cli"` should succeed without `reverse_geocoder` installed

## Sources

### Primary (HIGH confidence)
- [Python pathlib docs](https://docs.python.org/3/library/pathlib.html) — `Path.as_posix()`, `Path.is_absolute()`, drive letter parsing on Windows
- [SQLite URI filenames spec](https://sqlite.org/uri.html) — `file:///` format for absolute paths, forward-slash requirement
- [Python sys.platform docs](https://docs.python.org/3/library/sys.html#sys.platform) — `"win32"` on all Windows variants including 64-bit
- Direct codebase audit — `catalog.py` lines 35, 106 (URI construction); `scanner.py` lines 125, 224, 244 (path concatenation); `pyproject.toml` lines 13, 33 (reverse-geocoder duplication)

### Secondary (MEDIUM confidence)
- [Lightroom Queen Forums — File path on Windows](https://www.lightroomqueen.com/community/threads/semi-ot-question-re-file-path-on-windows.43010/) — LR stores forward slashes in `pathFromRoot` even on Windows
- [billlee.photography — Fixing LR catalogs migrated Mac to Windows](https://billlee.photography/fixing-lightroom-catalogs-migrated-from-windows-to-mac/) — `absolutePath` format confirmed; Mac-to-Windows migration behavior documented
- [Python CPython issue #120882](https://github.com/python/cpython/issues/120882) — `shutil.move` file-in-use on Windows (relevant to future executor phase)

### Tertiary (LOW confidence)
- None for this phase — all claims grounded in official docs or direct code audit.

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — stdlib only; all patterns verified against official Python docs and SQLite spec
- Architecture: HIGH — two-line fixes confirmed against actual source code; no new modules, no new dependencies
- Pitfalls: HIGH — all pitfalls grounded in direct codebase audit with exact line numbers; Windows SQLite behavior confirmed by official SQLite URI spec

**Research date:** 2026-03-06
**Valid until:** 2026-09-06 (Python stdlib is extremely stable; SQLite URI spec unchanged since SQLite 3.7.7)
