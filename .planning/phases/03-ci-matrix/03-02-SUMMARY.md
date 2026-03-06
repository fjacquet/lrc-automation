---
phase: 03-ci-matrix
plan: 02
subsystem: infra
tags: [github-actions, sbom, anchore, release, ci]

requires: []
provides:
  - "release.yml with SBOM artifact attached to every GitHub release via anchore/sbom-action@v0"
  - "setup-uv@v7 with cache enabled in release workflow"
  - "uv run commands replacing make check in release workflow"
affects:
  - "03-ci-matrix"

tech-stack:
  added:
    - anchore/sbom-action@v0 (GitHub Actions step)
  patterns:
    - "SBOM generation via anchore/sbom-action before release upload"
    - "uv run commands for CI steps instead of make targets"

key-files:
  created: []
  modified:
    - .github/workflows/release.yml

key-decisions:
  - "anchore/sbom-action@v0 chosen over actions/attest-sbom: sbom-action produces a downloadable file on the releases page; attest-sbom creates a cryptographic attestation stored in GitHub API, not visible as a release artifact"
  - "setup-uv bumped to v7 with enable-cache: true for consistency with ci.yml and faster release builds"
  - "make check replaced by individual uv run commands for explicit step visibility in CI logs"
  - "SBOM step positioned after uv build and before softprops/action-gh-release so sbom-action auto-detects release context from push.tags trigger"

patterns-established:
  - "SBOM generation: anchore/sbom-action@v0 with artifact-name and format: spdx-json before the release upload step"

requirements-completed:
  - CI-04

duration: 5min
completed: 2026-03-06
---

# Phase 03 Plan 02: CI Matrix - SBOM Release Artifact Summary

**SBOM attached to every GitHub release via anchore/sbom-action@v0 producing lrc-automation-sbom.spdx.json, with setup-uv@v7 and uv run commands replacing make check**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-06T20:50:00Z
- **Completed:** 2026-03-06T20:55:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `anchore/sbom-action@v0` step to release.yml before `softprops/action-gh-release` — every tag push now produces `lrc-automation-sbom.spdx.json` as a release artifact
- Bumped `astral-sh/setup-uv` from v4 to v7 with `enable-cache: true` for consistency with ci.yml and faster release builds
- Replaced `make check` with four explicit `uv run` commands (ruff check, ruff format --check, mypy, pytest) for clearer CI step visibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Add SBOM generation step and upgrade release.yml** - `bab01ba` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `.github/workflows/release.yml` - Added SBOM step, bumped setup-uv to v7, replaced make check with uv run commands

## Decisions Made
- `anchore/sbom-action@v0` chosen over `actions/attest-sbom` because sbom-action produces a downloadable `.spdx.json` file visible on the GitHub releases page, while attest-sbom creates a cryptographic attestation stored in the GitHub API — not a downloadable artifact.
- `enable-cache: true` added to setup-uv@v7 to speed up release builds via uv cache.
- `make check` replaced by individual `uv run` commands for explicit visibility of each check step in CI logs.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The `anchore/sbom-action@v0` uses the existing `permissions: contents: write` already present at the job level.

## Next Phase Readiness
- CI-04 requirement satisfied: every release tag push will now attach `lrc-automation-sbom.spdx.json` as a release artifact
- Release workflow is consistent with ci.yml: both use setup-uv@v7, both use uv run commands

---
*Phase: 03-ci-matrix*
*Completed: 2026-03-06*
