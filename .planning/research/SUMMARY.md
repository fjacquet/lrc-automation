# Project Research Summary

**Project:** lrc-automation — v0.6.0 Multiplatform (Mac + Windows)
**Domain:** Python CLI tool — Lightroom Classic catalog automation (SQLite + disk operations)
**Researched:** 2026-03-06
**Confidence:** HIGH

## Executive Summary

lrc-automation is a macOS-first Python CLI that directly manipulates Lightroom Classic's SQLite catalog and moves photos on disk. The v0.6.0 milestone extends the tool to Windows while maintaining the existing architecture. The scope is narrower than a typical greenfield port: only four targeted areas require change — process detection, SQLite URI construction, path separator handling for SQL writes, and platform-aware AppleDouble cleanup. The existing stack (click, rich, sqlite3, pathlib, ruff, mypy, pytest, uv) is correct and unchanged; the only new runtime dependency is psutil for cross-platform Lightroom process detection.

The recommended approach is surgical: targeted changes to existing modules (`catalog.py`, `constants.py`, `executor.py`, `cli.py`) rather than introducing a platform abstraction layer. The codebase's single-caller pattern for each platform concern does not justify a new module. Three of the six critical pitfalls affect Phase 1 and must be resolved before any write operations are tested on Windows: the SQLite URI backslash bug (tool is completely unusable until fixed), the silent `pgrep` failure (catalog corruption risk), and the string-concatenation path bug (silent wrong-date classification in scanner).

The highest-confidence risk is the SQLite URI path format: `f"file:{self.catalog_path}?mode=ro"` fails on Windows because `Path.__str__()` returns backslashes, and the SQLite URI protocol requires forward slashes. This is a blocking bug detectable in the first pytest run on Windows. The `path_from_root` forward-slash invariant (Lightroom always stores `/` in `pathFromRoot`, even on Windows) is confirmed by community reverse-engineering with medium-high confidence and means the existing pathlib path construction code requires no changes — only the places where new `pathFromRoot` values are written to the database (`str(rel) + "/"` must become `rel.as_posix() + "/"`) need fixing.

## Key Findings

### Recommended Stack

The existing stack is validated and requires only one addition. See [STACK.md](.planning/research/STACK.md) for full detail.

**Core technologies:**

- **psutil >=7.0.0**: cross-platform Lightroom process detection — replaces macOS-only `pgrep` subprocess call; ships binary wheels for Windows amd64/arm64, macOS, Linux; no C compiler needed
- **types-psutil >=7.0.0** (dev): mypy stubs for psutil in strict mode — required because project uses mypy strict
- **sys.platform (stdlib)**: platform branching — idiomatic in modern Python, no new library needed
- **pathlib.Path (stdlib)**: path construction from catalog strings — already correct; handles forward-slash catalog strings on Windows via `Path("C:/Users/...")` drive-letter parsing
- **astral-sh/setup-uv@v7**: GitHub Actions uv setup — current recommended version for CI matrix

**What NOT to add:** pywin32, platformdirs, plumbum, watchdog, colorama — none are needed for this milestone.

**Pre-existing inconsistency to fix:** `reverse_geocoder` appears in both `dependencies` and `[geo]` optional-dependencies. Remove from core `dependencies` as part of v0.6.0 cleanup.

### Expected Features

See [FEATURES.md](.planning/research/FEATURES.md) for full detail with technical notes.

**Must have (table stakes) — blocking for Windows users:**

- Cross-platform process detection (psutil) — safety-critical; without it, Windows users have no guard against running `apply` while Lightroom is open
- SQLite URI forward-slash fix — without it, the tool fails to open any catalog on Windows
- `path_from_root` forward-slash fix in executor.py — without it, Lightroom shows moved folders as "missing" after `apply`
- CI matrix: Windows runner — validates the above work before shipping
- Windows default catalog path documentation — low-effort onboarding improvement

