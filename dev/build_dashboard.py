#!/usr/bin/env python3
"""
Build 10x-factorio-engineer/assets/dashboard.html from the vanilla-HTML source.

Reads  : dev/dashboard.html
Writes : 10x-factorio-engineer/assets/dashboard.html  (minified by default)

Minification (stdlib only, no external tools):
  - Strips HTML comments
  - Strips leading/trailing whitespace from every line
  - Drops blank lines
  Script/style content is NOT parsed — whitespace inside <script> and <style>
  blocks is collapsed only at the line level, which is safe for well-formed JS.

Usage:
    python dev/build_dashboard.py            # minify → assets/dashboard.html
    python dev/build_dashboard.py --no-min   # copy as-is
    python dev/build_dashboard.py --open     # build then open in browser
"""

import argparse
import os
import re
import webbrowser

parser = argparse.ArgumentParser(description="Build 10x-factorio-engineer/assets/dashboard.html")
parser.add_argument("--no-min", action="store_true", help="Skip minification, copy as-is")
parser.add_argument("--open",   action="store_true", help="Open bundle.html in browser after build")
args = parser.parse_args()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_DIR  = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(DEV_DIR, "dashboard.html")
OUT  = os.path.join(REPO_ROOT, "10x-factorio-engineer", "assets", "dashboard.html")

with open(SRC, encoding="utf-8") as f:
    html = f.read()

if not args.no_min:
    # 1. Strip HTML comments (not inside script/style — safe because our file has none)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # 2. Strip leading/trailing whitespace from each line and drop blank lines
    lines = [ln.strip() for ln in html.splitlines()]
    html  = "\n".join(ln for ln in lines if ln)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

src_size = os.path.getsize(SRC)
out_size = os.path.getsize(OUT)
saving   = 100 * (1 - out_size / src_size)
print(f"Written: 10x-factorio-engineer/assets/dashboard.html")
print(f"  Source : {src_size:,} bytes  ({SRC})")
print(f"  Output : {out_size:,} bytes  ({saving:.0f}% smaller)")

if args.open:
    webbrowser.open(OUT)
