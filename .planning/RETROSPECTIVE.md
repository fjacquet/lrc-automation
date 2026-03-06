# lrc-automation — Project Retrospective

> Living document. One section per milestone, updated at completion.

---

## Milestone: v0.6.0 — Multiplatform

**Shipped:** 2026-03-06
**Phases:** 4 | **Plans:** 10 | **Tasks:** ~20

### What Was Built

- **Phase 1 (Path Safety):** SQLite URI helper `_path_to_sqlite_uri()` for Windows drive-letter paths; backslash normalisation in scanner; `geo` extra decoupled from core install
- **Phase 2 (Write Safety):** `psutil` cross-platform process detection; `path.as_posix()` SQL writes for `pathFromRoot`; `sys.platform` AppleDouble guard; `PermissionError` retry loop
- **Phase 3 (CI Matrix):** 3-OS GitHub Actions matrix (ubuntu/macos/windows); `.gitattributes` LF enforcement; `setup-uv@v7`; SBOM release artifact via `anchore/sbom-action`
- **Phase 4 (UX and Docs):** Zero-config catalog discovery (`_discover_default_catalog`); Windows onboarding in README + docs/usage.md; ADR-007 multiplatform decisions; PRD + CHANGELOG updated

### What Worked

- **TDD RED-GREEN pattern** — Consistently used across all phases. Failing tests first commit, fix second commit. Caught cross-platform edge cases (e.g., `Path.is_absolute()` returning `False` for drive-letter paths on macOS).
- **Surgical, contained changes** — No new platform abstraction layer. Each fix has exactly one call site. Kept diff size small and review tractable.
- **Wave parallelization in Phase 4** — Plans 04-01 and 04-02 ran in parallel (different file sets), saving time.
- **Research-first planning** — Researcher identified the `Path.is_absolute()` cross-platform gotcha before implementation, preventing a wasted iteration.
- **`home_dir` injection pattern** — Testable without monkeypatching builtins; cleaner than mock-based approaches.

### What Was Inefficient

- **`make check` unavailable on Windows runners** — Discovered during Phase 3; required switching to individual `uv run` steps in CI. Could have been caught earlier in planning.
- **`reverse_geocoder` Windows wheel gap** — Known constraint, forced `uv sync` without `--all-extras` on Windows. Phase 1 UX-03 fix (geo extra) was the right call but the CI implication only surfaced in Phase 3.
- **STATE.md `percent: 33%`** — Tools calculated progress at 33% even after all phases completed (likely based on milestone version tracking). Minor cosmetic issue.

### Patterns Established

- `norm_root = photo.root_absolute_path.replace("\\", "/")` — normalise at call site, not at model construction
- `_MOVE_RETRY_SLEEP` as module-level constant for monkeypatching in tests
- `monkeypatch.delenv('LRC_CATALOG_PATH')` required in auto-discovery tests when env var set in dev environment
- ADR format established: Status/Date/Context/Decisions/Consequences/Alternatives (ADR-001 through ADR-007)

### Key Lessons

- **Test on macOS for Windows paths too** — `Path("C:/foo").is_absolute()` is `False` on macOS. Always use posix string checks for drive-letter detection cross-platform.
- **WAL mode is incompatible with Windows file locking** — Document this at the call site to prevent future accidental enablement.
- **Rollback action must be appended AFTER the disk op completes** — Prevents ghost rollbacks if the op fails before completing.
- **`click.Path(exists=True)` breaks optional args** — Drop `exists=True` and validate manually in the command body when the argument may be `None`.

### Cost Observations

- Model mix: sonnet throughout (researcher, planner, checker, executor, verifier)
- Sessions: 1 continuous session (single day)
- Notable: All 4 phases planned and executed in a single session; 215 tests passing at completion

---

## Cross-Milestone Trends

| Metric | v0.6.0 |
|--------|--------|
| Phases | 4 |
| Plans | 10 |
| Avg tasks/plan | ~2 |
| Test count at ship | 215 |
| Verification pass rate | 100% (all phases passed first attempt) |
| Gap closure cycles | 0 |
| Python LOC | 7,815 |
