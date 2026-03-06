# Requirements: lrc-automation

**Defined:** 2026-03-06
**Core Value:** Photos stay at the path their EXIF capture date dictates, so the Lightroom catalog folder tree always reflects reality.

## v0.6.0 Requirements

Requirements for the multiplatform milestone (Mac + Windows support).

### PATH — Path Safety

- [x] **PATH-01**: Tool opens Lightroom catalog on Windows without SQLite URI error (normalize `file:` URI to forward slashes before opening)
- [x] **PATH-02**: Scan correctly extracts dates when catalog root uses Windows drive-letter paths (`C:/Photos/`) combined with `pathFromRoot`
- [x] **PATH-03**: Tool detects and warns the user when a Mac-origin catalog (`absolutePath` contains `/Volumes/`) is opened on Windows, without crashing

### PROC — Process Detection & Write Safety

- [x] **PROC-01**: Tool detects Lightroom Classic running on Windows via `psutil` (replaces the silent `pgrep` no-op, checks `Lightroom.exe`)
- [x] **PROC-02**: `pathFromRoot` SQL column is always written with forward slashes on Windows so Lightroom can locate folders after a move
- [x] **PROC-03**: AppleDouble (`._*`) file cleanup is skipped silently on non-macOS platforms (no errors, no spurious log entries)
- [x] **PROC-04**: File moves retry on `PermissionError` to handle transient antivirus scan locks on Windows

### CI — CI & Dev Tooling

- [ ] **CI-01**: GitHub Actions CI runs and passes on `windows-latest` runner using `uv run` commands (no dependency on `make`)
- [ ] **CI-02**: Repository has `.gitattributes` enforcing LF line endings so `ruff format --check` passes on Windows CI checkout
- [ ] **CI-03**: CI workflow uses `setup-uv@v7` (current stable, up from v4)
- [x] **CI-04**: SBOM (Software Bill of Materials) is generated automatically at release build time and attached to the GitHub release as an artifact

### UX — User Experience & Docs

- [ ] **UX-01**: `--catalog` flag is optional; tool auto-discovers the default catalog path for the current OS (macOS: `~/Pictures/Lightroom/`, Windows: `%USERPROFILE%\Pictures\Lightroom\`)
- [ ] **UX-02**: README and `docs/usage.md` include a Windows installation and first-run section
- [x] **UX-03**: `reverse_geocoder` is moved back to optional `[geo]` extra dependency (fixes pre-existing packaging regression from v0.5.0)
- [ ] **UX-04**: ADR written documenting the multiplatform approach and decisions (process detection, path normalisation, SBOM)
- [ ] **UX-05**: `docs/prd.md` updated to reflect multiplatform scope (Mac + Windows target platforms)
- [ ] **UX-06**: `CHANGELOG.md` updated for v0.6.0 with all changes documented

## Future Requirements

### Cross-platform (deferred)

- Cross-OS catalog migration (Mac catalog opened on Windows with `/Volumes/` paths) — Lightroom itself handles reconciliation via "Find Missing Folder"; too complex for this milestone
- Linux end-user support — Lightroom Classic does not run on Linux; CI-only coverage is sufficient

## Out of Scope

| Feature | Reason |
|---------|--------|
| Linux end-user support | Lightroom Classic is Mac/Windows only |
| Cross-OS catalog migration | Lightroom's own "Find Missing Folder" handles this; out of our safety boundary |
| Auto-repair of Mac catalogs on Windows | Too risky; warn and exit is the correct behavior |
| GUI | CLI tool for power users; no change to this decision |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PATH-01 | Phase 1 | Complete |
| PATH-02 | Phase 1 | Complete |
| PATH-03 | Phase 1 | Complete |
| UX-03 | Phase 1 | Complete |
| PROC-01 | Phase 2 | Complete |
| PROC-02 | Phase 2 | Complete |
| PROC-03 | Phase 2 | Complete |
| PROC-04 | Phase 2 | Complete |
| CI-01 | Phase 3 | Pending |
| CI-02 | Phase 3 | Pending |
| CI-03 | Phase 3 | Pending |
| CI-04 | Phase 3 | Complete |
| UX-01 | Phase 4 | Pending |
| UX-02 | Phase 4 | Pending |
| UX-04 | Phase 4 | Pending |
| UX-05 | Phase 4 | Pending |
| UX-06 | Phase 4 | Pending |

**Coverage:**

- v0.6.0 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 — traceability filled after roadmap creation*
