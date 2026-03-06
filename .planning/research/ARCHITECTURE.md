# Architecture Patterns: Multiplatform Support

**Domain:** Python CLI tool — Lightroom Classic catalog automation
**Milestone:** v0.6.0 Multiplatform (Mac + Windows + Linux)
**Researched:** 2026-03-06
**Overall confidence:** HIGH (verified against psutil docs, official Lightroom catalog documentation, Python pathlib docs)

---

## Executive Summary

Adding Windows and Linux support to lrc-automation touches four discrete concerns:
process detection, path construction from catalog strings, AppleDouble cleanup scoping,
and default catalog path discovery. Each concern has a natural owner in the existing
module structure. The recommended approach avoids a new abstraction layer in favor of
targeted changes to existing modules — the codebase is not large enough to justify a
full platform abstraction.

The highest-risk change is process detection: the current `pgrep` subprocess call silently
degrades (`FileNotFoundError` swallowed) on Windows rather than raising a meaningful error.
psutil replaces it with a genuine cross-platform check. Path construction from `absolutePath`
is already safe because Lightroom stores forward slashes even on Windows (verified from
community catalog reverse-engineering).

---

## Recommended Architecture

### Component Boundaries (unchanged + additions)

| Component | Responsibility | Modified for v0.6.0? |
|-----------|---------------|----------------------|
| `catalog.py` | Connection, safety checks, backup | YES — process detection rewrite |
| `constants.py` | Process names, lock suffix, layout patterns | YES — add Windows process name + default paths dict |
| `executor.py` | Disk moves, AppleDouble cleanup, empty-dir removal | YES — guard AppleDouble with `sys.platform` |
| `validators.py` | Integrity checks, disk audit | MAYBE — path construction already correct via pathlib |
| `scanner.py` | Query + build PhotoRecord list | NO — pathlib already handles forward-slash paths |
| `models.py` | Dataclasses for records and reports | NO |
| `cli.py` | Entry point, command wiring | MINOR — default catalog path hint per OS |
| `utils.py` | Date parsing, path helpers | NO |
| **No new module** | Platform abstraction | NOT RECOMMENDED — see rationale below |

### Why Not a New `platform.py` Module

A `platform.py` shim is only warranted when the same platform concern is referenced from
multiple callers. In this codebase:
- Process detection is called from exactly one place: `CatalogConnection.check_lightroom_not_running()`
- AppleDouble logic is called from exactly one place: `executor.py:_is_effectively_empty()` and `_delete_apple_double_files()`
- Default catalog path is referenced from exactly one place: `cli.py`

Indirection through a platform module would add a layer with no concrete benefit at this
scale. Keep each concern in its natural home.

---

## Integration Points: New vs Modified

### 1. Process Detection — `catalog.py` (MODIFIED, lines 57-71)

**Current code (macOS-only):**
```python
result = subprocess.run(
    ["pgrep", "-f", LR_PROCESS_NAME],
    capture_output=True, text=True, timeout=5,
)
```

**Recommended replacement — psutil:**
```python
import psutil

def _lightroom_running() -> bool:
    """Return True if any Lightroom Classic process is running."""
    names = {LR_PROCESS_NAME_MACOS, LR_PROCESS_NAME_WIN}
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] in names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False
```

psutil's `process_iter(attrs)` is the standard cross-platform API — it works identically
on Windows, macOS, and Linux. The attrs argument pre-fetches only the requested fields,
which avoids `AccessDenied` errors on fields the tool doesn't need (HIGH confidence —
verified against psutil official docs).

**Key behavioral difference:** The current code raises `LightroomRunningError` on returncode 0
and silently passes on `FileNotFoundError` (i.e., no detection on Windows). With psutil the
check always runs and always produces a boolean result. Silent pass-through is eliminated.

**subprocess import:** Remove after this change — it is only used for pgrep.

---

### 2. Process Name Constants — `constants.py` (MODIFIED)

**Current:**
```python
# Lightroom process name on macOS
LR_PROCESS_NAME = "Adobe Lightroom Classic"
```

**Recommended:**
```python
# Lightroom process names per platform (as reported by psutil proc.info["name"])
LR_PROCESS_NAME_MACOS = "Adobe Lightroom Classic"
LR_PROCESS_NAME_WIN   = "Lightroom.exe"
LR_PROCESS_NAME_LINUX = "Lightroom"          # hypothetical; LR does not run natively on Linux

# Default catalog paths per platform (used only for help text / discovery)
DEFAULT_CATALOG_PATHS: dict[str, str] = {
    "darwin":  "~/Pictures/Lightroom/Lightroom Catalog.lrcat",
    "win32":   "~/Pictures/Lightroom/Lightroom Catalog.lrcat",
    "linux":   "",   # not applicable
}
```

