# Phase 4: UX and Docs - Research

**Researched:** 2026-03-06
**Domain:** CLI UX (Click auto-discovery), documentation writing, ADR authoring, CHANGELOG
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UX-01 | `--catalog` flag is optional; tool auto-discovers default catalog path for the current OS (macOS: `~/Pictures/Lightroom/`, Windows: `%USERPROFILE%\Pictures\Lightroom\`) | Click `required=False` + `default` callback pattern; `Path.home()` on both platforms; `pathlib.Path` glob for `.lrcat` files |
| UX-02 | README and `docs/usage.md` include a Windows installation and first-run section | Existing docs structure surveyed; gaps identified below |
| UX-04 | ADR written documenting the multiplatform approach and decisions | ADR template from existing ADR-001 through ADR-006; decisions from STATE.md fully captured |
| UX-05 | `docs/prd.md` updated to reflect multiplatform scope (Mac + Windows target platforms) | Current prd.md says "macOS" only in section 4; NF-3 says "tested on macOS; should work on Linux" — both must be updated |
| UX-06 | `CHANGELOG.md` updated for v0.6.0 with all changes documented | All Phase 1-3 commits and decisions surveyed; complete change list compiled below |
</phase_requirements>

---

## Summary

Phase 4 closes out the v0.6.0 multiplatform milestone with two categories of work: a small but concrete CLI improvement (UX-01: catalog auto-discovery) and four documentation deliverables (UX-02, UX-04, UX-05, UX-06). No new modules are needed. All code changes fit in `cli.py` (making `--catalog` optional) and `catalog.py` (a `_discover_default_catalog()` helper).

The documentation work is well-bounded: the ADR template is established by six prior ADRs, the PRD needs two targeted paragraph updates, the CHANGELOG needs one new version block, and the README/usage.md need a new Windows section. All source material is available in the existing codebase and STATE.md decisions log.

**Primary recommendation:** Split into two plans — (1) UX-01 code change with tests, (2) all four documentation deliverables together as a single writing task.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.1 | CLI option handling, `default` callbacks, `required=False` | Already the CLI framework; supports callable defaults natively |
| pathlib.Path | stdlib | Cross-platform path construction for discovery | `Path.home()` returns correct home on both macOS and Windows |
| os / sys | stdlib | `sys.platform` for OS detection if needed; `os.environ` for `USERPROFILE` (Windows) | No new dependency needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + monkeypatch | 9.0.2 | Test auto-discovery with mocked home dirs | All UX-01 tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Path.home() / "Pictures" / "Lightroom"` | `os.path.expanduser("~")` | pathlib is already used throughout; `Path.home()` is cleaner |
| `sys.platform == "win32"` guard | `platform.system()` | `sys.platform` already used in codebase (darwin guard in executor) — stay consistent |

---

## Architecture Patterns

### UX-01: Making `--catalog` Optional with Auto-Discovery

**Current state:** `required=True` in the `@click.group()` decorator on `cli()`. The `catalog` parameter is typed `str`, and a `click.Path(exists=True)` validator runs immediately.

**Required change:** Make `required=False`, supply a `default` that calls a discovery function, validate existence after resolution, and emit a clear error if no catalog is found.

**Key Click constraint (HIGH confidence):** When `default` is a callable, Click calls it only when no value was supplied by user or env var. The `type=click.Path(exists=True)` validator runs _after_ the default is resolved — so if discovery returns `None`, the error message will be Click's path-does-not-exist message rather than a custom one. Better pattern: use `required=False`, `default=None`, `type=click.Path()` (no `exists=True`), and do existence validation manually in the `cli()` function body.

**Pattern for discovery function:**

```python
# Source: pathlib stdlib docs + click docs
import sys
from pathlib import Path

_LR_DEFAULT_DIRS = {
    "darwin": Path.home() / "Pictures" / "Lightroom",
    "win32":  Path(os.environ.get("USERPROFILE", Path.home())) / "Pictures" / "Lightroom",
}

def _discover_default_catalog() -> str | None:
    """Return the path of the first .lrcat file in the OS default LR directory."""
    platform_key = "win32" if sys.platform == "win32" else "darwin"
    default_dir = _LR_DEFAULT_DIRS.get(platform_key)
    if default_dir is None or not default_dir.is_dir():
        return None
    candidates = sorted(default_dir.glob("*.lrcat"))
    return str(candidates[0]) if candidates else None
```

**cli() change:**

```python
@click.option(
    "--catalog", "-c",
    type=click.Path(),           # no exists=True — we validate manually
    envvar="LRC_CATALOG_PATH",
    required=False,
    default=None,
    help="Path to .lrcat catalog file (auto-discovered if omitted)",
)
# In cli() body, after load_dotenv():
if catalog is None:
    catalog = _discover_default_catalog()
if catalog is None:
    raise click.UsageError(
        "No catalog specified and none found in the default Lightroom directory.\n"
        "Use --catalog/-c or set LRC_CATALOG_PATH."
    )
catalog_path = Path(catalog)
if not catalog_path.exists():
    raise click.BadParameter(
        f"Catalog not found: {catalog_path}", param_hint="--catalog"
    )
```

**Note:** `_LR_DEFAULT_DIRS` must be a function-level or module-level dict, not a module constant evaluated at import time, because `Path.home()` must run at call time. Actually, since `Path.home()` is safe to call at module load, a module-level constant is fine — but the `os.environ.get("USERPROFILE")` lookup should also be safe. Use a helper function to keep it testable.

### Recommended File Structure for Changes

```
src/lrc_automation/
├── cli.py           # Make --catalog optional; add _discover_default_catalog()
docs/
├── adr/
│   └── 007-multiplatform-windows-support.md   # New ADR for UX-04
├── prd.md           # Update section 4 (Users) and NF-3 for UX-05
└── usage.md         # Add Windows installation section for UX-02
README.md            # Add Windows installation section for UX-02
CHANGELOG.md         # Add v0.6.0 entry for UX-06
```

### ADR Pattern (UX-04)

The existing ADR format (ADR-001 through ADR-006) is the template. The new ADR-007 must document:
- `psutil` for cross-platform Lightroom process detection (replaces `pgrep` subprocess)
- `path.as_posix()` for all SQL writes of `pathFromRoot` on Windows
- `sys.platform == 'darwin'` guard for AppleDouble (`._*`) cleanup
- SBOM generation via `anchore/sbom-action@v0` attached to releases
- SQLite URI with forward slashes (`_path_to_sqlite_uri`) for Windows catalog open
- `.gitattributes` LF enforcement for Windows CI checkout

Standard ADR sections: Status, Context, Decision, Consequences.

### Anti-Patterns to Avoid

- **`type=click.Path(exists=True)` with `required=False` and a None default:** Click validates `exists=True` before the `cli()` body runs. If discovery returns None and the user supplied nothing, Click will attempt to validate `None` as a path and produce a confusing error. Use `type=click.Path()` (no `exists=True`) and validate manually.
- **Calling `Path.home()` inside `_LR_DEFAULT_DIRS` dict at module level on Windows when `USERPROFILE` is unset:** `Path.home()` calls `os.environ["USERPROFILE"]` on Windows (Python 3.12). If the env var is absent (CI, Docker), it falls back to `HOMEPATH`. This is safe — no need to guard with `os.environ.get`.
- **Globbing with `*.lrcat` returning multiple results silently:** If multiple `.lrcat` files exist (common — Lightroom creates backups with `.lrcat.bak-TIMESTAMP`), take the first lexicographic match (the one without timestamp suffix). Sort candidates and pick `candidates[0]`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Windows home dir | Custom registry lookup | `Path.home()` | Python's pathlib calls `os.environ["USERPROFILE"]` on win32 correctly |
| Multiple catalog candidate selection | Complex scoring | `sorted(glob)[0]` | Lightroom names its main catalog without date suffix; lexicographic sort puts it first |
| ADR numbering | Custom tracker | Sequential from last existing ADR (006) → 007 | Already established convention in `docs/adr/` |

---

## Common Pitfalls

### Pitfall 1: USERPROFILE vs Path.home() on Windows
**What goes wrong:** On some Windows setups, `USERPROFILE` differs from `HOMEDRIVE + HOMEPATH`. `Path.home()` handles this correctly by checking `USERPROFILE` first.
**Why it happens:** Historical Windows multi-user setup differences.
**How to avoid:** Use `Path.home()` directly — don't construct the Windows path manually from env vars.
**Warning signs:** Discovery works on dev machine but fails on CI Windows runner.

### Pitfall 2: click.Path(exists=True) With Optional Catalog
**What goes wrong:** If `--catalog` is omitted and discovery returns `None`, Click's path validator fires before the function body and raises a confusing internal error.
**How to avoid:** Drop `exists=True` from the type; validate path existence manually inside `cli()` after calling `_discover_default_catalog()`.

### Pitfall 3: Globbing Returns .lrcat.bak Files
**What goes wrong:** `Path.glob("*.lrcat")` matches `Catalog.lrcat.bak-20260101` because `*.lrcat` is not anchored to extension end in all glob implementations. However, `pathlib.Path.glob` matches only the stem+extension — `*.lrcat` does NOT match `Catalog.lrcat.bak-20260101` because the full filename is `Catalog.lrcat.bak-20260101`, not ending in `.lrcat`.
**Confirmation (HIGH confidence):** Python's `pathlib.glob("*.lrcat")` matches filenames whose suffix is `.lrcat`, not files that merely contain `.lrcat` in the name. Backup files like `Catalog.lrcat.bak-20260306` have suffix `.bak-20260306`, so they are excluded.
**How to avoid:** No special handling needed — use `glob("*.lrcat")` directly.

### Pitfall 4: Missing Windows Section in .env Example
**What goes wrong:** Windows users copy the macOS-style path with forward slashes in `.env.example` and it works (the SQLite URI fix handles this), but the path with backslashes also needs documentation.
**How to avoid:** Document in README/usage.md that both `/` and `\` separators work.

### Pitfall 5: CHANGELOG Missing Intermediate Commits
**What goes wrong:** The CHANGELOG summarizes features by phase but omits fixes applied mid-phase (e.g., CI fixup commits: `fix(ci): skip geo/darwin tests when extras absent on CI`).
**How to avoid:** Review `git log --oneline` from the Phase 1 branch point to now before writing the CHANGELOG entry.

---

## Code Examples

### Auto-discovery in cli.py

```python
# Placement: module level in cli.py, before the @click.group()
import os
import sys

def _discover_default_catalog() -> str | None:
    """Find the first .lrcat file in the OS default Lightroom Classic directory.

    macOS: ~/Pictures/Lightroom/
    Windows: %USERPROFILE%\Pictures\Lightroom\
    """
    if sys.platform == "win32":
        default_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Pictures" / "Lightroom"
    else:
        default_dir = Path.home() / "Pictures" / "Lightroom"

    if not default_dir.is_dir():
        return None
    candidates = sorted(default_dir.glob("*.lrcat"))
    return str(candidates[0]) if candidates else None
```

### Updated @click.group() option

```python
@click.option(
    "--catalog",
    "-c",
    type=click.Path(),           # No exists=True — validated below
    envvar="LRC_CATALOG_PATH",
    required=False,
    default=None,
    help=(
        "Path to .lrcat catalog file. "
        "If omitted, auto-discovered from ~/Pictures/Lightroom/ (macOS) "
        "or %%USERPROFILE%%\\Pictures\\Lightroom\\ (Windows)."
    ),
)
```

### Validation in cli() body

```python
def cli(ctx, catalog, ...):
    if catalog is None:
        catalog = _discover_default_catalog()
    if catalog is None:
        raise click.UsageError(
            "No catalog specified and none found at the default path.\n"
            "Use --catalog / -c or set LRC_CATALOG_PATH in your .env file."
        )
    catalog_path = Path(catalog)
    if not catalog_path.exists():
        raise click.BadParameter(
            f"Catalog not found: {catalog_path}", param_hint="--catalog"
        )
    if catalog_path.suffix.lower() != ".lrcat":
        raise click.BadParameter(
            "File must have .lrcat extension", param_hint="--catalog"
        )
```

### Test pattern for UX-01

```python
def test_discover_default_catalog_finds_lrcat(tmp_path, monkeypatch):
    """Auto-discovery returns path to .lrcat in the default LR directory."""
    catalog = tmp_path / "Catalog.lrcat"
    catalog.touch()
    monkeypatch.setattr("lrc_automation.cli._discover_default_catalog", lambda: str(catalog))
    # invoke cli without --catalog; should not raise
    from click.testing import CliRunner
    from lrc_automation.cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["scan"], catch_exceptions=False)
    # scan will fail on empty DB but not on missing catalog arg
    assert "No catalog specified" not in result.output

