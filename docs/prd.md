# Product Requirements Document: lrc-automation

**Version:** 0.6.1
**Date:** 2026-03-07
**Author:** fjacquet
**Status:** Living document

---

## 1. Problem Statement

Adobe Lightroom Classic stores photo metadata in a SQLite catalog (`.lrcat`) and organises files on disk in date-based folder hierarchies. Over years of use three classes of disorder accumulate:

1. **Misplaced photos** — photos filed in the wrong date folder because the import used file-system modification date rather than EXIF `DateTimeOriginal`.
2. **Duplicate date prefixes in filenames** — camera utilities prepend a date to filenames that already carry a date, producing names like `29122012-29122012-IMG_131334.jpg`.
3. **Loss of location context** — GPS-tagged photos land in anonymous date folders with no indication of where they were taken.
4. **Inconsistent filename date prefix format** — some files carry a European-order `DDMMYYYY` prefix (e.g. `02052002-volcan`) while the rest of the archive uses `YYMMDD`. This makes chronological sorting unreliable.

Lightroom Classic's Lua SDK provides no `moveToFolder()` API and cannot be used to fix these problems programmatically. Adobe's cloud APIs target Lightroom CC (cloud) and do not interact with local `.lrcat` catalogs.

---

## 2. Goals

| ID | Goal |
|----|------|
| G1 | Detect misplaced photos by comparing EXIF `captureTime` against the folder the photo currently lives in |
| G2 | Generate a dry-run plan so the user can review all proposed moves before anything is changed |
| G3 | Apply changes atomically: move files on disk and update the SQLite catalog in a single transaction |
| G4 | Keep the catalog link-complete at all times — no "missing photos" after a run |
| G5 | Optionally enrich target paths with `Country/City` subfolders derived from embedded GPS coordinates |
| G6 | Never lose data — mandatory backup before writes, full rollback on any error |
| G7 | Detect and propose normalisation of DDMMYYYY filename prefixes to YYMMDD, with GPS-based target folder suggestions |
| G8 | Audit every catalog record against disk and surface misplaced or missing files with a persistent log |
| G9 | Clean up empty directories and AppleDouble metadata files left behind after apply runs |
| G10 | Distribute as a standalone binary (no Python required) and as a Docker image, in addition to a Python package |

---

## 3. Non-Goals

- Real-time / background monitoring (run on demand only)
- Lightroom Classic plugin / in-app UI
- Support for Lightroom CC (cloud) catalogs
- Duplicate photo detection / deduplication
- AI-based photo tagging or scene classification

---

## 4. Users

**Primary user:** Solo photographer managing a large personal archive (10K–200K photos) with Lightroom Classic on macOS or Windows.

Assumed context:
- Comfortable with a terminal
- Unwilling to manually relocate thousands of files
- Needs confidence (dry-run, backup, rollback) before trusting an automated tool with a 1 GB catalog

**Platform support:**
- Primary platform: macOS. Full feature set including the `[geo]` extra (offline reverse geocoding).
- Secondary platform: Windows. All core features are supported. The `[geo]` extra (offline reverse geocoding) is macOS/Linux only due to a missing Windows wheel for `reverse_geocoder`.
- Linux: CI-only. Lightroom Classic does not run on Linux; Linux support exists solely for automated testing.

---

## 5. Functional Requirements

### 5.1 Catalog Connection

