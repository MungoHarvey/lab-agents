---
name: nucleic-acid-analysis
description: >
  Read and extract RNA quantification data (Qubit, TapeStation, qPCR) from
  experiment folders on OneDrive. Use when the user wants to read Metadata.xlsx,
  TapeStation CSVs, or Qubit values from experiment folders.
---

# RNA Quantification Data Reading Skill

Utilities for reading and extracting RNA quantification metrics (Qubit, TapeStation, etc.) from experiment data files on OneDrive.

**Data source**: OneDrive synced SharePoint folders. Use `find_onedrive_base()`, `read_with_retry()`, `LIBRARIES`, and `find_experiment_folder()` from the **`read-from-sharepoint`** skill for OneDrive paths, retry logic, library discovery, and read-only policy.

---

## Fuzzy column matching

Column names vary across experiments — different assays, Unicode vs ASCII, abbreviated vs full names. Always use this helper:

```python
def find_column(df, candidates: list[str]) -> str | None:
    """Find the first matching column from a list of candidate names (case-insensitive).
    Normalises Unicode micro sign (µ, U+00B5) to ASCII 'u' for matching.
    Returns the actual column name from the DataFrame, or None."""
    def norm(s: str) -> str:
        return s.lower().strip().replace("\u00b5", "u")
    col_map = {norm(c): c for c in df.columns}
    for name in candidates:
        actual = col_map.get(norm(name))
        if actual is not None:
            return actual
    return None
```

---

## Metadata.xlsx

Always read `Sheet1` (the primary data sheet). Some files (SK443, SK444, SK447, SK449) have a second sheet `'data to plot'` — this is a derived summary for plotting and can be ignored.

```python
folder = find_experiment_folder("SK550")
meta_files = read_with_retry(lambda: list(folder.glob("*Metadata*.xlsx")))
df = read_with_retry(lambda: pd.read_excel(meta_files[0], sheet_name="Sheet1"))
```

### Qubit column candidates

Two distinct Qubit measurements exist — **RNA Qubit** (intermediate QC) and **Final Library Qubit** (post-library-prep). The scRNA-seq library (07) files typically lack RNA Qubit columns and only have Final Lib Qubit.

```python
# RNA Qubit (intermediate QC, scTIP-seq library)
rna_qubit_col = find_column(df, [
    "RNA Qubit Conc (ng/ul)",
    "Qubit RNA conc. (ng/µL)",   # 'data to plot' sheet variant (Unicode µ)
    "Qubit Conc (ng/ul)",
    "Qubit (ng/ul)",
])

# Final library Qubit (present in all files)
lib_qubit_col = find_column(df, [
    "Final Lib Qubit Conc (ng/ul)",
])
```

### TapeStation column candidates

Three assay types exist with different column names:

```python
# HSD5000 assay (library QC — scRNA-seq and late scTIP-seq)
ts_d5000_conc = find_column(df, [
    "TapeStation HS D5000 100-1000 bp Conc (ng/ul)",
])
ts_d5000_peak = find_column(df, [
    "TapeStation HS D5000 peak (bp)",
])
ts_d5000_molarity = find_column(df, [
    "TapeStation HS D5000 100-1000 bp Molarity (pM)",
])

# HSRNA assay (RNA QC — scTIP-seq library)
ts_rna_conc = find_column(df, [
    "TapeStation HS RNA Conc (ng/ul)",
    "TapeStation HS RNA conc. (ng/µL)",  # 'data to plot' variant
])
ts_rna_peak = find_column(df, [
    "TapeStation HS RNA peak (bp)",
])
ts_rna_molarity = find_column(df, [
    "TapeStation HS RNA Molarity (pM)",
])

# gDNA assay (early experiments SK272, SK277 only)
ts_gdna_conc = find_column(df, [
    "TapeStation gDNA Conc (ng/ul)",
])
ts_gdna_peak = find_column(df, [
    "TapeStation gDNA peak (bp)",
])
```

### All known Metadata columns

| Column | Assay | Present in |
|--------|-------|-----------|
| `RNA Qubit Conc (ng/ul)` | RNA Qubit | scTIP-seq (03) library, SK297+ |
| `Final Lib Qubit Conc (ng/ul)` | Library Qubit | All files |
| `TapeStation HS D5000 100-1000 bp Conc (ng/ul)` | HSD5000 | scRNA-seq (07) + late scTIP-seq |
| `TapeStation HS D5000 peak (bp)` | HSD5000 | Same |
| `TapeStation HS D5000 100-1000 bp Molarity (pM)` | HSD5000 | Same |
| `TapeStation HS RNA Conc (ng/ul)` | HSRNA | scTIP-seq (03) library |
| `TapeStation HS RNA peak (bp)` | HSRNA | Same |
| `TapeStation HS RNA Molarity (pM)` | HSRNA | Same |
| `TapeStation gDNA Conc (ng/ul)` | gDNA | SK272, SK277 only |
| `TapeStation gDNA peak (bp)` | gDNA | SK272, SK277 only |
| `Aim` | — | Most files (enzyme/condition name) |
| `Sample` | — | Sample identifier |
| `PCR.cycles` | — | PCR cycling protocol |