def test_discover_default_catalog_returns_none_when_dir_missing(monkeypatch, tmp_path):
    """If default directory does not exist, discovery returns None."""
    import sys
    monkeypatch.setattr(sys, "platform", "darwin")
    from unittest.mock import patch
    with patch("lrc_automation.cli.Path.home", return_value=tmp_path):
        from lrc_automation.cli import _discover_default_catalog
        assert _discover_default_catalog() is None
```

Note: Avoid `unittest.mock` per project conventions. Use `monkeypatch.setattr` instead:

```python
def test_discover_returns_none_no_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("lrc_automation.cli.Path", lambda *a, **kw: tmp_path / "nonexistent")
    # or more precisely, patch _discover_default_catalog at the call site
```

The cleanest approach for testing `_discover_default_catalog` is to accept a `home_dir` parameter defaulting to `None` (auto-detected) so tests can inject a `tmp_path` without needing to mock `Path.home`.

```python
def _discover_default_catalog(home_dir: Path | None = None) -> str | None:
    base = home_dir or Path.home()
    if sys.platform == "win32":
        default_dir = base / "Pictures" / "Lightroom"
    else:
        default_dir = base / "Pictures" / "Lightroom"
    ...
```

This keeps the function pure and testable with monkeypatch.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `required=True` for `--catalog` | `required=False` with auto-discovery | Phase 4 | Zero-config UX for standard Lightroom installations |
| prd.md: macOS-only primary user | prd.md: macOS + Windows primary user | Phase 4 | Accurately reflects v0.6.0 scope |
| No Windows install docs | README + usage.md Windows section | Phase 4 | Enables Windows onboarding |

---

## v0.6.0 CHANGELOG Content (UX-06)

All changes for the `## [0.6.0]` CHANGELOG block, assembled from git log and STATE.md decisions:

