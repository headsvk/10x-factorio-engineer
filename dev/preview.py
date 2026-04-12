#!/usr/bin/env python3
"""
Generate dev/preview.tmp.html with a factory state pre-loaded in localStorage.

Reads dev/sample/state.json by default (or a custom path via --state).
Use the Claude Preview MCP tool (server: dashboard-preview, port 7474) to view.

Usage:
    python dev/preview.py                          # use dev/sample/state.json
    python dev/preview.py --state PATH/TO/x.json   # use a different JSON file
    python dev/preview.py --no-min                 # use unminified dev/dashboard.html
"""

import argparse
import base64
import json
import os
import re

DEV_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(DEV_DIR)

parser = argparse.ArgumentParser(description="Preview dashboard with factory state")
parser.add_argument("--state", default=None, help="JSON state file to load (default: dev/sample/state.json)")
parser.add_argument("--no-min", action="store_true", help="Use unminified dev/dashboard.html")
args = parser.parse_args()

state_path = args.state or os.path.join(DEV_DIR, "sample", "state.json")

if args.no_min:
    src = os.path.join(DEV_DIR, "dashboard.html")
else:
    src = os.path.join(REPO_ROOT, "10x-factorio-engineer", "assets", "dashboard.html")

with open(state_path, encoding="utf-8") as f:
    sample_b64 = base64.b64encode(
        json.dumps(json.load(f), separators=(',', ':')).encode()
    ).decode()

with open(src, encoding="utf-8") as f:
    html = f.read()

# Inject a seed script before the first <script> so it runs before app init,
# pre-populating localStorage so the sample factory appears immediately.
seed_script = f"""<script>
localStorage.setItem('factorio_engineer_state', {repr(sample_b64)});
</script>
"""
html = html.replace("<script>", seed_script + "<script>", 1)

out_path = os.path.join(DEV_DIR, "preview.tmp.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Preview written: {out_path}")
print(f"State: {state_path}")