The old `LR_PROCESS_NAME` should remain as a deprecated alias pointing to the macOS value
so existing tests that reference it do not break before they are updated.

**Confidence:** MEDIUM — `Lightroom.exe` confirmed from file.net process database; the
process name as reported by psutil `proc.info["name"]` on Windows matches the executable
filename without path.

---

### 3. Path Construction from `absolutePath` — NO CODE CHANGE REQUIRED

**Finding (HIGH confidence, verified from Lightroom catalog community research):**
Lightroom Classic stores `absolutePath` in `AgLibraryRootFolder` using **forward slashes on
all platforms**, including Windows. Example Windows value: `C:/Users/Photos/Lightroom/`.
The `pathFromRoot` column in `AgLibraryFolder` also uses forward slashes.

**Why pathlib is already safe:**
`Path("C:/Users/Photos/Lightroom/") / "2023/12/"` — on Windows, `pathlib.Path` treats the
leading `C:/` as a drive specifier and constructs a valid `WindowsPath`. The existing code
that does `Path(root_absolute_path) / path_from_root / filename` throughout
`executor.py`, `validators.py`, and `models.py` is already correct.

**One edge case to guard:** If a catalog was originally created on macOS and copied to
Windows, `absolutePath` may contain a POSIX path like `/Volumes/photo/2023/`. `Path()` on
Windows would interpret this as a relative UNC-like path, not a Windows absolute path. This
is a cross-OS catalog migration scenario, not a native Windows catalog scenario — document
as unsupported in v0.6.0 scope.

**validators.py path construction (line 171):**
```python
root_year_str = root_absolute_path.rstrip("/").split("/")[-1]
```
This string split on `/` is safe because Lightroom always uses forward slashes. No change
needed.

---

### 4. AppleDouble Cleanup — `executor.py` (MODIFIED)

**Current:** `_is_effectively_empty()` and `_delete_apple_double_files()` treat all `._*`
files as AppleDouble metadata and skip/delete them unconditionally.

**Recommended:** Guard with `sys.platform` check, not a boolean flag or class hierarchy.

```python
import sys

_IS_MACOS = sys.platform == "darwin"

def _is_effectively_empty(directory: Path) -> bool:
    for entry in directory.iterdir():
        if _IS_MACOS and entry.name.startswith("._"):
            continue  # AppleDouble metadata — macOS only
        return False
    return True

def _delete_apple_double_files(directory: Path) -> None:
    if not _IS_MACOS:
        return  # No-op on non-macOS; ._* files do not exist on native NTFS/ext4
    for entry in directory.iterdir():
        if entry.name.startswith("._") and entry.is_file():
            ...
```

**Rationale for `sys.platform` over a flag parameter:**
- AppleDouble files are a macOS filesystem artifact — they do not exist on NTFS or ext4
- Making it a flag would require plumbing through CatalogConnection → CLI, adding complexity
  with no practical benefit
- `sys.platform` evaluated at module-load time produces a single module-level boolean with
  zero overhead
- The `cleanup` CLI command docstring currently mentions "macOS ._* metadata files" — update
  to "macOS AppleDouble (._*) files" and add "(skipped on non-macOS)" note

**cli.py cleanup command help text** also references AppleDouble behavior — minor wording
update only, no logic change.

---

### 5. Default Catalog Path Discovery — `cli.py` (MINOR)

The `--catalog` option is already required. Default path discovery is optional UX polish.

**Recommended approach:** Add a `_default_catalog_path()` helper that returns a platform-
specific hint for the `--catalog` help string or for auto-discovery fallback:

```python
import sys
from pathlib import Path

def _default_catalog_path() -> Path | None:
    """Return platform default LR Classic catalog location, or None."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Pictures" / "Lightroom" / "Lightroom Catalog.lrcat"
    if sys.platform == "win32":
        return home / "Pictures" / "Lightroom" / "Lightroom Catalog.lrcat"
    return None
```

**Verified:** Both macOS and Windows default to `~/Pictures/Lightroom/Lightroom Catalog.lrcat`
(confirmed from Adobe helpx.adobe.com preference file locations documentation — HIGH confidence).

This can optionally become the `default` value on the `--catalog` Click option in v0.6.0,
removing `required=True` when the default exists and the file is found.

---

### 6. Dependencies — `pyproject.toml` (MODIFIED)

Add psutil as a core (non-optional) dependency:
```toml
[project]
dependencies = [
    "psutil>=5.9",   # cross-platform process detection
    ...
]
```

psutil is actively maintained, ships pre-compiled wheels for Windows/macOS/Linux on PyPI,
and adds no meaningful install size overhead. It does not need to be an optional extra —
process detection is a core safety invariant, not an optional feature.

