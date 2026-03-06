# Phase 3: CI Matrix - Research

**Researched:** 2026-03-06
**Domain:** GitHub Actions CI — multi-OS matrix, line-ending hygiene, SBOM generation
**Confidence:** HIGH

## Summary

Phase 3 upgrades the project's GitHub Actions configuration to achieve three goals: a three-platform
(ubuntu/macos/windows), two-version (3.12/3.13) CI matrix that replaces the current ubuntu-only
workflow; a `.gitattributes` file that enforces LF line endings on checkout so `ruff format --check`
passes on the Windows runner; and an SBOM artifact automatically attached to every GitHub release.

The existing `ci.yml` runs `make check` which is unavailable on Windows runner images by default.
CI-01 therefore requires replacing the `make check` call with explicit `uv run` commands that work
identically on all three platforms. The current `setup-uv@v4` reference must be bumped to `v7`
(CI-03). The SBOM requirement (CI-04) is best served by `anchore/sbom-action@v0`, which
auto-detects GitHub release context and uploads the SBOM as a release asset without additional
upload steps.

**Primary recommendation:** Expand `ci.yml` to a 3x2 matrix using `uv run` commands instead of
`make`; add `.gitattributes`; bump `setup-uv` to `v7`; add `anchore/sbom-action@v0` to
`release.yml`.

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CI-01 | GitHub Actions CI runs and passes on `windows-latest` runner using `uv run` commands (no dependency on `make`) | `make` is not available on `windows-latest`; replace all `make check` steps with explicit `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` calls |
| CI-02 | Repository has `.gitattributes` enforcing LF line endings so `ruff format --check` passes on Windows CI checkout | File does not exist yet; `* text=auto eol=lf` pattern is the standard; no re-normalisation of existing files is needed because all source was committed on macOS |
| CI-03 | CI workflow uses `setup-uv@v7` (current stable, up from v4) | v7.3.1 is latest stable; v7 adds OS-aware cache keys and separate Python binary caching; drop-in replacement for v4 |
| CI-04 | SBOM is generated automatically at release build time and attached to the GitHub release as an artifact | `anchore/sbom-action@v0` auto-detects release context and uploads to release assets; requires `contents: write` permission which `release.yml` already has |
</phase_requirements>

## Standard Stack

### Core

| Library / Action | Version | Purpose | Why Standard |
|-----------------|---------|---------|--------------|
| `astral-sh/setup-uv` | `v7` (latest: v7.3.1) | Install uv and manage Python version in CI | Official action from uv's own team; v7 is current stable |
| `anchore/sbom-action` | `v0` (latest: v0.23.0) | Generate SBOM and upload as release asset | Maintained by Anchore/Syft team; auto-detects release context; most widely used GitHub SBOM action |
| `.gitattributes` | n/a (Git feature) | Enforce LF on checkout for all text files | Built-in Git mechanism; zero runtime cost; works before any tool runs |

### Supporting

| Library / Action | Version | Purpose | When to Use |
|-----------------|---------|---------|-------------|
| `actions/checkout` | `v4` | Checkout repository | Already in use; no change needed |
| `cyclonedx-python` | `uv tool` | Alternative Python-specific SBOM generator | If CycloneDX format is preferred over SPDX; syft (used by sbom-action) is format-agnostic |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `anchore/sbom-action@v0` | `CycloneDX/gh-python-generate-sbom@v2` | CycloneDX action is deprecated; upstream recommends direct `cyclonedx-py` CLI |
| `anchore/sbom-action@v0` | `actions/attest-sbom` | attest-sbom creates a cryptographic attestation, not a downloadable file artifact; does not appear as a file on the releases page |
| `make check` in CI | Makefile with `bash -c` wrapper | Adding bash dependency on Windows adds complexity; direct `uv run` is cleaner |

## Architecture Patterns

### Recommended Project Structure (CI files)

```
.github/
├── workflows/
│   ├── ci.yml          # Expanded to 3-OS × 2-Python matrix; uv run replaces make
│   ├── release.yml     # Add anchore/sbom-action step before release creation
│   └── docs.yml        # No changes needed
.gitattributes           # NEW: enforce LF for all text files
```

### Pattern 1: Multi-OS Matrix with uv run

**What:** Use `strategy.matrix` with both `os` and `python-version` dimensions; replace `make check`
with individual `uv run` commands.

