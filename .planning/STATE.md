---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: milestone
status: planning
stopped_at: Completed 04-ux-and-docs-03-PLAN.md
last_updated: "2026-03-06T21:40:23.747Z"
last_activity: 2026-03-06 — Roadmap created for v0.6.0 Multiplatform milestone
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 10
  completed_plans: 10
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-06)

**Core value:** Photos stay at the path their EXIF capture date dictates, so the Lightroom catalog folder tree always reflects reality.
**Current focus:** Phase 1 - Path Safety (v0.6.0 Multiplatform)

## Current Position

Phase: 1 of 4 (Path Safety)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-03-06 — Roadmap created for v0.6.0 Multiplatform milestone

Progress: [███░░░░░░░] 33%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-path-safety P03 | 198 | 2 tasks | 3 files |
| Phase 01-path-safety P02 | 12 | 2 tasks | 2 files |
| Phase 01-path-safety P01 | 4 | 2 tasks | 2 files |
| Phase 02-write-safety P01 | 3 | 2 tasks | 5 files |
| Phase 02-write-safety P02 | 4 | 2 tasks | 4 files |
| Phase 03-ci-matrix P02 | 5 | 1 tasks | 1 files |
| Phase 03-ci-matrix P01 | 5 | 2 tasks | 2 files |
| Phase 04-ux-and-docs P02 | 2 | 2 tasks | 3 files |
| Phase 04-ux-and-docs P01 | 2 | 2 tasks | 2 files |
| Phase 04-ux-and-docs P03 | 94 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v0.6.0 scope: Surgical module-level changes only — no new platform abstraction layer; each platform concern has exactly one caller in the existing codebase.
- psutil chosen over pgrep subprocess: cross-platform hard dependency; binary wheels available for all target platforms.
- PATH-01 (SQLite URI fix) is Day 1 blocker — without it the tool fails to open any catalog on Windows.
- UX-03 (geo extra packaging fix) grouped into Phase 1 alongside pyproject.toml changes to keep all packaging edits in one phase.
- [Phase 01-path-safety]: Remove pycountry from dev group alongside reverse_geocoder: both are geo-only, neither belongs in core dev environment
- [Phase 01-path-safety]: Normalise backslash at call-site with norm_root variable rather than at PhotoRecord construction for surgical fix
- [Phase 01-path-safety]: TDD RED-GREEN: commit failing tests before fix, then fix code in separate commit
- [Phase 01-path-safety]: _path_to_sqlite_uri detects Windows drive-letter paths via posix string check because Path.is_absolute() is platform-dependent on macOS
- [Phase 02-write-safety]: psutil.process_iter replaces pgrep subprocess: cross-platform, no external binary, AccessDenied handling built in
- [Phase 02-write-safety]: types-psutil added as dev dependency for mypy strict mode compliance
- [Phase 02-write-safety]: WAL mode not enabled in check_lightroom_not_running — Windows file-locking semantics prohibit it
- [Phase 02-write-safety]: sys.platform == 'darwin' is the guard for all AppleDouble logic
- [Phase 02-write-safety]: Rollback action appended AFTER successful file op completes to prevent ghost rollbacks
- [Phase 02-write-safety]: _MOVE_RETRY_SLEEP is a module-level constant so tests can zero it via monkeypatch
- [Phase 03-ci-matrix]: anchore/sbom-action@v0 chosen over actions/attest-sbom: produces downloadable release artifact visible on releases page
- [Phase 03-ci-matrix]: setup-uv bumped to v7 with enable-cache: true in release.yml for consistency with ci.yml
- [Phase 03-ci-matrix]: make check replaced by individual uv run commands in release.yml for explicit CI step visibility
- [Phase 03-ci-matrix]: gitattributes eol=lf prevents CRLF failures on Windows runners
- [Phase 03-ci-matrix]: setup-uv@v7 with enable-cache: true replaces v4 for OS-aware cache keys in multi-OS matrix
- [Phase 03-ci-matrix]: uv sync without --all-extras on all platforms — reverse_geocoder lacks Windows wheel
- [Phase 03-ci-matrix]: Individual uv run steps replace make check — make is unavailable on Windows runners
- [Phase 04-ux-and-docs]: ADR-007 follows same Status/Date/Context/Decisions/Consequences/Alternatives format as ADR-001 through ADR-006
- [Phase 04-ux-and-docs]: Windows docs placed as subsection of Installation in README; docs/usage.md Windows section placed before Configuration for Windows user onboarding flow
- [Phase 04-ux-and-docs]: home_dir parameter on _discover_default_catalog() for testability — avoids monkeypatching Path.home()
- [Phase 04-ux-and-docs]: type=click.Path() (no exists=True) allows None through to manual existence check in cli() body
- [Phase 04-ux-and-docs]: monkeypatch.delenv('LRC_CATALOG_PATH') required in no-catalog tests since dev machine has env var set
- [Phase 04-ux-and-docs]: PRD Section 4 names macOS and Windows as primary platforms; Linux documented as CI-only
- [Phase 04-ux-and-docs]: v0.6.0 CHANGELOG entry covers all Phase 1-4 changes: 11 Added, 4 Fixed, 3 Changed items

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 3 research flag: validate `reverse_geocoder` wheel availability on PyPI for Python 3.12/3.13 on Windows before committing CI approach (`--all-extras` gate on Windows runner may be needed).
- Phase 2 note: WAL mode should be documented in architecture comments during executor changes to prevent future accidental enablement on Windows.

### Codebase Notes

- Real catalog: ~92K photos across mixed folder naming conventions
- NAS at `/Volumes/photo/` not always mounted — offline handling needed
- Tests use in-memory SQLite; never `unittest.mock`, use `monkeypatch`
- `make check` must pass before commits
- `insert_after_symbol` can inject inside method body — prefer `replace_content` for tail-of-class edits

## Session Continuity

Last session: 2026-03-06T21:40:23.745Z
Stopped at: Completed 04-ux-and-docs-03-PLAN.md
Resume file: None
