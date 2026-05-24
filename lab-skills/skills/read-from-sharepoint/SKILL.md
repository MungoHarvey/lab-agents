---
name: read-from-sharepoint
description: >
  Read-only access to lab data files from synced OneDrive (SharePoint) folders.
  Use when any skill or task needs to read experiment data files (Metadata.xlsx,
  TapeStation CSVs/PDFs, qPCR files, EVOS images, Experiment Summaries).
  Trigger on: reading SharePoint data, loading experiment files, accessing OneDrive data.
---

# Read from SharePoint (OneDrive) Skill

Provides strictly read-only access to lab data via locally-synced OneDrive folders.

## STRICT READ-ONLY POLICY

**NEVER write, move, rename, copy-into, or delete ANY file under OneDrive paths.**

These folders are shared team resources synced from SharePoint. Any modification
propagates to all team members. Violations risk data loss for the entire lab.

Allowed operations:
- `open()` with mode `"r"` or `"rb"` only
- `pd.read_excel()`, `pd.read_csv()` (read-only by default)
- `Document()` from python-docx (read-only load)
- `ls`, `find`, `stat` via shell (read-only)

Forbidden operations:
- Any `open()` with `"w"`, `"a"`, `"x"` modes
- `shutil.copy/move`, `os.rename`, `os.remove`, `pathlib.Path.unlink/rename/write_*`
- `rsync`, `cp`, `mv`, `rm` targeting OneDrive paths
- Saving/writing any file back to OneDrive paths

## OneDrive base paths

The OneDrive sync location varies by OS and user. Detect it automatically:

```python
import os, platform
from pathlib import Path

def find_onedrive_base() -> Path:
    """Auto-detect the OneDrive shared library root for Imperial College London.
    Works on macOS and Windows."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":  # macOS
        base = home / "Library" / "CloudStorage"
    elif system == "Windows":
        # OneDrive Business typically syncs here
        base = home / "OneDrive - Imperial College London"
        if base.exists():
            return base
        # Fallback: check LOCALAPPDATA or common locations
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "OneDrive"
    else:
        raise OSError(f"Unsupported platform: {system}")

    # Find the Imperial shared library folder
    if base.exists():
        candidates = [p for p in base.iterdir()
                      if p.is_dir() and "ImperialCollegeLondon" in p.name]
        if candidates:
            return candidates[0]
        # Try broader match
        candidates = [p for p in base.iterdir()
                      if p.is_dir() and "Imperial" in p.name]
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        f"OneDrive Imperial folder not found. Searched: {base}\n"
        "Ensure OneDrive is installed and syncing the Skene lab shared libraries."
    )

ONEDRIVE_BASE = find_onedrive_base()

def discover_libraries(base: Path) -> dict[str, Path]:
    """Auto-discover Skene lab shared libraries under OneDrive base.
    Scans for folders prefixed with 'Skene lab -' and generates short aliases."""
    import re
    libs = {}
    if not base.exists():
        return libs
    for p in sorted(base.iterdir()):
        if not p.is_dir() or not p.name.startswith("Skene lab -"):
            continue
        # Extract the descriptive part after the number, e.g. "07 scRNA-seq" → "scrna"
        match = re.search(r"\d+\s+(.+)$", p.name.split(" - ")[-1])
        if match:
            alias = re.sub(r"[^a-z0-9]", "", match.group(1).lower())
        else:
            alias = re.sub(r"[^a-z0-9]", "", p.name.split(" - ")[-1].lower())
        libs[alias] = p
    return libs

LIBRARIES = discover_libraries(ONEDRIVE_BASE)
```

## Retry logic for cloud-synced files

OneDrive files may not be immediately available — they can be cloud-only placeholders
that need time to download. Always wrap file reads with retry logic:

```python
import time

def read_with_retry(read_fn, max_retries=3, delays=(2, 5, 10)):
    """
    Retry a read operation that may fail due to OneDrive sync latency.

    read_fn: callable that performs the read (e.g. lambda: pd.read_excel(path))
    Returns the result of read_fn on success.
    Raises the last exception after all retries are exhausted.
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            result = read_fn()
            if result is None:
                raise ValueError("Read returned None — file may still be syncing")
            return result
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            last_err = e
            if attempt < max_retries - 1:
                wait = delays[attempt] if attempt < len(delays) else delays[-1]
                print(f"  Retry {attempt + 1}/{max_retries} in {wait}s: {e}")
                time.sleep(wait)
    raise last_err
```

### Usage examples

```python
# Reading an Excel file with retry
df = read_with_retry(lambda: pd.read_excel(metadata_path, sheet_name="Sheet1"))

# Reading a CSV with retry
ts_df = read_with_retry(lambda: pd.read_csv(csv_path, encoding="latin-1"))

# Reading a docx with retry
doc = read_with_retry(lambda: Document(str(docx_path)))

# Listing directory contents with retry (folder may not be synced yet)
contents = read_with_retry(lambda: list(folder.iterdir()))
```

## Finding experiment folders

```python
def find_experiment_folder(experiment_id: str, library: str | None = None) -> Path | None:
    """
    Find an experiment folder by ID prefix in OneDrive libraries.
    If library is specified, search only that library.
    Otherwise, search all discovered libraries and return the first match.
    Returns the best match (most data files) or None.
    """
    search_libs = [LIBRARIES[library]] if library and library in LIBRARIES else LIBRARIES.values()

    for root in search_libs:
        if not root.exists():
            continue
        try:
            candidates = read_with_retry(
                lambda r=root: [p for p in r.iterdir() if p.is_dir() and p.name.startswith(experiment_id)]
            )
        except (FileNotFoundError, OSError):
            continue
        if not candidates:
            continue
        if len(candidates) == 1:
            return candidates[0]
        return max(candidates, key=lambda p: len(list(p.rglob("*.xlsx"))))

    return None
```

## Common file patterns in experiment folders

```
<experiment_id>_<description>/
├── *Metadata*.xlsx          — Sample metadata, Qubit, TapeStation values
├── EVOS Images/             — SYBR-stained cell images (.heic/.png/.tif)
├── Tapestation/             — TapeStation PDFs and/or sampleTable CSVs
├── qPCR/                    — qPCR .eds, .xlsx, plots, R scripts
└── <experiment_id> - Experiment Summary.docx  — Completed summary (if exists)
```

## Important notes

- **Always output the full OneDrive path** when reporting which file was read, so the user can verify
- **If a file fails after all retries**, report the error clearly and suggest the user check that OneDrive is synced
  - macOS: System Settings > OneDrive > sync status
  - Windows: OneDrive system tray icon > sync status
- **Never cache or copy** OneDrive files to local directories without explicit user request
- **All output files** (generated summaries, plots, etc.) must be saved to the **working directory**, never to OneDrive paths
