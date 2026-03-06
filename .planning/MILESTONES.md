# Milestones

## v0.6.0 Multiplatform (Shipped: 2026-03-06)

**Phases completed:** 4 phases, 10 plans, 4 tasks

**Key accomplishments:**
- (none recorded)

---

## v0.5.0 — Cross-Root & Reconcile (2026-02-28)

**Goal:** Complete the repair pipeline: cross-root year migrations, reconcile found-elsewhere files, full disk audit, cleanup utilities.

**Phases completed:** 1–8 (bootstrapped; phases were implemented ad-hoc before GSD adoption)

**Shipped:**

- Cross-root migration (`--fix root-migrations`): 406 year-in-year photos fixed
- DDMMYYYY→YYMMDD renames wired into `apply`
- `cleanup` command (empty dirs + AppleDouble files)
- `reconcile` command (fix folder pointers for found-elsewhere files)
- Full disk audit with JSON/CSV output
- `--log-file` debug logging
- 12 new tests for cross-root migration

## v0.4.0 — Broadened Scanner (2026-02-17)

**Shipped:**

- ISO YYYY-MM-DD folder pattern detection
- French date folder detection (`1 avril 2016`)
- Year-in-root + month-in-path pattern
- 23 new tests

## v0.3.0 — GPS Location Folders (2026-02-17)

**Shipped:**

- Optional `--location-folders` flag
- Offline reverse geocoding via `reverse_geocoder`
- Optional `[geo]` extra
- 34 new tests

## v0.2.0 — Configurable Layout (2026-02-17)

**Shipped:**

- `LRC_TARGET_LAYOUT` env var / `--target-layout` CLI option
- 10 new tests

## v0.1.0 — Foundation (2026-02-17)

**Shipped:**

- Core CLI: scan, plan, apply, validate, restore
- SQLite + disk move pipeline with full rollback
- 37 tests, MkDocs site, GitHub Actions CI
