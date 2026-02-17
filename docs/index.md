# lrc-automation

A Python CLI tool for automating Lightroom Classic catalog maintenance. It directly manipulates the `.lrcat` SQLite catalog and moves/renames files on disk, keeping Lightroom's catalog links intact.

## Why?

Lightroom Classic organizes photos in date-based folders, but sometimes files end up in the wrong folder (e.g. filed by file modification date instead of EXIF capture date). The Lightroom Classic Lua SDK cannot move photos between folders programmatically, so this tool works directly with the `.lrcat` SQLite database.

## Features

- **Scan** (read-only): Identify misplaced photos and files with duplicate date prefixes. Detects dates in `YYYY/MM/`, `YYYY-MM-DD`, and French date folder patterns (e.g. `1 avril 2016`)
- **Plan** (read-only): Generate a change plan, exportable to JSON or CSV for review
- **Apply** (write): Move files on disk and update the catalog, with mandatory backup and rollback on error
- **Validate**: Run integrity checks on the catalog
- **Restore**: Restore catalog from a backup

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Lightroom Classic **must be closed** during `apply` operations

## Quick start

```bash
git clone <repo-url>
cd lrc-automation
uv sync
lrc-auto -c "/path/to/catalog.lrcat" scan
```
