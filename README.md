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
  preview.py                # Generates preview.tmp.html with factory state pre-loaded; use Claude Preview MCP to view
  sample/
    state.json              # Sample factory state source JSON — edit directly, paste into Import dialog to test
  my-factory.json           # Dev factory state for local testing
  test_cli.py               # unittest suite (182 tests, stdlib only)
  artifact-api/
    test.html               # claude.ai runtime API test suite — paste as vnd.ant.html to verify window.claude/storage
    research.md             # Field research doc for claude.ai artifact APIs
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

# Space Age with big mining drills (Fulgora)
python assets/cli.py --item holmium-plate --rate 30 --location fulgora --miner big

# Pipe into jq
python assets/cli.py --item processing-unit --rate 10 | jq .raw_resources

# Human-readable terminal output
python assets/cli.py --item electronic-circuit --rate 60 --format human
```

Use `--format human` for a quick terminal overview; omit it (or pass `--format json`) to get structured JSON for piping to `jq` or other tools.

#### Sample `--format human` output

```
$ python assets/cli.py --item electronic-circuit --rate 60 --format human

=== electronic-circuit @ 60.0/min ===
Location: vanilla  |  Assembler: 3  |  Furnace: electric  |  Miner: electric

Production Steps
----------------
copper-cable                    180.0/min    0.6 -> 1 assembling-machine-3
  power: 225.0 kW  (375.0 kW ceil)
  <- copper-plate                  90.0/min

copper-plate                    90.0/min    2.4 -> 3 electric-furnace
  power: 432.0 kW  (540.0 kW ceil)
  <- copper-ore                    90.0/min

iron-plate                      60.0/min    1.6 -> 2 electric-furnace
  power: 288.0 kW  (360.0 kW ceil)
  <- iron-ore                      60.0/min

electronic-circuit              60.0/min    0.4 -> 1 assembling-machine-3
  power: 150.0 kW  (375.0 kW ceil)
  <- copper-cable                  180.0/min
  <- iron-plate                    60.0/min

Raw Resources
-------------
  copper-ore                      90.0/min
  iron-ore                        60.0/min

Miners Needed
-------------
  iron-ore                        2.0 electric-mining-drill (2 ceil)
  copper-ore                      3.0 electric-mining-drill (3 ceil)

Power
-----
  Total: 1.545 MW  (2.1 MW with ceil counts)
```

With modules + beacons + machine quality the header shows configuration and each step includes a detail line:
```
=== electronic-circuit @ 60.0/min ===
Location: vanilla  |  Assembler: 3  |  Furnace: electric  |  Miner: electric
Machine quality: legendary  |  Beacon quality: normal
Modules:  assembling-machine-3 = 4x prod-3-normal
Beacons:  assembling-machine-3 = 8x tier-3-legendary

Production Steps
----------------
electronic-circuit              60.0/min    0.0098 -> 1 legendary assembling-machine-3
  modules: 4x prod-3-normal  |  beacons: 8x tier-3-legendary  |  speed bonus: +10.6066
  power: 15.5084 kW  (1575.0 kW ceil)  +  960.0 kW beacons
  <- copper-cable                  128.5714/min
  <- iron-plate                    42.8571/min
...
```

See [SKILL.md §2](10x-factorio-engineer/SKILL.md) for the complete flags reference and full JSON output shape.

### Running Tests

```bash
python -m unittest dev.test_cli -v
```

182 tests, stdlib only.

---

## Component 2 — Claude Skill

`SKILL.md` turns Claude into an active factory co-pilot:

- **CLI mode** — Claude calls `python assets/cli.py` for all production math, tracks factory state conversationally, and outputs `FACTORY_STATE` JSON at session end for import into the dashboard.
- **Dashboard mode** — a published `application/vnd.ant.html` artifact with an Overview tab (science SPM headline + grouped production lines), Bus Balance (player-declared bus items vs. consumed rates), per-line machine tables, bottleneck detection, and in-artifact chat. Dark and light themes; state persists via `window.storage` (cross-device) with `localStorage` fallback. Import/Export buttons sync state with CLI sessions.

See [SKILL.md §3](10x-factorio-engineer/SKILL.md) for the factory state schema shared by the skill and the dashboard.

### Dashboard screenshots

| Dark theme | Light theme |
|:----------:|:-----------:|
| ![Dashboard dark](dev/screenshots/readme__dark.png) | ![Dashboard light](dev/screenshots/readme__light.png) |

### Building the dashboard

```bash
python dev/build_dashboard.py    # minify dev/dashboard.html → assets/dashboard.html
python dev/build_dashboard.py --open    # build and open in browser
python dev/preview.py            # preview with dev/sample/state.json pre-loaded
python dev/preview.py --state PATH/TO/x.json  # preview with a custom state file
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

### Skill / Workflow

- **GitHub Actions: skill zip** — bundle `SKILL.md`, `assets/`, and `references/` into a `.zip` for claude.ai project knowledge

### Infra

- **GitHub Actions: test runner** — run `dev/test_cli.py` on every push to `main` and on PRs

---

## License

The source code (`10x-factorio-engineer/`, `dev/`) is MIT licensed — see [LICENSE](LICENSE).

The vendored data files (`10x-factorio-engineer/assets/*.json`) are from KirkMcDonald's Factorio
Calculator and are licensed under the **Apache License 2.0**. See [NOTICE](NOTICE)
for attribution details.
