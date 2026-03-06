# Phase 2: Write Safety - Research

**Researched:** 2026-03-06
**Domain:** Windows cross-platform write correctness — process detection, path normalisation in SQL writes, platform-gated cleanup, and file-move retry
**Confidence:** HIGH

---

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-01 | Tool detects Lightroom Classic running on Windows via `psutil` (replaces the silent `pgrep` no-op, checks `Lightroom.exe`) | psutil.process_iter API confirmed; safe iteration pattern documented; exact process name constant identified |
| PROC-02 | `pathFromRoot` SQL column is always written with forward slashes on Windows so Lightroom can locate folders after a move | Three write sites identified in `executor.py` and `reconciler.py`; `Path.as_posix()` fix confirmed; Windows backslash risk in `str(rel)` pattern documented |
| PROC-03 | AppleDouble (`._*`) file cleanup is skipped silently on non-macOS platforms (no errors, no spurious log entries) | `sys.platform == 'darwin'` guard pattern confirmed; `_delete_apple_double_files` and `_is_effectively_empty` callers identified |
| PROC-04 | File moves retry on `PermissionError` to handle transient antivirus scan locks on Windows | Retry-with-backoff pattern confirmed; `shutil.move` raises `PermissionError` on Windows AV lock; `time.sleep` + loop implementation documented |
</phase_requirements>

---

## Summary

Phase 2 makes four targeted edits to the existing codebase: replacing the macOS-only `pgrep` subprocess with `psutil.process_iter` for cross-platform process detection; ensuring all SQL writes of `pathFromRoot` use `Path.as_posix()` rather than `str(Path)` so forward slashes are always stored; gating the AppleDouble cleanup path behind `sys.platform == 'darwin'`; and adding a small retry loop around `shutil.move` to tolerate transient `PermissionError` from Windows antivirus scanner locks.

