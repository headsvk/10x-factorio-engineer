# 10x Factorio Engineer

A Factorio factory co-pilot built on two components:

| Component | What it does |
|-----------|-------------|
| **CLI Calculator** (`assets/cli.py`) | Zero-dependency Python CLI — resolves full production chains and emits clean JSON |
| **Claude Skill** (`10x-factorio-engineer/`) | System-prompt + published web artifact that turns Claude into an active planning assistant |

---

## Repository Structure

```
10x-factorio-engineer/
  SKILL.md                  # Skill definition — CLI usage, output format, factory state schema
  assets/
    cli.py                  # Calculator — entire implementation
    dashboard.html          # Built artifact — paste into claude.ai as application/vnd.ant.html
    vanilla-2.0.55.json     # KirkMcDonald dataset — base game
    space-age-2.0.55.json   # KirkMcDonald dataset — Space Age DLC
  references/
    *.md                    # Split strategy reference files (11 topics: early-game, factory-layouts, trains, megabase, planets, space-platforms, power, combat-defense, logistics-circuits, quality, resources)
dev/
  dashboard.html            # Dashboard source — single vanilla HTML, no build deps
  build_dashboard.py        # Minifies dashboard.html → assets/dashboard.html
  preview.py                # Opens dashboard in browser with sample state pre-loaded
  gen_sample_state.py       # Encodes sample-state.json → sample-state.b64
  sample-state.json         # Sample factory state source JSON
  sample-state.b64          # Sample factory state base64-encoded — paste into Import dialog to test
  test_cli.py               # unittest suite (136 tests, stdlib only)
  artifact-api-test.html    # claude.ai runtime API test suite
  artifact-api.md           # Field research doc for claude.ai artifact APIs
```

Data files are vendored; auto-downloaded from KirkMcDonald's GitHub on first run.

---

## Component 1 — CLI Calculator

**Requirements:** Python 3.10+, no third-party packages.

```bash
# Basic usage
python assets/cli.py --item electronic-circuit --rate 60

# Multi-target: solve two items at once (shared sub-recipes merged)
python assets/cli.py --item electronic-circuit --rate 60 --item automation-science-pack --rate 30

# Productivity + beacon modules
python assets/cli.py --item electronic-circuit --rate 60 \
    --modules "assembling-machine-3=4:prod:3:normal" \
    --beacon "assembling-machine-3=8:3:legendary" \
    --machine-quality legendary

# Override recipe
python assets/cli.py --item solid-fuel --rate 20 --recipe solid-fuel=solid-fuel-from-light-oil

# Machine-count mode — specify machines instead of a target rate
python assets/cli.py --item transport-belt --machines 2 --assembler 2

# Bus items (pull iron/copper from bus, don't recurse into smelting)
python assets/cli.py --item electronic-circuit --rate 1800 \
    --bus-item iron-plate --bus-item copper-plate

# Space Age with big mining drills
python assets/cli.py --item holmium-plate --rate 30 --dataset space-age --miner big

# Pipe into jq
python assets/cli.py --item processing-unit --rate 10 | jq .raw_resources
```

See [SKILL.md §2](10x-factorio-engineer/SKILL.md) for the complete flags reference and full JSON output shape.

### Running Tests

```bash
python -m unittest dev.test_cli -v
```

136 tests, stdlib only.

---

## Component 2 — Claude Skill

`SKILL.md` turns Claude into an active factory co-pilot:

- **CLI mode** — Claude calls `python assets/cli.py` for all production math, tracks factory state conversationally, and outputs `FACTORY_STATE` JSON at session end for import into the dashboard.
- **Dashboard mode** — a published `application/vnd.ant.html` artifact with an Overview tab (science SPM headline + grouped production lines), Bus Balance (player-declared bus items vs. consumed rates), per-line machine tables, bottleneck detection, and in-artifact chat. Dark and light themes; state persists via `window.storage` (cross-device) with `localStorage` fallback. Import/Export buttons sync state with CLI sessions.

See [SKILL.md §3](10x-factorio-engineer/SKILL.md) for the factory state schema shared by the skill and the dashboard.

### Building the dashboard

```bash
python dev/build_dashboard.py    # minify dev/dashboard.html → assets/dashboard.html
python dev/build_dashboard.py --open    # build and open in browser
python dev/preview.py            # open dev/dashboard.html in browser with sample state pre-loaded
```

---

## Data Source

Dataset JSON files are sourced from
[KirkMcDonald/kirkmcdonald.github.io](https://github.com/KirkMcDonald/kirkmcdonald.github.io),
the same data that powers <https://kirkmcdonald.github.io/calc.html>.

---

## Future Work

### CLI / Calculator

- **Quality recycling loops** — model the throughput cost of quality recycling lines for legendary production
- **Multi-target solve** — one CLI call for a full science block with shared intermediates deduplicated

### Dashboard

- **Factorio icons** — item and machine icons throughout the UI
- **Shopping list view** — total machines, belts, and modules needed to physically build all lines
- **Multi-save slots** — switch between named factory states without manual import/export

### Skill / Workflow

- **Structured onboarding** — ask dataset → assembler → furnace → prod module tier upfront
- **GitHub Actions: skill zip** — bundle `SKILL.md`, `assets/`, and `references/` into a `.zip` for claude.ai project knowledge

### Infra

- **GitHub Actions: test runner** — run `dev/test_cli.py` on every push to `main` and on PRs

---

## License

The source code (`10x-factorio-engineer/`, `dev/`) is MIT licensed — see [LICENSE](LICENSE).

The vendored data files (`10x-factorio-engineer/assets/*.json`) are from KirkMcDonald's Factorio
Calculator and are licensed under the **Apache License 2.0**. See [NOTICE](NOTICE)
for attribution details.
