---
phase: 3
slug: ci-matrix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src/` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | CI-01, CI-03 | CI workflow lint | `grep -r 'setup-uv@v7' .github/workflows/` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | CI-02 | file check | `test -f .gitattributes && grep 'text=auto' .gitattributes` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | CI-04 | workflow lint | `grep -r 'sbom-action' .github/workflows/release.yml` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `.gitattributes` — creates `* text=auto eol=lf` rule (CI-02)
- [ ] `.github/workflows/ci.yml` — multi-OS matrix with `windows-latest`, `macos-latest`, `ubuntu-latest` and `setup-uv@v7` (CI-01, CI-03)
- [ ] `.github/workflows/release.yml` — add `anchore/sbom-action` step (CI-04)

*All changes are config-file edits; no new test files needed beyond verification commands above.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI matrix badge shows green for all 3 OS | CI-01 | Requires actual GitHub Actions run | Push to branch, verify badge on GitHub |
| SBOM artifact visible on release page | CI-04 | Requires a real GitHub release | Create test tag, verify release artifacts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