**Should have (differentiators — UX improvements):**

- Catalog path auto-discovery (optional `--catalog`) — zero-config startup; currently requires explicit `--catalog` flag
- AppleDouble cleanup log clarity — cosmetic; `sys.platform` guard makes intent explicit on non-macOS
- Windows MAX_PATH documentation — advise `LongPathsEnabled` registry key for deep photo library paths

**Defer to v2+:**

- Automatic Mac→Windows path migration (`absolutePath` rewriting) — risks data loss; use Lightroom's own "Find Missing Folder" workflow
- Windows Registry integration for LR path — fragile, proprietary format
- GUI or installer — tool is CLI-first; `pipx install` is sufficient
- Linux desktop integration — LR Classic does not run on Linux natively; Linux support is CI-only
- Shadow copy / VSS integration — marginal safety gain over existing `shutil.copy2` backup

### Architecture Approach

The v0.6.0 multiplatform work touches four discrete modules with no cross-cutting concern warranting a new abstraction layer. Each platform concern has exactly one caller in the existing codebase, so targeted in-place changes are the correct pattern. The data flow from Lightroom catalog strings to concrete `Path` objects is already safe because Lightroom stores `absolutePath` and `pathFromRoot` with forward slashes universally — `pathlib.Path` handles these correctly on all platforms. See [ARCHITECTURE.md](.planning/research/ARCHITECTURE.md) for full detail.

**Modules modified and their changes:**

1. **catalog.py** — process detection rewrite (pgrep → psutil); SQLite URI forward-slash fix
2. **constants.py** — add `LR_PROCESS_NAME_MACOS`, `LR_PROCESS_NAME_WIN`; add `DEFAULT_CATALOG_PATHS` dict; keep `LR_PROCESS_NAME` as alias
3. **executor.py** — `sys.platform` guard on AppleDouble functions; `rel.as_posix()` instead of `str(rel)` for pathFromRoot SQL writes; Thumbs.db/desktop.ini skip in `_is_effectively_empty`
4. **cli.py** — `_default_catalog_path()` helper; `.suffix.lower()` check for `.lrcat` extension validation
5. **pyproject.toml** — add psutil to dependencies; add types-psutil to dev; remove reverse-geocoder from core dependencies
6. **.github/workflows/ci.yml** — OS matrix (ubuntu-latest, macos-latest, windows-latest); platform-conditional make/uv steps
7. **.gitattributes** — add `* text=auto eol=lf` to prevent CRLF corruption on Windows CI checkout

**Modules unchanged:** scanner.py, models.py, validators.py, utils.py, planner.py, reconciler.py, reporter.py

### Critical Pitfalls

See [PITFALLS.md](.planning/research/PITFALLS.md) for full detail including code examples and detection strategies.

1. **SQLite URI backslash bug** (`catalog.py`) — `f"file:{self.catalog_path}?mode=ro"` uses `str(Path)` which returns backslashes on Windows; SQLite URI requires forward slashes. Fix: use `path_to_sqlite_uri(path)` helper with `path.as_posix()` and `///` prefix for absolute paths. Blocks all catalog operations on Windows.

2. **Silent pgrep failure = no process guard on Windows** (`catalog.py`) — `pgrep` raises `FileNotFoundError` which is silently caught, so Windows users get no protection against running `apply` while Lightroom is open. High corruption risk. Fix: replace with `psutil.process_iter(["name"])` as a hard dependency.

3. **String concatenation path bug** (`scanner.py`, `utils.py`) — `root_absolute_path + path_from_root` produces mixed-separator strings on Windows catalogs where `absolutePath` uses backslashes. `extract_date_from_path()` splits on `/` only and silently misclassifies photos. Fix: use `Path(root_absolute_path) / path_from_root` everywhere; normalise `\\` to `/` before string-split operations.

