# ADR-007: Multiplatform Windows Support

**Status:** Accepted
**Date:** 2026-03-06
**Decision Makers:** fjacquet

## Context

lrc-automation v0.6.0 extends the tool from macOS-only to macOS + Windows. Lightroom Classic
runs on both platforms, and user requests indicated demand for Windows support without
introducing a new platform-abstraction layer.

The existing codebase had four platform-specific gaps preventing correct operation on Windows:

1. **Catalog open** — `CatalogConnection.open()` built `file:///C:\Users\...` URIs, which
   SQLite rejects. The URI must use forward slashes (`file:///C:/Users/...`).
2. **Process detection** — `check_lightroom_not_running()` called `pgrep` via subprocess.
   `pgrep` is a POSIX utility absent on Windows.
3. **Path writes** — `executor.py` and `planner.py` wrote `AgLibraryFile.pathFromRoot` using
   the native `Path` string representation. On Windows this produces backslashes, which
   Lightroom (a SQLite-first application with a Unix-origin schema) cannot parse.
4. **Disk cleanup** — `executor.py` removed AppleDouble (`._*`) files unconditionally. On
   Windows these files do not exist and the cleanup step raised errors on non-macOS volumes.

In addition, the CI pipeline ran only on `ubuntu-latest`, so Windows-specific regressions
went undetected. A cross-platform matrix was added covering `ubuntu-latest`, `macos-latest`,
and `windows-latest` for Python 3.12 and 3.13.

---

## Decisions

### 1. SQLite URI Forward-Slash Fix (PATH-01)

`_path_to_sqlite_uri()` in `catalog.py` converts the catalog path to a POSIX string before
building the `file:///` URI:

```python
posix = path.as_posix()
if not posix.startswith("/"):
    # Windows drive-letter path: C:/Users/... → file:///C:/Users/...
    return f"file:///{posix}?{query}"
else:
    return f"file://{posix}?{query}"
```

Detection uses `posix.startswith("/")` because POSIX absolute paths start with `/` while
Windows drive-letter paths (e.g. `C:/Users/...`) do not. `Path.is_absolute()` is unreliable
for this check because its result is platform-dependent at runtime.

### 2. psutil for Process Detection (PROC-01)

`psutil.process_iter(["name"])` replaces the `pgrep` subprocess call in
`check_lightroom_not_running()`:

```python
import psutil

LIGHTROOM_PROCESS_NAMES = {"Adobe Lightroom Classic", "Lightroom.exe"}

def check_lightroom_not_running(catalog_path: Path) -> None:
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] in LIGHTROOM_PROCESS_NAMES:
                raise CatalogLockedError(...)
        except psutil.AccessDenied:
            continue
```

`psutil` is a hard dependency with binary wheels for all target platforms (macOS, Windows,
Linux). `AccessDenied` exceptions are caught and skipped so the lock check degrades
gracefully on restricted process tables.

### 3. path.as_posix() for SQL pathFromRoot Writes (PROC-02)

All writes to `AgLibraryFile.pathFromRoot` use `Path.as_posix()` to produce forward-slash
strings. Lightroom's SQLite schema stores folder paths with forward slashes regardless of the
host OS; native `str(Path(...))` on Windows would produce backslashes and break folder
lookups after a move.

This applies in `executor.py` (`_execute_move`) and `planner.py` (`_ensure_folder_chain`).

### 4. sys.platform == 'darwin' for AppleDouble Guard (PROC-03)

AppleDouble (`._*`) file cleanup in `executor.py` is gated on `sys.platform == "darwin"`:

```python
if sys.platform == "darwin":
    _remove_apple_double(src_dir, base_name)
```

This guard is identical to the existing pattern elsewhere in the codebase. On Windows and
Linux the step is silently skipped — no errors, no spurious log entries.

### 5. PermissionError Retry Loop (PROC-04)

File moves in `executor.py` retry on `PermissionError` up to `_MOVE_RETRY_COUNT` times with
`_MOVE_RETRY_SLEEP` seconds between attempts:

```python
_MOVE_RETRY_COUNT = 3
_MOVE_RETRY_SLEEP = 0.5  # seconds

for attempt in range(_MOVE_RETRY_COUNT):
    try:
        shutil.move(str(src), str(dst))
        break
    except PermissionError:
        if attempt == _MOVE_RETRY_COUNT - 1:
            raise
        time.sleep(_MOVE_RETRY_SLEEP)
```