| ID | Requirement |
|----|------------|
| F-CAT-1 | Accept catalog path via `--catalog` / `-c` CLI flag or `LRC_CATALOG_PATH` env var; when omitted, auto-discover the default catalog at `~/Pictures/Lightroom/` (macOS/Linux) or `%USERPROFILE%\Pictures\Lightroom\` (Windows) |
| F-CAT-2 | Detect if Lightroom is open (`.lrcat-lock` file + process name check via `psutil`) and abort with a clear error |
| F-CAT-3 | Create a timestamped backup of the catalog before any write operation |
| F-CAT-4 | Expose a `restore` command to replace the catalog from a backup |

### 5.2 Scanning

| ID | Requirement |
|----|------------|
| F-SCAN-1 | Parse capture dates from the **full path** (root + pathFromRoot), not just the leaf folder |
| F-SCAN-2 | Recognise `YYYY/MM/`, `YYYY-MM-DD/`, and French date patterns (`D mois YYYY`) |
| F-SCAN-3 | Skip photos with no parseable date in their path (topical folders) |
| F-SCAN-4 | Filter bogus dates (1904-01-01, dates outside 1900–2100) |
| F-SCAN-5 | Report the count and list of misplaced photos |
| F-SCAN-6 | Detect duplicate date prefixes in filenames |

### 5.3 Planning

| ID | Requirement |
|----|------------|
| F-PLAN-1 | Compute the correct target path for each misplaced photo using `captureTime` and the configured `LRC_TARGET_LAYOUT` pattern (default `%Y/%m/`) |
| F-PLAN-2 | Resolve target folders, creating new `AgLibraryFolder` rows as needed |
| F-PLAN-3 | Handle filename collisions in the target folder by appending `_1`, `_2`, etc. |
| F-PLAN-4 | Export the plan as JSON for external inspection |

### 5.4 Execution

| ID | Requirement |
|----|------------|
| F-EXEC-1 | Move physical files on disk (including RAW+JPG pairs and XMP sidecars) |
| F-EXEC-2 | Update `AgLibraryFile.folder` in a single `BEGIN IMMEDIATE … COMMIT` transaction |
| F-EXEC-3 | Maintain a rollback stack: reverse all disk moves on any error |
| F-EXEC-4 | Support cross-filesystem moves (copy + delete) transparently |
| F-EXEC-5 | Skip virtual copies (they share the master's physical file) |
| F-EXEC-6 | After the main transaction commits, sweep source directories; `rmdir` any now-empty directory and delete its `AgLibraryFolder` DB row |
| F-EXEC-7 | Report `folders_removed` count in the execution summary |
| F-EXEC-8 | Retry on `PermissionError` for transient antivirus scan locks on Windows |

### 5.5 Validation

| ID | Requirement |
|----|------------|
| F-VAL-1 | Run `PRAGMA integrity_check` before and after every write session |
| F-VAL-2 | Verify all moved files exist at their new paths after `apply` |
| F-VAL-3 | `audit_files_on_disk()`: check every catalog record against disk (no cap); return a typed `FileAuditResult` with all missing entries |
| F-VAL-4 | For each missing file, rglob the root's parent directory (one pass per unique parent) to locate where the file actually lives on disk |
| F-VAL-5 | Export audit results as JSON or CSV via `validate --output FILE` |
| F-VAL-6 | Detect year-in-year folder anomalies (`check_year_in_year`) |

### 5.6 Cleanup

| ID | Requirement |
|----|------------|
| F-CLEAN-1 | `lrc-auto cleanup` walks every catalog root bottom-up and removes directories that contain no real files |
| F-CLEAN-2 | On macOS, delete AppleDouble (`._*`) files before attempting `rmdir` |
| F-CLEAN-3 | Remove orphaned `AgLibraryFolder` rows for deleted directories |
| F-CLEAN-4 | Never touch photo files — cleanup is always safe to run |

### 5.7 Prefix Format Normalisation

| ID | Requirement |
|----|------------|
| F-PREFIX-1 | Detect filenames carrying a DDMMYYYY prefix: `^(\d{2})(\d{2})(\d{4})-(.+)$` |
| F-PREFIX-2 | Propose a YYMMDD equivalent: strip century, reorder to `YYMMDD-rest` |
| F-PREFIX-3 | Validate that the embedded date is real before proposing a rename (reject bogus dates such as 1904-01-01) |
| F-PREFIX-4 | For GPS-tagged files, include a `Country/City/` target-folder suggestion alongside the proposed name |
| F-PREFIX-5 | Location belongs in the **folder hierarchy**, not in the filename |
| F-PREFIX-6 | Sort GPS-tagged proposals first in the scan report |

### 5.8 Location Folders (optional `[geo]` extra)

| ID | Requirement |
|----|------------|
| F-GEO-1 | When `--location-folders` is set, append `Country/City/` to the target path |
| F-GEO-2 | Resolve GPS coordinates offline using `reverse-geocoder` (no network calls) |
| F-GEO-3 | Convert ISO 3166-1 alpha-2 country codes to full country names using `pycountry` |
| F-GEO-4 | Sanitize country and city names for use as folder names (strip `/ \ : * ? " < > |`) |
| F-GEO-5 | Cache resolved coordinates in-memory; support batch resolution for efficiency |
| F-GEO-6 | Fall back gracefully (omit location suffix) if coordinates cannot be resolved |

### 5.9 Logging

| ID | Requirement |
|----|------------|
| F-LOG-1 | All operations write to a log file at DEBUG level alongside the catalog (`<catalog>.log`) by default |
| F-LOG-2 | Override log path with `--log-file PATH` / `LRC_LOG_FILE` env var |
| F-LOG-3 | Console handler stays at WARNING unless `-v` is set; file handler always at DEBUG |
| F-LOG-4 | Logged events: every `MOVE`, `RENAME`, `SKIP`, `REMOVED empty folder` in executor; audit start/summary and every `MISSING` file in validate; `RECONCILE` entries in reconcile |

### 5.10 Reconciliation

| ID | Requirement |
|----|------------|
| F-REC-1 | `lrc-auto reconcile` runs `audit_files_on_disk()` then updates `AgLibraryFile.folder` for each unambiguous `found_elsewhere` file |
| F-REC-2 | Find or create the `AgLibraryFolder` row matching the file's actual disk location |
| F-REC-3 | Skip ambiguous matches (`found_at` has more than one candidate); log a warning |
| F-REC-4 | Require a catalog backup before writing (same guard as `apply`) |
| F-REC-5 | Report reconciled count, skipped-ambiguous count, and truly-missing count |