---

## Sentinel values (non-numeric cells)

Qubit and TapeStation columns contain these non-numeric values:

| Value | Meaning | Treatment |
|-------|---------|-----------|
| `'TL'`, `'Too low'` | Below Qubit detection limit | → `0.0` |
| `'/'` | Not measured / not applicable | → `None` (skip) |
| `'-'` | Not run / not applicable | → `None` (skip) |
| `'SK275'` (or other `SK___`) | Cross-reference to another experiment | → `None` (skip, log warning) |
| `'358 & 21458'` | Two peaks in one cell (HSRNA) | → parse first value, or flag |
| `''`, `'nan'`, `NaN` | Empty | → `None` (skip) |

```python
import re

def qubit_to_float(val) -> float | None:
    """Convert a Qubit/TapeStation cell value to float.
    Returns 0.0 for 'TL'/'Too low', None for missing/not-measured."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    sl = s.lower()
    if sl in ("tl", "too low"):
        return 0.0
    if sl in ("/", "-", "", "nan") or sl.startswith("sk"):
        return None
    # Handle dual-peak values like "358 & 21458" — take the first
    if " & " in s:
        s = s.split(" & ")[0].strip()
    try:
        return float(s)
    except ValueError:
        return None
```

---

## TapeStation sampleTable CSV

When Metadata.xlsx is missing or you need per-peak detail, read the sampleTable CSVs.

### Three assay schemas

| Assay | Conc column | Unit | Extra columns |
|-------|------------|------|---------------|
| **HSRNA** | `Conc. [pg/µl]` | pg/µl | `RINe`, `28S/18S (Area)` |
| **HSD5000** | `Conc. [pg/µl]` | pg/µl | — |
| **gDNA** | `Conc. [ng/µl]` | ng/µl | `DIN` |

**Unit conversion**: HSRNA and HSD5000 concentrations are in **pg/µl** — divide by 1000 for ng/µl. gDNA is already in ng/µl.

### Reading sampleTable CSVs

```python
def read_sample_tables(folder: Path, assay: str = "all") -> pd.DataFrame:
    """Read and concatenate sampleTable CSVs from a folder.
    assay: 'hsrna', 'hsd5000', 'gdna', or 'all'.
    Filters out ladder wells. Returns combined DataFrame."""
    # Also check for .xlsx sampleTable (one known case: SK094-97 gDNA)
    csvs = list(folder.rglob("*sampleTable.csv"))
    xlsxs = [f for f in folder.rglob("*sampleTable.xlsx")]

    frames = []
    for f in csvs:
        try:
            df = read_with_retry(lambda p=f: pd.read_csv(p, encoding="latin-1"))
            # Filter by assay type
            if assay == "hsrna" and "RINe" not in df.columns:
                continue
            if assay == "hsd5000" and ("RINe" in df.columns or "DIN" in df.columns):
                continue
            if assay == "gdna" and "DIN" not in df.columns:
                continue
            frames.append(df)
        except Exception as e:
            print(f"  Warning: could not read {f.name}: {e}")

    for f in xlsxs:
        try:
            df = read_with_retry(lambda p=f: pd.read_excel(p, sheet_name="in"))
            frames.append(df)
        except Exception as e:
            print(f"  Warning: could not read {f.name}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # Remove ladder wells
    if "Sample Description" in combined.columns:
        combined = combined[~combined["Sample Description"].str.lower().str.contains("ladder", na=False)]
    return combined
```

### Concentration extraction from CSVs

```python
def get_csv_concentration(df: pd.DataFrame) -> tuple[str, float]:
    """Get concentration column and unit multiplier from a sampleTable DataFrame.
    Returns (column_name, multiplier_to_ng_ul)."""
    if "Conc. [ng/µl]" in df.columns:
        return "Conc. [ng/µl]", 1.0       # gDNA — already ng/µl
    if "Conc. [pg/µl]" in df.columns:
        return "Conc. [pg/µl]", 0.001      # HSRNA/HSD5000 — pg to ng
    # Fallback: try find_column
    col = find_column(df, ["Conc. [pg/µl]", "Conc. [ng/µl]"])
    if col and "ng" in col.lower():
        return col, 1.0
    if col:
        return col, 0.001
    return None, 1.0
```

### Alert flags

TapeStation CSVs have an `Alert` column with string flags:
- `'!'` — warning (e.g. low signal)
- `'!!'` — error/out-of-range (sample may be unreliable)

Always check and report alert flags when presenting results.

---

## compactPeakTable CSVs (per-peak detail)

For per-peak analysis (e.g. fragment size distributions), use compactPeakTable CSVs:

```python
peak_csvs = list(folder.rglob("*compactPeakTable.csv"))
```

Key columns: `Well`, `Sample Description`, `Peak`, `Size [bp]`, `Calibrated Conc. [pg/µl]`, `Peak Molarity [pmol/l]`, `From [bp]`, `To [bp]`, `% Integrated Area`.

Multiple rows per sample (one per detected peak). Useful when sampleTable gives a single summary concentration but the user wants peak-level detail.

---

## Standalone Qubit .xlsx files

