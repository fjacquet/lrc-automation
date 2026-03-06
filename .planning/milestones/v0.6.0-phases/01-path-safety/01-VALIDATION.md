---
phase: 1
slug: path-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | PATH-01 | unit | `uv run pytest tests/test_catalog.py -k sqlite_uri -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | PATH-02 | unit | `uv run pytest tests/test_scanner.py -k windows_path -x -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | PATH-03 | unit | `uv run pytest tests/test_catalog.py -k cross_os_warning -x -q` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | UX-03 | integration | `uv run pip show lrc-automation 2>/dev/null; uv run pytest tests/test_packaging.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_catalog.py` — add stubs for SQLite URI fix (PATH-01) and cross-OS warning (PATH-03)
- [ ] `tests/test_scanner.py` — add stubs for Windows drive-letter path handling (PATH-02)

*Existing test infrastructure covers the framework; only new test stubs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pip install lrc-automation` on a clean env does not pull reverse_geocoder | UX-03 | Requires a real clean install environment | `pip install lrc-automation` in a fresh venv; `pip show reverse-geocoder` must show "not found" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