**Note:** Remove the `subprocess` import from `catalog.py` after the psutil migration.

---

## Data Flow — Path Construction (annotated)

```
AgLibraryRootFolder.absolutePath   (always forward-slash, e.g. "C:/Photos/" or "/Volumes/photo/")
        +
AgLibraryFolder.pathFromRoot       (always forward-slash, e.g. "2023/12/")
        +
AgLibraryFile.baseName + extension (e.g. "IMG_1234.jpg")
        |
        v
Path(absolutePath) / pathFromRoot / f"{baseName}.{extension}"
        |
        v  [pathlib resolves drive letters on Windows, POSIX paths on macOS/Linux]
PhotoRecord.full_path              (concrete Path object — platform-native)
```

No changes needed to this flow. pathlib already bridges the forward-slash catalog string to
the native filesystem representation on each platform.

---

## Suggested Build Order

The changes are low-coupling enough that most can be done in parallel, but the ordering
below minimizes merge conflicts and provides fast test feedback.

### Step 1 — Constants (no functional impact, pure addition)
Modify `constants.py`:
- Add `LR_PROCESS_NAME_MACOS`, `LR_PROCESS_NAME_WIN`, `LR_PROCESS_NAME_LINUX`
- Add `DEFAULT_CATALOG_PATHS` dict
- Keep `LR_PROCESS_NAME` as alias (do not remove yet)
- Update any test that asserts on `LR_PROCESS_NAME` to use the new names

**Why first:** All other steps import from constants. Doing this first ensures
the constants exist when needed and avoids circular change ordering.

### Step 2 — psutil dependency (build infrastructure)
Update `pyproject.toml` to add psutil. Run `uv sync`. Confirm psutil imports cleanly.
Add a trivial smoke test: `import psutil; psutil.process_iter(["name"])` returns without error.

**Why second:** The process detection rewrite in Step 3 depends on psutil being installed.

### Step 3 — Process detection rewrite in `catalog.py`
- Remove `import subprocess`
- Add `import psutil`
- Replace `check_lightroom_not_running()` body with psutil-based implementation
- Update or replace tests that mock `subprocess.run` with tests that monkeypatch
  `psutil.process_iter` (use `monkeypatch.setattr`, never `unittest.mock`)

**Why third:** Self-contained, well-tested change. Failing tests immediately visible.
No other module touches this logic.

### Step 4 — AppleDouble guard in `executor.py`
- Add `_IS_MACOS = sys.platform == "darwin"` module-level constant
- Add guard to `_is_effectively_empty()` and `_delete_apple_double_files()`
- Update CLI docstring for `cleanup` command
- Tests: add a test that verifies `_is_effectively_empty()` treats `._file` as real content
  when `_IS_MACOS` is False (monkeypatch the module-level flag)

**Why fourth:** Isolated change with clear test strategy. No dependency on Steps 1-3.

### Step 5 — Default catalog path in `cli.py`
- Add `_default_catalog_path()` helper
- Optionally wire into `--catalog` Click option as a computed default
- Document platform-specific paths in `--help` output

**Why fifth:** UX improvement only. All safety-critical changes are already done.
Can be deferred to a separate PR if scope creep is a concern.

### Step 6 — CI matrix expansion
- Add `windows-latest` and `ubuntu-latest` to GitHub Actions OS matrix
- Add `python-version: ["3.12", "3.13"]` if not already present
- Verify psutil wheel availability in CI (it ships wheels for all three platforms)
- Mark any macOS-only tests with `pytest.mark.skipif(sys.platform != "darwin", ...)`

**Why last:** Requires all code changes to be complete and tests to pass locally first.
CI failures on new platforms surface any remaining implicit macOS assumptions.

---

## Patterns to Follow

### Pattern 1: sys.platform Module-Level Guard

**What:** Evaluate `sys.platform` once at module import time into a boolean constant.
Use that constant in logic rather than calling `sys.platform` inline.

**When:** When a behavior is binary by OS family (macOS vs. everything else), not
when it depends on runtime configuration.

```python
# executor.py (top of file)
import sys
_IS_MACOS = sys.platform == "darwin"

# in function body
if _IS_MACOS and entry.name.startswith("._"):
    continue
```

### Pattern 2: psutil process_iter with attrs

**What:** Always pass the `attrs` list to `process_iter()`. This pre-fetches only the
needed fields and avoids `AccessDenied` exceptions on fields like `cmdline` that
require elevated privileges on Windows.

**When:** Any process lookup. Never use `psutil.process_iter()` without `attrs`.

```python
for proc in psutil.process_iter(["name"]):
    try:
        if proc.info["name"] in target_names:
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass  # process exited or access denied — skip
```

