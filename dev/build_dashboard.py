#!/usr/bin/env python3
"""
Build 10x-factorio-engineer/assets/dashboard.html from the vanilla-HTML source.

Reads  : dev/dashboard.html
Writes : 10x-factorio-engineer/assets/dashboard.html  (minified)

Minification uses the `minify-html` library (pip install minify-html), a
tokenizer-based minifier that safely handles the dashboard's multi-line
template literals, regex literals, and embedded URLs:
  - Strips HTML, CSS, and JS comments
  - Collapses whitespace inside <script> and <style> blocks (not just per-line)
  - Minifies HTML structure

This is a dev-time build dependency only; the produced artifact remains a
single self-contained vanilla HTML file with no runtime dependencies.

Usage:
    python dev/build_dashboard.py          # minify → assets/dashboard.html
    python dev/build_dashboard.py --open   # build then open in browser
"""

import argparse
import os
import webbrowser

try:
    import minify_html
except ImportError:
    raise SystemExit(
        "build_dashboard.py requires the 'minify-html' package.\n"
        "Install it with:  python -m pip install minify-html"
    )

parser = argparse.ArgumentParser(description="Build 10x-factorio-engineer/assets/dashboard.html")
parser.add_argument("--open", action="store_true", help="Open bundle.html in browser after build")
args = parser.parse_args()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_DIR  = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(DEV_DIR, "dashboard.html")
OUT  = os.path.join(REPO_ROOT, "10x-factorio-engineer", "assets", "dashboard.html")

with open(SRC, encoding="utf-8") as f:
    html = f.read()

html = minify_html.minify(html, minify_css=True, minify_js=True)

# newline="" stops Windows text-mode from translating \n to \r\n, so the
# artifact is written with LF endings and matches the repo's text=auto policy
# (otherwise every rebuild produces a CRLF file that git warns it'll normalize).
with open(OUT, "w", encoding="utf-8", newline="") as f:
    f.write(html)

src_size = os.path.getsize(SRC)
out_size = os.path.getsize(OUT)
saving   = 100 * (1 - out_size / src_size)
print(f"Written: 10x-factorio-engineer/assets/dashboard.html")
print(f"  Source : {src_size:,} bytes  ({SRC})")
print(f"  Output : {out_size:,} bytes  ({saving:.0f}% smaller)")

if args.open:
    webbrowser.open(OUT)