All four changes are surgical: no new modules, no new abstractions, no new external dependencies beyond `psutil` (which is already the chosen solution per the project's locked decisions). The changes span three existing files — `catalog.py`, `executor.py`, `reconciler.py` — and one constant (`LR_PROCESS_NAME` in `constants.py`).

The tests follow the project's established patterns: `monkeypatch` for `sys.platform` and `psutil`, in-memory SQLite catalogs for DB-side assertions, and `tmp_path` + actual files on disk for file-operation tests.

**Primary recommendation:** Implement all four PROC requirements in two plans: one for `catalog.py` (PROC-01) and one for `executor.py` + `reconciler.py` (PROC-02, PROC-03, PROC-04).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `psutil` | >=5.x (latest: 7.x) | Cross-platform process enumeration | Locked project decision; binary wheels for all platforms |
| `sys` (stdlib) | — | `sys.platform` OS check | Zero-dep platform guard |
| `pathlib.Path` | stdlib | `.as_posix()` for slash normalisation | Already used throughout codebase |
| `shutil` | stdlib | `shutil.move` file operations | Already used in `executor.py` |
| `time` | stdlib | `time.sleep` for retry backoff | Standard retry idiom |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest.MonkeyPatch` | pytest >=9 | Patch `sys.platform`, `psutil.process_iter`, `shutil.move` in tests | All cross-platform behaviour tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `psutil.process_iter` | `subprocess.run(['pgrep', ...])` | `pgrep` is macOS/Linux only — silent no-op on Windows; psutil is cross-platform |
| `Path.as_posix()` | Manual `.replace('\\', '/')` | `as_posix()` is the stdlib-idiomatic way; avoids double-escape bugs |
| `time.sleep` retry | `tenacity` library | `tenacity` is a heavy dependency for a two-line retry loop; stdlib sufficient |

**Installation:**

```bash
# psutil must be added to pyproject.toml core dependencies
# (not already present — it was used in a test but not in core deps)
uv add psutil
```

Note: `psutil` is not currently in `pyproject.toml` `dependencies`. It must be added as a core (non-optional) dependency before Phase 2 code can run.

---

## Architecture Patterns

### Recommended File Changes

```
src/lrc_automation/
├── catalog.py          # PROC-01: replace pgrep with psutil.process_iter
├── constants.py        # PROC-01: add LR_PROCESS_NAME_WINDOWS = "Lightroom.exe"
├── executor.py         # PROC-02: as_posix() in cleanup; PROC-03: darwin guard;
│                       #          PROC-04: retry loop in _apply_file_op
└── reconciler.py       # PROC-02: as_posix() in _reconcile_one
```

### Pattern 1: psutil Cross-Platform Process Detection (PROC-01)

**What:** Replace the `subprocess.run(['pgrep', ...])` block in `CatalogConnection.check_lightroom_not_running()` with `psutil.process_iter`.

**When to use:** Any platform; replaces the current macOS-only pgrep path entirely.

**Current code location:** `catalog.py` lines 98-111

**Fix pattern:**

```python
# Source: psutil official docs https://psutil.readthedocs.io/en/latest/#processes
import psutil

def check_lightroom_not_running(self) -> None:
    lock_path = Path(str(self.catalog_path) + LOCK_FILE_SUFFIX)
    if lock_path.exists():
        raise LightroomRunningError(
            f"Catalog is locked (found {lock_path.name}). Close Lightroom first."
        )

    lr_names = {LR_PROCESS_NAME, LR_PROCESS_NAME_WINDOWS}
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] in lr_names:
                    raise LightroomRunningError(
                        "Lightroom Classic appears to be running. "
                        "Close it before modifying the catalog."
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except LightroomRunningError:
        raise
    except Exception:
        pass  # psutil unavailable or OS error — fall through
```

**Constants needed in `constants.py`:**

```python
LR_PROCESS_NAME = "Adobe Lightroom Classic"     # macOS
LR_PROCESS_NAME_WINDOWS = "Lightroom.exe"       # Windows
```

### Pattern 2: pathFromRoot Forward-Slash Normalisation (PROC-02)

**What:** Replace `str(rel)` with `rel.as_posix()` wherever a `Path.relative_to()` result is written into the `pathFromRoot` SQL column.

**Affected locations:**

1. `executor.py` — `cleanup_empty_folders()` function, line 369:

   ```python
   # BEFORE (writes backslashes on Windows)
   path_from_root = str(rel) + "/"
   # AFTER
   path_from_root = rel.as_posix() + "/"
   ```

2. `reconciler.py` — `_reconcile_one()` method, line 94:

   ```python
   # BEFORE (writes backslashes on Windows)
   path_from_root = str(rel.parent) + "/"
   # AFTER
   path_from_root = rel.parent.as_posix() + "/"
   ```

**Not affected:** `executor._create_folders()` — the `path_from_root` argument there comes from `plan.folders_to_create`, which is assembled via `"/".join(parts) + "/"` string arithmetic (always forward slashes).

**Not affected:** `ChangeExecutor._cleanup_empty_folders()` — uses `change.photo.current_folder_path` which comes directly from the DB `pathFromRoot` column (already stored string).

### Pattern 3: AppleDouble Guard (PROC-03)

**What:** Wrap the `_delete_apple_double_files()` call and the `._` name check inside `_is_effectively_empty()` behind `sys.platform == "darwin"`.

**Current location:** `executor.py`, `_is_effectively_empty()` and `cleanup_empty_folders()`.

**Fix pattern:**

```python
import sys

def _is_effectively_empty(directory: Path) -> bool:
    for entry in directory.iterdir():
        if sys.platform == "darwin" and entry.name.startswith("._"):
            continue  # AppleDouble metadata — macOS only
        return False
    return True

# In cleanup_empty_folders:
# Replace unconditional _delete_apple_double_files(full_dir) with:
if sys.platform == "darwin":
    _delete_apple_double_files(full_dir)
```

**Result on Windows:** `_is_effectively_empty` treats `._*` files as real content (directory not considered empty), and no `._*` deletion is attempted. No errors, no spurious log entries.

### Pattern 4: PermissionError Retry Loop (PROC-04)

**What:** Wrap the `shutil.move` / `os.rename` call in `_apply_file_op` with a retry loop that sleeps briefly on `PermissionError`.

**Current location:** `executor.py`, `ChangeExecutor._apply_file_op()`, line 232.

**Recommended approach:** Maximum 3 attempts, 0.5 second sleep, only retry on `PermissionError`.

```python
import time

_MOVE_RETRIES = 3
_MOVE_RETRY_SLEEP = 0.5  # seconds

def _apply_file_op(self, src: Path, dst: Path, move: bool) -> None:
    if not src.exists():
        logger.warning("SKIP (source not found): %s", src)
        raise SkippableError(f"Source file not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        logger.warning("SKIP (destination exists): %s", dst)
        raise SkippableError(f"Destination already exists: {dst}")
    op = shutil.move if move else os.rename
    last_err: Exception | None = None
    for attempt in range(_MOVE_RETRIES):
        try:
            op(str(src), str(dst))
            last_err = None
            break
        except PermissionError as e:
            last_err = e
            logger.debug(
                "RETRY %d/%d (PermissionError): %s", attempt + 1, _MOVE_RETRIES, src
            )
            time.sleep(_MOVE_RETRY_SLEEP)
    if last_err is not None:
        raise last_err
    # ... rest of logging + rollback registration
```

**Rollback safety:** The rollback action is only registered after a successful move, so a final failure after all retries does not corrupt the rollback list.

### Anti-Patterns to Avoid

- **Using `str(Path.relative_to(...))` for SQL writes on Windows:** Always use `.as_posix()`. `str(WindowsPath)` produces backslashes; Lightroom requires forward slashes in `pathFromRoot`.
- **Checking `proc.name() == "Adobe Lightroom Classic"` only:** On Windows the process is named `Lightroom.exe`, not the macOS display name.
- **Catching broad `Exception` in retry loop:** Only `PermissionError` should trigger a retry; other errors (disk full, wrong permissions) should fail immediately.
- **Deleting `._*` files on Windows:** Windows does not create AppleDouble files; the directory iteration and deletion loop must be guarded by `sys.platform == "darwin"`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform process list | Custom subprocess per OS | `psutil.process_iter` | Handles macOS, Windows, Linux; race-safe; handles AccessDenied |
| Forward-slash path strings | `.replace('\\', '/')` | `Path.as_posix()` | Stdlib method, handles edge cases (UNC paths, mixed separators) |

**Key insight:** `psutil.process_iter` is the canonical way to enumerate processes cross-platform; the existing `pgrep` approach was always a macOS-specific workaround.

---

## Common Pitfalls

### Pitfall 1: `psutil.AccessDenied` During Process Iteration

**What goes wrong:** On Windows, certain system processes raise `AccessDenied` when their name is queried; unguarded code crashes mid-iteration.
**Why it happens:** Windows security model restricts cross-user process inspection.
**How to avoid:** Wrap each `proc.info["name"]` access in a try/except for `(psutil.NoSuchProcess, psutil.AccessDenied)` inside the `process_iter` loop.
**Warning signs:** CI failure on Windows with `psutil.AccessDenied` traceback.

### Pitfall 2: `str(rel)` Writes Backslashes on Windows

**What goes wrong:** `cleanup_empty_folders` and `reconciler._reconcile_one` derive `pathFromRoot` from `Path.relative_to()`. On Windows, `str()` of a `WindowsPath` uses backslashes. Lightroom then cannot find the folders.
**Why it happens:** `Path.__str__` is OS-dependent; `Path.as_posix()` is always forward-slash.
**How to avoid:** Use `rel.as_posix()` (and `rel.parent.as_posix()`) everywhere `pathFromRoot` is written.
**Warning signs:** Post-apply Lightroom shows moved folders as "missing"; pathFromRoot column contains `\` characters.

### Pitfall 3: AppleDouble `._` Check Breaks on Windows

**What goes wrong:** `_is_effectively_empty` treats a directory containing `._Thumbnail.jpg` as empty and tries to delete it; on Windows this could either fail (file is real content, not AppleDouble) or succeed unexpectedly.
**Why it happens:** `._*` naming convention is macOS-specific; on Windows these may be legitimate filenames.
**How to avoid:** Gate the `._` prefix check and deletion behind `sys.platform == "darwin"`.
**Warning signs:** Test `test_removes_apple_double_files_before_rmdir` passes on macOS but produces unexpected behaviour on Windows.

### Pitfall 4: Retry Loop Registers Rollback Before Success

**What goes wrong:** If rollback is registered before a successful move, a failed-then-retried-then-succeeded move could create a duplicate rollback entry pointing to a stale path.
**Why it happens:** Rollback registration placed before the success check.
**How to avoid:** Only append to `_rollback_actions` after confirming the operation succeeded (i.e., after the loop exits without error).
**Warning signs:** Double-move during rollback; file ends up at unexpected location.

### Pitfall 5: `psutil` Not in `pyproject.toml` Core Dependencies

**What goes wrong:** Tool installs fine but crashes on first `apply` run with `ModuleNotFoundError: No module named 'psutil'`.
**Why it happens:** `psutil` is a locked dependency choice but has not yet been added to `pyproject.toml`.
**How to avoid:** Add `psutil>=5.9` to `[project] dependencies` in the same plan that modifies `catalog.py`.
**Warning signs:** `uv run lrc-auto apply` fails immediately on a clean install.

---

## Code Examples

Verified patterns from official sources and codebase inspection:

### psutil Safe Process Iteration

```python
# Source: https://psutil.readthedocs.io/en/latest/#processes
import psutil

for proc in psutil.process_iter(["name"]):
    try:
        if proc.info["name"] in {"Adobe Lightroom Classic", "Lightroom.exe"}:
            # process found
            pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
```

### Path.as_posix() for pathFromRoot SQL writes

```python
# Source: Python stdlib pathlib docs
# Before storing a relative Path as pathFromRoot in SQLite:
rel = full_dir.relative_to(root_path)
path_from_root = rel.as_posix() + "/"   # Always "2023/06/" — never "2023\\06\\"
```

### sys.platform AppleDouble Guard

```python
import sys

# Guard any macOS-only filesystem behaviour
if sys.platform == "darwin":
    _delete_apple_double_files(full_dir)
```

### PermissionError Retry

```python
import time

_MOVE_RETRIES = 3
_MOVE_RETRY_SLEEP = 0.5

last_err: Exception | None = None
for attempt in range(_MOVE_RETRIES):
    try:
        shutil.move(str(src), str(dst))
        last_err = None
        break
    except PermissionError as e:
        last_err = e
        time.sleep(_MOVE_RETRY_SLEEP)
if last_err is not None:
    raise last_err
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pgrep` subprocess (macOS only) | `psutil.process_iter` (cross-platform) | Phase 2 | Windows process detection works |
| `str(rel)` for pathFromRoot | `rel.as_posix()` | Phase 2 | No backslashes stored in SQL on Windows |
| Unconditional AppleDouble cleanup | `sys.platform == "darwin"` guard | Phase 2 | cleanup command safe on Windows |
| Single-attempt shutil.move | Retry loop with sleep | Phase 2 | Survives transient AV locks on Windows |

**Deprecated/outdated:**

- `subprocess.run(['pgrep', ...])` in `catalog.py`: replaced by psutil; will be removed entirely.
- `LR_PROCESS_NAME` string: still valid for macOS; `LR_PROCESS_NAME_WINDOWS` constant added alongside it.

---

## Open Questions

1. **`psutil` minimum version**
   - What we know: psutil 5.x has `process_iter(attrs=[...])` API; latest is 7.x.
   - What's unclear: whether 5.9 is sufficient or if 6.0+ is needed.
   - Recommendation: Use `psutil>=5.9` in pyproject.toml (5.9 added Windows ARM support; widely available).

2. **Retry count and sleep duration for PROC-04**
   - What we know: Windows AV scans are typically < 1 second; 3 retries × 0.5s = 1.5s total wait.
   - What's unclear: Whether longer waits are needed for slow storage or heavy AV.
   - Recommendation: Start with 3 retries, 0.5s sleep; make constants module-level so they can be adjusted without refactoring.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_catalog.py tests/test_executor.py tests/test_reconciler.py -x` |
| Full suite command | `uv run pytest -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROC-01 | psutil detects `Lightroom.exe` on Windows | unit | `uv run pytest tests/test_catalog.py -k "psutil or lightroom_running" -x` | ❌ Wave 0 |
| PROC-01 | psutil detects `Adobe Lightroom Classic` on macOS | unit | `uv run pytest tests/test_catalog.py -k "psutil or lightroom_running" -x` | ❌ Wave 0 |
| PROC-01 | No crash when AccessDenied during process_iter | unit | `uv run pytest tests/test_catalog.py -k "access_denied" -x` | ❌ Wave 0 |
| PROC-02 | cleanup_empty_folders writes forward-slash pathFromRoot | unit | `uv run pytest tests/test_executor.py -k "posix or forward_slash" -x` | ❌ Wave 0 |
| PROC-02 | reconciler._reconcile_one writes forward-slash pathFromRoot | unit | `uv run pytest tests/test_reconciler.py -k "posix or forward_slash" -x` | ❌ Wave 0 |
| PROC-03 | cleanup skips AppleDouble deletion on non-macOS | unit | `uv run pytest tests/test_executor.py -k "apple_double or non_darwin" -x` | ❌ Wave 0 |
| PROC-03 | _is_effectively_empty treats ._* as real on non-macOS | unit | `uv run pytest tests/test_executor.py -k "effectively_empty" -x` | ❌ Wave 0 |
| PROC-04 | PermissionError on first attempt retried and succeeds | unit | `uv run pytest tests/test_executor.py -k "retry or permission_error" -x` | ❌ Wave 0 |
| PROC-04 | All retries exhausted → PermissionError raised, no partial disk state | unit | `uv run pytest tests/test_executor.py -k "retry_exhausted" -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_catalog.py tests/test_executor.py tests/test_reconciler.py -x`
- **Per wave merge:** `uv run pytest -v`
- **Phase gate:** Full suite green + `make check` before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] New test functions in `tests/test_catalog.py` — covers PROC-01 (psutil detection, AccessDenied handling)
- [ ] New test functions in `tests/test_executor.py` — covers PROC-02 (as_posix), PROC-03 (darwin guard), PROC-04 (retry)
- [ ] New test functions in `tests/test_reconciler.py` — covers PROC-02 (reconciler forward-slash write)
- [ ] `psutil` added to `pyproject.toml` core deps: `uv add psutil`

_(All tests use existing conftest fixtures; no new fixtures needed.)_

---

## Sources

### Primary (HIGH confidence)

- psutil official docs <https://psutil.readthedocs.io/en/latest/#processes> — process_iter API, exception hierarchy
- Python stdlib `pathlib.Path.as_posix()` documentation — always returns forward-slash string
- Direct codebase inspection (`catalog.py`, `executor.py`, `reconciler.py`, `constants.py`) — exact line numbers of all write sites

### Secondary (MEDIUM confidence)

- psutil GitHub <https://github.com/giampaolo/psutil> — Windows process name `Lightroom.exe` verified as standard `.exe` naming
- Python `sys.platform` documentation — `"darwin"` on macOS, `"win32"` on Windows regardless of 32/64-bit

### Tertiary (LOW confidence)

- Windows AV scan lock timing (0.5s sleep estimate) — based on general knowledge; specific timing needs empirical validation on target hardware

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — psutil is locked decision; stdlib only otherwise
- Architecture: HIGH — three exact file locations identified; fix patterns are single-line changes
- Pitfalls: HIGH — all derived from direct code inspection, not speculation
- Retry parameters: LOW — timing is empirical; constants are tunable

**Research date:** 2026-03-06
**Valid until:** 2026-06-06 (psutil API is stable; pathlib stdlib is stable)
