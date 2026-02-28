# ADR-006: Cross-Root Year-In-Year Migration

**Status:** Accepted
**Date:** 2026-02-28
**Decision Makers:** fjacquet

## Context

Analysis of the T7 Shield volume revealed 406 photos living in incorrect year-root
folders — a pattern referred to as "year-in-year". For example:

```
Root:          /Volumes/T7 Shield/Lightroom/2013/
pathFromRoot:  2012/08/
Full path:     /Volumes/T7 Shield/Lightroom/2013/2012/08/IMG_001.JPG
captureTime:   2012-08-15
```

The photo belongs in the **2012** root (`/Volumes/T7 Shield/Lightroom/2012/`) but was
imported or moved into the **2013** root by a prior buggy operation. Breakdown of the 406
affected files across year-root combinations:

| Root → pfr year | Count |
|-----------------|------:|
| 2013 → 2012     |   163 |
| 2024 → 2003     |    49 |
| 2026 → 2015     |    46 |
| 2022 → 2003     |    46 |
| (others)        |   102 |

Two distinct sub-cases exist:

- **Cross-root** (majority ~398): the photo's `captureTime.year` matches the year embedded
  in `pathFromRoot`, not the year of the current root. The file must be physically moved to
  a different root directory.
- **Intra-root** (~8): the photo's `captureTime.year` matches the current root year, but
  `pathFromRoot` starts with a spurious year segment (e.g. `2015/01/` inside the 2022
  root). The file stays in the same root but the spurious year prefix is stripped.

The existing `scan_year_in_year_photos()` scanner already detected these photos. What was
missing was a planner method and executor support to actually fix them.

---

## Decision

### 1. Extend `FileChange` with two optional cross-root fields

```python
target_root_id: int | None = None
target_root_absolute_path: str | None = None
```

When both are `None` (all existing callers), executor behaviour is unchanged. When set,
the executor uses the target root for both the disk destination path and the folder-ID
lookup, enabling cross-root moves in a single transaction.

This is preferred over a new `ChangeType` because:
- The operation is still fundamentally a `MOVE_PHOTO` (folder FK update + disk move).
- Backwards compatibility is maintained: all existing tests pass without change.
- The optional fields self-document whether a move is cross-root or intra-root.

### 2. Add `_plan_root_migrations()` to `ChangePlanner`

The method:
1. Calls `scanner.scan_year_in_year_photos()` to find all year-in-year photos.
2. Loads all catalog root folders via `scanner.get_root_folders()`.
3. For each photo, strips the spurious leading year from `pathFromRoot` to get the
   corrected sub-path (`"08/"` from `"2012/08/"`).
4. Finds the target root by matching `capture_time.year` against each root's last
   path segment (via `_find_root_for_year()` static helper).
5. Skips photos with no matching root in the catalog (warn).
6. Skips cross-root moves where the target root directory does not exist on disk (warn).
7. Calls `_ensure_folder_chain()` in the target root to queue any missing folders.
8. Resolves filename collisions and appends `FileChange` with cross-root fields set only
   when `target_root.id_local != photo.root_folder_id`.

### 3. Guard `--fix root-migrations` as explicit opt-in

```python
def build_plan(
    self,
    include_moves: bool = True,
    include_renames: bool = True,
    include_root_migrations: bool = False,   # default OFF
) -> ChangePlan: ...
```

`--fix all` does **not** include root migrations. Users must pass `--fix root-migrations`
explicitly. Rationale:

- Cross-root moves touch files across multiple volume directories and carry higher risk.
- 406 files is a significant batch; users should consciously opt in.
- The existing `--fix all` behaviour is preserved for routine maintenance.

### 4. Executor: use `target_root_absolute_path` in `_execute_move()`

Two targeted changes in `_execute_move()`:

```python
# Disk destination:
dest_root = change.target_root_absolute_path or photo.root_absolute_path
dst_dir = Path(dest_root) / target_path

# Folder-ID lookup (folder must belong to target root, not source root):
effective_root_id = change.target_root_id or photo.root_folder_id
key = (effective_root_id, target_path)
target_folder_id = folder_id_map.get(key)
```

No changes to `_create_folders()` — it already queries all `AgLibraryRootFolder` rows and
creates folders in whichever root is requested. The rollback mechanism is unchanged.

### 5. Validators: use `target_root_absolute_path` in `postflight_check()`

```python
dest_root = change.target_root_absolute_path or change.photo.root_absolute_path
new_path = Path(dest_root) / target_folder / f"{base}.{ext}"
```

This ensures the post-flight file-existence check looks in the correct root directory.

---

## Consequences

### Positive
- 406 year-in-year photos can be migrated to their correct year roots without manual work.
- Cross-root and intra-root cases are handled uniformly with the same `FileChange` type.
- Existing `--fix all` workflow is unaffected.
- Full rollback on any error (disk + DB).

### Negative / Risks
- Target root directory must exist on disk (checked at plan time; skipped if absent).
- No automatic creation of new `AgLibraryRootFolder` rows — only existing catalog roots
  are valid destinations. If the target year-root does not exist in the catalog, the photo
  is skipped with a warning.
- Moving files between physical volumes (e.g. from one external drive to another) is
  supported but only if both drives are mounted. If a target drive is absent, the plan
  skips the affected photos.

### Invariants preserved
- `capture_time` must not be `None` — photos without EXIF time are skipped.
- Target root must be an existing `AgLibraryRootFolder` row.
- Target root directory must exist on disk for cross-root moves.
- `AgLibraryRootFolder` rows are never created or deleted by this operation.
- `--fix all` never triggers root migrations (explicit `--fix root-migrations` required).

---

## Alternatives Considered

### A — New `ChangeType.MIGRATE_ROOT`
A dedicated change type would make the intent explicit in code but would require
duplicating most of `_execute_move()` and changing the reporter, JSON export schema, and
all call sites. The optional-field approach on `FileChange` is less invasive and achieves
the same result.

### B — Shell script using `rsync` + manual DB edits
Fast to write but fragile: no rollback, no catalog integrity check, no collision
handling, and no post-flight validation. Rejected.

### C — Run during `--fix all`
Rejected on safety grounds. Root migrations affect files across different volume
directories and should remain an explicit, supervised operation.
