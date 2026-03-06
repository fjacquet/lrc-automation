# Usage

## Windows Installation and First Run

### Requirements

- Windows 10 or later
- Python 3.12+ (from [python.org](https://www.python.org/downloads/) or the Windows Store)
- `uv` or `pipx`

### Install with uv

```powershell
pip install uv
uv tool install lrc-automation
```

### Install with pipx

```powershell
pip install pipx
pipx install lrc-automation
```

### MAX_PATH Advisory

Windows limits file paths to 260 characters by default. If your Lightroom catalog root paths are deeply nested (e.g. on a NAS or an external drive with a long mount path), enable long-path support before running the tool:

**Option 1 — Group Policy Editor:**

1. Open `gpedit.msc`
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

**Option 2 — PowerShell (requires admin):**

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

### First Run

The `--catalog` / `-c` flag is optional. The tool auto-discovers the default Lightroom Classic catalog at `%USERPROFILE%\Pictures\Lightroom\` when no catalog is specified:

```powershell
# Auto-discover default Lightroom catalog
lrc-auto scan

# Or specify explicitly (both slash styles work equally well)
lrc-auto -c "C:\Users\YourName\Pictures\Lightroom\Catalog.lrcat" scan
lrc-auto -c "C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat" scan
```

If discovery fails (default directory doesn't exist or is empty), the tool prints a usage error:

```
Error: No catalog specified and none found at the default path.
Use --catalog / -c or set LRC_CATALOG_PATH in your .env file.
```

### .env File on Windows

Create a `.env` file in the directory where you run `lrc-auto`. Both forward slashes and escaped backslashes work as path separators:

```env
# Forward slashes (recommended — works on all platforms)
LRC_CATALOG_PATH=C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat
LRC_BACKUP_DIR=C:/Users/YourName/Documents/LightroomBackups

# Backslashes also work (Windows-native style)
LRC_CATALOG_PATH=C:\\Users\\YourName\\Pictures\\Lightroom\\Catalog.lrcat
```

### Known Limitations on Windows

- **Location folders (`--location-folders`):** The `[geo]` extra (`reverse_geocoder`) has no Windows wheel on PyPI. GPS-based `Country/City/` subfolders are available on macOS and Linux only.
- **AppleDouble (`._*`) cleanup:** The `cleanup` command's AppleDouble removal step is silently skipped on Windows (those files only appear on macOS-formatted volumes).

## Configuration

Copy `.env.example` to `.env` and set your catalog path:

```bash
cp .env.example .env
```

```env
LRC_CATALOG_PATH=/path/to/your/Lightroom Catalog.lrcat
LRC_BACKUP_DIR=                # optional, defaults to catalog directory
LRC_TARGET_LAYOUT=%Y/%m/       # optional, strftime format for target folders
LRC_LOCATION_FOLDERS=false     # optional, enable GPS-based Country/City subfolders
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

### Location-based subfolders (optional)

If your photos have GPS coordinates, you can organize them into `Country/City/` subfolders within the date hierarchy.

**Install the geo extra:**

```bash
pip install lrc-automation[geo]
```

**Enable via CLI flag or environment variable:**

```bash
# CLI flag
lrc-auto --location-folders -c catalog.lrcat scan

# Environment variable
LRC_LOCATION_FOLDERS=true lrc-auto -c catalog.lrcat scan
```

When enabled, photos with GPS data are placed in folders like `2023/06/CH/Zurich/` instead of just `2023/06/`. Photos without GPS coordinates fall back to the date-only path.

The feature uses the `reverse_geocoder` library for fast, offline lookups (no internet required). Country codes follow ISO 3166-1 alpha-2 (e.g. `CH`, `FR`, `NZ`).

## Supported folder structures

The scanner detects dates in folder paths using multiple patterns. It scans the **full path** (root folder + pathFromRoot) **right-to-left**, so the deepest (most specific) date segment wins.

| Pattern | Example | Detection |
|---------|---------|-----------|
| `YYYY/MM/` | `2023/06/` | Classic date hierarchy |
| `YYYY-MM-DD` | `2023-12-24/` | ISO date folders (day is ignored, year+month extracted) |
| French dates | `1 avril 2016/` | Apple Photos / iPhoto exports. Supports accented forms (`février`, `août`, `décembre`) and is case-insensitive |
| Year in root + month | Root `/photos/2021/` + path `06/` | Year detected from root path, month from immediate subfolder |

### Filtering

- **Lightroom epoch (1904)**: Year 1904 is the default "no date" value in Lightroom. Folders with this year are skipped.
- **Topical folders**: Folders without any recognizable date pattern (e.g. `Vacances/`, `Family/`) are silently skipped — they will not appear as misplaced.
- **Year range**: Only years between 1900 and 2100 are accepted (excluding 1904).

### Examples from real catalogs

```
/Volumes/photo/Weekends/2023/2023-12-24/IMG_1234.CR2  → detected as 2023/12
/Volumes/photo/iphone/1 avril 2016/IMG_5678.JPG       → detected as 2016/04
/Volumes/photo/2021/06/DSC_9012.NEF                   → detected as 2021/06
/Volumes/photo/Vacances/Summer/IMG_3456.JPG            → skipped (no date)
```
