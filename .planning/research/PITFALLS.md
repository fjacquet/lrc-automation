# Domain Pitfalls

**Domain:** Adding Windows support to a macOS Python CLI tool (filesystem + SQLite operations)
**Project:** lrc-automation v0.6.0 Multiplatform
**Researched:** 2026-03-06
**Overall confidence:** HIGH (grounded in codebase audit + official documentation)

---

## Critical Pitfalls

Mistakes that cause silent data corruption, catalog mismatches, or test failures that are hard
to reproduce without a Windows machine.

---

### Pitfall 1: SQLite URI Path — Backslash Breaks the `file:` Protocol

**What goes wrong:** `catalog.py` uses URI-mode connections: `f"file:{self.catalog_path}?mode=ro"`.
On Windows, `self.catalog_path` (a `pathlib.Path`) resolves to a backslash path, e.g.
`C:\Users\user\catalog.lrcat`. The SQLite URI protocol requires forward slashes and, for an
absolute Windows path with a drive letter, requires a leading slash before the drive letter:
`file:///C:/Users/user/catalog.lrcat`. A raw backslash path will cause `sqlite3.OperationalError:
unable to open database file`.

**Why it happens:** `pathlib.Path.__str__()` on Windows returns the OS-native path with
backslashes. The `file:` URI format is defined by RFC 3986 and SQLite's own VFS — both require
forward slashes.

**Consequences:** The `validate_is_lrcat()` check and the read-only scan command both fail on
Windows. No data is corrupted, but the tool is entirely unusable until fixed.

**Prevention:**
```python
# catalog.py — replace raw path in URI construction with:
uri_path = self.catalog_path.as_posix()  # forward slashes, no drive-letter prefix issue
# For Windows absolute paths, pathlib.Path.as_posix() on "C:\foo" yields "C:/foo"
# SQLite accepts this form; no extra slash needed for Windows absolute paths.
uri = f"file:{uri_path}?mode=ro"
```
Apply to both the `validate_is_lrcat()` read-only connect and the `open(readonly=True)` path.

**Detection:** `pytest` on Windows fails immediately in `TestCatalogConnection` with
`OperationalError`. Add an explicit URI-path test that asserts forward slashes.

**Phase:** Phase 1 (foundation) — blocks all other features.

---

### Pitfall 2: `pgrep` Hard Crash on Windows (FileNotFoundError silently eaten)

**What goes wrong:** `catalog.py:check_lightroom_not_running()` calls `subprocess.run(["pgrep",
"-f", LR_PROCESS_NAME])`. On Windows, `pgrep` does not exist. The code already wraps this in a
`try/except FileNotFoundError: pass`, which means the process check is silently skipped — but only
the bare `pgrep` binary absence is caught. Any other subprocess error on Windows (e.g. permissions,
encoding) surfaces as an unhandled exception.

More importantly, the constant `LR_PROCESS_NAME = "Adobe Lightroom Classic"` is the macOS process
name. On Windows, the Lightroom Classic process is named `Lightroom.exe`. Catching
`FileNotFoundError` and continuing means Windows users get no process guard at all — they can
corrupt the catalog by running the tool while Lightroom is open.

**Why it happens:** The code was written macOS-first. The silent fallback was intentional for
environments without `pgrep`, but it leaves Windows users unprotected.

**Consequences:** HIGH — catalog corruption risk if the user runs `lrc-auto apply` while Lightroom
Classic is open on Windows.

**Prevention:** Replace `pgrep` with `psutil.process_iter()`, which is a declared dependency target
for v0.6.0:
```python
import psutil

def _is_lightroom_running() -> bool:
    lr_names = {"Adobe Lightroom Classic", "Lightroom.exe", "lightroom"}
    return any(
        p.info["name"] in lr_names
        for p in psutil.process_iter(["name"])
        if p.info["name"]
    )
```
Add `psutil` to `pyproject.toml` dependencies (not optional — it is a safety invariant).

**Detection:** Unit test that monkeypatches `psutil.process_iter` to return a fake LR process and
asserts `LightroomRunningError` is raised.

**Phase:** Phase 1 (foundation) — safety invariant, must be first.

---

### Pitfall 3: String Concatenation for Full Paths Breaks on Windows

**What goes wrong:** Multiple files use raw string concatenation to build full file paths:
- `scanner.py`: `full_folder = photo.root_absolute_path + photo.current_folder_path`
- `utils.py`: `build_full_path()` does `f"{root_absolute}{path_from_root}{base_name}.{extension}"`