### Pattern 3: Path(catalog_string) for absolutePath Values

**What:** Pass Lightroom's `absolutePath` string directly to `Path()`. Do not attempt
to detect or replace separators. Lightroom uses forward slashes universally; pathlib
handles them correctly on Windows.

**When:** Anywhere `absolutePath` or `pathFromRoot` is used to construct a disk path.

```python
# Correct — works on both Windows and macOS
full_path = Path(absolute_path) / path_from_root / filename

# Wrong — unnecessary string manipulation
full_path = Path(absolute_path.replace("/", os.sep)) / ...
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Subprocess for Process Detection

**What:** Calling `pgrep`, `tasklist`, `ps`, or any platform-specific shell utility
via subprocess.

**Why bad:** Silent failure on missing utility (`FileNotFoundError` swallowed), fragile
output parsing, process name matching varies by OS, elevated permission issues.

**Instead:** Use `psutil.process_iter(["name"])` — same API on all platforms.

### Anti-Pattern 2: os.sep for Catalog Path Construction

**What:** Using `os.sep` or `os.path.join` to construct paths from catalog strings,
or replacing `/` with `\` in `absolutePath` before passing to Path.

**Why bad:** Lightroom stores paths with forward slashes universally. Manually replacing
separators introduces double-replacement bugs and is unnecessary since pathlib handles
mixed separators correctly.

**Instead:** `Path(absolute_path) / path_from_root` — pathlib normalizes on construction.

### Anti-Pattern 3: unittest.mock for psutil

**What:** Using `unittest.mock.patch("psutil.process_iter")` in tests.

**Why bad:** Project coding standard explicitly prohibits `unittest.mock` — use
`pytest.MonkeyPatch` exclusively.

**Instead:**
```python
def test_lr_not_running_when_no_match(monkeypatch):
    def fake_iter(attrs):
        return iter([])
    monkeypatch.setattr("psutil.process_iter", fake_iter)
    # assert no exception raised
```

### Anti-Pattern 4: New Platform Abstraction Module

**What:** Creating a `platform_utils.py` or `platform_adapter.py` with a class hierarchy
or factory pattern for platform behaviors.

**Why bad:** Overkill for three single-call sites. Adds indirection that makes the code
harder to read without reducing duplication. The `sys.platform` checks are already
self-documenting when written inline or as a module-level boolean.

**Instead:** Direct `sys.platform == "darwin"` / `sys.platform == "win32"` guards in the
three modules that need them.

---

## Scalability Considerations

| Concern | Current (macOS only) | After v0.6.0 |
|---------|---------------------|--------------|
| Process detection | pgrep subprocess, silent fail on Windows | psutil, uniform API, raises on detection |
| Path handling | POSIX paths only | Forward-slash catalog strings work via pathlib on all platforms |
| AppleDouble cleanup | Always active | macOS only, no-op elsewhere |
| Default catalog path | Hardcoded macOS hint | Per-platform dict |
| CI coverage | macOS only | macOS + Windows + Linux matrix |

---

## Sources

- psutil official documentation: [https://psutil.readthedocs.io/](https://psutil.readthedocs.io/)
- psutil GitHub (giampaolo/psutil): [https://github.com/giampaolo/psutil](https://github.com/giampaolo/psutil) — HIGH confidence
- Adobe Lightroom Classic preference file locations: [https://helpx.adobe.com/lightroom-classic/kb/preference-file-and-other-file-locations.html](https://helpx.adobe.com/lightroom-classic/kb/preference-file-and-other-file-locations.html) — HIGH confidence
- Lightroom Classic catalog absolutePath format (Windows): Community reverse-engineering at [https://www.lightroomqueen.com/community/threads/semi-ot-question-re-file-path-on-windows.43010/](https://www.lightroomqueen.com/community/threads/semi-ot-question-re-file-path-on-windows.43010/) and [https://billlee.photography/fixing-lightroom-catalogs-migrated-from-windows-to-mac/](https://billlee.photography/fixing-lightroom-catalogs-migrated-from-windows-to-mac/) — MEDIUM confidence (community verified, consistent across multiple sources)
- lightroom.exe process name on Windows: [https://www.file.net/process/lightroom.exe.html](https://www.file.net/process/lightroom.exe.html) — MEDIUM confidence
- Python pathlib cross-platform behavior: [https://docs.python.org/3/library/pathlib.html](https://docs.python.org/3/library/pathlib.html) — HIGH confidence
- GitHub Actions matrix strategy: [https://codefresh.io/learn/github-actions/github-actions-matrix/](https://codefresh.io/learn/github-actions/github-actions-matrix/) — HIGH confidence
