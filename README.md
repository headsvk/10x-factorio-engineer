# 10x Factorio Engineer

A Factorio factory co-pilot built on two components:

| Component | What it does |
|-----------|-------------|
| **CLI Calculator** (`cli.py`) | Zero-dependency Python CLI — resolves full production chains and emits clean JSON |
| **Claude Skill** (`skill/`) | System-prompt + React dashboard that turns Claude into an active planning assistant |

---

## Repository Structure

```
cli.py                      # Calculator — entire implementation
test_cli.py                 # unittest suite (59 tests, stdlib only)
generate_preview.py         # Builds skill/assets/preview.html for local dev
data/
  vanilla-2.0.55.json       # KirkMcDonald dataset — base game
  space-age-2.0.55.json     # KirkMcDonald dataset — Space Age DLC
skill/
  SKILL.md                  # Skill definition document
  assets/
    dashboard.jsx           # React factory dashboard component
    preview.html            # Generated — run generate_preview.py (gitignored)
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
python cli.py --item electronic-circuit --rate 60

# With specific machines and productivity modules
python cli.py --item processing-unit --rate 10 --assembler 3 --furnace electric --prod-module 3

# Override which recipe to use for an item
python cli.py --item solid-fuel --rate 20 --recipe solid-fuel=solid-fuel-from-light-oil

# Space Age DLC
python cli.py --item holmium-plate --rate 30 --dataset space-age --miner big

# Pipe into jq for specific keys
python cli.py --item processing-unit --rate 10 | jq .raw_resources
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
python -m unittest test_cli -v
```

59 tests, stdlib only.

---

## Component 2 — Claude Skill

The skill turns Claude into an active factory co-pilot. It has two parts:

### skill/SKILL.md

A system-prompt document defining Claude's behaviour as a planning assistant:

- **Always call `python cli.py`** for production math — never compute chains mentally.
- **Track the factory conversationally** — parse freeform player updates
  ("just placed 12 electric furnaces on copper"), maintain a structured
  factory-state JSON in context, detect bottlenecks, suggest next steps.
- **Launch/update a React artifact** (the dashboard) when the player wants
  a visual overview.

### skill/assets/dashboard.jsx

A self-contained React component (dark theme, no external dependencies).
Claude renders it as a `application/vnd.ant.react` artifact by prepending
a `FACTORY_STATE` constant:

```js
const FACTORY_STATE = { /* current factory state JSON */ };
// … full dashboard.jsx follows …
```

**Header:** compact brand label (`10x Factorio Engineer`) + config pills
(`[Space Age]` when applicable, `[Assembler 3]`, `[Electric Furnace]`,
`[Productivity N]`). Save name shown as a subtle subtitle.

**Dashboard features:**

| Section | Contents |
|---------|----------|
| Science Packs | Gradient progress bars — actual vs. target rate. All 7 vanilla packs and 5 Space Age packs (Metallurgic/Agricultural/Electromagnetic/Cryogenic/Promethium) have distinct colours. Sorted in canonical research-tree order. |
| Bottleneck banner | Red alert strip, shown only when issues exist |
| Overview tab | Compact line list with % completion + Next Steps |
| Lines tab | Expandable card per production line: machine table (placed vs needed), raw resource rates, miners/extractors (`N× Mining Drill` or `X% yield Pumpjack`), belt lane counts |
| Issues tab | Bottlenecks + next steps with traffic-light colours |
| Chat Log tab | Player/Claude message bubbles |

All machine and item IDs are displayed as friendly names (`assembling-machine-3`
→ `Assembler 3`, `logistic-science-pack` → `Logistic Science`) everywhere in
the UI, including free-text bottleneck and next-step strings.

**Local preview:** `python generate_preview.py` builds `skill/assets/preview.html` —
a single self-contained HTML file that opens in any browser without a server.

### Factory State Schema

Claude keeps this JSON object in context and updates it after every player message:

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

---

## Data Source

Dataset JSON files are sourced from
[KirkMcDonald/kirkmcdonald.github.io](https://github.com/KirkMcDonald/kirkmcdonald.github.io),
the same data that powers <https://kirkmcdonald.github.io/calc.html>.

---

## License

The source code (`cli.py`, `test_cli.py`, `skill/`) is MIT licensed — see [LICENSE](LICENSE).

The vendored data files (`data/*.json`) are from KirkMcDonald's Factorio
Calculator and are licensed under the **Apache License 2.0**. See [NOTICE](NOTICE)
for attribution details.
