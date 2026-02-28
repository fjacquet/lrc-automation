# ADR-005: Catalog Reconciliation Command

**Status:** Accepted
**Date:** 2026-02-28
**Decision Makers:** fjacquet

## Context

`audit_files_on_disk()` (added in ADR-004) classifies missing catalog records into two
buckets:

- **`found_elsewhere`** — file exists on disk but not at its catalog path. The catalog
  pointer is wrong; the file is safe.
- **`truly_missing`** — file cannot be found anywhere under the root's parent directory.

The 19,127 wrong-location moves produced by the year-doubling bug (ADR-003) left files at
paths like `/Volumes/T7 Shield/Lightroom/2012/2012/10/CH/Saillon/IMG_001.JPG` while the
catalog records still pointed to `/Volumes/T7 Shield/Lightroom/2012/10/CH/Saillon/`. Running
`validate` after the fix showed these as `found_elsewhere`. There was no way to repair the
catalog pointers without manually editing the DB.

The `validate` command is explicitly read-only (ADR-004, "What `audit_files_on_disk()` Does
NOT Do"). Mixing reconciliation into `validate` would violate that invariant and confuse
users who run it as a non-destructive check.

---

## Decision

### Add `lrc-auto reconcile` as a new write command

**Rationale for a separate command (not `validate --fix`):**

- Preserves `validate` as a safe read-only operation.
- Follows the existing pipeline style: `scan` → `plan` → `apply` → `validate` → `reconcile`.
- Can be safely skipped; users who only want to audit are not forced into a write path.
- The name communicates intent clearly: bring catalog and disk back into agreement.

### What `reconcile` does

1. Takes a mandatory catalog backup (same guard as `apply`).
2. Calls `CatalogValidator.audit_files_on_disk()` to obtain `FileAuditResult`.
3. For each **unambiguous** `found_elsewhere` entry (`len(found_at) == 1`):
   a. Parses the actual path to derive `pathFromRoot` relative to the root's `absolutePath`.
   b. Finds the `AgLibraryFolder` row matching that `pathFromRoot` + `rootFolder`, or
      creates a new row if it doesn't exist.
   c. `UPDATE AgLibraryFile SET folder = <new_folder_id> WHERE id_local = <file_id>`.
   d. Logs `RECONCILE <expected_path> → <actual_path>` at INFO level.
4. **Skips** ambiguous entries (`len(found_at) > 1`): logs a WARNING and reports them
   separately so the user can resolve manually.
5. Does **not** move files on disk — only updates catalog pointers.
6. All DB updates run inside a single `BEGIN IMMEDIATE … COMMIT` transaction.
7. Returns a `ReconcileReport` with reconciled, skipped, and truly-missing counts.

### New models

```python
@dataclass
class ReconcileChange:
    file_id: int
    old_folder_id: int
    new_folder_id: int
    actual_path: Path
    expected_path: Path

@dataclass
class ReconcileReport:
    reconciled: list[ReconcileChange]
    skipped_ambiguous: list[MissingFile]
    truly_missing: list[MissingFile]
```

### Alternative considered: move files to expected location

Instead of updating the DB pointer, move the file back to the expected path. Rejected:

- The expected path may no longer be correct (e.g. the original location was itself wrong
  before the year-doubling run).
- Moving large numbers of files risks data loss if the destination already exists.
- The DB update is reversible via backup restore; a mass file move is not easily reversible.

### Alternative considered: `validate --fix`

Rejected — would make `validate` a write command, breaking the read-only invariant and
removing the user's ability to audit without risk of modification.

---

## Affected Files

| File | Change |
|------|--------|
| `src/lrc_automation/models.py` | Add `ReconcileChange`, `ReconcileReport` dataclasses |
| `src/lrc_automation/reconciler.py` | **New** — `CatalogReconciler` class |
| `src/lrc_automation/reporter.py` | Add `print_reconcile_report` |
| `src/lrc_automation/cli.py` | Add `reconcile` command |
| `tests/test_reconciler.py` | **New** — `TestCatalogReconciler` |

## Tests

- `test_reconcile_found_elsewhere` — one `found_elsewhere` file → DB pointer updated,
  `reconciled` count = 1.
- `test_reconcile_ambiguous_skipped` — two files with same name → entry skipped, in
  `skipped_ambiguous`.
- `test_reconcile_truly_missing_untouched` — truly missing file → no DB update, in
  `truly_missing`.
- `test_reconcile_creates_new_folder_row` — actual path maps to a folder not yet in
  `AgLibraryFolder` → new row created, file pointer updated.

---

## Consequences

**Positive:**
- Provides a one-command repair path after a bad `apply` run produces `found_elsewhere` files.
- No files are moved; only catalog metadata changes — low risk.
- Backup guard ensures the user can restore if the reconciliation produces unexpected results.
- `validate` stays read-only.

**Negative:**
- After reconciliation, files remain at their actual (possibly wrong) disk location. A
  subsequent `apply` run may move them again to the correct date folder.
- Ambiguous matches (same filename in multiple locations) require manual resolution.
- If the root volume is offline, all files under that root are reported as `truly_missing`
  and skipped — no reconciliation happens for them (consistent with ADR-004 OQ-B behaviour).
