#!/usr/bin/env python3
"""Labstep query helper. Usage:

  python3 labstep-query.py experiments [--count N] [--search TERM]
  python3 labstep-query.py experiment <ID_OR_SKXX>
  python3 labstep-query.py reagents <EXPERIMENT_ID_OR_SKXX>
  python3 labstep-query.py protocol <PROTOCOL_ID>
  python3 labstep-query.py protocols [--count N] [--search TERM]
  python3 labstep-query.py resources [--count N] [--search TERM]
"""
import os
import sys

import labstep
from dotenv import load_dotenv

load_dotenv()
user = labstep.authenticate(apikey=os.environ.get("LABSTEP_API_KEY"))


def _find_experiment(ref: str):
    """Find experiment by numeric ID or SKXX identifier."""
    if ref.isdigit():
        return user.getExperiment(int(ref))
    # Search by custom_identifier (SKXX)
    ref_upper = ref.upper()
    for exp in user.getExperiments(count=200):
        if (getattr(exp, "custom_identifier", "") or "").upper() == ref_upper:
            return exp
    return None


def cmd_experiments(args):
    count = 10
    search = None
    i = 0
    while i < len(args):
        if args[i] == "--count" and i + 1 < len(args):
            count = int(args[i + 1]); i += 2
        elif args[i] == "--search" and i + 1 < len(args):
            search = args[i + 1]; i += 2
        else:
            i += 1
    exps = user.getExperiments(count=count, search_query=search) if search else user.getExperiments(count=count)
    for e in exps:
        sk = getattr(e, "custom_identifier", "") or ""
        author = getattr(e, "author", None)
        author_name = ""
        if author:
            if isinstance(author, dict):
                name = author.get("name") or author.get("full_name") or author.get("username") or ""
            else:
                name = getattr(author, "full_name", None) or getattr(author, "name", None) or getattr(author, "email", "")
            if name:
                author_name = f" [{name}]"
        print(f"{sk} (ID {e.id}){author_name}: {e.name}")


def cmd_experiment(args):
    exp = _find_experiment(args[0])
    if not exp:
        print(f"Experiment '{args[0]}' not found."); return
    sk = getattr(exp, "custom_identifier", "") or ""
    print(f"# {sk}: {exp.name} (ID {exp.id})")
    print(f"Link: https://app.labstep.com/experiment-workflow/{exp.id}")
    
    # Author / Creator
    author = getattr(exp, "author", None)
    if author:
        if isinstance(author, dict):
            author_name = author.get("name") or author.get("full_name") or author.get("username") or "Unknown"
        else:
            author_name = getattr(author, "full_name", None) or getattr(author, "name", None) or getattr(author, "email", "Unknown")
        print(f"Author: {author_name}")
    
    # Collaborators
    try:
        collaborators = exp.getCollaborators()
        if collaborators:
            collab_names = []
            for c in collaborators:
                name = getattr(c, "full_name", None) or getattr(c, "name", None) or getattr(c, "email", None)
                if name:
                    collab_names.append(name)
            if collab_names:
                print(f"Collaborators: {', '.join(collab_names)}")
    except Exception:
        pass
    
    print()

    # Protocols
    protos = exp.getProtocols()
    if protos:
        print("## Protocols")
        for p in protos:
            print(f"  - {p.name} (ID {p.id})")
        print()

    # Data fields
    fields = exp.getDataFields()
    if fields:
        print("## Data Fields")
        for f in fields:
            val = getattr(f, "value", None) or getattr(f, "number", None) or ""
            unit = getattr(f, "unit", "") or ""
            if val:
                print(f"  - {f.label}: {val} {unit}".strip())
            else:
                print(f"  - {f.label}: (empty)")
        print()

    # Files
    files = exp.getFiles()
    if files:
        print("## Files")
        for fi in files:
            print(f"  - {getattr(fi, 'name', '?')}")
        print()

    # Comments
    comments = exp.getComments()
    if comments:
        print("## Comments")
        for c in comments:
            print(f"  - {getattr(c, 'body', '')[:120]}")