On macOS, `root_absolute_path` from the catalog ends with `/` (e.g. `/Volumes/photo/2023/`),
so concatenation works. On Windows, `absolutePath` in `AgLibraryRootFolder` ends with `\` or `/`
inconsistently depending on the Lightroom version and OS. `pathFromRoot` uses `/` as separator
even on Windows catalogs. The result is a mixed-separator string that `Path()` may misinterpret.

**Why it happens:** Lightroom itself stores `absolutePath` with the OS-native separator when the
catalog was created on Windows (e.g. `C:\Users\Photos\`), and `pathFromRoot` uses forward slashes
(`2023/06/`). Concatenation produces `C:\Users\Photos\2023/06/` — a mixed path.

**Consequences:** `Path(mixed_path).exists()` may work on Windows (NTFS accepts both), but
`extract_date_from_path()` splits on `/` only, so it fails to parse segments from
`C:\Users\Photos\2023/06/` — returning `None` and causing photos to be incorrectly classified as
"no date found, skip".

**Prevention:**
- In `PhotoRecord.full_path` (models.py), reconstruct using `Path(root_absolute_path) /
  path_from_root / f"{base_name}.{extension}"` instead of string concatenation.
- In `extract_date_from_path()` and any path-segment logic, normalise separators before splitting:
  `full_path.replace("\\", "/")`.
- Add a test with a Windows-style `absolutePath` (`C:\Users\Photos\`) and verify date extraction
  still returns the correct year/month.

**Detection:** Test with a catalog fixture that uses Windows-style `absolutePath` values.

**Phase:** Phase 1 (path normalisation) — affects scan, plan, validate, reconcile.

---

### Pitfall 4: `path_from_root` Stored with Forward Slashes — Catalog SQL Mismatch

**What goes wrong:** The executor stores `path_from_root` values into `AgLibraryFolder.pathFromRoot`
using string operations. On macOS, these always use `/`. But when creating new folders on Windows
(`executor.py:_create_folders`), `Path(root_path) / path_from_root` resolves to a Windows path
with backslashes. If the string is then derived from `str(full_dir.relative_to(root_path))`, the
`pathFromRoot` value stored in the catalog will contain backslashes on Windows. Lightroom then
cannot find the folder because it stores and queries `pathFromRoot` with forward slashes.

**Why it happens:** `str(Path(...).relative_to(...))` on Windows returns backslashes.
`cleanup_empty_folders()` in executor.py uses exactly this pattern:
`path_from_root = str(rel) + "/"`.

**Consequences:** After an `apply` run on Windows, Lightroom shows folders as "missing" because
the `pathFromRoot` value in the catalog is `2023\06\` instead of `2023/06/`.

**Prevention:** Wherever a `pathFromRoot` string is derived from a `Path` object, use
`rel.as_posix() + "/"` instead of `str(rel) + "/"`. Apply this consistently in
`_cleanup_empty_folders()` and any new folder creation logic.

**Detection:** Executor test that verifies the `pathFromRoot` column value uses only `/` separators
after execution on a mock Windows-style catalog.

**Phase:** Phase 2 (executor / SQL writes) — critical correctness.

---

### Pitfall 5: `shutil.move` Cross-Drive Failure + Antivirus PermissionError

**What goes wrong:** `executor.py:_apply_file_op()` uses `shutil.move(str(src), str(dst))`.
On Windows, `shutil.move` internally calls `os.rename` first; if source and destination are on
different drives, `os.rename` raises `OSError: [WinError 17] The system cannot move the file to
a different disk drive`. `shutil.move` then falls back to copy+delete, which can fail with
`PermissionError: [WinError 32]` if Windows Defender or another antivirus scanner has a handle on
the newly copied file before the delete step.

Additionally, `os.rename` on Windows is not guaranteed to be atomic. Between the copy and delete,
a crash leaves an orphaned copy at the destination with no source.

**Why it happens:** NTFS does not support cross-volume renames. Windows real-time antivirus
(Defender) routinely holds temporary locks on files immediately after they are written.

**Consequences:** A file is copied to the destination but not deleted from the source. The rollback
action (`partial(op, dst, src)`) tries to move back — but the source still exists, so the move
back fails silently (`contextlib.suppress(OSError)`). The catalog is updated but the disk has two
copies. Lightroom will show the file in the new location but the old file remains on disk, wasting
space and potentially confusing subsequent scans.

**Prevention:**
1. Wrap cross-drive moves with a retry loop (1-2 retries, 100ms delay) to handle transient
   antivirus locks.
2. After `shutil.move`, verify the destination exists and source does not before updating the
   catalog. Log and raise `SkippableError` if the state is ambiguous.
3. Document that cross-drive operations (e.g. catalog on C: and photos on D:) require Defender
   real-time protection exceptions or the `--dry-run` flag for first validation.

**Detection:** Mock `shutil.move` to raise `OSError(17, ...)` and assert the executor falls back
gracefully without catalog corruption.

**Phase:** Phase 2 (executor) — needs explicit Windows path in test matrix.

---

### Pitfall 6: `os.rename` Semantics Differ — Windows Does Not Allow Overwrite

**What goes wrong:** `executor.py:_apply_file_op()` uses `os.rename` for in-place renames. The
code first checks `if dst.exists(): raise SkippableError(...)`, which prevents most overwrites.
However, on Windows, `os.rename(src, dst)` raises `FileExistsError` if `dst` exists — unlike
POSIX where it atomically replaces. This means a race condition (two concurrent processes, or a
sidecar whose XMP already exists at the target) can raise an unhandled `FileExistsError` that
escapes the `SkippableError` guard.

**Why it happens:** POSIX `rename(2)` is atomic and replaces the target. `MoveFileEx` on Windows
requires an explicit `MOVEFILE_REPLACE_EXISTING` flag, which Python's `os.rename` does not set.

**Prevention:** Use `Path.rename()` with an explicit pre-check, or switch to `os.replace()` for
cases where overwrite is intentional (xmp sidecars). Keep the `SkippableError` guard for the main
photo file.

**Phase:** Phase 2 (executor).

---

## Moderate Pitfalls

Mistakes that cause test failures, incorrect behaviour in edge cases, or developer friction.

---

### Pitfall 7: `Path.as_posix()` on Absolute Windows Paths Omits Drive Letter in URI Context

**What goes wrong:** `Path("C:/Users/foo").as_posix()` returns `"C:/Users/foo"`. SQLite URI mode
requires `file:///C:/Users/foo` (triple slash before drive letter on Windows). Using
`f"file:{path.as_posix()}"` produces `file:C:/Users/foo` — two slashes missing, which SQLite
rejects.