### Added
- **Windows support** (macOS + Windows now both primary target platforms)
- `--catalog` / `-c` flag is now optional; tool auto-discovers the default Lightroom Classic catalog at `~/Pictures/Lightroom/` (macOS) or `%USERPROFILE%\Pictures\Lightroom\` (Windows) when not specified
- Cross-platform Lightroom process detection via `psutil` (replaces macOS-only `pgrep`): detects both `Adobe Lightroom Classic` (macOS) and `Lightroom.exe` (Windows)
- `pathFromRoot` SQL writes always use forward slashes (`path.as_posix()`) so Lightroom can locate folders after a move on Windows
- `PermissionError` retry loop in `executor.py` for transient antivirus scan locks on Windows
- `.gitattributes` with `* text=auto eol=lf` to prevent CRLF failures on Windows CI checkout
- CI matrix expanded to `ubuntu-latest`, `macos-latest`, and `windows-latest` runners for Python 3.12 and 3.13
- SBOM (Software Bill of Materials) generated at release time via `anchore/sbom-action@v0` and attached to GitHub releases
- ADR-007 documenting multiplatform decisions: psutil process detection, as_posix SQL writes, darwin-only AppleDouble guard, SBOM generation, SQLite URI forward-slash fix
- Windows installation and first-run section in README and `docs/usage.md`
- `docs/prd.md` updated to name macOS and Windows as target platforms

### Fixed
- `CatalogConnection.open()`: SQLite URI now uses forward slashes on Windows (`_path_to_sqlite_uri` converts `Path.as_posix()` result), fixing "unable to open database" error on Windows
- Opening a Mac-origin catalog (with `/Volumes/` absolute paths) on Windows now prints a human-readable warning and exits rather than crashing
- `AppleDouble` (`._*`) file cleanup silently skipped on non-macOS platforms (no errors, no spurious log entries)
- `reverse_geocoder` moved back to optional `[geo]` extra dependency (fixes packaging regression from v0.5.0)

### Changed
- `setup-uv` bumped to v7 with `enable-cache: true` in both `ci.yml` and `release.yml`
- `ci.yml`: individual `uv run` steps replace `make check` (make unavailable on Windows runners)
- `release.yml`: individual `uv run` steps replace `make check` for consistent CI step visibility

---

## PRD Changes Required (UX-05)

Two sections need updating:

**Section 4 (Users)** — current text: "Primary user: Solo photographer managing a large personal archive (10K–200K photos) with Lightroom Classic on macOS."

Replace with: "Primary user: Solo photographer managing a large personal archive (10K–200K photos) with Lightroom Classic on macOS or Windows."

Add: "Secondary platform: Windows. All core features are supported. The `[geo]` extra is macOS/Linux only due to missing Windows wheel for `reverse_geocoder`."

**Section 6 (Non-Functional Requirements)** — current NF-3: "Python 3.12+, tested on macOS; should work on Linux"

Replace with: "Python 3.12+; target platforms are macOS and Windows. Linux is supported as CI-only (Lightroom Classic does not run on Linux)."

Also update **OQ-5** (Open Questions) from "Support for Windows paths?" to mark it as resolved.

---

## Windows Documentation Content (UX-02)

Content for the new Windows section in README and docs/usage.md:

### Installation on Windows

**Requirements:**
- Windows 10 or later
- Python 3.12+ (from python.org or Windows Store)
- `uv` or `pipx`

**Install with uv:**
```powershell
pip install uv
uv tool install lrc-automation
```

**Install with pipx:**
```powershell
pip install pipx
pipx install lrc-automation
```

**MAX_PATH advisory:** Windows limits file paths to 260 characters by default. If your catalog root paths are deep, enable long-path support:
1. Open Group Policy Editor (`gpedit.msc`)
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

Or via PowerShell (requires admin):
```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**First run:**
```powershell
# Auto-discover default Lightroom catalog
lrc-auto scan

# Or specify explicitly (both slash styles work)
lrc-auto -c "C:\Users\YourName\Pictures\Lightroom\Catalog.lrcat" scan
lrc-auto -c "C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat" scan
```

