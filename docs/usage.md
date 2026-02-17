# Usage

## Configuration

Copy `.env.example` to `.env` and set your catalog path:

```bash
cp .env.example .env
```

```env
LRC_CATALOG_PATH=/path/to/your/Lightroom Catalog.lrcat
LRC_BACKUP_DIR=                # optional, defaults to catalog directory
LRC_TARGET_LAYOUT=%Y/%m/       # optional, strftime format for target folders
```

### Target folder layout

The `LRC_TARGET_LAYOUT` variable controls the target folder structure using Python `strftime` format codes. Defaults to `%Y/%m/` (e.g. `2023/06/`).

| Layout | Example | Description |
|--------|---------|-------------|
| `%Y/%m/` | `2023/06/` | Year/Month (default) |
| `%Y/%m/%d/` | `2023/06/15/` | Year/Month/Day |
| `%Y-%m/` | `2023-06/` | Year-Month with dash |
| `%Y/` | `2023/` | Flat yearly |

You can also pass it as a CLI option:

```bash
lrc-auto --target-layout "%Y/%m/%d/" -c catalog.lrcat scan
```

## Commands

### Scan (read-only, always safe)

```bash
# Scan for issues
lrc-auto -c "/path/to/catalog.lrcat" scan

# Export results to JSON or CSV
lrc-auto -c "/path/to/catalog.lrcat" scan -o results.json
lrc-auto -c "/path/to/catalog.lrcat" scan -o results.csv
```

### Plan (read-only)

```bash
# Preview all planned changes
lrc-auto -c "/path/to/catalog.lrcat" plan

# Plan only moves or only renames
lrc-auto -c "/path/to/catalog.lrcat" plan --fix moves
lrc-auto -c "/path/to/catalog.lrcat" plan --fix renames

# Export plan for review
lrc-auto -c "/path/to/catalog.lrcat" plan -o plan.json
```

### Apply (modifies catalog + disk)

```bash
# Apply all fixes (prompts for confirmation, creates backup)
lrc-auto -c "/path/to/catalog.lrcat" apply

# Apply only moves
lrc-auto -c "/path/to/catalog.lrcat" apply --fix moves

# Skip confirmation prompt
lrc-auto -c "/path/to/catalog.lrcat" apply -y
```

### Validate

```bash
lrc-auto -c "/path/to/catalog.lrcat" validate
```

### Restore from backup

```bash
lrc-auto -c "/path/to/catalog.lrcat" restore --backup-path /path/to/backup.lrcat.bak-20260217
```

## Supported folder structures

The scanner detects dates in folder paths using multiple patterns:

| Pattern | Example | Source |
|---------|---------|--------|
| `YYYY-MM-DD` | `/Volumes/photo/Weekends/2023/2023-12-24/` | ISO date folders |
| French dates | `/Volumes/photo/iphone/1 avril 2016/` | Apple Photos / iPhoto exports |
| `YYYY/MM/` | `2023/06/` | Classic date hierarchy |

Dates are extracted from both the root folder path and the `pathFromRoot` in the catalog.
