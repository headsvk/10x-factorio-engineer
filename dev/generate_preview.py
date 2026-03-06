#!/usr/bin/env python3
"""
Generate dev/preview.html from 10x-factorio-engineer/assets/dashboard.jsx.

Produces a single self-contained HTML file that opens directly in a browser
(no server needed) using Babel Standalone + React from CDN.

Usage:
    python dev/generate_preview.py
"""

import os
import re
import webbrowser

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR  = os.path.join(REPO_ROOT, "10x-factorio-engineer")
JSX_PATH   = os.path.join(SKILL_DIR, "assets", "dashboard.jsx")
OUT_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview.html")

# ---------------------------------------------------------------------------
# Sample FACTORY_STATE — generated from cli.py runs:
#
#   python cli.py --item automation-science-pack --rate 45 --assembler 3 --furnace electric
#   python cli.py --item logistic-science-pack   --rate 45 --assembler 3 --furnace electric
#
# Scenario: player has fully built the automation science line but only
# placed 2 of the 4 required assemblers on logistic science.
# ---------------------------------------------------------------------------

FACTORY_STATE_JS = r"""
const FACTORY_STATE = {
  "save_name": "My Factory",
  "dataset": "vanilla",
  "assembler": 3,
  "furnace": "electric",
  "prod_module": 0,
  "speed_bonus": 0.0,

  "targets": {
    "automation-science-pack": 45,
    "logistic-science-pack": 45
  },

  "lines": [
    {
      "item": "automation-science-pack",
      "target_rate": 45,
      "effective_rate": 45,
      "actual_machines": {
        "assembling-machine-3": 3,
        "electric-furnace": 5
      },
      "player_notes": "fully built, running smoothly",
      "cli_result": {
        "item": "automation-science-pack",
        "rate_per_min": 45.0,
        "dataset": "vanilla",
        "assembler": 3,
        "furnace": "electric",
        "miner": "electric",
        "prod_module": 0,
        "speed_bonus": 0.0,
        "production_steps": [
          { "recipe": "iron-plate",               "machine": "electric-furnace",    "machine_count": 2.4,  "machine_count_ceil": 3, "rate_per_min": 90.0  },
          { "recipe": "automation-science-pack",  "machine": "assembling-machine-3","machine_count": 3.0,  "machine_count_ceil": 3, "rate_per_min": 45.0  },
          { "recipe": "copper-plate",             "machine": "electric-furnace",    "machine_count": 1.2,  "machine_count_ceil": 2, "rate_per_min": 45.0  },
          { "recipe": "iron-gear-wheel",          "machine": "assembling-machine-3","machine_count": 0.3,  "machine_count_ceil": 1, "rate_per_min": 45.0  }
        ],
        "raw_resources": { "iron-ore": 90.0, "copper-ore": 45.0 },
        "miners_needed": {
          "copper-ore": { "machine": "electric-mining-drill", "machine_count": 1.5, "machine_count_ceil": 2, "rate_per_min": 45.0 },
          "iron-ore":   { "machine": "electric-mining-drill", "machine_count": 3.0, "machine_count_ceil": 3, "rate_per_min": 90.0 }
        },
        "belts_for_output": {
          "yellow": { "belts_needed": 0.05,   "throughput_per_belt": 900  },
          "red":    { "belts_needed": 0.025,  "throughput_per_belt": 1800 },
          "blue":   { "belts_needed": 0.0167, "throughput_per_belt": 2700 }
        }
      }
    },
    {
      "item": "logistic-science-pack",
      "target_rate": 45,
      "effective_rate": 22.5,
      "actual_machines": {
        "assembling-machine-3": 2,
        "electric-furnace": 3
      },
      "player_notes": "only placed 2/4 assemblers so far",
      "cli_result": {
        "item": "logistic-science-pack",
        "rate_per_min": 45.0,
        "dataset": "vanilla",
        "assembler": 3,
        "furnace": "electric",
        "miner": "electric",
        "prod_module": 0,
        "speed_bonus": 0.0,
        "production_steps": [
          { "recipe": "iron-plate",             "machine": "electric-furnace",    "machine_count": 6.6,  "machine_count_ceil": 7, "rate_per_min": 247.5 },
          { "recipe": "copper-cable",           "machine": "assembling-machine-3","machine_count": 0.45, "machine_count_ceil": 1, "rate_per_min": 135.0 },
          { "recipe": "copper-plate",           "machine": "electric-furnace",    "machine_count": 1.8,  "machine_count_ceil": 2, "rate_per_min": 67.5  },
          { "recipe": "iron-gear-wheel",        "machine": "assembling-machine-3","machine_count": 0.45, "machine_count_ceil": 1, "rate_per_min": 67.5  },
          { "recipe": "logistic-science-pack",  "machine": "assembling-machine-3","machine_count": 3.6,  "machine_count_ceil": 4, "rate_per_min": 45.0  },
          { "recipe": "inserter",               "machine": "assembling-machine-3","machine_count": 0.3,  "machine_count_ceil": 1, "rate_per_min": 45.0  },
          { "recipe": "electronic-circuit",     "machine": "assembling-machine-3","machine_count": 0.3,  "machine_count_ceil": 1, "rate_per_min": 45.0  },
          { "recipe": "transport-belt",         "machine": "assembling-machine-3","machine_count": 0.15, "machine_count_ceil": 1, "rate_per_min": 45.0  }
        ],
        "raw_resources": { "iron-ore": 247.5, "copper-ore": 67.5 },
        "miners_needed": {
          "iron-ore":   { "machine": "electric-mining-drill", "machine_count": 8.25, "machine_count_ceil": 9, "rate_per_min": 247.5 },
          "copper-ore": { "machine": "electric-mining-drill", "machine_count": 2.25, "machine_count_ceil": 3, "rate_per_min": 67.5  }
        },
        "belts_for_output": {
          "yellow": { "belts_needed": 0.05,   "throughput_per_belt": 900  },
          "red":    { "belts_needed": 0.025,  "throughput_per_belt": 1800 },
          "blue":   { "belts_needed": 0.0167, "throughput_per_belt": 2700 }
        }
      }
    }
  ],

  "bottlenecks": [
    "logistic-science-pack: producing 22.5/min, need 45/min — place 2 more assembling-machine-3s"
  ],

  "next_steps": [
    "Place 2 more assembling-machine-3 on logistic-science-pack to hit 45/min",
    "Add 4 more electric-furnace on iron-plate smelting for the logistic line"
  ],

  "chat_log": [
    { "from": "player", "text": "I want 45 science packs per minute for both red and green science" },
    { "from": "claude", "text": "For 45 automation science/min: 3 assemblers, 3 electric furnaces on iron, 2 on copper, 3 mining drills on iron, 2 on copper.\n\nFor 45 logistic science/min: 4 assemblers, 7 electric furnaces on iron, 2 on copper.\n\nShared iron smelting is the biggest investment — 9 furnaces total across both lines." },
    { "from": "player", "text": "ok placed 3 assemblers and 5 furnaces on the automation line, that one is done" },
    { "from": "claude", "text": "Automation science is at 100% — 45/min. Now for logistics: you need 4 assemblers and 9 furnaces. How many have you placed so far?" },
    { "from": "player", "text": "placed 2 assemblers and 3 furnaces on logistics" },
    { "from": "claude", "text": "Logistic science is at 50% — producing ~22.5/min. You need 2 more assemblers and 4 more furnaces to hit 45/min." }
  ]
};
""".strip()