### 5.11 Distribution

| ID | Requirement |
|----|------------|
| F-DIST-1 | Publish a Python wheel and sdist to GitHub Releases on every version tag |
| F-DIST-2 | Build and publish a standalone Windows `.exe` (PyInstaller, no Python install required) |
| F-DIST-3 | Build and publish a standalone macOS universal2 binary (PyInstaller, Apple Silicon + Intel) |
| F-DIST-4 | Build and push a Docker image to `ghcr.io/fjacquet/lrc-automation` with semver tags |
| F-DIST-5 | Attach an SBOM (SPDX-JSON) to every GitHub Release |

---

## 6. Non-Functional Requirements

| ID | Requirement |
|----|------------|
| NF-1 | All operations on the real catalog (92 K photos) must complete in < 5 minutes on typical hardware |
| NF-2 | Offline-only — no network calls in the default or `[geo]` configurations |
| NF-3 | Python 3.12+; target platforms are macOS and Windows. Linux is supported as CI-only (Lightroom Classic does not run on Linux). |
| NF-4 | Type-checked with mypy strict mode; linted with ruff |
| NF-5 | Test coverage via pytest; no `unittest.mock` (use `pytest.MonkeyPatch`) |
| NF-6 | The tool must never leave the catalog in a partially-updated state |

---

## 7. Configuration

| Variable | CLI flag | Default | Purpose |
|----------|----------|---------|---------|
| `LRC_CATALOG_PATH` | `-c` / `--catalog` | auto-discovered | Path to `.lrcat` file |
| `LRC_BACKUP_DIR` | `--backup-dir` | same dir as catalog | Backup destination |
| `LRC_TARGET_LAYOUT` | `--target-layout` | `%Y/%m/` | `strftime` pattern for target folder |
| `LRC_LOCATION_FOLDERS` | `--location-folders` | `false` | Append `Country/City/` from GPS |
| `LRC_LOG_FILE` | `--log-file` | `<catalog>.log` | Log file path |

---

## 8. CLI Surface

```
lrc-auto scan       [-c PATH] [-o FILE]              # Read-only: list misplaced photos
lrc-auto plan       [-c PATH] [-o FILE]              # Generate move plan
lrc-auto apply      [-c PATH] [-y] [--fix SCOPE]     # Execute plan (backup created first)
lrc-auto validate   [-c PATH] [-o FILE]              # Integrity check + full disk audit
lrc-auto cleanup    [-c PATH]                        # Remove empty dirs + AppleDouble files
lrc-auto reconcile  [-c PATH]                        # Fix catalog pointers for found-elsewhere files
lrc-auto restore    [-c PATH] --backup-path PATH     # Roll back to backup
```

---

## 9. Architecture Summary

```
CLI (cli.py)
  └─ CatalogConnection (catalog.py)       ← SQLite open/close/backup/lock
       ├─ CatalogScanner (scanner.py)     ← build PhotoRecord list
       ├─ ChangePlanner (planner.py)      ← build ChangePlan
       ├─ ChangeExecutor (executor.py)    ← disk moves + SQL updates + cleanup
       ├─ CatalogValidator (validators.py)← integrity checks + full disk audit
       ├─ CatalogReconciler (reconciler.py) ← fix catalog pointers for misplaced files
       ├─ LocationResolver (geocoder.py)  ← GPS → Country/City [geo]
       ├─ Reporter (reporter.py)          ← Rich terminal output + JSON/CSV export
       └─ log.py                          ← configure_logging (stdlib logging, no deps)
```

See [ADR-001](adr/001-lightroom-classic-catalog-automation.md) for the full design rationale.

---

## 10. Open Questions / Future Work

| # | Question |
|---|---------|
| OQ-1 | Should topical (non-date) folders be preserved as-is or given a configurable default target? |
| ~~OQ-2~~ | ~~Should the tool support renaming (stripping duplicate date prefixes)?~~ **Resolved:** duplicate-prefix removal and DDMMYYYY→YYMMDD normalisation both implemented (F-SCAN-6, F-PREFIX-1…6). |
| OQ-3 | Should a `--dry-run` flag on `apply` replace the separate `plan` command? |
| OQ-4 | MCP server wrapper — expose `scan` and `plan` results to AI assistants? |
| ~~OQ-5~~ | ~~Support for Windows paths?~~ **Resolved in v0.6.0:** full Windows support shipped. SQLite URI uses forward slashes (`as_posix()`), process detection uses `psutil`, catalog auto-discovery supports `%USERPROFILE%\Pictures\Lightroom\`. |
| OQ-6 | **Volume-offline handling** — should `validate` and `reconcile` skip roots whose `absolutePath` is not mounted, instead of reporting all their files as missing? |