**Prevention:** Build URI with a helper:
```python
def path_to_sqlite_uri(path: Path, readonly: bool = False) -> str:
    posix = path.as_posix()
    # Absolute Windows path: "C:/..." needs "///C:/..."
    # Absolute POSIX path: "/home/..." needs "///home/..."
    uri = f"file:///{posix}" if path.is_absolute() else f"file:{posix}"
    if readonly:
        uri += "?mode=ro"
    return uri
```

**Phase:** Phase 1 (catalog.py URI construction).

---

### Pitfall 8: GitHub Actions Windows Runner — `make` Not Available

**What goes wrong:** The current CI runs `make check`. The `windows-latest` GitHub Actions runner
does not have GNU Make installed by default. The `ci.yml` workflow will fail immediately on the
Windows matrix entry with `'make' is not recognized`.

**Prevention:** Either:
- Install `make` via chocolatey: `choco install make` as a CI step, or
- Replace the `make check` call with explicit `uv run` commands in the Windows matrix step:
  ```yaml
  - name: Lint + typecheck + test (Windows)
    if: runner.os == 'Windows'
    run: |
      uv run ruff check .
      uv run mypy src/
      uv run pytest -v
  ```
The `uv run ruff format --check` step needs awareness that Windows paths in error messages differ.

**Phase:** Phase 3 (CI matrix expansion).

---

### Pitfall 9: GitHub Actions Windows Runner — CRLF Line Endings in Checked-Out Files

**What goes wrong:** `actions/checkout@v4` on Windows defaults `core.autocrlf=true`, which
converts LF to CRLF in checked-out text files. This affects `.env.example`, fixture files, and
any file read by tests. `ruff format --check` will report formatting differences on files that
were LF on macOS. Tests that read file content and compare strings may fail on trailing `\r`.

**Prevention:**
- Add `.gitattributes` with `* text=auto eol=lf` to force LF in the repo and on checkout.
- Or set `git config core.autocrlf false` in the CI step before checkout.

**Phase:** Phase 3 (CI matrix) — set up `.gitattributes` in the same phase.

---

### Pitfall 10: `reverse_geocoder` Binary Wheel Availability on Windows