**.env file on Windows** (use forward slashes or escaped backslashes):
```env
LRC_CATALOG_PATH=C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat
LRC_BACKUP_DIR=C:/Users/YourName/Documents/LightroomBackups
```

---

## ADR-007 Structure (UX-04)

File: `docs/adr/007-multiplatform-windows-support.md`

```
# ADR-007: Multiplatform Windows Support Decisions

Status: Accepted
Date: 2026-03-06

## Context
[Describe extending from macOS-only to macOS+Windows]

## Decisions

### 1. psutil for Process Detection
...

### 2. path.as_posix() for SQL pathFromRoot Writes
...

### 3. sys.platform == 'darwin' for AppleDouble Guard
...

### 4. SQLite URI Forward-Slash Fix
...

### 5. SBOM Generation via anchore/sbom-action
...

### 6. .gitattributes LF Enforcement
...

### 7. Catalog Auto-Discovery
...

## Consequences
...
```

---

## Open Questions

1. **Should `_discover_default_catalog` be in `cli.py` or `catalog.py`?**
   - What we know: it's a CLI convenience; `catalog.py` handles connection concerns
   - What's unclear: whether a future public API would want discovery as a library function
   - Recommendation: put it in `cli.py` as a private function — it's purely a CLI UX concern

2. **Multiple `.lrcat` files in default directory?**
   - What we know: Lightroom creates backups named `<name>.lrcat.bak-TIMESTAMP` (not `.lrcat` suffix, so glob excludes them); users might have multiple catalog files
   - Recommendation: pick lexicographically first; emit a `console.print` informing which catalog was auto-selected