4. **pathFromRoot backslash written to catalog** (`executor.py`) — `str(rel) + "/"` produces backslashes on Windows which are stored in `AgLibraryFolder.pathFromRoot`; Lightroom cannot find the folders. Fix: `rel.as_posix() + "/"` everywhere a path segment is stored in SQL.

5. **cross-drive shutil.move + antivirus PermissionError** (`executor.py`) — `shutil.move` fails with WinError 17 on cross-drive moves; falls back to copy+delete which antivirus can lock, leaving ghost copies. Fix: retry loop (1-2 retries, 100ms delay) + post-move verification; document Defender exclusion for catalog/photo directories.

6. **os.rename FileExistsError on Windows** (`executor.py`) — POSIX `rename(2)` atomically replaces; Windows raises `FileExistsError` on overwrite. Fix: use `os.replace()` for sidecar XMP conflicts; keep `SkippableError` guard for main photo files.

## Implications for Roadmap

Based on combined research, a four-phase structure is recommended. The phase order is dictated by hard technical dependencies: Phase 1 bugs block Windows usability entirely; Phase 2 bugs cause silent data corruption; Phase 3 is CI infrastructure; Phase 4 is UX polish.

### Phase 1: Foundation — Path Safety and Process Detection

**Rationale:** Three critical pitfalls (SQLite URI, pgrep silent failure, string concatenation) block all other functionality on Windows. These must be fixed and unit-tested before any write operations are validated. This phase has no dependencies on other phases.

**Delivers:** A lrc-auto tool that opens catalogs, detects Lightroom process, and correctly scans photo paths on Windows without data corruption.

**Addresses features:** Cross-platform process detection (table stakes), absolutePath correctness on Windows (table stakes)

**Changes:**

- `catalog.py`: Replace `subprocess.run(["pgrep"...])` with `psutil.process_iter(["name"])`; add `path_to_sqlite_uri()` helper using `path.as_posix()` with `///` prefix
- `constants.py`: Add `LR_PROCESS_NAME_MACOS`, `LR_PROCESS_NAME_WIN`; keep `LR_PROCESS_NAME` alias
- `pyproject.toml`: Add psutil >=7.0.0 to dependencies; add types-psutil to dev; remove reverse-geocoder from core
- `scanner.py` / `utils.py`: Replace string concatenation with `Path()` division; normalise `\\` to `/` before split operations
- `cli.py`: `.suffix.lower()` check for `.lrcat` extension validation

**Avoids:** Pitfall 1 (SQLite URI), Pitfall 2 (pgrep), Pitfall 3 (string concatenation paths), Pitfall 15 (case-insensitive suffix)

**Research flag:** Standard patterns — no additional research needed; psutil API is well-documented.

### Phase 2: Executor — Write Correctness on Windows

**Rationale:** Write operations (apply, reconcile, cleanup) have distinct Windows failure modes that require separate treatment after Phase 1 scan/read correctness is established. Executor changes are higher-risk (write to both disk and SQLite) and must be tested against the corrected foundation from Phase 1.

**Delivers:** Safe apply/reconcile/cleanup operations on Windows that correctly write `pathFromRoot` with forward slashes and handle cross-drive moves and sidecar conflicts.

**Addresses features:** path_from_root forward-slash fix (table stakes), platform-aware AppleDouble cleanup (table stakes)

**Changes:**

- `executor.py`: `rel.as_posix() + "/"` everywhere `pathFromRoot` is constructed from a `Path`; add `_IS_MACOS` module-level constant; guard AppleDouble functions with `sys.platform`; extend `_is_effectively_empty` to skip Thumbs.db / desktop.ini; retry loop for cross-drive `shutil.move`; `os.replace()` for sidecar XMP conflicts; post-move verification

**Avoids:** Pitfall 4 (pathFromRoot backslash), Pitfall 5 (cross-drive move + antivirus), Pitfall 6 (os.rename overwrite), Pitfall 14 (Thumbs.db blocking cleanup)