**What goes wrong:** The optional `[geo]` extra uses `reverse_geocoder`, which ships compiled
C extensions. Binary wheels are available for common Python versions on Windows, but if the exact
Python version in the CI matrix is not covered, `uv sync --all-extras` will attempt to compile
from source — which requires a C compiler (MSVC or MinGW). GitHub Actions `windows-latest` has
MSVC available but the compile adds 5-10 minutes to CI and may fail on version mismatches.

**Prevention:** Pin `reverse_geocoder` to a version with known Windows wheels for Python 3.12/3.13,
or gate the geo extra out of the Windows CI matrix if wheels are unavailable:
```yaml
- run: uv sync  # base only on Windows
  if: runner.os == 'Windows'
- run: uv sync --all-extras  # with geo on Linux/macOS
  if: runner.os != 'Windows'
```

**Phase:** Phase 3 (CI matrix).

---

### Pitfall 11: `scan_year_in_year_photos()` Hardcodes `/` as Path Separator

**What goes wrong:** `scanner.py:scan_year_in_year_photos()` does:
```python
root_year_str = photo.root_absolute_path.rstrip("/").split("/")[-1]
path_year_str = photo.current_folder_path.split("/")[0]
```
On a Windows catalog, `root_absolute_path` may be `C:\Lightroom\2023\` (backslash). The `rstrip`
and `split("/")` calls will produce `C:\Lightroom\2023\` unsplit — last segment would be `""` after
rstrip, or the whole string. Year detection silently returns no results.

**Prevention:** Normalise separator before splitting: `path.replace("\\", "/")`.
Apply this to all path-segment operations in `scanner.py` and `utils.py`.

**Phase:** Phase 1 (path normalisation).

---

### Pitfall 12: SQLite WAL Mode — Windows Holds Locks After `close()`

**What goes wrong:** If a future version of lrc-automation enables WAL journal mode (`PRAGMA
journal_mode=WAL`) for performance, a known Windows-specific SQLite bug holds file locks on the
`.lrcat` file beyond `close()`. This leaves the `.lrcat-wal` and `.lrcat-shm` files open, which
blocks Lightroom from opening the catalog.

**Why it matters now:** The current code uses the default journal mode (DELETE/ROLLBACK), which
does not have this problem. But any future optimisation that enables WAL must be tested on Windows
before shipping.

**Prevention:** Do not enable WAL mode in v0.6.0. Document in code comments that WAL mode is
contraindicated on Windows for this use case. Add a test that verifies journal mode is not WAL
after the connection is opened.

**Phase:** Out of scope for v0.6.0, but flag in architecture docs.

---

### Pitfall 13: Default Catalog Path Discovery Differs Per Platform

**What goes wrong:** The CLI requires `--catalog` / `LRC_CATALOG_PATH`. If a future enhancement
adds auto-discovery of the default catalog location, the paths differ significantly:
- macOS: `~/Pictures/Lightroom/Lightroom Catalog-v13-3.lrcat`
- Windows: `%USERPROFILE%\Pictures\Lightroom\Lightroom Catalog-v13-3.lrcat`
  (or `C:\Users\<user>\Pictures\Lightroom\...`)
- Linux: No standard path (Lightroom Classic does not run natively on Linux)

Using `Path.home() / "Pictures" / "Lightroom"` is correct for both macOS and Windows because
`pathlib` maps `~` correctly on both platforms.

**Prevention:** Use `Path.home() / "Pictures" / "Lightroom"` as the base for auto-discovery. Never
hardcode `/` separator in path construction; always use `Path` division operator.

**Phase:** Phase 4 (default path discovery).

---

## Minor Pitfalls

---

### Pitfall 14: `AppleDouble` Cleanup Logic Running on Windows

**What goes wrong:** `executor.py:cleanup_empty_folders()` and `_is_effectively_empty()` contain
logic to detect and delete `._*` AppleDouble files. On Windows, this logic is harmless (no such
files exist), but calling `entry.name.startswith("._")` on entries that don't exist produces no
error — the function just returns `True` for the "effectively empty" check on genuinely empty
directories. However, Windows Thumbs.db files (hidden system files) are not filtered, so a
directory that only contains `Thumbs.db` would be considered "not effectively empty" and not
removed.

**Prevention:** Extend `_is_effectively_empty()` to also skip Windows thumbnail/metadata files:
```python
_SKIP_NAMES = frozenset({"Thumbs.db", "desktop.ini", ".DS_Store"})

