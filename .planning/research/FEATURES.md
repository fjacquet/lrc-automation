# Feature Landscape: Cross-Platform Support (v0.6.0)

**Domain:** Python CLI tool — Lightroom Classic catalog automation
**Milestone:** v0.6.0 Multiplatform (Mac + Windows)
**Researched:** 2026-03-06
**Scope:** Changes required to existing macOS features; not net-new product capabilities

---

## Context: What Already Works (macOS)

The following features exist and work correctly on macOS. This milestone changes
or adds platform-awareness to each:

| Existing Feature | macOS Status | Cross-Platform Challenge |
|-----------------|--------------|-------------------------|
| Process detection (`pgrep -f "Adobe Lightroom Classic"`) | Working | `pgrep` is POSIX-only; Windows uses `Lightroom.exe` |
| Lock file check (`.lrcat-lock`) | Working | Path is platform-neutral; no change needed |
| AppleDouble cleanup (`._*` files) | Working | macOS-only artifact; meaningless on Windows |
| Default catalog path (`~/Pictures/Lightroom/...`) | Working | Windows uses `%USERPROFILE%\Pictures\Lightroom\...` |
| `absolutePath` path construction from catalog | Working | Windows catalogs store `C:/Users/...` with forward slashes |
| `pathFromRoot` separator handling | Working | LR uses forward slashes on both OS; trailing slash preserved |
| Empty folder removal (`rmdir`) | Working | `pathlib` handles this cross-platform; no change needed |

---

## Table Stakes

Features users expect. Missing = the tool fails or silently corrupts data on Windows.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Cross-platform process detection** | Safety invariant — must not write while LR is open | Medium | Replace `subprocess.run(["pgrep", ...])` with `psutil.process_iter(attrs=["name","exe"])`. Windows exe is `Lightroom.exe`; macOS is `Adobe Lightroom Classic`. Lock file check already works on both. |
| **Windows default catalog path discovery** | `--catalog` is required; users need a sensible default or clear docs | Low | Windows default: `%USERPROFILE%\Pictures\Lightroom\Lightroom Catalog.lrcat`. Use `platformdirs.user_pictures_path() / "Lightroom"` or `Path.home() / "Pictures" / "Lightroom"`. macOS default already hard-coded in docs but not in CLI. |
| **`absolutePath` interpretation on Windows** | LR stores `C:/Users/name/Pictures/` (forward slashes, drive letter) | Medium | `Path("C:/Users/...")` works correctly in Python on Windows via `pathlib`. Drive letter preserved. The existing code uses `Path(root_path) / path_from_root` which is already correct — but must never call `.as_posix()` on the result when building real disk paths. Verify no string manipulation assumes POSIX separators. |
| **Platform-aware AppleDouble cleanup** | Running `cleanup` on Windows should not error or warn about `._*` files | Low | `._*` files are created by macOS on non-HFS+ volumes; they do not appear on native Windows NTFS. The `_is_effectively_empty` and `_delete_apple_double_files` functions already handle them as "skip if absent" — no Windows-specific failure path exists. Add a runtime platform guard so the cleanup docstring and log output reflect "macOS metadata files" only when `sys.platform == "darwin"`. |
| **CI matrix: Windows + Linux runners** | Without CI coverage, Windows regressions are invisible | Medium | Add `windows-latest` and `ubuntu-latest` to GitHub Actions matrix alongside existing macOS. Path separator tests, process detection tests, and cleanup tests all need to pass on Windows runners. |
| **Docs: Windows install and usage** | Without docs, Windows users cannot onboard | Low | Add Windows section to README: catalog path default, uv install on Windows, `.env` syntax with forward-slash paths, note that `cleanup` is primarily useful on macOS. |

---

## Differentiators

