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
  SKILL.md                  # Skill definition document
  assets/
    cli.py                  # Calculator — entire implementation
    dashboard.html          # Built artifact — paste into claude.ai as application/vnd.ant.html
    vanilla-2.0.55.json     # KirkMcDonald dataset — base game
    space-age-2.0.55.json   # KirkMcDonald dataset — Space Age DLC
  references/
    strategy-topics.md      # On-demand strategy reference
dev/
  dashboard.html            # Dashboard source — single vanilla HTML, no build deps
  build_dashboard.py        # Minifies dashboard.html → assets/dashboard.html
  sample-state.b64          # Sample factory state base64-encoded — paste into Import dialog to test
  test_cli.py               # unittest suite (59 tests, stdlib only)
  artifact-api-test.html    # claude.ai runtime API test suite (window.claude, window.storage, CDN loading, etc.)
  artifact-api.md           # Field research doc for claude.ai artifact APIs
```

Data files are vendored; auto-downloaded from KirkMcDonald's GitHub on first run.

---

## Component 1 — CLI Calculator

### Requirements

- Python 3.10+  (uses `dict | None` union syntax)
- No third-party packages — pure stdlib only

### Quick Start

```bash
# Basic usage
python assets/cli.py --item electronic-circuit --rate 60

# With specific machines and productivity modules
python assets/cli.py --item processing-unit --rate 10 --assembler 3 --furnace electric --prod-module 3

# Override which recipe to use for an item
python assets/cli.py --item solid-fuel --rate 20 --recipe solid-fuel=solid-fuel-from-light-oil

# Space Age DLC
python assets/cli.py --item holmium-plate --rate 30 --dataset space-age --miner big