**When to use:** When `make` is not reliably available on all target runners (Windows lacks it by
default on `windows-latest`).

**Example:**

```yaml
# Source: https://docs.astral.sh/uv/guides/integration/github/
jobs:
  check:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python-version }}
          enable-cache: true

      - run: uv sync

      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src/
      - run: uv run pytest -v
```

### Pattern 2: .gitattributes LF Enforcement

**What:** A `.gitattributes` file at repo root that normalises all text files to LF in the index
and on checkout.

**When to use:** Always for cross-platform Python projects; ruff checks line endings and will fail
`--check` if CRLF appears in committed files on Windows.

**Example:**

```
# Source: https://git-scm.com/docs/gitattributes
# Normalize all text files to LF line endings
* text=auto eol=lf

# Explicitly binary files (no line-ending conversion)
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.whl binary
*.tar.gz binary
*.lrcat binary
*.db binary
```

### Pattern 3: SBOM in Release Workflow

**What:** Add `anchore/sbom-action@v0` as a step in `release.yml` before the release creation
step. The action scans the workspace, generates an SPDX-JSON SBOM, and automatically attaches it
to the release because it detects the `push.tags` trigger context.

**When to use:** On every tag push that creates a release.

**Example:**

```yaml
# Source: https://github.com/anchore/sbom-action
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    artifact-name: lrc-automation-sbom.spdx.json
    format: spdx-json
```

The `release.yml` job already has `permissions: contents: write`, which is exactly what
`sbom-action` needs to upload as a release asset. No additional permission changes are required.

### Anti-Patterns to Avoid

- **Using `make check` in Windows CI jobs:** `make` is not installed on `windows-latest` GitHub
  runners. The job will fail with "make: command not found". Use direct `uv run` calls instead.
- **Pinning `setup-uv@v4`:** v4 is outdated; v7 has OS-aware cache keys that prevent binary
  incompatibility between runners. Using v4 in a multi-OS matrix risks cache corruption.
- **Using `actions/attest-sbom` for a downloadable artifact:** This action creates a cryptographic
  attestation stored in GitHub's attestation API, not a file shown on the releases page. The
  success criterion requires a visible artifact on the GitHub releases page — use
  `anchore/sbom-action` instead.
- **`--all-extras` on the Windows CI runner for the test suite:** `reverse_geocoder` (the `[geo]`
  extra) only ships a source distribution (tar.gz) on PyPI — no Windows binary wheel. Building
  from source requires a C compiler, scipy, and numpy build chain, which is fragile in CI. The
  standard `uv sync` (no `--all-extras`) is correct for the test matrix; the packaging tests
  (`test_packaging.py`) already test the import guard without the actual library installed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SBOM generation | Custom script parsing pyproject.toml | `anchore/sbom-action@v0` | Syft handles transitive dependencies, virtual env scanning, and format standards |
| Line-ending enforcement | Pre-commit hook or CI script | `.gitattributes` | Git normalises at commit/checkout time before any tool runs |
| Python version matrix | Manual workflow per Python version | `strategy.matrix` with `python-version` | Native GitHub Actions feature; cleaner, less duplication |
| uv cache on CI | Manual `actions/cache` configuration | `astral-sh/setup-uv@v7` with `enable-cache: true` | Action handles cache key composition including OS, uv version, lockfile hash |

**Key insight:** All four CI requirements are solvable with existing off-the-shelf GitHub Actions
and Git features. Zero custom tooling is needed.

## Common Pitfalls

### Pitfall 1: `make` not found on Windows runners

**What goes wrong:** `run: make check` exits with code 127 on `windows-latest` because GNU Make
is not pre-installed on GitHub-hosted Windows runners (unlike ubuntu/macos).
**Why it happens:** The existing `ci.yml` was written for ubuntu only; Windows runner environment
differs.
**How to avoid:** Replace `make check` with individual `uv run ruff check .`, `uv run ruff format
--check .`, `uv run mypy src/`, `uv run pytest -v` steps.
**Warning signs:** CI log shows "make: command not found" or "The system cannot find the path".

### Pitfall 2: CRLF in committed files causes ruff format --check to fail

