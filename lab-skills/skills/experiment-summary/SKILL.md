---
name: experiment-summary
description: >
  Generate a filled-in Experiment Summary .docx from lab data.
  Invoke with /experiment-summary or when the user asks to
  "write up an experiment", "generate experiment summary", or
  "fill in the summary template".
user_invocable: true
---

# /experiment-summary

Generate a completed Experiment Summary `.docx` by pulling data from Labstep and OneDrive, then filling in the lab template.

## Invocation

```
/experiment-summary <experiment_id_or_name>
```

Examples:
- `/experiment-summary SK550`
- `/experiment-summary "New lysis buffer test"`

If no argument is given, ask the user which experiment to summarise.

---

## Workflow

Follow these steps in order. At each step, tell the user what you found and what's still missing.

### Step 1 — Identify the experiment

Parse the argument as an experiment ID (e.g. `SK550`) or a search term.

### Step 2 — Pull metadata from Labstep

Use the `labstep` skill's API to fetch experiment details:

```python
import os, requests, labstep
from labstep.service.config import configService

def get_labstep_apikey() -> str:
    """Get Labstep API key from .env file or environment variable."""
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("LABSTEP_API_KEY")
    if key:
        return key
    raise RuntimeError("No Labstep API key found. Set LABSTEP_API_KEY in .env")

api_key = get_labstep_apikey()
user = labstep.authenticate(apikey=api_key)
base = configService.getHost()          # https://api.labstep.com
headers = {"apikey": api_key}

# Search by name/ID
experiments = user.getExperiments(search_query="SK550", count=5)
exp = experiments[0]  # or let the user pick if ambiguous

# Extract what we can
name = exp.name
data_fields = exp.getDataFields()
protocols = exp.getProtocols()
comments = exp.getComments()
tables = exp.getTables()
```

From Labstep, attempt to extract:
| Field | Source |
|-------|--------|
| **Model** | Data field named "Model" or "Cell line", or parse from experiment name |
| **Aim** | Data field named "Aim", or the experiment description/entry |
| **Methods** | Linked protocol bodies (see below) |
| **Discussion** | Comments or data field named "Discussion" / "Notes" |

#### Extracting protocol body text

Protocol content in Labstep is stored as ProseMirror JSON in the `state` field. The experiment-linked protocol copies often have **empty steps** — the actual content lives on the **protocol-collection's `last_version`**.

```python
def extract_text(node):
    """Recursively extract plain text from a ProseMirror node."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text = node.get("text", "")
        if text:
            return text
        children = node.get("content", [])
        result = "".join(extract_text(c) for c in children)
        if node.get("type") in ("paragraph", "heading", "blockquote", "list_item", "hard_break"):
            result += "\n"
        return result
    if isinstance(node, list):
        return "".join(extract_text(n) for n in node)
    return ""

def get_protocol_body(protocol, headers, base) -> str:
    """Get the full text body of a protocol.
    Tries the protocol-collection's last_version first (where content
    usually lives), then falls back to the experiment-linked copy."""
    # 1. Try the protocol-collection template (has actual content)
    collection_id = getattr(protocol, "protocol_collection_id", None)
    if collection_id:
        try:
            coll = requests.get(
                f"{base}/api/generic/protocol-collection/{collection_id}",
                headers=headers,
            ).json()
            version = coll.get("last_version") or coll.get("draft_version")
            if version and version.get("id"):
                vresp = requests.get(
                    f"{base}/api/generic/protocol/{version['id']}",
                    headers=headers,
                ).json()
                state = vresp.get("state")
                if state:
                    return extract_text(state).strip()
        except Exception:
            pass

    # 2. Fallback: experiment-linked protocol body
    try:
        resp = requests.get(
            f"{base}/api/generic/experiment/{protocol.id}",
            headers=headers,
        ).json()
        state = resp.get("state")
        if state:
            return extract_text(state).strip()
    except Exception:
        pass

    return ""

# Collect all protocol texts for the Methods section
methods_parts = []
for p in protocols:
    body = get_protocol_body(p, headers, base)
    if body:
        methods_parts.append(f"### {p.name}\n\n{body}")
    else:
        methods_parts.append(f"### {p.name}\n\n*(No body text found — protocol may be a draft)*")
methods_text = "\n\n".join(methods_parts)
```

