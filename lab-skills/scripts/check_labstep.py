#!/usr/bin/env python3
"""
Labstep Connection Test
Checks if Labstep API is configured and working.
"""

import os
import sys


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


def check_labstep_config():
    """Check if Labstep is configured and test connectivity."""
    # Load .env if needed
    if not os.environ.get('LABSTEP_API_KEY'):
        load_env_file(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
        load_env_file('~/.openclaw/.env')
    
    api_key = os.environ.get('LABSTEP_API_KEY')
    if not api_key:
        return {"configured": False, "error": "LABSTEP_API_KEY not found"}
    
    # Test API connectivity
    import json
    import urllib.request
    import ssl
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(
            "https://api.labstep.com/api/generic/experiment-workflow?count=1",
            headers={"apikey": api_key}
        )
        with urllib.request.urlopen(req, context=ssl_context) as resp:
            data = json.loads(resp.read().decode())
            return {
                "configured": True,
                "api_key": api_key[:10] + "...",
                "experiments_found": len(data.get("items", [])),
            }
    except Exception as e:
        return {"configured": False, "error": str(e)}


if __name__ == "__main__":
    result = check_labstep_config()
    print(result)
    sys.exit(0 if result["configured"] else 1)
