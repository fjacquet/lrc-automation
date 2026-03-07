# Usage Guide

## Quick Start

Close Lightroom Classic, then run:

```bash
# macOS — auto-discovers catalog at ~/Pictures/Lightroom/
lrc-auto scan

# Windows — auto-discovers catalog at %USERPROFILE%\Pictures\Lightroom\
lrc-auto scan

# Or point at a specific catalog
lrc-auto -c "/path/to/Lightroom Catalog.lrcat" scan
```

The recommended workflow is always **scan → plan → apply → validate**.

---

## Installation

### Option 1 — Python (recommended for full feature set)

```bash
# macOS / Linux / Windows
pip install uv
uv tool install lrc-automation
```

Or with `pipx`:

```bash
pipx install lrc-automation
```

To include GPS-based location folders (macOS / Linux only):

```bash
uv tool install "lrc-automation[geo]"
```

### Option 2 — Standalone binary (no Python required)

Download the pre-built binary from the [GitHub Releases](https://github.com/fjacquet/lrc-automation/releases/latest) page:

| Platform | File |
|----------|------|
| macOS (Apple Silicon + Intel) | `lrc-auto-macos-universal2` |
| Windows x86-64 | `lrc-auto-windows-x86_64.exe` |

**macOS:**

```bash
chmod +x lrc-auto-macos-universal2
sudo mv lrc-auto-macos-universal2 /usr/local/bin/lrc-auto
lrc-auto --help
```

!!! note "macOS Gatekeeper"
    On first run macOS may block the binary. Open **System Settings → Privacy & Security** and click **Allow Anyway**, or run:
    ```bash
    xattr -d com.apple.quarantine /usr/local/bin/lrc-auto
    ```

**Windows:**

```powershell
# Rename and place somewhere on your PATH (e.g. C:\Tools\)
Rename-Item lrc-auto-windows-x86_64.exe lrc-auto.exe
lrc-auto --help
```

### Option 3 — Docker

```bash
# Scan a catalog mounted from the host
docker run --rm \
  -v "/path/to/Lightroom:/catalog" \
  ghcr.io/fjacquet/lrc-automation:latest \
  scan -c /catalog/Catalog.lrcat

# Apply fixes (mount every volume root the catalog references)
docker run --rm \
  -v "/Volumes/photo:/photo" \
  -v "/path/to/Lightroom:/catalog" \
  ghcr.io/fjacquet/lrc-automation:latest \
  apply -c /catalog/Catalog.lrcat -y
```

!!! warning "Docker and disk moves"
    For `apply` to move files, the container needs read-write access to **every volume root** referenced in the catalog, not just the catalog directory.

---

## Windows Notes

### MAX_PATH advisory

Windows limits paths to 260 characters by default. If your catalog roots are deeply nested (NAS, external drive), enable long paths first:

**Group Policy Editor:**

1. Open `gpedit.msc`
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

**PowerShell (run as Administrator):**

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

### .env file on Windows

Both forward slashes and escaped backslashes work:

```env
# Forward slashes (recommended — works on all platforms)
LRC_CATALOG_PATH=C:/Users/YourName/Pictures/Lightroom/Catalog.lrcat
LRC_BACKUP_DIR=C:/Users/YourName/Documents/LightroomBackups

# Backslashes also work
LRC_CATALOG_PATH=C:\\Users\\YourName\\Pictures\\Lightroom\\Catalog.lrcat
```

### Known limitations on Windows

- **Location folders (`--location-folders`):** The `[geo]` extra has no Windows wheel. GPS-based `Country/City/` subfolders are macOS / Linux only.
- **AppleDouble (`._*`) cleanup:** Silently skipped on Windows — those files only appear on macOS-formatted volumes.

---

## Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

```env
LRC_CATALOG_PATH=/path/to/Lightroom Catalog.lrcat
LRC_BACKUP_DIR=                  # optional — defaults to catalog directory
LRC_TARGET_LAYOUT=%Y/%m/         # optional — strftime format for target folders
LRC_LOCATION_FOLDERS=false       # optional — enable GPS-based Country/City subfolders
LRC_LOG_FILE=                    # optional — defaults to <catalog>.log alongside catalog
```

All variables can also be passed as CLI flags; flags take precedence over env vars.

### Target folder layout

Controls the target folder structure using Python `strftime` codes. Defaults to `%Y/%m/`.

| Layout | Example | Description |
|--------|---------|-------------|
| `%Y/%m/` | `2023/06/` | Year/Month (default) |
| `%Y/%m/%d/` | `2023/06/15/` | Year/Month/Day |
| `%Y-%m/` | `2023-06/` | Year-Month with dash |
| `%Y/` | `2023/` | Flat yearly |

```bash
lrc-auto --target-layout "%Y/%m/%d/" -c catalog.lrcat scan
```

### Log file

A debug-level log is written alongside the catalog as `<catalog>.log` by default. The console shows only warnings unless `-v` is set.

```bash
# Override the log path
lrc-auto --log-file /tmp/lrc-debug.log -c catalog.lrcat apply

# Also print debug to the terminal
lrc-auto -v --log-file /tmp/lrc-debug.log apply
```

---

## Commands

### scan (read-only)

Detects misplaced photos (EXIF date does not match folder date) and duplicate / malformed filename prefixes.

```bash
lrc-auto scan
lrc-auto -c "/path/to/catalog.lrcat" scan
lrc-auto --location-folders scan        # show GPS-aware target paths

# Export results
lrc-auto scan -o results.json
lrc-auto scan -o results.csv
```

### plan (read-only)

Generates a move plan from scan results. Prints a table of all proposed changes and optionally exports it for review before touching anything.

```bash
lrc-auto plan
lrc-auto plan --fix moves               # moves only
lrc-auto plan --fix renames             # prefix renames only
lrc-auto plan -o plan.json              # export as JSON
```

### apply (modifies catalog + disk)

Executes the plan: moves files on disk and updates the catalog in a single atomic transaction. Always creates a timestamped backup first.

```bash
lrc-auto apply                          # prompts for confirmation
lrc-auto apply -y                       # skip confirmation prompt
lrc-auto apply --fix moves
lrc-auto apply --fix renames
```

On any error all disk moves are reversed automatically (rollback stack).

### validate

Runs `PRAGMA integrity_check`, checks every catalog record against disk, and reports missing / misplaced files.

```bash
lrc-auto validate

# Export audit results
lrc-auto validate -o audit.json
lrc-auto validate -o audit.csv
```

### cleanup

Removes empty directories left behind by `apply` runs and deletes macOS AppleDouble (`._*`) metadata files. Safe to run at any time — never touches photo files.

```bash
lrc-auto cleanup
```

What it does, in order:

1. Walks every catalog root bottom-up
2. On macOS: deletes `._*` files before attempting `rmdir`
3. Removes now-empty directories from disk
4. Removes orphaned `AgLibraryFolder` rows from the catalog

### reconcile

Runs a full disk audit, then fixes catalog pointers for files that exist on disk but are registered at the wrong path. **No files are moved** — only catalog metadata is updated.

```bash
lrc-auto reconcile
```

Useful after a partial `apply` run or an out-of-band file move left catalog pointers stale. Ambiguous matches (same filename found in multiple locations) are skipped and printed for manual resolution.

Output reports: reconciled count, skipped-ambiguous count, truly-missing count.

### restore

Rolls back the catalog from a timestamped backup created by `apply` or `reconcile`.

```bash
lrc-auto restore --backup-path /path/to/Catalog.lrcat.bak-20260306-120000
```

---

## Advanced: location-based subfolders

Requires the `[geo]` extra (macOS / Linux only):

```bash
uv tool install "lrc-automation[geo]"
# or
pip install "lrc-automation[geo]"
```

When enabled, photos with GPS data land in subfolders like `2023/06/CH/Zurich/` instead of `2023/06/`. Photos without GPS fall back to the date-only path.

```bash
lrc-auto --location-folders scan
lrc-auto --location-folders plan
lrc-auto --location-folders apply
```

Control the ordering of month and location within the path:

| `--location-order` | Example path |
|--------------------|-------------|
| `month_cc_city` (default) | `2023/06/CH/Zurich/` |
| `cc_city_month` | `CH/Zurich/2023/06/` |
| `cc_month_city` | `CH/2023/06/Zurich/` |

Lookups are performed offline using the `reverse_geocoder` K-D tree — no network calls. Country codes follow ISO 3166-1 alpha-2 (`CH`, `FR`, `NZ`, …).

---

## Supported folder structures

The scanner reads dates from the **full path** (root + pathFromRoot) right-to-left, so the deepest recognisable date segment wins.

| Pattern | Example | Notes |
|---------|---------|-------|
| `YYYY/MM/` | `2023/06/` | Classic Lightroom hierarchy |
| `YYYY-MM-DD` | `2023-12-24/` | ISO date folders — day ignored, year+month extracted |
| French dates | `1 avril 2016/` | Apple Photos / iPhoto exports; accented forms (`février`, `août`, `décembre`) and case-insensitive |
| Year in root + month | Root `/photos/2021/`, path `06/` | Year from root, month from immediate subfolder |

Filtered out automatically:

- **1904** — Lightroom's "no date" epoch value
- **Topical folders** — no recognisable date pattern (e.g. `Vacances/`, `Family/`) — silently skipped
- Years outside 1900–2100

### Path examples

```
/Volumes/photo/Weekends/2023/2023-12-24/IMG_1234.CR2  → 2023/12
/Volumes/photo/iphone/1 avril 2016/IMG_5678.JPG       → 2016/04
/Volumes/photo/2021/06/DSC_9012.NEF                   → 2021/06
/Volumes/photo/Vacances/Summer/IMG_3456.JPG            → skipped (no date)
```