**Always attempt Labstep lookup** — even if the experiment name doesn't match exactly, try partial matches (e.g. search for date, keywords from the folder name). Record which Labstep experiment was matched (if any) for the Sources section.

If a field can't be found in Labstep, note it as missing — you'll ask the user in Step 4.

### Step 3 — Pull QC data from OneDrive (read-only)

Read experiment files directly from the synced OneDrive folder. **All reads are strictly read-only.** Use retry logic since files may need time to sync from the cloud.

Use the following utilities from other skills (do not redefine them):
- **`find_onedrive_base()`**, **`read_with_retry()`**, **`LIBRARIES`**, **`find_experiment_folder()`** — see **`read-from-sharepoint`** skill
- **`qubit_to_float()`**, **`find_column()`** — see **`nucleic-acid-analysis`** skill

```python
import pandas as pd
from pathlib import Path

# These are provided by read-from-sharepoint and nucleic-acid-analysis skills:
# find_onedrive_base(), read_with_retry(), LIBRARIES, find_experiment_folder()
# qubit_to_float(), find_column()
```

**Search order**: `find_experiment_folder(exp_id)` searches all discovered OneDrive libraries automatically.

**From the experiment folder, extract:**

#### Qubit concentrations
```python
meta_files = read_with_retry(lambda: list(folder.glob("*Metadata*.xlsx")))
if meta_files:
    df = read_with_retry(lambda: pd.read_excel(meta_files[0], sheet_name="Sheet1"))
    qubit_col = find_column(df, [
        "RNA Qubit Conc (ng/ul)", "Final Lib Qubit Conc (ng/ul)",
        "Qubit Conc (ng/ul)", "Qubit (ng/ul)", "Qubit",
    ])
    samples = []
    for _, row in df.iterrows():
        name = str(row.get("Aim", row.get("Sample", f"Sample {_ + 1}")))
        conc = qubit_to_float(row.get(qubit_col))
        samples.append({"name": name, "conc": conc if conc is not None else ""})
```

#### TapeStation data

Format TapeStation as a **per-sample table** (list of dicts), not a single summary value:

```python
# From Metadata.xlsx — per-sample TapeStation values (fuzzy match)
ts_conc_col = find_column(df, [
    "TapeStation HS D5000 100-1000 bp Conc (ng/ul)",
    "TapeStation Conc (ng/ul)", "TS Conc (ng/ul)",
])
ts_peak_col = find_column(df, [
    "TapeStation HS D5000 peak (bp)", "TapeStation peak (bp)", "TS peak (bp)",
])
tapestation_samples = []
if ts_conc_col and df[ts_conc_col].notna().any():
    for _, row in df.iterrows():
        name = str(row.get("Aim", row.get("Sample", f"Sample {_ + 1}")))
        conc = row.get(ts_conc_col)
        peak = row.get(ts_peak_col) if ts_peak_col in df.columns else None
        if pd.notna(conc):
            tapestation_samples.append({
                "name": name,
                "conc": str(conc),
                "peak": str(peak) if pd.notna(peak) else "",
            })
else:
    # Fall back to TapeStation sampleTable CSV
    csvs = read_with_retry(lambda: list(folder.rglob("*sampleTable.csv")))
    if csvs:
        ts_df = read_with_retry(lambda: pd.read_csv(csvs[0], encoding="latin-1"))
        ts_df = ts_df[~ts_df["Sample Description"].str.lower().str.contains("ladder", na=False)]
        for _, row in ts_df.iterrows():
            name = str(row.get("Sample Description", f"Sample {_ + 1}"))
            conc_pg = row.get("Conc. [pg/µl]", None)
            conc_ng = f"{float(conc_pg) / 1000:.2f}" if pd.notna(conc_pg) else ""
            tapestation_samples.append({"name": name, "conc": conc_ng, "peak": ""})
```