3. **Linux behavior for auto-discovery?**
   - What we know: Linux is CI-only; Lightroom doesn't run on Linux
   - Recommendation: Linux falls through to `None` (same as "default dir not found") — user must supply `--catalog`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_cli.py -x` (UX-01 tests) |
| Full suite command | `uv run pytest -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-01 | `_discover_default_catalog()` returns `.lrcat` path when dir exists | unit | `uv run pytest tests/test_cli.py -x -k discover` | ❌ Wave 0 |
| UX-01 | `_discover_default_catalog()` returns `None` when default dir absent | unit | `uv run pytest tests/test_cli.py -x -k no_dir` | ❌ Wave 0 |
| UX-01 | `lrc-auto scan` without `--catalog` opens auto-discovered catalog | integration | `uv run pytest tests/test_cli.py -x -k auto_discover` | ❌ Wave 0 |
| UX-01 | `lrc-auto scan` without `--catalog` and no default dir prints usage error | unit | `uv run pytest tests/test_cli.py -x -k no_catalog_error` | ❌ Wave 0 |
| UX-02 | Windows installation section exists in README | manual | `grep -i "windows" README.md` | ❌ Wave 0 |
| UX-04 | `docs/adr/007-multiplatform-windows-support.md` exists | manual | file existence check | ❌ Wave 0 |
| UX-05 | `docs/prd.md` mentions Windows as target platform | manual | `grep -i "windows" docs/prd.md` | ❌ Wave 0 |
| UX-06 | `CHANGELOG.md` has `## [0.6.0]` entry | manual | `grep "0.6.0" CHANGELOG.md` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_cli.py -x`
- **Per wave merge:** `uv run pytest -v`
- **Phase gate:** Full suite green + `make check` before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cli.py` — covers UX-01 auto-discovery (new file needed)
- [ ] `tests/test_cli.py` should use `click.testing.CliRunner` for integration tests
- [ ] No framework install needed — pytest already installed