# Pipe into jq for specific keys
python assets/cli.py --item processing-unit --rate 10 | jq .raw_resources
```

### CLI Flags

| Flag | Default | Values | Description |
|------|---------|--------|-------------|
| `--item` | *(required)* | any item-id | Target item key (e.g. `iron-plate`) |
| `--rate` | *(required)* | float | Desired output in **items / minute** |
| `--assembler` | `3` | `1`, `2`, `3` | Assembling machine level for crafting recipes |
| `--furnace` | `electric` | `stone`, `steel`, `electric` | Furnace type for smelting recipes |
| `--miner` | `electric` | `electric`, `big` | Mining drill for solid ores (`big` = Space Age big mining drill) |
| `--prod-module` | `0` | `0`, `1`, `2`, `3` | Fill all module slots with productivity modules of this tier. Slot count is per-machine (e.g. assembling-machine-3 = 4 slots, electric-furnace = 2 slots). Machines with 0 slots are unaffected. |
| `--speed` | `0.0` | float | Speed bonus as a decimal (e.g. `0.5` = +50%). Applied uniformly to all machines. |
| `--dataset` | `vanilla` | `vanilla`, `space-age` | Game dataset |
| `--recipe` | *(none)* | `ITEM=RECIPE` | Override the recipe used for a specific item. Repeatable. E.g. `--recipe solid-fuel=solid-fuel-from-light-oil` |
| `--machine` | *(none)* | `CATEGORY=MACHINE` | Override the machine used for a recipe category. Repeatable. E.g. `--machine organic-or-assembling=assembling-machine-3` |

### Output JSON

```json
{
  "item": "electronic-circuit",
  "rate_per_min": 60.0,
  "dataset": "vanilla",
  "assembler": 3,
  "furnace": "electric",
  "miner": "electric",
  "prod_module": 0,
  "speed_bonus": 0.0,
  "production_steps": [
    {
      "recipe":             "electronic-circuit",
      "machine":            "assembling-machine-3",
      "machine_count":      2.56,
      "machine_count_ceil": 3,
      "rate_per_min":       60.0
    },
    {
      "recipe":             "copper-cable",
      "machine":            "assembling-machine-3",
      "machine_count":      1.6,
      "machine_count_ceil": 2,
      "rate_per_min":       180.0
    },
    {
      "recipe":             "iron-plate",
      "machine":            "electric-furnace",
      "machine_count":      1.6,
      "machine_count_ceil": 2,
      "rate_per_min":       60.0
    },
    {
      "recipe":             "copper-plate",
      "machine":            "electric-furnace",
      "machine_count":      2.4,
      "machine_count_ceil": 3,
      "rate_per_min":       90.0
    }
  ],
  "raw_resources": {
    "copper-ore": 90.0,
    "iron-ore":   60.0
  },
  "miners_needed": {
    "copper-ore": {
      "machine":            "electric-mining-drill",
      "machine_count":      3.0,
      "machine_count_ceil": 3,
      "rate_per_min":       90.0
    },
    "iron-ore": {
      "machine":            "electric-mining-drill",
      "machine_count":      2.0,
      "machine_count_ceil": 2,
      "rate_per_min":       60.0
    }
  },
  "belts_for_output": {
    "yellow": { "belts_needed": 0.0667, "throughput_per_belt": 900 },
    "red":    { "belts_needed": 0.0333, "throughput_per_belt": 1800 },
    "blue":   { "belts_needed": 0.0222, "throughput_per_belt": 2700 }
  }
}
```

### Key Output Fields

| Field | Description |
|-------|-------------|
| `production_steps` | Every recipe in the dependency tree. `machine_count` is exact (rational); `machine_count_ceil` rounds up to whole machines. |
| `raw_resources` | Items with no crafting recipe (ores, crude-oil, water …). Rates are items/minute required from the ground. |
| `miners_needed` | Per-resource extractor counts. Solid ores → `machine_count`. Crude-oil/fluids → `required_yield_pct` (FactorioLab style: total % yield needed across all pumpjack fields). Water → `offshore-pump` count. |
| `belts_for_output` | Full belt lanes needed for the *target item* output. Space Age adds a `turbo` tier (3600/min). |
| `recipe_overrides` | Only present when `--recipe` flags were passed. |
| `machine_overrides` | Only present when `--machine` flags were passed. |

### Recipe Selection

When an item has multiple recipes (e.g. `solid-fuel` has three), the tool picks by priority:

1. Explicit `--recipe ITEM=RECIPE` override
2. Recipe whose key exactly matches the item name
3. `advanced-oil-processing` (fallback for oil products)
4. First recipe after sorting by the game's own `order` field

### Oil Processing

`petroleum-gas`, `light-oil`, and `heavy-oil` are solved jointly as a 3-variable
linear system (AOP + heavy-oil cracking + light-oil cracking) to avoid
double-counting crude-oil when multiple oil products appear in the same chain.

### Productivity Modules

`--prod-module 3` fills every eligible machine's slots with productivity-module-3
(+10% per slot). Machine slot counts:

| Machine | Slots |
|---------|-------|
| Assembling machine 1 | 0 |
| Assembling machine 2 | 2 |
| Assembling machine 3 | 4 |
| Stone / steel furnace | 0 |
| Electric furnace | 2 |
| Chemical plant | 3 |
| Oil refinery | 3 |
| Centrifuge | 2 |
| Rocket silo | 4 |
| Electromagnetic plant | 5 |
| Electronics assembly | 5 |
| Foundry / cryogenic plant | 4 |
| Crusher | 2 |

Recipes that don't allow productivity (belts, inserters, buildings, weapons …)
are never boosted regardless of the flag.

### Machine Crafting Speeds

| Machine | Speed |
|---------|-------|
| Assembling machine 1/2/3 | 0.5 / 0.75 / 1.25 |
| Stone / steel / electric furnace | 1.0 / 2.0 / 2.0 |
| Chemical plant | 1.0 |
| Oil refinery | 1.0 |
| Centrifuge | 1.0 |
| Rocket silo | 1.0 |
| Foundry | 4.0 |
| Electromagnetic plant | 2.0 |
| Electronics assembly | 3.0 |
| Cryogenic plant / biochamber | 1.5 |
| Crusher | 1.0 |

### Caveats

- **Coal liquefaction**: cycle-detected ingredients are surfaced as raw inputs.
- **Steam**: treated as a raw resource (no crafting recipe in the dataset).
- **Beacons**: `--speed` applies uniformly to all machines; per-machine beacon amplification is not modelled.
- **Quality**: Space Age quality tiers are not modelled.
- **Belt counts** reflect only the *target item* output rate; intermediate ingredient belts are not calculated.

### Running Tests

```bash
python -m unittest dev.test_cli -v
```

59 tests, stdlib only.

---

## Component 2 — Claude Skill

The skill turns Claude into an active factory co-pilot with two parts that complement each other:

### Usage modes

**CLI mode** — power users, terminal
- Claude calls `python assets/cli.py` for all production math
- Tracks factory state conversationally
- At session end: Claude outputs the full `FACTORY_STATE` JSON for import into the dashboard

**Dashboard mode** — visual, cross-device, mobile-friendly
- A published `application/vnd.ant.html` artifact at a permanent URL
- State persists via `window.storage` (Anthropic server-side, cross-device) with `localStorage` fallback
- In-artifact chat via `window.claude.complete()` for light updates ("I placed 8 assemblers")
- Import/Export buttons for syncing state with CLI sessions
- Claude does not need to regenerate the artifact — it lives at a fixed URL

### State sync between modes

```
CLI session ends   →  Claude outputs FACTORY_STATE JSON
                   →  User clicks Export in dashboard, copies base64 code
                   →  User pastes code at start of next CLI session as context

User clicks Import →  Paste exported base64 (or plain JSON) into the Import dialog
                   →  Dashboard decodes and saves to window.storage
