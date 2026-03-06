# Roadmap: lrc-automation

## Milestones

- ✅ **v0.5.0 Cross-Root & Reconcile** - Phases 1-8 (shipped 2026-02-28, ad-hoc; bootstrapped into GSD)
- 🚧 **v0.6.0 Multiplatform** - Phases 1-4 (in progress)

## Overview

v0.6.0 extends lrc-automation from macOS-only to Windows + macOS by fixing four discrete problem areas in the existing codebase: catalog open/read safety on Windows paths, write correctness for SQL path columns and disk operations, CI matrix expansion to validate the changes on real runners, and UX/documentation polish so Windows users can onboard without friction. Each phase delivers a coherent, testable capability that unblocks the next.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Path Safety** - Catalog opens and scans correctly on Windows (SQLite URI, psutil, packaging) (completed 2026-03-06)
- [x] **Phase 2: Write Safety** - Apply/reconcile/cleanup write correct paths and handle Windows file-system edge cases (completed 2026-03-06)
- [ ] **Phase 3: CI Matrix** - Green CI on Windows + Linux runners, SBOM generation at release
- [ ] **Phase 4: UX and Docs** - Zero-config catalog discovery, Windows onboarding documentation, ADR, PRD, CHANGELOG

## Phase Details

### Phase 1: Path Safety

**Goal**: The tool opens any Lightroom catalog and correctly classifies photo paths on Windows without errors or silent misclassification.
**Depends on**: Nothing (first phase)
**Requirements**: PATH-01, PATH-02, PATH-03, UX-03
**Success Criteria** (what must be TRUE):

  1. Running `lrc-auto scan --catalog "C:/Users/user/Pictures/Lightroom/Catalog.lrcat"` on Windows opens the catalog without raising a SQLite URI error.
  2. Scan output correctly shows dates extracted from a catalog whose root uses a drive-letter `absolutePath` (e.g., `C:/Photos/`) — no photos wrongly classified as misplaced due to path separator confusion.
  3. Opening a Mac-origin catalog (one whose `absolutePath` contains `/Volumes/`) on Windows prints a human-readable warning and exits cleanly rather than crashing.
  4. `pip install lrc-automation` installs successfully without pulling in `reverse_geocoder` as a core dependency; `pip install "lrc-automation[geo]"` still provides geocoding.
**Plans**: 3 plans

Plans:

- [ ] 01-01-PLAN.md — Fix SQLite URI backslash bug and Mac-origin catalog warning in catalog.py (PATH-01, PATH-03)
- [ ] 01-02-PLAN.md — Fix path separator normalisation in scanner.py for Windows absolutePath (PATH-02)
- [ ] 01-03-PLAN.md — Remove reverse-geocoder from core dependencies in pyproject.toml (UX-03)

### Phase 2: Write Safety

**Goal**: Apply, reconcile, and cleanup operations execute correctly on Windows: pathFromRoot values are stored with forward slashes so Lightroom can locate folders, and disk operations handle Windows-specific file-system failures gracefully.
**Depends on**: Phase 1
**Requirements**: PROC-01, PROC-02, PROC-03, PROC-04
**Success Criteria** (what must be TRUE):

  1. Running `lrc-auto apply` on Windows while Lightroom is open is blocked with a "Lightroom is running" error (psutil detects `Lightroom.exe`); the same guard works on macOS.
  2. After `lrc-auto apply` moves photos on Windows, Lightroom can locate all moved folders without showing them as missing — confirming `pathFromRoot` was written with forward slashes.
  3. Running `lrc-auto cleanup` on Windows produces no errors and no spurious log entries related to AppleDouble (`._*`) file removal; the command silently skips that step.
  4. A file move that encounters a transient `PermissionError` (antivirus scan lock) is retried automatically and either succeeds or fails with a clear error message — no partial moves left on disk.
**Plans**: 2 plans

Plans:

- [ ] 02-01-PLAN.md — Replace pgrep with psutil cross-platform process detection in catalog.py (PROC-01)
- [ ] 02-02-PLAN.md — Fix as_posix SQL writes, darwin guard for AppleDouble cleanup, and PermissionError retry loop (PROC-02, PROC-03, PROC-04)

### Phase 3: CI Matrix

**Goal**: GitHub Actions CI passes on Windows, macOS, and Linux runners for Python 3.12 and 3.13, CRLF line-ending issues are prevented by `.gitattributes`, and an SBOM artifact is attached to every release.
**Depends on**: Phase 2
**Requirements**: CI-01, CI-02, CI-03, CI-04
**Success Criteria** (what must be TRUE):

  1. A push to the main branch triggers CI that runs and passes on `ubuntu-latest`, `macos-latest`, and `windows-latest` runners — the CI matrix badge shows green for all three.
  2. `ruff format --check` passes on the Windows CI runner with a fresh checkout — no failures caused by CRLF line endings in committed files.
  3. The CI workflow uses `astral-sh/setup-uv@v7`; no warnings about deprecated action versions appear in the CI log.
  4. A GitHub release build automatically attaches an SBOM file as a release artifact; the artifact is visible on the GitHub releases page.
**Plans**: TBD

### Phase 4: UX and Docs

**Goal**: Windows users can install and run lrc-auto without specifying `--catalog` for standard Lightroom installations, and documentation covers Windows installation, usage, and platform decisions.
**Depends on**: Phase 3
**Requirements**: UX-01, UX-02, UX-04, UX-05, UX-06
**Success Criteria** (what must be TRUE):

  1. On a machine with a standard Lightroom Classic installation, running `lrc-auto scan` (without `--catalog`) finds and opens the default catalog on both macOS (`~/Pictures/Lightroom/`) and Windows (`%USERPROFILE%\Pictures\Lightroom\`).
  2. README and `docs/usage.md` contain a Windows installation and first-run section that a new Windows user can follow to completion — covering `uv`/`pipx` install, `.env` file syntax, and the MAX_PATH advisory.
  3. An ADR document exists in `docs/adr/` documenting the multiplatform decisions: `psutil` for process detection, `path.as_posix()` for SQL writes, `sys.platform` for AppleDouble guard, and SBOM generation.
  4. `docs/prd.md` names macOS and Windows as the two target platforms and describes the constraints that keep Linux as CI-only.
  5. `CHANGELOG.md` has a complete v0.6.0 entry listing every shipped change from all four phases.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Path Safety | 3/3 | Complete   | 2026-03-06 |
| 2. Write Safety | 2/2 | Complete   | 2026-03-06 |
| 3. CI Matrix | 0/TBD | Not started | - |
| 4. UX and Docs | 0/TBD | Not started | - |