#### EVOS Images
```python
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

def make_thumbnails(folder: Path, output_dir: Path, max_size: int = 800) -> list[dict]:
    """Convert EVOS images (.heic/.png/.tif) to PNG thumbnails for embedding.
    Reads from OneDrive (read-only), writes thumbnails to output_dir (local).
    Returns list of {"name": str, "path": Path} for each thumbnail."""
    evos_dir = folder / "EVOS Images"
    if not evos_dir.exists():
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    thumbnails = []
    for img_path in sorted(evos_dir.iterdir()):
        if img_path.suffix.lower() not in (".heic", ".png", ".tif", ".tiff", ".jpg", ".jpeg"):
            continue
        try:
            if img_path.stat().st_size == 0:
                print(f"  Warning: skipping empty file {img_path.name}")
                continue
            img = read_with_retry(lambda p=img_path: Image.open(p))
            img.thumbnail((max_size, max_size))
            out = output_dir / f"{img_path.stem}.png"
            img.save(out, "PNG")
            thumbnails.append({"name": img_path.stem, "path": out})
        except Exception as e:
            print(f"  Warning: could not convert {img_path.name}: {e}")
    return thumbnails
```

**Thumbnail output** is saved to `<experiment_id>_thumbnails/` in the working directory (never to OneDrive).

#### If files fail after all retries
Report the error and suggest the user check OneDrive sync status (System Settings > OneDrive).

### Step 4 — Confirm with user

Present a summary of what was found and what's missing:

```
## Experiment Summary for SK550

**Found:**
- Model: HEK293T (from Labstep)
- Aim: Testing new lysis buffer (from Labstep)
- Qubit: 5 samples loaded from Metadata.xlsx
- TapeStation: Conc 2.45 ng/µl, peak 350 bp

**Still needed:**
- Summary of methods (not found in Labstep)
- Discussion

Please provide the missing fields, or type "skip" to leave them blank.
```

Wait for the user to fill in missing fields or confirm.

### Step 5 — Generate the document

```python
from docx import Document
from pathlib import Path

TEMPLATE = Path("support/Experiment Summary Template.docx")

def fill_experiment_summary(
    output_path: str,
    model: str,
    aim: str,
    methods: str,
    qubit_samples: list[dict],
    tapestation_samples: list[dict] | None = None,
    qpcr: str | None = None,
    discussion: str = "",
    thumbnails: list[dict] | None = None,
    sources: list[dict] | None = None,
):
    from docx.shared import Inches, Pt

    doc = Document(str(TEMPLATE))

    # Validate template structure
    if len(doc.tables) < 4:
        raise ValueError(
            f"Template has {len(doc.tables)} tables but 4 are expected "
            "(Qubit, EVOS, TapeStation, qPCR). Check the template file."
        )

    # Fill header paragraphs
    for p in doc.paragraphs:
        if p.text.startswith("Model:"):
            p.clear()
            p.add_run(f"Model: {model}")
        elif p.text.startswith("Aim:"):
            p.clear()
            p.add_run(f"Aim: {aim}")
        elif p.text.startswith("Summary of methods:"):
            p.clear()
            p.add_run(f"Summary of methods: {methods}")
        elif p.text.startswith("Discussion"):
            p.clear()
            p.add_run(f"Discussion and comparison to past experiments\n{discussion}")

    # Fill Qubit table (Table 0)
    qubit_table = doc.tables[0]
    while len(qubit_table.rows) > 2:
        qubit_table._tbl.remove(qubit_table.rows[2]._tr)
    for sample in qubit_samples:
        row = qubit_table.add_row()
        row.cells[0].text = str(sample["name"])
        row.cells[1].text = str(sample.get("conc", ""))

    # Fill EVOS Imaging table (Table 1) with thumbnails
    if thumbnails:
        img_table = doc.tables[1]
        # Clear existing placeholder content
        for row in img_table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.clear()
        # Place thumbnails into cells: 2 per row, starting at row 0
        # Row 0 is the header row — keep it, start images from row 1
        cell_idx = 0
        for thumb in thumbnails:
            row_i = 1 + cell_idx // 2
            col_i = cell_idx % 2
            # Add rows if needed
            while row_i >= len(img_table.rows):
                img_table.add_row()
            cell = img_table.rows[row_i].cells[col_i]
            cell.paragraphs[0].clear()
            cell.paragraphs[0].add_run(f"{thumb['name']}\n")
            cell.paragraphs[0].add_run().add_picture(str(thumb["path"]), width=Inches(2.8))
            cell_idx += 1

    # Fill TapeStation (Table 2) — per-sample rows: Sample | Conc (ng/µl) | Peak (bp)
    if tapestation_samples:
        ts_table = doc.tables[2]
        # Clear existing rows (keep header row 0)
        while len(ts_table.rows) > 1:
            ts_table._tbl.remove(ts_table.rows[1]._tr)
        # Add header if table was a single-cell layout — rebuild as 3-column
        # If template already has columns, just add data rows
        for sample in tapestation_samples:
            row = ts_table.add_row()
            row.cells[0].text = str(sample["name"])
            if len(row.cells) > 1:
                row.cells[1].text = str(sample.get("conc", ""))
            if len(row.cells) > 2:
                row.cells[2].text = str(sample.get("peak", ""))

    # Fill qPCR (Table 3)
    if qpcr:
        doc.tables[3].rows[1].cells[0].text = qpcr

    # Append Sources & Provenance section at the end of the document
    if sources:
        doc.add_paragraph()  # spacer
        p = doc.add_paragraph()
        run = p.add_run("Data Sources & File Paths")
        run.bold = True
        run.font.size = Pt(11)
        for src in sources:
            field = src.get("field", "")
            origin = src.get("source", "")
            path = src.get("path", "")
            line = f"{field}: {origin}"
            if path:
                line += f"\n    {path}"
            doc.add_paragraph(f"  - {line}")

    doc.save(output_path)
    return output_path
```

