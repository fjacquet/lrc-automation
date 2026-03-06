# Technology Stack

**Project:** lrc-automation — Windows/Mac/Linux multiplatform support (v0.6.0)
**Researched:** 2026-03-06
**Scope:** Cross-platform additions only. Existing stack (click, rich, sqlite3, pathlib, ruff, mypy, pytest, uv) is validated and unchanged.

---

## What Changes for Multiplatform

The existing stack is solid. Only ONE new runtime dependency is required. Everything else is either stdlib, configuration changes, or test additions.

---

## New Runtime Dependency

### Process Detection: psutil

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| psutil | >=7.0.0 | Cross-platform Lightroom process detection | Replaces macOS-only `pgrep` subprocess call in `catalog.py`. Ships binary wheels for Windows (amd64, arm64), macOS, and Linux. No build toolchain needed on Windows. |

**Current problem in `catalog.py`:**
```python
# Lines 58-71 — macOS-only, silently skips on Windows (FileNotFoundError)
result = subprocess.run(
    ["pgrep", "-f", LR_PROCESS_NAME],
    capture_output=True, text=True, timeout=5,
)
```

**psutil replacement pattern (cross-platform):**
```python
import psutil

def _is_lightroom_running(process_names: tuple[str, ...]) -> bool:
    """Return True if any process matching the given names is running."""
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() in process_names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False
```

**Process name per platform:**

| Platform | Process Name | Source |
|----------|-------------|--------|
| macOS | `Adobe Lightroom Classic` | Existing `LR_PROCESS_NAME` constant |
| Windows | `Lightroom.exe` | Windows Task Manager — multiple `lightroom.exe` instances are normal |
| Linux | N/A (LR not available on Linux) | Skip check; lock file is sufficient |

`psutil` latest: **7.2.2** (released 2026-01-28). Binary wheels available for Python 3.12/3.13 on Windows (amd64, arm64), macOS, and Linux. No C compiler needed.

**pyproject.toml change:**
```toml
dependencies = [
    "click>=8.3.1",
    "python-dotenv>=1.2.1",
    "rich>=14.3.2",
    "psutil>=7.0.0",   # ADD — replaces pgrep for cross-platform LR detection
]
```