Features that go beyond table stakes and improve the Windows user experience.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Catalog path auto-discovery** | Zero-config startup: tool finds the catalog without `--catalog` flag | Medium | Scan platform-specific default locations in order: env var → well-known path → glob for `*.lrcat` in Pictures/Lightroom. Requires `platformdirs` or manual `Path.home()` logic. Currently `--catalog` is required; making it optional improves UX on both platforms. |
| **Mixed-separator path normalization** | Catalogs migrated Mac→Windows or vice versa may have inconsistent absolutePaths | High | When a Mac-origin catalog opens on Windows, `absolutePath` may still contain `/Volumes/...`. The tool should detect this mismatch (path root doesn't match current OS) and warn rather than crash. Attempting auto-repair is out of scope for v0.6.0. |
| **psutil as optional dependency** | Keeps base install lightweight; falls back gracefully if psutil absent | Low | Wrap psutil import in `try/except ImportError`. Without psutil: lock file check only (existing behavior). With psutil: full process detection. Document `pip install lrc-automation[process]` or bundle psutil unconditionally (simpler). |

---

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Automatic Mac→Windows path migration** | `absolutePath` differences between platforms are Lightroom's own reconciliation problem; auto-rewriting them risks data loss | Detect and warn; document the manual LR procedure (use "Find Missing Folder" in Lightroom) |
| **Windows Registry integration for LR path** | LR preferences are in Adobe-proprietary format; parsing the Registry adds fragile dependency | Use well-known filesystem defaults + env var override |
| **GUI or installer** | Tool is CLI-first for power users; installer complexity does not belong in this milestone | Provide `pipx install lrc-automation` instructions for Windows |
| **Linux desktop integration** | Lightroom Classic does not run on Linux natively; Linux support is about CI runners, not end-user installs | Test on Linux CI for import/syntax correctness only; document "Linux: not a supported runtime" |
| **Shadow copy / VSS integration on Windows** | Catalog backup already uses `shutil.copy2`; VSS adds significant complexity for marginal safety gain | Backup to a user-specified `--backup-dir`; rely on existing atomic copy |

---

## Feature Dependencies

```
Cross-platform process detection
  → psutil added to dependencies (or optional [process] extra)
  → Constants updated: LR_PROCESS_NAME split into per-platform names
  → catalog.py: check_lightroom_not_running() rewritten

Windows default catalog path
  → platformdirs added OR Path.home() logic inlined
  → CLI: --catalog becomes optional (defaults to platform path)
  → Tests: parametrize default-path resolution per platform

absolutePath correctness on Windows
  → executor.py: audit Path(root_path) / path_from_root uses (already pathlib)
  → scanner.py: audit any string .split("/") or os.sep assumptions
  → cleanup_empty_folders: path_from_root derivation uses str(rel) + "/" (POSIX style)
    -- this must match what LR stores (forward slash), not os.sep

CI matrix expansion
  → .github/workflows/ci.yml: add matrix.os: [ubuntu-latest, windows-latest, macos-latest]
  → Tests that invoke pgrep or platform paths need pytest.mark.skipif guards

Platform-aware AppleDouble
  → Existing functions already correct; add sys.platform guard to log/docstring only
  → No functional change needed for Windows correctness
```

---

## Key Technical Findings (from research)

### absolutePath Format on Windows

Lightroom Classic stores `absolutePath` in `AgLibraryRootFolder` using **forward slashes with a trailing slash**, even on Windows. Format is `C:/Users/<name>/Pictures/Lightroom/`. Drive letter is preserved. The `pathFromRoot` field in `AgLibraryFolder` also uses forward slashes. This means:

- `Path("C:/Users/name/Pictures/")` works correctly in Python on Windows.
- Existing code `Path(root_path) / path_from_root` is safe — `pathlib` handles both separators.
- `path_from_root` cleanup logic in `executor.py` uses `str(rel) + "/"` which produces OS-native separators. This needs a fix: it must produce `rel.as_posix() + "/"` to match LR's forward-slash convention on all platforms.
- **Confidence: MEDIUM** (confirmed by multiple Lightroom Queen forum posts; not from official Adobe docs).

### Process Names by Platform

| Platform | Process Name to Match |
|----------|-----------------------|
| macOS | `"Adobe Lightroom Classic"` (current `LR_PROCESS_NAME`) |
| Windows | `"Lightroom.exe"` (executable in `C:\Program Files\Adobe\Adobe Lightroom Classic CC\`) |

psutil pattern: `psutil.process_iter(attrs=["name", "exe"])`, match on `p.info["name"]` case-insensitively, or substring match on `p.info["exe"]`.

### Default Catalog Paths

| Platform | Default Catalog Path |
|----------|---------------------|
| macOS | `~/Pictures/Lightroom/Lightroom Catalog.lrcat` (or `-v13-3` variant for LR 13) |
| Windows | `%USERPROFILE%\Pictures\Lightroom\Lightroom Catalog.lrcat` |
| Linux | Not applicable (LR does not run on Linux) |

Use `platformdirs.user_pictures_path()` (returns `Path`) to get the platform Pictures folder reliably.

### AppleDouble Files

`._*` files are created by macOS when writing to non-HFS+ volumes (ExFAT, FAT32, SMB). They do **not** appear on native Windows NTFS volumes. The existing `_is_effectively_empty` implementation correctly skips them when present; on Windows they simply never appear. No Windows-specific failure mode exists. The only change needed is documentation and log clarity.

### Windows MAX_PATH

Python 3.12+ on Windows with the `LongPathsEnabled` registry key set handles paths beyond 260 characters via pathlib. Photo libraries can have deep paths. Document that Windows users should enable long paths. Do not add `\\?\` prefix workarounds — that is a last resort.

---

## MVP Recommendation

Prioritize in this order:

1. **Cross-platform process detection** (psutil) — safety-critical; blocking for Windows write operations
2. **`path_from_root` forward-slash fix in executor.py** — correctness bug on Windows; existing `str(rel) + "/"` produces backslashes on Windows, mismatching LR catalog
3. **CI matrix: Windows runner** — validates items 1 and 2 work before shipping
4. **Windows default catalog path docs** — low-effort UX improvement
5. **AppleDouble log clarity** — cosmetic; no functional issue

Defer:
- Catalog path auto-discovery (optional `--catalog`): useful but not blocking
- Mixed-separator path normalization: complex, affects migrated catalogs only
- psutil as optional extra: simplest to make it unconditional for v0.6.0

---

## Sources

- [Lightroom Classic preference file and other file locations (Adobe)](https://helpx.adobe.com/lightroom-classic/kb/preference-file-and-other-file-locations.html) — MEDIUM confidence (official Adobe docs, path defaults)
- [Lightroom Queen Forums — Semi OT Question re File path on Windows](https://www.lightroomqueen.com/community/threads/semi-ot-question-re-file-path-on-windows.43010/) — MEDIUM confidence (community-verified: LR uses "/" on Windows in SQLite)
- [Lightroom Queen Forums — Problems using same catalog in Windows 11 and MacBook](https://www.lightroomqueen.com/community/threads/problems-using-same-catalog-in-windows-11-and-macbook-environments.49507/) — MEDIUM confidence (cross-platform path migration challenges)
- [psutil documentation](https://psutil.readthedocs.io/) — HIGH confidence (official docs; cross-platform process iteration)
- [file.net — Lightroom.exe process](https://www.file.net/process/lightroom.exe.html) — MEDIUM confidence (Windows executable name)
- [platformdirs PyPI](https://pypi.org/project/platformdirs/) — HIGH confidence (official package; `user_pictures_path()` for cross-platform Pictures folder)
- [Python pathlib docs](https://docs.python.org/3/library/pathlib.html) — HIGH confidence (pathlib.Path handles OS separators automatically)
- [Python on Windows — removing the MAX_PATH limitation](https://runebook.dev/en/docs/python/using/windows/removing-the-max-path-limitation) — MEDIUM confidence (Python docs mirror; long paths on Windows)
- [Lightroom Classic Catalog Image File Reader (GitHub)](https://github.com/thatlarrypearson/LightroomClassicCatalogReader) — LOW confidence (third-party reader; useful for schema confirmation)