**Research flag:** Standard patterns — executor changes are mechanical; retry logic is well-understood.

### Phase 3: CI Matrix Expansion

**Rationale:** CI must validate Phases 1 and 2 on the actual Windows runner before shipping. Several infrastructure issues (make unavailability, CRLF line endings, uv.lock platform markers, geo extra wheel availability) must be addressed as a cohesive infrastructure change.

**Delivers:** Green CI on ubuntu-latest, macos-latest, windows-latest for Python 3.12 and 3.13. Prevents Windows regressions going forward.

**Changes:**

- `.github/workflows/ci.yml`: OS matrix; conditional make/uv steps for Windows; gate `--all-extras` to non-Windows runners
- `.gitattributes`: `* text=auto eol=lf` to prevent CRLF corruption
- `uv.lock`: regenerate with `uv lock` covering both platforms; verify psutil and reverse-geocoder wheel availability

**Avoids:** Pitfall 8 (make unavailable on Windows), Pitfall 9 (CRLF line endings), Pitfall 10 (reverse_geocoder wheel), Pitfall 16 (uv.lock platform incompatibility)

**Research flag:** May need to validate reverse_geocoder wheel availability for Python 3.12/3.13 on Windows before committing to `--all-extras` in CI. Check PyPI wheel list.

### Phase 4: Default Catalog Path and Documentation

**Rationale:** Pure UX improvement with no safety implications. Can be deferred if scope is a concern; the tool is functionally complete after Phase 3. Adding catalog auto-discovery removes the required `--catalog` flag for standard installations.

**Delivers:** Zero-config startup for standard Lightroom installations on both platforms. Windows-specific documentation section in README.

**Changes:**

- `cli.py`: `_default_catalog_path()` helper; make `--catalog` optional when default exists and file is found
- `constants.py`: `DEFAULT_CATALOG_PATHS` dict
- `docs/` / `README.md`: Windows install section (uv/pipx, .env syntax, MAX_PATH guidance, note that cleanup is macOS-primary)

**Avoids:** Pitfall 13 (default catalog path per platform)

**Research flag:** Standard patterns — no additional research needed.

### Phase Ordering Rationale

- Phase 1 before Phase 2: scan correctness must be established before write correctness is meaningful; SQLite URI bug blocks even read-only operations
- Phase 2 before Phase 3: CI must run against complete, correct code to produce meaningful pass/fail signal
- Phase 3 before Phase 4: confirm the tool works on Windows CI before adding UX polish
- Pitfalls 1, 2, 3 cluster naturally into Phase 1 (all affect read paths); Pitfalls 4, 5, 6, 14 cluster into Phase 2 (all affect write paths); Pitfalls 8, 9, 10, 16 cluster into Phase 3 (all are CI infrastructure)
- The WAL mode pitfall (Pitfall 12) is out of scope for v0.6.0 but should be documented in architecture comments to prevent accidental enablement

### Research Flags

Phases needing deeper research during planning:

- **Phase 3:** Validate `reverse_geocoder` wheel availability on PyPI for Python 3.12 and 3.13 on Windows before committing CI approach. Check with `uv pip install reverse-geocoder --python-platform windows-x86_64 --dry-run`.

Phases with standard patterns (skip research-phase):

- **Phase 1:** psutil API is extensively documented; pathlib behavior is Python stdlib with official docs; all patterns confirmed HIGH confidence
- **Phase 2:** executor changes are mechanical (as_posix, sys.platform guard, retry loop); patterns well-established in Python ecosystem
- **Phase 4:** Path.home() and Click option defaults are stdlib/framework patterns with official documentation

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | psutil 7.2.2 confirmed on PyPI with binary wheels; setup-uv@v7 confirmed current; all stdlib tools need no verification |
| Features | MEDIUM-HIGH | Table stakes list confirmed against existing codebase audit; Windows absolutePath format confirmed by multiple community sources (Lightroom Queen forums, migration blog posts) — not official Adobe docs |
| Architecture | HIGH | Module boundaries verified against codebase; psutil API verified against official docs; pathlib behavior is Python stdlib; single-caller rationale confirmed by code audit |
| Pitfalls | HIGH | Critical pitfalls grounded in direct codebase audit (actual line references provided); Windows-specific behaviors confirmed by CPython issue tracker and SQLite documentation |

