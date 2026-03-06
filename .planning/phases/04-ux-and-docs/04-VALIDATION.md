---
phase: 4
slug: ux-and-docs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | UX-01 | unit | `uv run pytest tests/test_cli.py -k "auto_discover" -x -q` | W0 | pending |
| 4-01-02 | 01 | 1 | UX-01 | unit | `uv run pytest tests/test_cli.py -k "discover" -x -q` | W0 | pending |
| 4-02-01 | 02 | 2 | UX-02 | manual | see Manual-Only table | N/A | pending |
| 4-02-02 | 02 | 2 | UX-04 | manual | see Manual-Only table | N/A | pending |
| 4-03-01 | 03 | 2 | UX-05 | manual | see Manual-Only table | N/A | pending |
| 4-03-02 | 03 | 2 | UX-06 | manual | see Manual-Only table | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cli.py` — add stubs for auto-discovery tests (UX-01)

*Existing infrastructure covers most phase requirements. Only UX-01 code change requires new tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| README Windows section is complete and accurate | UX-02 | Prose/doc review | Read `README.md` Windows section and verify it covers `uv`/`pipx` install, `.env` syntax, MAX_PATH advisory |
| `docs/usage.md` Windows first-run section | UX-02 | Prose/doc review | Read `docs/usage.md` and verify Windows section is present and complete |
| ADR exists documenting multiplatform decisions | UX-04 | Doc existence + content review | Verify `docs/adr/` contains ADR covering `psutil`, `path.as_posix()`, `sys.platform`, SBOM |
| `docs/prd.md` names macOS+Windows as targets | UX-05 | Prose/doc review | Read `docs/prd.md` and verify macOS/Windows target platforms are named; Linux CI-only constraint documented |
| `CHANGELOG.md` v0.6.0 entry is complete | UX-06 | Content completeness review | Read `CHANGELOG.md` and verify `[0.6.0]` section lists all Phase 1-4 changes |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
