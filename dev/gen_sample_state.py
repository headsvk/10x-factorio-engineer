#!/usr/bin/env python3
"""
Regenerate dev/sample-state.b64 from dev/sample-state.json.

The encoding is:
    minified JSON (no extra whitespace) → UTF-8 bytes → standard base64

Usage:
    python dev/gen_sample_state.py              # read sample-state.json, write sample-state.b64
    python dev/gen_sample_state.py --src PATH   # use a different JSON source
    python dev/gen_sample_state.py --pretty     # also print the decoded JSON to stdout
"""

import argparse
import base64
import json
import os

parser = argparse.ArgumentParser(description="Encode a factory-state JSON to base64")
parser.add_argument("--src",    default=None, help="Source JSON file (default: dev/sample-state.json)")
parser.add_argument("--pretty", action="store_true", help="Print decoded JSON to stdout after writing")
args = parser.parse_args()

DEV_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = args.src or os.path.join(DEV_DIR, "sample-state.json")
OUT = os.path.join(DEV_DIR, "sample-state.b64")

with open(SRC, encoding="utf-8") as f:
    state = json.load(f)

minified = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
encoded  = base64.b64encode(minified.encode("utf-8")).decode("ascii")

with open(OUT, "w", encoding="ascii") as f:
    f.write(encoded)
    f.write("\n")

print(f"Written: {OUT}  ({len(encoded)} chars base64, {len(minified)} chars JSON)")

if args.pretty:
    print(json.dumps(state, indent=2, ensure_ascii=False))