### Step 6 — Save and report

- Save as `<experiment_id>_Experiment_Summary.docx` in the current working directory
- Tell the user the output path
- **Never overwrite the template**
- **Never write any file to OneDrive paths**

### Sources section

Every generated summary **must** include a "Data Sources & File Paths" section at the bottom of the document. Track provenance for every field by building a `sources` list during Steps 2–3:

```python
sources = []
# Example entries:
sources.append({"field": "Model", "source": "Labstep experiment 350101", "path": ""})
sources.append({"field": "Qubit", "source": "OneDrive Metadata.xlsx", "path": "<OneDrive>/SK550_.../Metadata.xlsx"})
sources.append({"field": "TapeStation", "source": "OneDrive sampleTable CSV", "path": "<OneDrive>/Tapestation/sampleTable.csv"})
sources.append({"field": "EVOS Images", "source": "OneDrive EVOS Images/ (6 files)", "path": "<OneDrive>/EVOS Images/"})
sources.append({"field": "Discussion", "source": "User input", "path": ""})
```

This allows anyone reading the summary to trace every data point back to its origin file or API call. Always use **full file paths** for OneDrive sources. For Labstep, include the experiment ID and name.

---

## Data source priority

| Field | 1st choice | 2nd choice | 3rd choice |
|-------|-----------|-----------|-----------|
| Model | Labstep data field | User input | — |
| Aim | Labstep data field / entry | User input | — |
| Methods | Labstep linked protocol | User input | — |
| Qubit | OneDrive Metadata.xlsx | User input | — |
| TapeStation | OneDrive Metadata.xlsx or CSV | User input | — |
| qPCR | OneDrive files | Labstep tables | User input |
| Imaging | OneDrive image files | User input | — |
| Discussion | Labstep comments | User input | — |

---

## Template location

```
support/Experiment Summary Template.docx
```

The template has 4 tables:
- **Table 0**: Qubit concentrations (sample name + ng/µl)
- **Table 1**: EVOS Imaging (image placeholders)
- **Table 2**: TapeStation HS D5000 (dilution, spectrum, size, conc, molarity)
- **Table 3**: qPCR side reaction

---

## Dependencies

```
pip install python-docx labstep pandas openpyxl Pillow pillow-heif
```

---

## Important notes

- **Never overwrite the template** — always save as a new file
- **OneDrive is strictly read-only** — never write, move, rename, or delete files in OneDrive paths
- **Labstep is read-only** — do not create or modify Labstep entries (see CLAUDE.md)
- **Retry on failure** — OneDrive files may need time to sync; retry up to 3 times with delays (2s, 5s, 10s)
- Qubit "TL" / "Too low" values → treat as 0.0
- TapeStation CSV concentrations are in pg/µl — divide by 1000 for ng/µl
- If multiple data sources disagree, prefer the OneDrive file data and flag the discrepancy to the user
