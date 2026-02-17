# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Known Issues
- Scanner only detects `YYYY/MM/` in `pathFromRoot`; real catalogs also use `YYYY-MM-DD` subfolders, French date folders, and dates in root folder paths
- No duplicate-prefix filenames found in real catalog (pattern may need broadening)

## [0.1.0] - 2026-02-17

### Added
- CLI with 5 commands: `scan`, `plan`, `apply`, `validate`, `restore`
- `CatalogScanner`: detect misplaced photos (folder date vs EXIF captureTime) and duplicate date prefixes in filenames
- `ChangePlanner`: build change plans with target folder resolution and collision handling
- `ChangeExecutor`: apply plans with disk moves + SQLite updates in a single transaction, with full rollback on error
- `CatalogValidator`: pre-flight and post-flight integrity checks (PRAGMA integrity_check, orphan detection)
- `Reporter`: Rich terminal output with scan summaries, change plan tables, and execution reports; JSON/CSV export
- `CatalogConnection`: context manager with backup, lock-file detection, and LR process check
- Date parsing for multiple captureTime formats (ISO 8601, EXIF-style, timezone offsets)
- Sidecar file handling (.xmp and sidecarExtensions) for moves and renames
- 37 tests with in-memory SQLite test catalogs
- ADR documenting why direct SQLite was chosen over Lua SDK
- README with usage examples and safety documentation
- Makefile with install/lint/format/typecheck/test/check/docs/clean targets
- GitHub Actions CI (Python 3.12/3.13 matrix) and docs deployment to GH Pages
- MkDocs Material documentation site (index, usage, architecture pages)
- mypy strict mode type checking
- Expanded ruff lint rules (bugbear, simplify, ruff-specific)
