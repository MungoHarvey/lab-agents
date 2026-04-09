#!/usr/bin/env python3
"""
Mirror all Labstep data to a local directory.

Exports experiments, protocols, and resources (with inventory items)
to a structured folder hierarchy.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

import labstep
from dotenv import load_dotenv

# ── Configuration ──────────────────────────────────────────────────
MIRROR_ROOT = Path(
    os.environ.get(
        "MIRROR_DIR",
        str(Path.home() / "labstep-mirror"),
    )
)
BATCH_SIZE = 1000  # max items per API call

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("labstep-mirror")


def authenticate():
    load_dotenv()
    key = os.environ.get("LABSTEP_API_KEY")
    if not key:
        sys.exit("LABSTEP_API_KEY not found in .env")
    return labstep.authenticate(apikey=key)


def safe_export(entity, dest: Path, label: str):
    """Export a single entity, returning True on success."""
    try:
        dest.mkdir(parents=True, exist_ok=True)
        entity.export(str(dest))
        return True
    except Exception as e:
        log.warning("FAILED %s: %s", label, e)
        return False


def export_resources(user, base: Path):
    """Export resources and their items as JSON (no .export() on resources)."""
    resources_dir = base / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    resources = user.getResources(count=BATCH_SIZE)
    total = len(resources)
    log.info("Exporting %d resources...", total)
    ok = 0

    for i, res in enumerate(resources, 1):
        try:
            safe_name = f"{res.id} - {res.name}"[:120]
            res_dir = resources_dir / safe_name
            res_dir.mkdir(parents=True, exist_ok=True)

            # Save resource metadata
            res_data = {
                "id": res.id,
                "name": res.name,
                "created_at": getattr(res, "created_at", None),
                "updated_at": getattr(res, "updated_at", None),
            }

            # Try to get category
            try:
                cat = res.getResourceCategory()
                if cat:
                    res_data["category"] = {"id": cat.id, "name": cat.name}
            except Exception:
                pass

            # Try to get metadata fields
            try:
                metadata = res.getMetadata()
                if metadata:
                    res_data["metadata"] = [
                        {"id": m.id, "label": getattr(m, "label", None),
                         "value": getattr(m, "value", None)}
                        for m in metadata
                    ]
            except Exception:
                pass

            # Try to get items
            try:
                items = res.getItems()
                if items:
                    res_data["items"] = []
                    for item in items:
                        item_data = {
                            "id": item.id,
                            "name": getattr(item, "name", None),
                            "availability": getattr(item, "availability", None),
                            "amount": getattr(item, "amount", None),
                            "unit": getattr(item, "unit", None),
                        }
                        try:
                            loc = item.getLocation()
                            if loc:
                                item_data["location"] = {
                                    "name": getattr(loc, "name", None),
                                    "guid": getattr(loc, "guid", None),
                                }
                        except Exception:
                            pass
                        res_data["items"].append(item_data)
            except Exception:
                pass

            with open(res_dir / "resource.json", "w") as f:
                json.dump(res_data, f, indent=2, default=str)

            ok += 1
            if i % 50 == 0:
                log.info("  Resources: %d / %d", i, total)

        except Exception as e:
            log.warning("FAILED resource %s (id=%s): %s", res.name, res.id, e)

    log.info("Resources done: %d / %d succeeded", ok, total)
    return ok


def main():
    start = time.time()
    user = authenticate()
    log.info("Authenticated. Mirror root: %s", MIRROR_ROOT)
    MIRROR_ROOT.mkdir(parents=True, exist_ok=True)

    errors = []

    # ── Experiments ────────────────────────────────────────────────
    exp_dir = MIRROR_ROOT / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)

    experiments = user.getExperiments(count=BATCH_SIZE)
    total_exp = len(experiments)
    log.info("Exporting %d experiments...", total_exp)

    exp_ok = 0
    for i, exp in enumerate(experiments, 1):
        label = f"experiment {exp.id} ({exp.name})"
        if safe_export(exp, exp_dir, label):
            exp_ok += 1
        if i % 10 == 0:
            elapsed = time.time() - start
            rate = i / elapsed * 60
            log.info("  Experiments: %d / %d  (%.0f/min)", i, total_exp, rate)

    log.info("Experiments done: %d / %d succeeded", exp_ok, total_exp)

    # ── Protocols ─────────────────────────────────────────────────
    proto_dir = MIRROR_ROOT / "protocols"
    proto_dir.mkdir(parents=True, exist_ok=True)

    protocols = user.getProtocols(count=BATCH_SIZE)
    total_proto = len(protocols)
    log.info("Exporting %d protocols...", total_proto)

    proto_ok = 0
    for i, proto in enumerate(protocols, 1):
        label = f"protocol {proto.id} ({proto.name})"
        if safe_export(proto, proto_dir, label):
            proto_ok += 1
        if i % 10 == 0:
            log.info("  Protocols: %d / %d", i, total_proto)

    log.info("Protocols done: %d / %d succeeded", proto_ok, total_proto)

    # ── Resources (inventory) ─────────────────────────────────────
    res_ok = export_resources(user, MIRROR_ROOT)

    # ── Summary ───────────────────────────────────────────────────
    elapsed = time.time() - start
    summary = {
        "mirrored_at": datetime.now().isoformat(),
        "experiments": {"total": total_exp, "exported": exp_ok},
        "protocols": {"total": total_proto, "exported": proto_ok},
        "resources": {"total": len(user.getResources(count=1)), "exported": res_ok},
        "elapsed_seconds": round(elapsed, 1),
    }
    with open(MIRROR_ROOT / "mirror_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    log.info(
        "Mirror complete in %.0f min. Experiments: %d/%d, Protocols: %d/%d, Resources: %d",
        elapsed / 60, exp_ok, total_exp, proto_ok, total_proto, res_ok,
    )


if __name__ == "__main__":
    main()