def cmd_reagents(args):
    exp = _find_experiment(args[0])
    if not exp:
        print(f"Experiment '{args[0]}' not found."); return
    sk = getattr(exp, "custom_identifier", "") or ""
    print(f"# Reagents for {sk}: {exp.name}")
    print()

    protos = exp.getProtocols()
    if not protos:
        print("No protocols linked — cannot determine reagents."); return

    seen = set()
    for proto in protos:
        inv = proto.getInventoryFields()
        if inv:
            print(f"## From protocol: {proto.name}")
            for item in inv:
                name = getattr(item, "name", None) or "Unknown"
                amount = getattr(item, "amount", "") or ""
                units = getattr(item, "units", "") or ""
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    line = f"  - {name}"
                    if amount or units:
                        line += f": {amount} {units}".strip()
                    print(line)
            print()


def cmd_protocol(args):
    proto = user.getProtocol(int(args[0]))
    sk = getattr(proto, "custom_identifier", "") or ""
    print(f"# Protocol: {proto.name} (ID {proto.id})")
    if sk:
        print(f"Identifier: {sk}")
    print()

    steps = proto.getSteps()
    if steps:
        print("## Steps")
        for idx, s in enumerate(steps, 1):
            name = getattr(s, "name", "") or f"Step {idx}"
            body = getattr(s, "body", "") or ""
            print(f"  {idx}. {name}")
            if body:
                print(f"     {body[:200]}")
        print()

    inv = proto.getInventoryFields()
    if inv:
        print("## Reagents / Inventory")
        for item in inv:
            name = getattr(item, "name", "?")
            amount = getattr(item, "amount", "") or ""
            units = getattr(item, "units", "") or ""
            line = f"  - {name}"
            if amount or units:
                line += f": {amount} {units}".strip()
            print(line)
        print()

    fields = proto.getDataFields()
    if fields:
        print("## Data Fields")
        for f in fields:
            val = getattr(f, "value", None) or ""
            print(f"  - {f.label}: {val}" if val else f"  - {f.label}")

    timers = proto.getTimers()
    if timers:
        print("\n## Timers")
        for t in timers:
            print(f"  - {getattr(t, 'name', '?')}: {getattr(t, 'hours', 0)}h {getattr(t, 'minutes', 0)}m {getattr(t, 'seconds', 0)}s")


def cmd_protocols(args):
    count = 10
    search = None
    i = 0
    while i < len(args):
        if args[i] == "--count" and i + 1 < len(args):
            count = int(args[i + 1]); i += 2
        elif args[i] == "--search" and i + 1 < len(args):
            search = args[i + 1]; i += 2
        else:
            i += 1
    protos = user.getProtocols(count=count, search_query=search) if search else user.getProtocols(count=count)
    for p in protos:
        sk = getattr(p, "custom_identifier", "") or ""
        print(f"{sk} (ID {p.id}): {p.name}" if sk else f"ID {p.id}: {p.name}")


def cmd_resources(args):
    count = 10
    search = None
    i = 0
    while i < len(args):
        if args[i] == "--count" and i + 1 < len(args):
            count = int(args[i + 1]); i += 2
        elif args[i] == "--search" and i + 1 < len(args):
            search = args[i + 1]; i += 2
        else:
            i += 1
    resources = user.getResources(count=count, search_query=search) if search else user.getResources(count=count)
    for r in resources:
        print(f"ID {r.id}: {r.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    commands = {
        "experiments": cmd_experiments,
        "experiment": cmd_experiment,
        "reagents": cmd_reagents,
        "protocol": cmd_protocol,
        "protocols": cmd_protocols,
        "resources": cmd_resources,
    }
    fn = commands.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}\n{__doc__}"); sys.exit(1)
    fn(rest)