**What goes wrong:** On Windows, `git checkout` converts LF to CRLF for text files (default
`core.autocrlf=true` in many Windows Git installations). When `ruff format --check` runs, it
detects the CRLF endings and considers the file "would be reformatted".
**Why it happens:** Without `.gitattributes`, line-ending handling depends on each developer's
local Git config; CI runners may also apply CRLF conversion.
**How to avoid:** Add `.gitattributes` with `* text=auto eol=lf` before expanding CI to Windows.
If files have already been checked in with CRLF (unlikely here since all commits are from macOS),
run `git add --renormalize .` after adding `.gitattributes`.
**Warning signs:** ruff format --check fails only on Windows runner, passes on ubuntu/macos.

### Pitfall 3: setup-uv cache invalidation between v4 and v7

**What goes wrong:** Bumping from v4 to v7 invalidates the existing CI cache. First runs after
the bump will be slower (full uv install + dependency download).
**Why it happens:** v7 changed cache key format to include OS version; this is intentional to
prevent binary incompatibility.
**How to avoid:** Expected single-time slowdown; no action needed. Just be aware CI takes longer
on the first run.
**Warning signs:** CI log shows "Cache not found" on first run after bump — this is normal.

### Pitfall 4: reverse_geocoder [geo] extra fails to build on Windows CI

**What goes wrong:** `uv sync --all-extras` on Windows fails because `reverse_geocoder==1.5.1`
has only a source distribution on PyPI. Building from source requires `scipy` which requires a
C compiler that is not reliably available.
**Why it happens:** `reverse_geocoder` was last released in 2016 and has never shipped Windows
wheels.
**How to avoid:** Do NOT use `--all-extras` in the CI matrix test steps. Use plain `uv sync`.
The `[geo]` extra is only needed for live geo lookups, not the test suite (tests stub it out).
**Warning signs:** Build log shows "building wheel for reverse_geocoder" followed by compile
errors.

### Pitfall 5: SBOM action duplicate artifact names in matrix builds

**What goes wrong:** If `anchore/sbom-action` is used inside a matrix job, all matrix instances
try to upload an artifact with the same name, causing an artifact-upload conflict.
**Why it happens:** Default artifact name is static; matrix runs concurrently.
**How to avoid:** SBOM generation belongs in `release.yml` which runs on a single non-matrix job
(ubuntu-latest only). Do not add SBOM generation to the CI matrix job.
**Warning signs:** GitHub Actions error "An artifact with this name already exists".

## Code Examples

Verified patterns from official sources:

### Complete ci.yml (multi-OS matrix, uv run, no make)

```yaml
# Source: https://docs.astral.sh/uv/guides/integration/github/
name: CI

on:
  push:
    branches: [maincd]
  pull_request:
    branches: [maincd]

jobs:
  check:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python-version }}
          enable-cache: true

      - run: uv sync

      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src/
      - run: uv run pytest -v
```

### SBOM step addition to release.yml

```yaml
# Source: https://github.com/anchore/sbom-action
# Add this step BEFORE the softprops/action-gh-release step.
# The existing `permissions: contents: write` already covers this action.
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    artifact-name: lrc-automation-sbom.spdx.json
    format: spdx-json
```

### .gitattributes

```
# Source: https://git-scm.com/docs/gitattributes
# Normalise all text files to LF on commit and checkout
* text=auto eol=lf

# Binary files — no line-ending conversion
*.whl binary
*.tar.gz binary
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.lrcat binary
*.db binary
*.sqlite binary
```

### Fixing existing files after adding .gitattributes (if needed)

