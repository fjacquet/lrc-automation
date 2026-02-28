# ADR-004: Full Disk Audit, Parent-Folder File Search, and Structured Logging

**Status:** Accepted
**Date:** 2026-02-28
**Decision Makers:** fjacquet

## Context

After the Switzerland run produced 19,127 wrong-location moves (fixed by ADR-003), a second
inspection of the catalog revealed 372 year-in-year anomalies. The existing `validate`
command output:

```
Warning: Total year-in-year files: 372
```

This surfaced the need for a deeper integrity capability:

1. **Completeness** — `check_files_exist_on_disk()` capped output at 20 files; useless for
   auditing a 92K-photo catalog.
2. **Findability** — when a file is missing at its catalog path, there was no mechanism to
   locate it elsewhere on disk. The user needs to know "is the file gone, or just moved
   outside Lightroom?"
3. **Auditability** — all output went to the Rich console and was lost after the session.
   There was no persistent log of what was checked, what was found missing, or what `apply`
   did to the catalog.

---

## Decisions

### Decision 1: Replace capped warning list with structured `FileAuditResult`

**Decision:** Replace `check_files_exist_on_disk() -> list[str]` (capped at 20) with
`audit_files_on_disk() -> FileAuditResult`. The new method returns a structured object:

```python
@dataclass
class MissingFile:
    expected_path: Path
    base_name: str
    extension: str
    root_folder_id: int
    file_id: int
    found_at: list[Path]   # [] → gone; [p] → found elsewhere; [p, q] → ambiguous

@dataclass
class FileAuditResult:
    total_checked: int
    missing: list[MissingFile]
    # Properties: present_count, found_elsewhere_count, truly_missing_count
```

**Rationale:** A flat `list[str]` cannot be exported, cannot drive reconciliation, and
cannot be tested meaningfully. A typed result structure enables: Rich table rendering,
JSON/CSV export, and future automated reconciliation without changing the validator API.

`check_files_exist_on_disk()` is kept for backward-compatibility with existing tests.

### Decision 2: Parent-folder file search algorithm

**Decision:** For each missing file, search inside the **parent** of the root's
`absolutePath`. If the root is `/Volumes/photo/2023/`, search `/Volumes/photo/` — which
covers all sibling year-roots (`2022/`, `2021/`, etc.).

The search uses a **single `rglob` pass per unique parent directory** to build a
`filename → [paths]` index, then all missing files are looked up in that index. This is
`O(disk_files + missing_files)` instead of `O(disk_files × missing_files)`.

```python
def _search_parent(root_path: Path) -> Path:
    parent = root_path.parent
    return parent if parent != root_path else root_path
```

**Rationale:** The most common cause of a file being "missing" from its catalog path is
that it was moved to a sibling year-root (e.g. by a previous buggy apply run). Searching
the parent covers this case without a full-disk sweep. A full-disk scan was considered but
rejected: it could take minutes on a large NAS and would produce false positives from
unrelated photo directories.

**Edge case — volume unmounted:** If the parent directory doesn't exist (NAS offline),
`audit_files_on_disk()` logs a warning and skips the search for that parent. Files under
that root are all reported as `found_at = []` (truly missing from the perspective of the
running system).

### Decision 3: `--log-file` and structured file logging

**Decision:** Add `src/lrc_automation/log.py` with `configure_logging(log_file, verbose)`.
The function attaches a `FileHandler` at `DEBUG` level alongside the existing Rich console
(which stays at `WARNING` unless `-v` is set). The default log file path is
`<catalog_path>.log` — i.e. right next to the `.lrcat` file.

CLI-level wiring:
- New `--log-file PATH` option on the `cli` group (env: `LRC_LOG_FILE`)
- `configure_logging` is called at group entry, before any command runs
- Each submodule uses `logging.getLogger(__name__)` — no circular imports, no side effects
  at import time

Logged events:
- `validate` start and summary counts
- Every `MISSING` file (path + where found, if found)
- Every `MOVE`, `RENAME`, `SKIP`, and `REMOVED empty folder` in the executor
- `apply` completion summary

**Rationale:** Console output is ephemeral. A log file alongside the catalog gives the user
a permanent audit trail, especially important when running `apply` on 92K files. Using
Python's stdlib `logging` instead of a third-party library (loguru, structlog) avoids a new
dependency and works with any existing log infrastructure the user may have.

**Why `WARNING` console, `DEBUG` file?** The console is for interactive feedback — flooding
it with 92K `INFO: MOVE …` lines would obscure the Rich progress bar. The file captures
everything for post-hoc review.

### Decision 4: `--output` on `validate`, structured export

**Decision:** Add `--output FILE` to `validate`. When specified, writes a JSON or CSV
export of the `FileAuditResult`. CSV columns: `status, expected_path, found_at, ambiguous`.
JSON includes all counts at the top level plus a `missing` array.

**Rationale:** The validate output can have hundreds of rows. The Rich table is useful for
a quick scan; CSV/JSON is needed for sorting, filtering, and feeding into reconciliation
scripts.

---

## What `audit_files_on_disk()` Does NOT Do

It does **not** modify the catalog or move files. It is a **read-only diagnostic**.

Reconciliation (updating `AgLibraryFile.folder` to match where a file was actually found)
is a separate operation (see Open Questions).

---

## Affected Files

| File | Change |
|------|--------|
| `src/lrc_automation/log.py` | **New** — `configure_logging(log_file, verbose)` |
| `src/lrc_automation/models.py` | Added `MissingFile`, `FileAuditResult` dataclasses |
| `src/lrc_automation/validators.py` | Added `audit_files_on_disk()`, `_search_parent()` |
| `src/lrc_automation/executor.py` | Added `logging.getLogger()`, log each file operation |
| `src/lrc_automation/cli.py` | `--log-file` option, `configure_logging` call, rewrote `validate` |
| `src/lrc_automation/reporter.py` | Added `print_audit_result`, `export_audit_json`, `export_audit_csv` |

## Tests

- `tests/test_validators.py` — `TestAuditFilesOnDisk` (4 cases):
  - `test_all_present` — no missing entries
  - `test_missing_truly_gone` — file deleted, no match in parent
  - `test_missing_found_in_parent` — file in sibling year-root, found by parent search
  - `test_result_counts` — mixed scenario, all counters verified

---

## Open Questions

**OQ-A: Reconciliation** — When `found_elsewhere_count > 0`, should the tool offer to
update `AgLibraryFile.folder` (and optionally move the file) to bring the catalog and disk
back into sync? This is the natural next step after an audit finds misplaced files. It would
require a new `reconcile` CLI command (or a `--fix` flag on `validate`).

**OQ-B: Volume-offline handling** — Should `validate` skip roots whose `absolutePath` is
not mounted, instead of reporting all their files as missing? This would reduce noise when
a secondary drive (e.g. T7 Shield) is not connected.

---

## Consequences

**Positive:**
- Every missing file is now surfaced regardless of count.
- Users can distinguish "gone" from "moved outside Lightroom" without manual searching.
- A log file alongside the catalog provides a permanent audit trail.
- The CSV/JSON export feeds into scripts and reconciliation tools.

**Negative:**
- `rglob` on a large NAS parent directory can take 10–30 seconds for the first run. For
  a 92K-file archive spread over year-roots, this is acceptable. Subsequent calls in the
  same session hit the OS page cache.
- The default log file (`.log` alongside `.lrcat`) grows indefinitely. Log rotation is
  not implemented; users must manage the file manually.