# ---------------------------------------------------------------------------
# Read and transform dashboard.jsx
# ---------------------------------------------------------------------------

with open(JSX_PATH, encoding="utf-8") as f:
    jsx = f.read()

# 1. Strip the leading JSDoc block  /** ... */
jsx = re.sub(r"^/\*\*.*?\*/\s*", "", jsx, flags=re.DOTALL)

# 2. Remove `export default` so the function is just a plain declaration
jsx = jsx.replace("export default function FactoryDashboard", "function FactoryDashboard")

# ---------------------------------------------------------------------------
# Assemble HTML
# ---------------------------------------------------------------------------

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Factory Dashboard — Preview</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #111; }}
  </style>
  <!-- React + ReactDOM (development builds for readable errors) -->
  <script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
  <!-- Babel Standalone — transpiles JSX in the browser -->
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
  <div id="root"></div>

  <script type="text/babel">
    /* ── Factory state (generated by cli.py) ─────────────────────────── */
    {FACTORY_STATE_JS}

    /* ── Dashboard component (auto-included from dashboard.jsx) ───────── */
    {jsx}

    /* ── Mount ────────────────────────────────────────────────────────── */
    ReactDOM.createRoot(document.getElementById("root"))
      .render(<FactoryDashboard />);
  </script>
</body>
</html>
"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Written: {os.path.relpath(OUT_PATH, REPO_ROOT)}")
print(f"  JSX source:  {os.path.relpath(JSX_PATH, REPO_ROOT)}  ({jsx.count(chr(10))} lines)")
print(f"  Output size: {len(HTML):,} bytes")
print()
webbrowser.open(OUT_PATH)