```bash
# Only needed if CRLF files are already in the index (not expected here)
git add --renormalize .
git commit -m "chore: normalise line endings to LF"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `astral-sh/setup-uv@v4` | `astral-sh/setup-uv@v7` | v7.0.0 (late 2024) | OS-aware cache keys; separate Python binary caching; prevents cross-platform cache poisoning |
| Ubuntu-only CI | 3-OS matrix | Phase 3 (this phase) | Windows and macOS coverage catches platform-specific bugs |
| No SBOM | SBOM via anchore/sbom-action | Phase 3 (this phase) | Supply chain transparency; compliance with emerging SBOM requirements |
| `make check` in CI | Direct `uv run` commands | Phase 3 (this phase) | Works on Windows runner without installing GNU Make |

**Deprecated/outdated:**

- `astral-sh/setup-uv@v4`: Outdated; lacks OS-aware cache keys needed for a multi-OS matrix.
- `CycloneDX/gh-python-generate-sbom@v2`: Officially deprecated by CycloneDX; use `cyclonedx-py` CLI or `anchore/sbom-action` instead.

## Open Questions

1. **Does `reverse_geocoder` have undocumented Windows wheels anywhere?**
   - What we know: PyPI page only lists a source distribution (tar.gz, 2016). Issue #74 in the GitHub repo ("Wheel") was reopened in 2023 but remains unresolved.
   - What's unclear: Whether a conda-forge or alternative source provides Windows wheels.
   - Recommendation: Proceed with the safe approach — do NOT use `--all-extras` in the Windows CI runner. The test suite does not need the geo extra to pass.

2. **Should the CI matrix also run `uv sync --all-extras` on Linux/macOS runners?**
   - What we know: CI-01 only requires Windows runner to use `uv run`. The success criteria focus on passing CI on all three platforms.
   - What's unclear: Whether comprehensive testing of the `[geo]` extra path is a separate concern.
   - Recommendation: Limit scope to `uv sync` (no extras) on all three platforms to keep the matrix uniform and avoid platform-specific conditional steps. The geo import guard is already tested in `test_packaging.py` without the library installed.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_packaging.py -v` |
| Full suite command | `uv run pytest -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CI-01 | CI workflow runs on Windows with `uv run` commands | manual/CI | Push to branch and observe GitHub Actions result | ❌ Wave 0 — no local test possible; verified by CI green badge |
| CI-02 | `.gitattributes` LF enforcement prevents CRLF in index | smoke | `git check-attr eol -- src/lrc_automation/cli.py` outputs `eol: lf` | ❌ Wave 0 |
| CI-03 | `setup-uv@v7` in workflow file | static check | `grep "setup-uv@v7" .github/workflows/ci.yml` | ❌ Wave 0 |
| CI-04 | SBOM artifact appears on GitHub release | manual/CI | Trigger release tag, inspect GitHub releases page for `*.spdx.json` | ❌ Wave 0 — no local test; verified by release inspection |

**Note:** CI-01, CI-03, and CI-04 are infrastructure changes verifiable only by running actual CI
or inspecting GitHub UI. There are no unit tests to write for these. CI-02 is verifiable locally
via `git check-attr` after adding `.gitattributes`.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_packaging.py -v` (confirm packaging tests still pass)
- **Per wave merge:** `uv run pytest -v` (full suite)
- **Phase gate:** Full suite green on local macOS + CI green on all three platforms before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] No new test files needed — all phase requirements are infrastructure changes (YAML, `.gitattributes`).
- [ ] CI-01/CI-04 verification is manual (observe GitHub Actions log and releases page).
- [ ] `git check-attr eol -- src/lrc_automation/cli.py` confirms CI-02 locally after `.gitattributes` is added.

## Sources

### Primary (HIGH confidence)

- [astral-sh/uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/) — recommended workflow structure, v7 usage, matrix pattern
- [astral-sh/setup-uv releases](https://github.com/astral-sh/setup-uv/releases) — v7.3.1 latest; v7 breaking change summary
- [anchore/sbom-action GitHub](https://github.com/anchore/sbom-action) — v0.23.0 current; `contents: write` permission; release asset auto-upload

### Secondary (MEDIUM confidence)

- [git-scm.com/docs/gitattributes](https://git-scm.com/docs/gitattributes) — `text=auto eol=lf` syntax confirmed in official Git docs
- [pypi.org/project/reverse_geocoder/](https://pypi.org/project/reverse_geocoder/) — only tar.gz available (no wheels), last release 2016; Windows build risk confirmed

### Tertiary (LOW confidence)

- [CycloneDX/gh-python-generate-sbom README](https://github.com/CycloneDX/gh-python-generate-sbom/blob/master/README.md) — self-declared deprecated; mentioned for completeness only

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — official docs and action repos consulted directly
- Architecture: HIGH — patterns derived from official uv docs and sbom-action README
- Pitfalls: HIGH for make/CRLF (well-known issues); MEDIUM for reverse_geocoder Windows build (confirmed source-dist-only but build environment not tested)

**Research date:** 2026-03-06
**Valid until:** 2026-06-06 (stable domain; setup-uv and sbom-action release frequently but v7/v0 major pins remain stable)
