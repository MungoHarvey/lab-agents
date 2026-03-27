#!/usr/bin/env python3
"""
Labstep CLI Query Tool
Fast CLI access to Labstep data - list experiments, protocols, resources.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
import ssl
from datetime import datetime


def load_env_file(path):
    """Load key=value pairs from .env file into os.environ."""
    try:
        with open(os.path.expanduser(path)) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key] = val
    except FileNotFoundError:
        pass


# Load .env from project root or ~/.openclaw/.env
load_env_file(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_env_file('~/.openclaw/.env')

# API Configuration
API_KEY = os.environ.get('LABSTEP_API_KEY')
if not API_KEY:
    print("Error: LABSTEP_API_KEY not found. Set it in .env or ~/.openclaw/.env", file=sys.stderr)
    sys.exit(1)
BASE_URL = "https://api.labstep.com"

# SSL context (Labstep API needs this)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def api_call(endpoint, params=None):
    """Make API call to Labstep."""
    url = f"{BASE_URL}{endpoint}"
    if params:
        query = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
        url = f"{url}?{query}"

    req = urllib.request.Request(url, headers={"apikey": API_KEY})
    with urllib.request.urlopen(req, context=ssl_context) as response:
        return json.loads(response.read().decode())


def list_experiments(search=None, count=20):
    """List recent experiments with SK numbers."""
    params = {"count": str(count)}
    if search:
        params["search_query"] = search

    data = api_call("/api/generic/experiment-workflow", params)
    experiments = data.get("items", [])

    if not experiments:
        print("No experiments found.")
        return

    print(f"Found {len(experiments)} experiment(s):\n")
    print("-" * 80)

    for exp in experiments:
        exp_id = exp.get("id", "N/A")
        name = exp.get("name", "Untitled")
        custom_id = exp.get("custom_identifier", "")
        # Get author from entity_users_preview
        author = "Unknown"
        entity_users = exp.get("entity_users_preview", [])
        if entity_users:
            user = entity_users[0].get("user", {})
            author = user.get("name", "Unknown")
        created = exp.get("created_at", "")[:10] if exp.get("created_at") else ""

        if custom_id:
            print(f"{custom_id}: {name} by {author} ({created})")
        else:
            print(f"ID:{exp_id}: {name} by {author} ({created})")


def get_experiment(sk_number):
    """Get experiment details by SK number."""
    # Search by custom identifier (SK number)
    data = api_call("/api/generic/experiment-workflow", {"search_query": sk_number, "count": "10"})
    experiments = data.get("items", [])

    # Find exact match
    exp = None
    for e in experiments:
        if e.get("custom_identifier") == sk_number:
            exp = e
            break

    if not exp:
        print(f"Experiment {sk_number} not found.")
        return

    # Get author from entity_users_preview
    author = "Unknown"
    entity_users = exp.get("entity_users_preview", [])
    if entity_users:
        user = entity_users[0].get("user", {})
        author = user.get("name", "Unknown")

    print(f"\n{'='*80}")
    print(f"Experiment: {exp.get('name', 'Untitled')}")
    print(f"SK Number: {exp.get('custom_identifier', 'N/A')}")
    print(f"ID: {exp.get('id')}")
    print(f"Author: {author}")
    print(f"Created: {exp.get('created_at', '')[:10]}")
    print(f"State: {exp.get('state', 'unknown')}")
    print(f"URL: https://app.labstep.com/experiment-workflow/{exp.get('id')}")
    print(f"{'='*80}\n")

    # Print description/entry if available
    entry = exp.get('entry', '')
    if entry:
        print("Description:")
        print(entry[:500] + "..." if len(entry) > 500 else entry)
        print()


def list_protocols(search=None, count=20):
    """List protocols."""
    params = {"count": str(count)}
    if search:
        params["search_query"] = search
    
    data = api_call("/api/generic/protocol", params)
    protocols = data.get("protocols", [])
    
    if not protocols:
        print("No protocols found.")
        return
    
    print(f"Found {len(protocols)} protocol(s):\n")
    print("-" * 80)
    
    for proto in protocols:
        proto_id = proto.get("id", "N/A")
        name = proto.get("name", "Untitled")
        author = proto.get("author", {}).get("name", "Unknown") if proto.get("author") else "Unknown"
        created = proto.get("created_at", "")[:10] if proto.get("created_at") else ""
        
        print(f"ID:{proto_id}: {name} by {author} ({created})")


def list_resources(search=None, count=20):
    """Search resources/inventory."""
    params = {"count": str(count)}
    if search:
        params["search_query"] = search
    
    data = api_call("/api/generic/resource", params)
    resources = data.get("resources", [])
    
    if not resources:
        print("No resources found.")
        return
    
    print(f"Found {len(resources)} resource(s):\n")
    print("-" * 80)
    
    for res in resources:
        res_id = res.get("id", "N/A")
        name = res.get("name", "Untitled")
        category = res.get("resource_category", {}).get("name", "Uncategorized") if res.get("resource_category") else "Uncategorized"
        
        print(f"ID:{res_id}: {name} [{category}]")


def get_reagents(sk_number):
    """Get reagents/inventory for an experiment."""
    # First get experiment ID
    data = api_call("/api/generic/experiment-workflow", {"search_query": sk_number, "count": "10"})
    experiments = data.get("items", [])

    exp_id = None
    for e in experiments:
        if e.get("custom_identifier") == sk_number:
            exp_id = e.get("id")
            break

    if not exp_id:
        print(f"Experiment {sk_number} not found.")
        return

    # Get inventory fields for experiment
    try:
        data = api_call(f"/api/generic/experiment-workflow/{exp_id}/inventory-field")
        fields = data.get("items", [])

        if not fields:
            print(f"No reagents/inventory found for {sk_number}.")
            return

        print(f"\nReagents/Inventory for {sk_number}:\n")
        print("-" * 80)

        for field in fields:
            name = field.get("name", "Unnamed")
            amount = field.get("amount", "")
            units = field.get("units", "")
            resource = field.get("resource", {}).get("name", "") if field.get("resource") else ""

            print(f"• {name}: {amount} {units} ({resource})")

    except Exception as e:
        print(f"Could not fetch reagents: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Query Labstep electronic lab notebook',
        prog='labstep-query'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Experiments
    exp_parser = subparsers.add_parser('experiments', help='List experiments')
    exp_parser.add_argument('--search', '-s', help='Search query')
    exp_parser.add_argument('--count', '-n', type=int, default=20, help='Number of results')
    
    # Single experiment
    exp_detail = subparsers.add_parser('experiment', help='Get experiment by SK number')
    exp_detail.add_argument('sk_number', help='SK number (e.g., SK592)')
    
    # Reagents
    reagent_parser = subparsers.add_parser('reagents', help='Get reagents for experiment')
    reagent_parser.add_argument('sk_number', help='SK number (e.g., SK592)')
    
    # Protocols
    proto_parser = subparsers.add_parser('protocols', help='List protocols')
    proto_parser.add_argument('--search', '-s', help='Search query')
    proto_parser.add_argument('--count', '-n', type=int, default=20, help='Number of results')
    
    # Resources
    res_parser = subparsers.add_parser('resources', help='Search resources/inventory')
    res_parser.add_argument('--search', '-s', help='Search query')
    res_parser.add_argument('--count', '-n', type=int, default=20, help='Number of results')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'experiments':
            list_experiments(search=args.search, count=args.count)
        elif args.command == 'experiment':
            get_experiment(args.sk_number)
        elif args.command == 'reagents':
            get_reagents(args.sk_number)
        elif args.command == 'protocols':
            list_protocols(search=args.search, count=args.count)
        elif args.command == 'resources':
            list_resources(search=args.search, count=args.count)
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} - {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