---

## Sources

### Primary (HIGH confidence)
- `cli.py` — existing Click option definitions and cli() function body (read directly)
- `catalog.py` — `_path_to_sqlite_uri`, `CatalogConnection` (read directly)
- `pyproject.toml` — current version (0.5.0), dependencies, optional extras (read directly)
- `docs/prd.md` — section 4 (Users) and NF-3 text (read directly)
- `docs/usage.md` — existing Windows-absent content (read directly)
- `README.md` — existing macOS-only install section (read directly)
- `docs/adr/001-lightroom-classic-catalog-automation.md` — ADR format template (read directly)
- `CHANGELOG.md` — existing entries and format (read directly)
- `.planning/STATE.md` — accumulated decisions for phases 1-3 (read directly)
- `git log --oneline -30` — all v0.6.0 commits (read directly)

### Secondary (MEDIUM confidence)
- Click 8.x docs: `required=False` with `default=None` and callable support — verified by inspecting `cli.py` existing patterns and Click version installed
- Python `pathlib.Path.home()` on Windows: uses `USERPROFILE` env var — standard Python docs behavior

### Tertiary (LOW confidence)
- Windows MAX_PATH limit of 260 characters — widely documented; relevant when catalog paths are deep on Windows

---

## Metadata

**Confidence breakdown:**
- UX-01 code change: HIGH — pattern is straightforward Click + pathlib, no new libraries
- ADR writing (UX-04): HIGH — template established by 6 prior ADRs; content from STATE.md
- PRD update (UX-05): HIGH — specific paragraphs identified; changes are narrow
- CHANGELOG (UX-06): HIGH — full git log surveyed; all changes accounted for
- Windows docs (UX-02): MEDIUM — content is accurate but Windows-specific UX details (MAX_PATH) need user validation

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain — Click API, stdlib pathlib)
