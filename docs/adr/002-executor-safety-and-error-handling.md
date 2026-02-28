# ADR-002: Executor Safety, Error Handling, and Fail-Early Strategy

**Status:** Accepted
**Date:** 2026-02-28
**Decision Makers:** fjacquet

## Context

The `apply` command modifies both the SQLite catalog and the filesystem simultaneously. A failure mid-run can leave these two in an inconsistent state (catalog updated, disk not — or vice versa), which Lightroom would interpret as missing files.

During real-world testing on a 72,000-photo catalog (T7 Shield drive), the following failure mode was observed:

- The executor processed 2,240 renames successfully, then hit a 2,241st file whose source was missing on disk (catalog/disk desync: the file existed in the catalog but had been deleted or moved outside Lightroom).
- The original code treated all exceptions equally: it rolled back SQL and all 2,240 disk renames, then reported "Succeeded: 2,240" — which was **completely misleading** since nothing persisted.
- The post-flight validator ran against the full plan (all 2,240 changes) and emitted 2,240 "Renamed file not found" warnings — flooding the output and causing a false alarm ("disaster?").

## Decisions

### 1. Distinguish SkippableError from rollback-worthy errors

**Decision:** Introduce `SkippableError(ExecutionError)` raised when a pre-disk-op validation fails (source file not found, destination already exists). For these errors, no disk operation has occurred, so the change is skipped and execution continues. A full rollback is only triggered for exceptions that occur *after* a disk operation has started (OS errors, SQL failures).

**Rationale:** A single missing file in a 2,240-item plan should not abort the entire run. The catalog/disk desync is a pre-existing condition — skipping that one file is correct behavior.

```
SkippableError  → record_error, continue to next change
Exception       → record_error, rollback all, return
```

### 2. Pre-execution plan source check

**Decision:** Before any disk or SQL write, `CatalogValidator.preflight_plan_check(plan)` iterates all planned changes and verifies each source file exists. All missing paths are reported upfront. The user is prompted to confirm before execution proceeds.

**Rationale:** Fail-early, fail-visibly. Surfacing all missing files before touching anything gives the user full information and prevents partial runs. The executor's `SkippableError` handles any file that disappears between this check and execution (TOCTOU window), but the check eliminates the most common case.

### 3. ExecutionReport.rolled_back flag

**Decision:** `ExecutionReport` carries a `rolled_back: bool` field. When a mid-operation rollback is triggered, `mark_rolled_back()` is called, which sets the flag and **clears** `succeeded`. The reporter checks this flag and prints `ROLLED BACK — error occurred; all disk and catalog changes have been reversed.` instead of a misleading success count.

**Rationale:** "Succeeded: 2,240" after a full rollback is a lie. Clearing `succeeded` ensures no downstream code (XMP reminder, post-flight check) acts on rolled-back changes.

### 4. postflight_check receives only committed changes

**Decision:** `postflight_check` accepts `list[FileChange]` (the succeeded list) instead of the full `ChangePlan`. The `apply` command passes `[] if report.rolled_back else report.succeeded`.

**Rationale:** Checking the full plan after a rollback produces N false-alarm warnings (all new-name files "not found" because they were reversed). The post-flight check is only meaningful for changes that actually committed.

## Error Taxonomy

| Situation | Exception | Behavior |
|---|---|---|
| Source file missing on disk | `SkippableError` | Skip, record error, continue |
| Destination already exists on disk | `SkippableError` | Skip, record error, continue |
| OS rename/move failure | `OSError` → caught as `Exception` | Rollback all, mark `rolled_back` |
| SQL update failure | `sqlite3.Error` → caught as `Exception` | Rollback all, mark `rolled_back` |

## Consequences

- **Positive:** A single missing file no longer aborts the entire batch.
- **Positive:** Users see all missing files before any change is made.
- **Positive:** The output is honest: rolled-back runs are clearly labelled.
- **Positive:** Post-flight warnings are only real warnings, not noise.
- **Negative:** A catalog with many missing files will produce many skip errors in the report. This is intentional — it surfaces the desync for the user to investigate with `lrc-auto validate`.
- **Note:** The TOCTOU window between `preflight_plan_check` and actual execution is accepted. Files disappearing mid-run are handled by `SkippableError`.

## Alternatives Considered

### Strict mode (abort on any missing file)
Keep the original rollback-all behaviour but surface a clear error. Rejected: too disruptive for large catalogs with occasional desync.

### Skip silently without reporting
Skip missing files without telling the user. Rejected: the user needs to know about catalog/disk desyncs so they can reconcile them via Lightroom's "Find Missing Photos" or the `validate` command.
