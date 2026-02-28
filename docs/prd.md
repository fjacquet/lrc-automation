# Product Requirements Document: lrc-automation

**Version:** 0.5.x
**Date:** 2026-02-28
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

---

## 3. Non-Goals

- Real-time / background monitoring (run on demand only)
- Lightroom Classic plugin / in-app UI
- Support for Lightroom CC (cloud) catalogs
- Duplicate photo detection / deduplication
- AI-based photo tagging or scene classification

---

## 4. Users

**Primary user:** Solo photographer managing a large personal archive (10K–200K photos) with Lightroom Classic on macOS.

Assumed context:
- Comfortable with a terminal
- Unwilling to manually relocate thousands of files
- Needs confidence (dry-run, backup, rollback) before trusting an automated tool with a 1 GB catalog

---

## 5. Functional Requirements

### 5.1 Catalog Connection

| ID | Requirement |
|----|------------|
| F-CAT-1 | Accept catalog path via `--catalog` / `-c` CLI flag or `LRC_CATALOG_PATH` env var |
| F-CAT-2 | Detect if Lightroom is open (`.lrcat-lock` file + process name check) and abort with a clear error |
| F-CAT-3 | Create a timestamped backup of the catalog before any write operation |
| F-CAT-4 | Expose a `restore` command to replace the catalog from a backup |

### 5.2 Scanning

| ID | Requirement |
|----|------------|
| F-SCAN-1 | Parse capture dates from the **full path** (root + pathFromRoot), not just the leaf folder |
| F-SCAN-2 | Recognise `YYYY/MM/`, `YYYY-MM-DD/`, and French date patterns (`D mois YYYY`) |
| F-SCAN-3 | Skip photos with no parseable date in their path (topical folders) |
| F-SCAN-4 | Filter bogus dates (1904-01-01, dates in the future) |
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

### 5.5 Validation

| ID | Requirement |
|----|------------|
| F-VAL-1 | Run `PRAGMA integrity_check` before and after every write session |
| F-VAL-2 | Verify all moved files exist at their new paths |
| F-VAL-3 | Detect orphaned `AgLibraryFile` rows (no matching file on disk) |

### 5.6 Prefix Format Normalisation

| ID | Requirement |
|----|------------|
| F-PREFIX-1 | Detect filenames carrying a DDMMYYYY prefix: `^(\d{2})(\d{2})(\d{4})-(.+)$` |
| F-PREFIX-2 | Propose a YYMMDD equivalent: strip century, reorder to `YYMMDD-rest` |
| F-PREFIX-3 | Validate that the embedded date is real before proposing a rename (reject bogus dates such as 1904-01-01) |
| F-PREFIX-4 | For GPS-tagged files, include a `Country/City/` target-folder suggestion alongside the proposed name |
| F-PREFIX-5 | Location belongs in the **folder hierarchy**, not in the filename |
| F-PREFIX-6 | Sort GPS-tagged proposals first in the scan report |

### 5.7 Location Folders (optional `[geo]` extra)

| ID | Requirement |
|----|------------|
| F-GEO-1 | When `--location-folders` is set, append `Country/City/` to the target path |
| F-GEO-2 | Resolve GPS coordinates offline using `reverse-geocoder` (no network calls) |
| F-GEO-3 | Convert ISO 3166-1 alpha-2 country codes to full country names using `pycountry` |
| F-GEO-4 | Sanitize country and city names for use as folder names (strip `/ \ : * ? " < > |`) |
| F-GEO-5 | Cache resolved coordinates in-memory; support batch resolution for efficiency |
| F-GEO-6 | Fall back gracefully (omit location suffix) if coordinates cannot be resolved |

---

## 6. Non-Functional Requirements

| ID | Requirement |
|----|------------|
| NF-1 | All operations on the real catalog (92 K photos) must complete in < 5 minutes on typical hardware |
| NF-2 | Offline-only — no network calls in the default or `[geo]` configurations |
| NF-3 | Python 3.12+, tested on macOS; should work on Linux |
| NF-4 | Type-checked with mypy strict mode; linted with ruff |
| NF-5 | Test coverage via pytest; no `unittest.mock` (use `pytest.MonkeyPatch`) |
| NF-6 | The tool must never leave the catalog in a partially-updated state |

---

## 7. Configuration

| Variable | CLI flag | Default | Purpose |
|----------|----------|---------|---------|
| `LRC_CATALOG_PATH` | `-c` / `--catalog` | — | Path to `.lrcat` file |
| `LRC_BACKUP_DIR` | `--backup-dir` | same dir as catalog | Backup destination |
| `LRC_TARGET_LAYOUT` | `--layout` | `%Y/%m/` | `strftime` pattern for target folder |
| `LRC_LOCATION_FOLDERS` | `--location-folders` | `false` | Append `Country/City/` from GPS |

---

## 8. CLI Surface

```
lrc-auto scan      [-c PATH]                        # Read-only: list misplaced photos
lrc-auto plan      [-c PATH] [-o plan.json]          # Generate move plan
lrc-auto apply     [-c PATH] [--dry-run]             # Execute plan
lrc-auto validate  [-c PATH]                         # Integrity check
lrc-auto restore   [-c PATH] --backup-path PATH      # Roll back to backup
```

---

## 9. Architecture Summary

```
CLI (cli.py)
  └─ CatalogConnection (catalog.py)   ← SQLite open/close/backup/lock
       ├─ CatalogScanner (scanner.py) ← build PhotoRecord list
       ├─ ChangePlanner (planner.py)  ← build ChangePlan
       ├─ ChangeExecutor (executor.py)← disk moves + SQL updates
       ├─ Validators (validators.py)  ← integrity checks
       └─ LocationResolver (geocoder.py) ← GPS → Country/City [geo]
```

See [ADR-001](adr/001-lightroom-classic-catalog-automation.md) for the full design rationale.

---

## 10. Open Questions / Future Work

| # | Question |
|---|---------|
| OQ-1 | Should topical (non-date) folders be preserved as-is or given a configurable default target? |
| ~~OQ-2~~ | ~~Should the tool support renaming (stripping duplicate date prefixes)?~~ **Resolved:** duplicate-prefix removal and DDMMYYYY→YYMMDD normalisation both implemented in the scanner (F-SCAN-6, F-PREFIX-1…6). |
| OQ-3 | Should a `--dry-run` flag on `apply` replace the separate `plan` command? |
| OQ-4 | MCP server wrapper — expose `scan` and `plan` results to AI assistants? |
| OQ-5 | Support for Windows paths (backslash separators in `AgLibraryFolder.pathFromRoot`)? |