Both constants are module-level so tests can zero them via `monkeypatch` without sleeping.
This handles transient antivirus scan locks on Windows, which briefly hold exclusive file
handles during on-access scanning.

### 6. SBOM via anchore/sbom-action (CI-04)

`anchore/sbom-action@v0` generates an SPDX Software Bill of Materials (SBOM) artifact
attached to every GitHub release:

```yaml
- uses: anchore/sbom-action@v0
  with:
    artifact-name: sbom.spdx.json
```

`anchore/sbom-action@v0` was chosen over `actions/attest-sbom` because it produces a
downloadable file visible on the releases page, rather than a signed attestation stored in
GitHub's artifact storage. The downloadable SBOM is more accessible for dependency audits.

### 7. .gitattributes LF Enforcement (CI-02)

`.gitattributes` contains:

```
* text=auto eol=lf
```

This prevents CRLF line-ending failures when `ruff format --check` runs on Windows CI
runners with a fresh checkout. Without this setting, Git on Windows converts LF to CRLF on
checkout, and `ruff format --check` reports all files as needing reformatting.

### 8. Catalog Auto-Discovery (UX-01)

`_discover_default_catalog(home_dir=None)` in `cli.py` finds the first `.lrcat` file in
the OS default Lightroom Classic directory:

```python
def _discover_default_catalog(home_dir: Path | None = None) -> str | None:
    base = home_dir or Path.home()
    if sys.platform == "win32":
        default_dir = base / "Pictures" / "Lightroom"
    else:
        default_dir = base / "Pictures" / "Lightroom"
    if not default_dir.is_dir():
        return None
    candidates = sorted(default_dir.glob("*.lrcat"))
    return str(candidates[0]) if candidates else None
```

- **macOS/Linux:** `~/Pictures/Lightroom/`
- **Windows:** `%USERPROFILE%\Pictures\Lightroom\` (via `Path.home()`)

The `--catalog` / `-c` option is now `required=False`. When no catalog is supplied and
discovery finds nothing, the CLI raises `click.UsageError` with a human-readable message.

The `home_dir` parameter keeps the function pure and testable via `monkeypatch` without
mocking `Path.home`.

---

## Consequences

### Positive

- The tool now works on Windows for all core operations (scan, plan, apply, validate,
  reconcile, restore).
- CI matrix confirms correctness on 3 OS × 2 Python version combinations (6 matrix jobs).
- SBOM attached to every release improves supply-chain transparency.
- `--catalog` is optional on macOS and Windows for standard Lightroom installations.

### Negative

- `reverse_geocoder` (the `[geo]` extra) has no Windows wheel on PyPI. Location-folder
  features (`--location-folders`) are macOS/Linux only.
- The `[geo]` extra test suite is skipped on Windows CI runners (`uv sync` without
  `--all-extras` on Windows).

### Neutral

- WAL mode was intentionally **not** enabled. Windows file-locking semantics interact poorly
  with WAL alongside the existing `.lrcat-lock` strategy. This was noted in `catalog.py` via
  an architecture comment to prevent future accidental enablement on Windows.
- `pgrep` subprocess code was removed entirely; `psutil` is now the single process-detection
  path on all platforms.
- `types-psutil` was added to the dev dependency group for mypy strict-mode compliance.

---

## Alternatives Considered

### A — New Platform Abstraction Layer

A dedicated `platform.py` module with OS-specific subclasses was considered for process
detection and path handling. Rejected: the scope of platform-specific code is narrow (four
call sites), and a new abstraction layer would add indirection without benefit. Each concern
has exactly one caller in the existing codebase.

### B — Keep pgrep on macOS, Add Windows-only psutil Branch

Use `pgrep` on macOS as before, with a `sys.platform == "win32"` branch that calls psutil.
Rejected: psutil works correctly on macOS, eliminates the subprocess overhead, and has
better `AccessDenied` handling. Maintaining two code paths for the same behavior adds
unnecessary complexity.

### C — WAL Mode for Concurrent Access

Enable SQLite WAL mode to allow concurrent readers during write operations. Rejected: WAL
requires an additional `-shm` shared-memory file that conflicts with Windows file-locking
semantics when the `.lrcat-lock` file is also in use. The existing lock strategy is
sufficient for the single-user, Lightroom-must-be-closed workflow.