def _is_effectively_empty(directory: Path) -> bool:
    for entry in directory.iterdir():
        if entry.name.startswith("._") or entry.name in _SKIP_NAMES:
            continue
        return False
    return True
```

**Phase:** Phase 2 (platform-aware cleanup).

---

### Pitfall 15: `Path.suffix` Comparison is Case-Sensitive on POSIX, Not on Windows

**What goes wrong:** `cli.py` checks `catalog_path.suffix != ".lrcat"`. On Windows, a user might
pass `Catalog.LRCAT` and `Path.suffix` returns `".LRCAT"`, so the check fails with a misleading
error (`"File must have .lrcat extension"`). On macOS/Linux, the same input would also fail — but
on Windows the filesystem itself is case-insensitive, so the file exists and opens fine; only the
validation rejects it.

**Prevention:** `catalog_path.suffix.lower() != ".lrcat"` in `cli.py` and `validate_is_lrcat()`.

**Phase:** Phase 1 (trivial, low risk).

---

### Pitfall 16: `uv sync` Lockfile Incompatibility Between macOS and Windows

**What goes wrong:** `uv.lock` is generated on macOS. When `uv sync` runs on Windows in CI with
`--frozen`, it may fail if any locked dependency has a platform marker that doesn't match the
Windows runner. The `pyproject.toml` likely does not yet declare `[tool.uv] environments` to cover
both platforms.

**Prevention:** After adding `psutil` and any Windows-specific dependencies, run
`uv lock` on both platforms (or use `uv lock --python-platform windows-x86_64`) to ensure the
lockfile covers both platforms. Commit the updated `uv.lock`.

**Phase:** Phase 3 (CI).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| catalog.py URI construction | SQLite `file:` URI needs forward slashes + correct leading slashes | Use `path.as_posix()` with URI helper |
| Process detection refactor | `pgrep` silently skipped, leaving Windows users unprotected | Replace with `psutil.process_iter()` as a hard dependency |
| Path string concatenation (scanner, utils) | Mixed separators break date extraction on Windows catalogs | Normalise `\\` to `/` before all segment operations |
| executor.py pathFromRoot writes | `str(rel)` on Windows yields backslashes stored in catalog | Use `rel.as_posix()` everywhere a path segment goes into SQL |
| executor.py file moves | Cross-drive `shutil.move` fails or leaves ghost copies with antivirus | Add retry + post-move verification |
| executor.py `os.rename` for sidecars | Windows raises `FileExistsError` on overwrite instead of replacing | Use `os.replace()` for sidecar XMP conflicts |
| CI workflow expansion | `make` not available on `windows-latest` runner | Inline `uv run` commands for Windows matrix |
| CI checkout | CRLF conversion breaks `ruff format --check` | Add `.gitattributes` with `eol=lf` |
| `[geo]` extra in CI | `reverse_geocoder` may not have Windows wheels for all Python versions | Gate `--all-extras` to non-Windows runners or verify wheel availability |
| Default catalog path | `%USERPROFILE%` vs `~` expansion | Use `Path.home() / "Pictures" / "Lightroom"` |
| WAL mode (future) | Windows SQLite holds locks after `close()` | Document: do not enable WAL on Windows |

---

## Sources

- Python docs — pathlib: https://docs.python.org/3/library/pathlib.html
- SQLite URI filenames: https://sqlite.org/uri.html
- Microsoft Learn — Maximum Path Length: https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
- psutil cross-platform process iteration: https://psutil.readthedocs.io/
- SQLite WAL Windows lock bug: https://github.com/oven-sh/bun/issues/25964
- shutil.move file-in-use on Windows: https://github.com/python/cpython/issues/120882
- WinError 17 cross-drive move: https://github.com/pypa/pip/issues/2859
- uv GitHub Actions integration: https://docs.astral.sh/uv/guides/integration/github/
- astral-sh/setup-uv action: https://github.com/astral-sh/setup-uv
- GitHub Actions CRLF issue: https://github.com/actions/checkout/issues/135
- Lightroom Windows absolutePath format: https://www.lightroomqueen.com/community/threads/problems-using-same-catalog-in-windows-11-and-macbook-environments.49507/
- SQLite URI path confusion Flask/SQLAlchemy: https://www.pythontutorials.net/blog/confusion-about-uri-path-to-configure-sqlite-database/
- pathlib PureWindowsPath comparison: https://github.com/python/cpython/issues/104947
