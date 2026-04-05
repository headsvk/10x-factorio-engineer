#!/usr/bin/env python3
"""
Generate dev/preview.tmp.html with sample state pre-loaded in localStorage.

Reads dev/sample-state.b64 and injects it so the sample factory appears
immediately when the file is opened. Use the Claude Preview MCP tool
(server: dashboard-preview, port 7474) to view the result.

Usage:
    python dev/preview.py
    python dev/preview.py --no-min   # use unminified source dashboard
"""

import argparse
import os
import re

DEV_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(DEV_DIR)

parser = argparse.ArgumentParser(description="Preview dashboard with sample state")
parser.add_argument("--no-min", action="store_true", help="Use unminified dev/dashboard.html")
args = parser.parse_args()

if args.no_min:
    src = os.path.join(DEV_DIR, "dashboard.html")
else:
    src = os.path.join(REPO_ROOT, "10x-factorio-engineer", "assets", "dashboard.html")

my_factory_json = os.path.join(DEV_DIR, "my-factory.json")
my_factory_b64  = os.path.join(DEV_DIR, "my-factory.b64")

if os.path.exists(my_factory_b64):
    b64_path = my_factory_b64
elif os.path.exists(my_factory_json):
    # Auto-encode on the fly
    import base64, json
    with open(my_factory_json, encoding="utf-8") as f:
        b64_path = None
        sample_b64 = base64.b64encode(
            json.dumps(json.load(f), separators=(',', ':')).encode()
        ).decode()
else:
    b64_path = os.path.join(DEV_DIR, "sample-state.b64")

with open(src, encoding="utf-8") as f:
    html = f.read()

if b64_path is not None:
    with open(b64_path, encoding="utf-8") as f:
        sample_b64 = f.read().strip()

# Inject a seed script that pre-populates localStorage before the app boots.
# Placed just before </body> so it runs after the DOM is parsed but we inject
# it before the existing inline <script> which calls loadState() on init.
# Actually we need it BEFORE the main script — insert before the main <script>.
seed_script = f"""<script>
localStorage.setItem('factorio_engineer_state', {repr(sample_b64)});
</script>
"""

# Insert before the first <script> block so seed runs before app init
html = html.replace("<script>", seed_script + "<script>", 1)

out_path = os.path.join(DEV_DIR, "preview.tmp.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Preview written: {out_path}")