```

### Dashboard features

Single vanilla HTML file — no React, no build toolchain, no external dependencies. Source in `dev/dashboard.html`, minified artifact in `10x-factorio-engineer/assets/dashboard.html`.

| Section | Contents |
|---------|----------|
| Header | Brand label + storage mode pill (Cloud sync / Local only) + config badges + Import/Export |
| Science Packs | Gradient progress bars — actual vs. target rate. All 7 vanilla packs and 5 Space Age packs have distinct colours. Sorted in canonical research-tree order. |
| Bottleneck banner | Red alert strip, shown only when issues exist |
| Overview tab | Compact line list with % completion + Next Steps |
| Lines tab | Expandable card per production line: machine table (placed vs needed), raw resources, miners/extractors, belt lane counts |
| Issues tab | Bottlenecks + next steps with traffic-light colours |
| Chat tab | In-artifact conversation with Claude (`window.claude.complete()`). Claude can update factory state directly from chat responses. |

### Storage behaviour

| Storage | Available | Scope |
|---------|-----------|-------|
| `window.storage` | Published artifact only | Cross-device (Anthropic server-side, 20 MB) |
| `localStorage` | Always | Same browser/device only |

The dashboard tries `window.storage` first and falls back to `localStorage` transparently. A storage mode pill in the header shows which is active.

### Building the dashboard

```bash
python dev/build_dashboard.py           # minify dev/dashboard.html → assets/dashboard.html
python dev/build_dashboard.py --no-min  # copy as-is (easier to inspect)
python dev/build_dashboard.py --open    # build and open in browser
```

### Factory State Schema

Both the CLI skill and the dashboard share this JSON schema:

```jsonc
{
  "save_name": "My Factory",
  "dataset": "vanilla",           // "vanilla" | "space-age"
  "assembler": 3,                 // 1 | 2 | 3
  "furnace": "electric",          // "stone" | "steel" | "electric"
  "prod_module": 0,               // 0–3
  "speed_bonus": 0.0,
  "targets": { "automation-science-pack": 45 },
  "lines": [
    {
      "item": "electronic-circuit",
      "target_rate": 60.0,
      "effective_rate": 52.0,       // derived from actual placed machines
      "cli_result": { /* full cli.py output */ },
      "actual_machines": { "assembling-machine-3": 3 },
      "player_notes": "still need furnaces"
    }
  ],
  "bottlenecks": ["iron-plate: need 60/min, actual ~45/min — add 1 electric furnace"],
  "next_steps":  ["Build copper-plate smelting: 3 electric furnaces for 90/min"],
  "chat_log":    [{ "from": "player", "text": "…" }, { "from": "claude", "text": "…" }]
}
```

### SKILL.md

Defines Claude's behaviour as a planning assistant:

- **Always call `python assets/cli.py`** for production math — never compute chains mentally.
- **Track the factory conversationally** — parse freeform player updates, maintain `FACTORY_STATE` in context, detect bottlenecks, suggest next steps.
- **Output `FACTORY_STATE` JSON** at session end for import into the dashboard.
- **Load `references/strategy-topics.md`** on demand for layout, trains, megabases, Space Age, power, and combat questions.

---

## Data Source

Dataset JSON files are sourced from
[KirkMcDonald/kirkmcdonald.github.io](https://github.com/KirkMcDonald/kirkmcdonald.github.io),
the same data that powers <https://kirkmcdonald.github.io/calc.html>.

---

## Future Work

### CLI / Calculator

- **Beacon support** — model beacon amplification per machine; `--beacon` flag specifying module tier and count
- **Quality tiers** — Space Age quality; `--quality` flag affecting machine speeds and recipe yields
- **Power output** — MW per production line (machines × active/idle draw) and total for the factory
- **Multi-target solve** — one CLI call for a full science block (e.g. red + green + blue simultaneously, shared intermediates deduplicated)
- **Preferences file** — `--prefs factorio-prefs.json` to load default flags (assembler, furnace, recipe/machine overrides) so they don't need repeating each call

### Dashboard

- **Further minification** — inline CSS/JS whitespace stripping, dead-code removal, shorter variable names to shrink the artifact below 30 kB
- **Factorio icons** — item and machine icons from [deniszholob/icons-factorio](https://github.com/deniszholob/icons-factorio) throughout the UI
- **Cleaner design** — visual polish pass: spacing, typography, colour hierarchy
- **Shopping list view** — total machines, belts, and modules needed to physically build all lines
- **Multi-save slots** — switch between named factory states without manual import/export

### Skill / Workflow

- **Structured onboarding** — ask dataset → assembler → furnace → prod module tier upfront rather than inferring mid-session
- **`FACTORY_STATE` diff** — Claude summarises what changed between two exported states
- **GitHub Actions: skill zip** — CI job that bundles `SKILL.md`, `assets/`, and `references/` into a `.zip` ready to upload to claude.ai as a project knowledge file

### Infra

- **GitHub Actions: test runner** — run `dev/test_cli.py` on every push to `main` and on PRs

---

## License

The source code (`10x-factorio-engineer/`, `dev/`) is MIT licensed — see [LICENSE](LICENSE).

The vendored data files (`10x-factorio-engineer/assets/*.json`) are from KirkMcDonald's Factorio
Calculator and are licensed under the **Apache License 2.0**. See [NOTICE](NOTICE)
for attribution details.