A few early experiments (SK083, SK085, SK157, SK175, SK177, SK533) have standalone Qubit export files (e.g. `SK533 Qubit.xlsx`) instead of or alongside Metadata.xlsx. These are raw instrument exports with non-standard headers (`Unnamed: 0`, `Unnamed: 1`, ...) and cannot be reliably parsed without visual inspection. When encountered, warn the user and fall back to manual entry.

---

## Enzyme name normalisation

```python
IVT_NORM = {
    "hiscribet7 ivt kit (neb)": "HiScribe",
    "hiscribet7 1h": "HiScribe", "hiscribet7 2h": "HiScribe",
    "megascript t7 ivt kit (thermofisher)": "Mega",
    "t7 ribomax ivt kit (promega)": "RiboMax",
    "t7 ribomax 1h": "RiboMax", "t7 ribomax 2h": "RiboMax",
    "hi-t7 ivt kit (neb)": "Hi-T7", "hi-t7 kit": "Hi-T7",
    "standard kit": "Standard",
    "negative control": "Neg ctl",
}

RT_NORM = {
    "smart mmlv rtase kit": "SMART",
    "maxima h minus": "Maxima",
    "sigma-aldrich m-mlv reverse transcriptase": "Sigma",
    "sigma-aldrich m-mlv rt": "Sigma",
    "superscript iv": "SuperScript",
    "superscrip iv": "SuperScript",
    "negative control": "Neg ctl",
}

PCR_NORM = {
    "superfi ii": "SuperFi",
    "phusion high-fidelity": "Phusion",
    "primestar max": "PrimeStar",
    "nebNext ultra ii q5": "NEBNext",
    "negative control": "Neg ctl",
}
```

When an enzyme name is not found in the normalisation dict, use the raw name as the label and print a warning.

---

## Reusable helper: build_panel_data

```python
def build_panel_data(experiments, aim_norm, qubit_col_candidates, order):
    """Read Metadata.xlsx for a list of (exp_id, root) pairs.
    Returns (data_dict, exp_ids_dict) keyed by normalised enzyme label.
    qubit_col_candidates: list of candidate column names (passed to find_column)."""
    data    = {e: [] for e in order}
    exp_ids = {e: [] for e in order}
    for exp_id, root in experiments:
        folder = find_experiment_folder(exp_id)
        if not folder:
            continue
        meta_files = read_with_retry(lambda: list(folder.glob("*Metadata*.xlsx")))
        if not meta_files:
            continue
        df = read_with_retry(lambda: pd.read_excel(meta_files[0], sheet_name="Sheet1"))
        qubit_col = find_column(df, qubit_col_candidates if isinstance(qubit_col_candidates, list) else [qubit_col_candidates])
        if qubit_col is None:
            print(f"  Warning: no Qubit column found in {meta_files[0].name}")
            continue
        for _, row in df.iterrows():
            aim   = str(row.get("Aim", "")).strip()
            label = aim_norm.get(aim.lower())
            if label is None:
                label = aim
                if aim and label not in order:
                    print(f"  Warning: unknown enzyme '{aim}' in {exp_id}, using raw name")
            if label not in order:
                continue
            val = qubit_to_float(row.get(qubit_col))
            if val is None:
                continue
            data[label].append(val)
            exp_ids[label].append(exp_id)
    for e in order:
        if not data[e]:
            data[e] = None
    return data, exp_ids
```

---

## Typical concentration ranges

From scanning all 49 Metadata files and 150 sampleTable CSVs:

| Measurement | Unit | Typical range | Outlier notes |
|-------------|------|---------------|---------------|
| RNA Qubit | ng/µl | 0–500 | IVT RNA can exceed 1000 ng/µl |
| Final Lib Qubit | ng/µl | 0–50 | Most are 1–20 ng/µl |
| TS HSD5000 conc (CSV) | pg/µl | 1.6–95,000 | >50,000 = high-yield IVT (SK109, SK134, SK172) |
| TS HSRNA conc (CSV) | pg/µl | 1.6–95,000 | Same scale |
| TS gDNA conc (CSV) | ng/µl | 1–95 | Already in ng/µl |
| RINe | — | 1.0–9.1 | IVT RNA is intentionally fragmented; low RINe is expected |
| DIN | — | 1.0–9.9 | gDNA integrity |

---

## Tips

1. **All reads use retry logic** — OneDrive files may need time to sync from cloud
2. **Check units** — Qubit is ng/µl; TapeStation HSRNA/HSD5000 conc is pg/µl (÷1000); gDNA is ng/µl
3. **Note dilutions** — Document any sample dilutions before measurement
4. **Never write to OneDrive** — all output goes to the working directory
5. **Unicode µ vs ASCII u** — `find_column()` normalises this automatically
6. **Dual-peak cells** — HSRNA columns may contain `'358 & 21458'` — `qubit_to_float()` takes the first value
7. **Cross-references** — Values like `'SK275'` mean data is in another experiment's file
8. **scRNA-seq (07) vs scTIP-seq (03)** — scRNA-seq Metadata files lack RNA Qubit columns; only have Final Lib Qubit and D5000 TapeStation