**Overall confidence:** HIGH

### Gaps to Address

- **`Lightroom.exe` process name on Windows**: Confirmed from file.net process database (MEDIUM confidence). If process detection fails in Windows testing, also try case-insensitive match on `"lightroom"` and substring match on `proc.info["exe"]` path. The `psutil` `exe` attribute provides the full path, which is more reliable than process name.

- **absolutePath format on Windows catalogs created natively on Windows**: The forward-slash finding is confirmed from community reverse-engineering of Mac-created catalogs opened on Windows, and from cross-platform migration posts. A catalog created natively on Windows may store backslashes. Test with an actual Windows-created catalog during implementation; the path normalisation code in Phase 1 handles both cases.

- **reverse_geocoder wheel availability on Windows**: Not verified at research time. Needs explicit validation before Phase 3 CI setup. Gate `--all-extras` out of Windows CI if wheels are unavailable.

- **WAL mode documentation**: Not flagged in existing codebase comments. Should be added during Phase 2 to prevent future performance optimisations from accidentally enabling WAL mode on Windows.

## Sources

### Primary (HIGH confidence)

- [psutil documentation v7.x](https://psutil.readthedocs.io/) — process_iter API, attrs parameter, exception handling
- [psutil PyPI — v7.2.2](https://pypi.org/project/psutil/) — wheel availability confirmation
- [Python pathlib docs](https://docs.python.org/3/library/pathlib.html) — Path separator handling, as_posix(), drive letter parsing
- [SQLite URI filenames](https://sqlite.org/uri.html) — forward-slash requirement, `///` prefix for absolute paths
- [Adobe Lightroom Classic preference file locations](https://helpx.adobe.com/lightroom-classic/kb/preference-file-and-other-file-locations.html) — default catalog paths per platform
- [astral-sh/setup-uv GitHub](https://github.com/astral-sh/setup-uv) — v7 current recommendation
- [GitHub Actions matrix strategy](https://codefresh.io/learn/github-actions/github-actions-matrix/) — OS matrix patterns

### Secondary (MEDIUM confidence)

- [Lightroom Queen Forums — Semi OT Question re File path on Windows](https://www.lightroomqueen.com/community/threads/semi-ot-question-re-file-path-on-windows.43010/) — LR uses forward slashes in SQLite on Windows
- [Lightroom Queen Forums — Mac/Windows catalog problems](https://www.lightroomqueen.com/community/threads/problems-using-same-catalog-in-windows-11-and-macbook-environments.49507/) — cross-platform catalog migration challenges
- [billlee.photography — Fixing LR catalogs migrated Mac→Windows](https://billlee.photography/fixing-lightroom-catalogs-migrated-from-windows-to-mac/) — absolutePath format confirmed
- [file.net — Lightroom.exe process](https://www.file.net/process/lightroom.exe.html) — Windows process name
- [GitHub Actions windows-latest = Windows Server 2025](https://github.com/actions/runner-images/issues/12677) — runner image details, D:\ unavailability
- [shutil.move file-in-use on Windows](https://github.com/python/cpython/issues/120882) — antivirus PermissionError pattern
- [WinError 17 cross-drive move](https://github.com/pypa/pip/issues/2859) — cross-drive move failure mode

### Tertiary (LOW confidence)

- [Lightroom Classic Catalog Image File Reader (GitHub)](https://github.com/thatlarrypearson/LightroomClassicCatalogReader) — schema confirmation (third-party reader)

---
*Research completed: 2026-03-06*
*Ready for roadmap: yes*