Note: `reverse-geocoder>=1.5.1` is currently in `dependencies` but should be `[geo]` optional only (it's already in `[project.optional-dependencies]` — this is a pre-existing inconsistency to fix as part of v0.6.0 cleanup).

---

## Path Handling: No New Library Needed

`pathlib.Path` handles Windows paths correctly in Python 3.12. No additional library is required.

**What pathlib already handles on Windows:**
- `Path.home()` returns the correct home directory (`C:\Users\username`)
- `/` operator joins with OS-appropriate separator
- `Path.mkdir(parents=True, exist_ok=True)` works on Windows
- `Path.exists()`, `iterdir()`, `rglob()` all work cross-platform
- `str(Path(...))` uses backslashes on Windows automatically

**The real issue — `absolutePath` in the Lightroom catalog:**

Lightroom's `AgLibraryRootFolder.absolutePath` stores paths in the format they were written when the catalog was last used. On macOS this is a POSIX path (`/Volumes/photo/`). On Windows it will be a Windows path with drive letter and backslashes (e.g. `C:\Users\user\Pictures\`). The scanner and executor construct `Path(absolutePath) / pathFromRoot` — this will work correctly on each respective platform because `Path()` parses the native format. The only risk is **cross-platform catalog transfer** (Mac catalog opened on Windows), which is an edge case outside this milestone's scope.

**Pathlib usage is correct as-is. No change needed.**

---

## Platform-Aware Code Patterns

Use `sys.platform` (stdlib) for platform branching. No new library.

```python
import sys

def _platform_lr_process_names() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("adobe lightroom classic",)
    elif sys.platform == "win32":
        return ("lightroom.exe",)
    else:
        return ()  # Linux: LR not available; rely on lock file only
```

**AppleDouble cleanup on Windows:**
The `_is_effectively_empty()` and `_delete_apple_double_files()` functions in `executor.py` check for `._*` files. On Windows these files never exist, so the functions are harmlessly idempotent — no code change strictly required. However, adding a `sys.platform == "darwin"` guard makes intent explicit and avoids the `os.walk` overhead for `._*` matching on non-macOS.

---

## Default Catalog Path Discovery

Stdlib `pathlib.Path.home()` is sufficient. No new library.

| Platform | Default Path | Python Expression |
|----------|-------------|-------------------|
| macOS | `~/Pictures/Lightroom/Lightroom Catalog-v13-3.lrcat` | `Path.home() / "Pictures" / "Lightroom"` |
| Windows | `%USERPROFILE%\Pictures\Lightroom\Lightroom Catalog.lrcat` | `Path.home() / "Pictures" / "Lightroom"` |
| Linux | `~/Pictures/Lightroom/Lightroom Catalog.lrcat` | `Path.home() / "Pictures" / "Lightroom"` |

The path structure is identical across platforms; only the base home directory changes, and `Path.home()` handles that.

---

## Types Stubs for psutil

`types-psutil` is available on PyPI for mypy strict mode.

```toml
[dependency-groups]
dev = [
    ...
    "types-psutil>=7.0.0",   # ADD — mypy stubs for psutil
]
```

---

## GitHub Actions CI Matrix

**Windows runner name:** `windows-latest` (currently Windows Server 2025 image as of 2026-02).

**setup-uv action:** Current version is `astral-sh/setup-uv@v7`.

**Recommended CI matrix:**

```yaml
jobs:
  check:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python-version }}

      - run: uv sync
      - run: make check
```

**Windows-specific gotchas:**

| Gotcha | Detail | Mitigation |
|--------|--------|-----------|
| D:\ drive unavailable | `windows-latest` (Server 2025) only has C:\, not D:\ | Don't use D:\ in tests or temp paths |
| `make` not available | Windows Server 2025 does not ship GNU `make` by default | Either install via `choco install make` step, or replace `make check` with explicit `uv run` commands |
| Line endings in test fixtures | Git's `autocrlf` can corrupt test fixture files | Add `.gitattributes` with `* text=auto eol=lf` |
| `PATHEXT` and script discovery | `lrc-auto` entry point resolves to `lrc-auto.exe` on Windows; uv handles this | No action needed; uv entry points work on Windows |
| `uv sync` cache | `uv` caches packages in `%LOCALAPPDATA%\uv` on Windows | Use `cache: true` in `setup-uv@v7` to enable cross-run caching |

**`make` on Windows — recommended solution:**

Replace `make check` in CI with explicit steps to avoid the `make` dependency issue:

```yaml
- run: uv run ruff check .
- run: uv run ruff format --check .
- run: uv run mypy src/
- run: uv run pytest -v
```

Or conditionally use `make` only on non-Windows:

```yaml
- name: Run checks (Unix)
  if: runner.os != 'Windows'
  run: make check

- name: Run checks (Windows)
  if: runner.os == 'Windows'
  run: |
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy src/
    uv run pytest -v
```

---

## pyproject.toml Changes Summary

```toml
[project]
dependencies = [
    "click>=8.3.1",
    "python-dotenv>=1.2.1",
    "rich>=14.3.2",
    "psutil>=7.0.0",                # NEW — cross-platform process detection
    # remove reverse-geocoder from here; it belongs in [geo] only
]

[project.optional-dependencies]
geo = ["reverse_geocoder>=1.5.1", "pycountry>=24.6.1"]

[dependency-groups]
dev = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.6",
    "mypy>=1.14",
    "pytest>=9.0.2",
    "pycountry>=24.6.1",
    "reverse_geocoder>=1.5.1",
    "ruff>=0.15.1",
    "types-psutil>=7.0.0",          # NEW — mypy stubs
]
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Process detection | psutil 7.x | `subprocess + pgrep` | pgrep is macOS/Linux only; absent on Windows |
| Process detection | psutil 7.x | `wmi` (Windows) + `psutil` (others) | WMI is Windows-only; doubles complexity |
| Process detection | psutil 7.x | `subprocess + tasklist` (Windows) + `pgrep` (Mac) | Platform branching at subprocess level; fragile |
| Path handling | stdlib pathlib | `pywin32` | pywin32 is Windows-only; pathlib handles cross-platform paths correctly for our use case |
| Platform detection | `sys.platform` (stdlib) | `platform.system()` | Both are stdlib; `sys.platform` is more idiomatic in modern Python |

---

## What NOT to Add

- **pywin32**: Windows-only, not needed; pathlib handles our path use cases.
- **plumbum / sh**: Shell-wrapping libraries; we only need one cross-platform process check.
- **watchdog**: File system watching; out of scope (no daemon mode per ADR).
- **platformdirs**: The `~ / Pictures / Lightroom` pattern is stable across all platforms; `Path.home()` is sufficient.
- **colorama**: Rich already handles Windows terminal colors via its own Windows console support.

---

## Sources

- [psutil PyPI — v7.2.2, 2026-01-28](https://pypi.org/project/psutil/)
- [psutil documentation v7.x](https://psutil.readthedocs.io/en/latest/)
- [astral-sh/setup-uv GitHub](https://github.com/astral-sh/setup-uv) — v7 is current recommended
- [uv GitHub Actions integration](https://docs.astral.sh/uv/guides/integration/github/)
- [GitHub Actions windows-latest = Windows Server 2025](https://github.com/actions/runner-images/issues/12677)
- [Adobe: Lightroom Classic default catalog paths](https://helpx.adobe.com/lightroom-classic/kb/preference-file-and-other-file-locations.html)
- [Lightroom.exe Windows process documentation](https://www.file.net/process/lightroom.exe.html)
- [GitHub Actions Early February 2026 updates](https://github.blog/changelog/2026-02-05-github-actions-early-february-2026-updates/)
