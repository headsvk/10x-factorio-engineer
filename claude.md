# 10x Factorio Engineer — Claude Context

Kept up-to-date so Claude can understand the full project without needing conversation history.

---

## Project Overview

Two components that work together to act as a Factorio factory co-pilot:

**Component 1 — CLI Calculator** (`skill/assets/cli.py`)
Single-file zero-dependency Python CLI. Takes an item + target rate and emits
precise JSON covering machine counts, raw resource rates, miner counts, and belt
requirements. Based on KirkMcDonald's recipe data. Claude calls this for all
production math — it never does the recursive recipe tree in its head.

```
python skill/assets/cli.py --item <item-id> --rate <N> [options]
```

**Component 2 — Claude Skill** (`skill/`)
A `SKILL.md` that tells Claude how to behave as a planning assistant: when and
how to call the CLI, how to track the player's factory conversationally, and how
to render a React artifact dashboard showing science-pack progress, bottlenecks,
and per-line machine counts. The dashboard component lives in
`skill/assets/dashboard.jsx`. A strategy reference file
(`skill/references/strategy-topics.md`) is loaded on demand for layout,
combat, power, Space Age, and other non-math questions.

---

## Maintenance Rules

**These rules apply every time you edit any file in this repo.**

| Trigger | Required follow-up action |
|---------|--------------------------|
| `skill/assets/dashboard.jsx` is modified | No change to `SKILL.md` required — Section 6 references the file directly. Run `python dev/generate_preview.py` to update the local preview. |
| `skill/assets/cli.py` output shape changes (new fields, renamed keys) | Update the **JSON Output Shape** table and any affected sections in this file (`claude.md`) and in `skill/SKILL.md` Section 2. |
| New CLI flag added | Add it to the **CLI Flags** table in `claude.md` and the matching table in `skill/SKILL.md` Section 2. |
| Any `.py` file is created or edited | Run `get_errors` on the file afterwards and fix all Pylance errors before finishing. Prefer `assert x is not None` over `assertIsNotNone(x)` when the result is used afterward — Pylance uses the former as a type-narrowing guard but not the latter. |
| Before making a commit | Review `README.md` and update it to reflect any changes made (test counts, new CLI flags, new features, changed behaviour, etc.). |

The goal is that `claude.md` always accurately describes the codebase. `SKILL.md` Section 6 references `skill/assets/dashboard.jsx` — keep that file up to date.

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `skill/assets/cli.py` | Calculator — entire implementation, stdlib only |
| `skill/assets/vanilla-2.0.55.json` | KirkMcDonald dataset — base game |
| `skill/assets/space-age-2.0.55.json` | KirkMcDonald dataset — Space Age DLC |
| `dev/test_cli.py` | `unittest` suite (59 tests, stdlib only) — dev only |
| `skill/SKILL.md` | Skill definition — Claude gameplay assistant behaviour |
| `skill/assets/dashboard.jsx` | React artifact — factory dashboard component |
| `skill/references/strategy-topics.md` | On-demand strategy reference: layouts, trains, megabases, Space Age, power, combat |
| `dev/generate_preview.py` | Script that builds `skill/assets/preview.html` for local dev |

Dataset files are vendored. Auto-downloaded from KirkMcDonald's GitHub if missing.

---

## Component 1: CLI Calculator

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--item` | required | Item ID (e.g. `electronic-circuit`) |
| `--rate` | required | Target items/minute |
| `--assembler` | `3` | Assembling machine level 1/2/3 |
| `--furnace` | `electric` | `stone` / `steel` / `electric` |
| `--miner` | `electric` | `electric` / `big` (big = Space Age big mining drill) |
| `--prod-module` | `0` | Productivity module tier to fill all slots (0=none, 1/2/3). Slot count is per-machine (e.g. assembling-machine-3=4, electric-furnace=2). |
| `--speed` | `0.0` | Speed bonus as decimal (e.g. `0.5` = +50%) |
| `--dataset` | `vanilla` | `vanilla` / `space-age` |
| `--recipe` | _(none)_ | Override recipe for a specific item. Repeatable. Format: `ITEM=RECIPE-KEY` (e.g. `--recipe rocket-fuel=ammonia-rocket-fuel`) |
| `--machine` | _(none)_ | Override machine for a recipe category. Repeatable. Format: `CATEGORY=MACHINE-KEY` (e.g. `--machine organic-or-assembling=assembling-machine-3`) |

---

## JSON Output Shape

```json
{
  "item": "processing-unit",
  "rate_per_min": 10,
  "dataset": "vanilla",
  "assembler": 3,
  "furnace": "electric",
  "miner": "electric",
  "prod_module": 0,
  "speed_bonus": 0.0,
  "production_steps": [
    {
      "recipe": "processing-unit",
      "machine": "assembling-machine-3",
      "machine_count": 7.5,
      "machine_count_ceil": 8,
      "rate_per_min": 10.0
    }
  ],
  "raw_resources": {
    "crude-oil": 487.18,
    "iron-ore": 120.0
  },
  "miners_needed": {
    "crude-oil": {
      "machine": "pumpjack",
      "required_yield_pct": 81.2,
      "rate_per_min": 487.18
    },
    "iron-ore": {
      "machine": "electric-mining-drill",
      "machine_count": 4.0,
      "machine_count_ceil": 4,
      "rate_per_min": 120.0
    }
  },
  "belts_for_output": {
    "yellow": { "belts_needed": 0.0111, "throughput_per_belt": 900 },
    "red":    { "belts_needed": 0.0056, "throughput_per_belt": 1800 },
    "blue":   { "belts_needed": 0.0037, "throughput_per_belt": 2700 }
  },
  "recipe_overrides": { "heavy-oil": "coal-liquefaction" },
  "machine_overrides": { "metallurgy": "assembling-machine-3" }
}
```

Notes:
- `pumpjack` emits `required_yield_pct` instead of `machine_count` (FactorioLab style — the total yield % across all pumpjack fields needed)
- `offshore-pump` emits `machine_count` + `machine_count_ceil`
- `space-age` dataset adds a `turbo` belt tier (3600/min) to `belts_for_output`
- `recipe_overrides` key is present only when `--recipe` flags were passed
- `machine_overrides` key is present only when `--machine` flags were passed

---

## Architecture

### Key functions

| Function | Role |
|----------|------|
| `load_data(dataset)` | Load JSON; auto-download if missing |
| `load_prefs(path)` | Load `factorio-prefs.json` from CWD (or given path); returns `{}` if absent |
| `build_raw_set(data)` | Items with no recipe (ores, crude-oil, water, etc.) |
| `build_recipe_index(data)` | `{item_key: [recipe, ...]}`, skips recycling + barrel subgroups |
| `build_resource_info(data)` | `{item: {mining_time, yield, category}}` using `Fraction` |
| `get_machine(cat, assembler_level, furnace_type)` | Maps recipe category → `(machine_key, speed)` |
| `pick_recipe(item_key, recipe_idx, overrides)` | Picks canonical recipe (see selection logic below) |
| `_gauss2 / _gauss3` | Exact `Fraction` Gaussian elimination (2×2 and 3×3) |
| `solve_oil_system(...)` | Joint linear solve for refinery recipe (AOP / CL / simple-CL) + cracking |
| `Solver.solve(item_key, rate)` | Recursive tree walk; defers oil products |
| `Solver.resolve_oil(data)` | Injects oil linear-system results into steps/raw_resources |
| `compute_miners(...)` | Per-resource miner/pump counts |
| `format_output(...)` | Assembles final JSON dict |

### `Solver` class state

- `steps`: `{recipe_key: {recipe, machine, machine_count, rate_per_min}}` — accumulated across all tree paths
- `raw_resources`: `{item: Fraction}` — total demanded rate
- `surplus`: `{item: Fraction}` — co-product credits not yet consumed
- `oil_demands`: `{item: Fraction}` — deferred petroleum-gas/light-oil/heavy-oil demands
- `machine_overrides`: `{category: machine_key}` — redirects category’s default machine

---

## Arithmetic

All numeric values use `fractions.Fraction` internally. Only converted to `float` in `format_output()`. This eliminates floating-point accumulation errors.

---

## Recipe Selection Logic (`pick_recipe`)

Priority (in `pick_recipe`):
1. Explicit `--recipe ITEM=RECIPE` override passed in from CLI.
2. Recipe whose `key == item_key` (exact match).
3. `advanced-oil-processing` (legacy fallback for oil products).
4. Entry in `RECIPE_DEFAULTS` (hard-coded preferred recipes that override the order-sort default when the order-sort winner is un-automatable or causes circular dependencies in the solver).
5. First candidate after sorting all candidates by the game's `order` field.

Step 5's sort ensures the game-preferred variant is chosen when no exact match exists (e.g. `solid-fuel-from-petroleum-gas` over the less-efficient heavy-oil and petroleum-gas variants).

### `RECIPE_DEFAULTS`

A module-level dict that maps `item_key → recipe_key` for items where the order-sort default is wrong:

| Item | Default recipe | Reason |
|------|---------------|--------|
| `nutrients` | `nutrients-from-yumako-mash` | `nutrients-from-fish` sorts first but is un-automatable (raw-fish not minable) and causes a circular dependency via `fish-breeding → nutrients` |

### Why this matters

- **Vanilla**: `solid-fuel` has 3 recipes. Sorting by `order` picks `solid-fuel-from-petroleum-gas` (order `b[fluid-chemistry]-c[...]`), which is the game's canonical display order. Use `--recipe solid-fuel=solid-fuel-from-light-oil` to override.
- **Space Age**: 37 items have multiple recipes. Common cases: casting upgrades in foundry for plates/cable/gears/pipe, alternative processes for `rocket-fuel`, `nutrients`, etc.

---

## Oil Processing

`petroleum-gas`, `light-oil`, `heavy-oil` are in `OIL_PRODUCTS` and handled specially:

1. During `Solver.solve()`, demands for these are **deferred** into `oil_demands{}` (not recursed into immediately).
2. After the whole tree is walked, `Solver.resolve_oil()` calls `solve_oil_system()` once to solve the refinery + HOC + LOC jointly.
3. This prevents double-counting crude-oil when multiple oil products are needed by different sub-trees.

**Refinery recipe selection** (in `resolve_oil()`):
1. If any oil product has a `--recipe` override pointing to an `oil-processing` recipe (e.g. `coal-liquefaction`, `simple-coal-liquefaction`), use it.
2. Otherwise default to `advanced-oil-processing` (or `basic-oil-processing`).

The linear system (where `ref_H` is the **net** heavy-oil yield = gross output − self-consumed input, handling coal-liquefaction's 25-heavy-oil self-feed):
```
ref_H * r - hoc_in * h                  = D_heavy
ref_L * r + hoc_out * h - loc_in * l    = D_light
ref_P * r               + loc_out * l   = D_petgas
```
Negative-variable cases (surplus of one oil fraction) are handled by clamping to zero and re-solving the reduced system.

**Coal liquefaction** (`--recipe heavy-oil=coal-liquefaction`):
- Inputs: coal 10 + heavy-oil 25 (self-consumed, excluded from raw demands) + steam 50
- Net outputs per cycle: heavy-oil 65, light-oil 20, petroleum-gas 10
- `ref_H = 90 − 25 = 65` — the solver handles the circular self-feed transparently
- coal and steam become raw resources; crude-oil is absent

**Simple coal liquefaction** (`--recipe heavy-oil=simple-coal-liquefaction`, Space Age Vulcanus):
- Inputs: coal 10 + calcite 2 + sulfuric-acid 25 (no self-consuming heavy oil)
- Output: heavy-oil 50 only; cracking handles light-oil / petgas demand

---

## Machine Category Mappings

**Vanilla:**
- `smelting` → furnace (stone/steel/electric per `--furnace`)
- `chemistry` → chemical-plant (speed 1)
- `oil-processing` → oil-refinery (speed 1)
- `centrifuging` → centrifuge (speed 1)
- `rocket-building` → rocket-silo (speed 1)
- everything else → assembling-machine-N per `--assembler`

**Space Age additions:**
- `cryogenics*` → cryogenic-plant (speed 3/2)
- `organic*` → biochamber (speed 3/2)
- `electromagnetics` → electromagnetic-plant (speed 2)
- `electronics*` → electronics-assembly (speed 3)
- `metallurgy*`, `crafting-with-fluid-or-metallurgy` → foundry (speed 4)
- `crushing` → crusher (speed 1)
- `pressing` → agricultural-tower (speed 1)
- `captive-spawner-process` → captive-spawner (speed 1)

---

## Miner Logic

| Resource category | Machine | Output metric |
|-------------------|---------|---------------|
| `offshore` | `offshore-pump` | `machine_count` (fixed 1200/min each) |
| `basic-fluid` (crude-oil, heavy-oil springs) | `pumpjack` | `required_yield_pct` |
| everything else (solid ores) | `electric-mining-drill` or `big-mining-drill` | `machine_count` |

**Pumpjack yield formula:**
```
rate_at_100pct = (pumpjack_speed / mining_time) * yield * 60
required_pct   = demanded_rate / rate_at_100pct * 100
```
This matches FactorioLab's display. Players divide this across their pumpjack fields.

---

## Tests

```bash
python -m unittest dev.test_cli -v
```

`dev/test_cli.py` contains 59 tests covering:

| Class | What's tested |
|-------|---------------|
| `TestPickRecipe` | Exact key match, order-sort fallback, override priority, unknown override fall-through |
| `TestElectronicCircuit` | Raw resource rates (iron-ore=60, copper-ore=90 at 60/min) |
| `TestOilChainNoDoubleCounting` | crude-oil ≈ 487.18 for processing-unit at 10/min; AOP counted once; no oil products in raw_resources |
| `TestPumpjackYield` | `required_yield_pct` ≈ 81.2% for crude-oil; water → offshore-pump |
| `TestRecipeOverride` | `--recipe` override flag; default solid-fuel = petroleum-gas variant; override surfaced in JSON output |
| `TestSpaceAgeMachineRouting` | superconductor routes to electromagnetic-plant + foundry + cryogenic-plant |
| `TestBigMiningDrill` | 4 big drills for tungsten-ore at 60/min; electric drill for vanilla iron |
| `TestMachineCategoryVanilla` | assembler-3 default; electric/stone furnace; chemical-plant; oil-refinery |
| `TestProductivityBonus` | prod-module-3 on assembling-machine-3 reduces count; stone-furnace (0 slots) ignores prod; electric-furnace 2-slot ratio; speed bonus |
| `TestFractionArithmetic` | All `raw_resources` and `machine_count` values remain `Fraction` throughout |
| `TestCoalLiquefaction` | `coal-liquefaction` via `--recipe heavy-oil=coal-liquefaction`; net heavy-oil math (65/cycle); coal+steam in raw; AOP not used; cracking engaged for petgas demand |
| `TestSimpleCoalLiquefaction` | `simple-coal-liquefaction` (Space Age); coal+calcite+sulfuric-acid in raw; no crude-oil; cracking for petgas |
| `TestGlebaMachineRouting` | `organic` → biochamber (no assembler); `pressing` → agricultural-tower (count=1/4 for transport-belt); `captive-spawner-process` → captive-spawner with zero inputs |
| `TestNutrientsRecipes` | Default picks `nutrients-from-yumako-mash` via `RECIPE_DEFAULTS` (not fish); no circular dependency; fish route still available via `--recipe` override; bioflux override full biochamber chain |
| `TestSpaceAgeTurboBelt` | Space Age `format_output` includes `turbo` belt tier (3600/min); vanilla does not |
| `TestMachineOverride` | `--machine CATEGORY=MACHINE` redirects category to a different machine; unknown machine falls through; machine_overrides appears in JSON output |
| `TestPrefsFile` | `load_prefs()` returns `{}` for missing file; reads all supported fields (dataset, assembler, recipe_overrides, machine_overrides, preferred_belt) |

---

## Dataset Schema (KirkMcDonald format)

Top-level keys: `items[]`, `recipes[]`, `resources[]`, `planets[]`

**Recipe fields:**
- `key` — unique string ID (matches item name for simple recipes)
- `category` — determines machine type
- `energy_required` — crafting time in seconds
- `ingredients[]` — `{name, amount}`
- `results[]` — `{name, amount}` (multi-output for oil/co-products)
- `allow_productivity` — bool
- `subgroup` — used to filter out barrel recipes
- `order` — game's display sort string (useful for recipe selection)

**Resource fields:**
- `key` / `results[{name, amount}]` — what the resource produces
- `mining_time` — drill mining time
- `category` — `"basic-fluid"` for pumpjack, `"offshore"` for offshore pump, else solid

---

## Excluded Recipes

- `subgroup` in `["empty-barrel", "fill-barrel"]` — barrel packing/unpacking
- `category` in `["recycling", "recycling-or-hand-crafting"]` — Space Age recycler output recipes

---

## Known Limitations / Pending Work

1. **No quality support**: Space Age quality tiers not modelled.

2. **No beacon support**: Speed bonus (`--speed`) and productivity (`--prod-module`) are applied uniformly across all machines. Beacon amplification is not modelled.

---

## Dependencies

Stdlib only — no `pip install` required: `argparse`, `json`, `math`, `os`, `sys`, `urllib.request`, `collections`, `fractions`.

---

## Component 2: Claude Skill

### Purpose

`skill/SKILL.md` is a system-prompt document that turns Claude into an active
Factorio gameplay assistant. It defines three responsibilities:

1. **Precise calculations** — always call `python skill/assets/cli.py`, never compute
   production chains mentally.
2. **Conversational factory tracking** — parse freeform player updates ("just
   placed 12 electric furnaces on copper"), maintain a structured factory-state
   JSON in context, detect bottlenecks, and suggest next steps.
3. **Strategy guidance** — load `skill/references/strategy-topics.md` on demand
   to answer questions about layouts, trains, megabases, Space Age planets,
   power, combat, and more.

### skill/SKILL.md sections

| Section | Contents |
|---------|----------|
| 1 — Role | Co-pilot persona: exact numbers, CLI-first, no mental math |
| 2 — Calculator | CLI flags, examples, JSON output schema, item ID resolution |
| 3 — Factory State Model | Full JSON schema Claude keeps in context |
| 4 — Answering Planning Questions | 5-step protocol: identify → run CLI → parse → format → update state |
| 5 — Dashboard Artifact | When/how to launch, FACTORY_STATE injection protocol |
| 6 — React Dashboard | Full inline JSX for copy-paste into a React artifact |
| 7 — Session Start | Greeting + dataset/assembler/module onboarding |
| 8 — Common Workflows | Scripts for "how many machines", "I just built N", "plan science", etc. |
| 9 — Item ID Quick Reference | Player shorthand → internal item ID map |
| 10 — Error Handling | Unknown items, no-recipe items, direct oil product requests |
| 11 — Strategy Guide Reference | When/how to load `skill/references/strategy-topics.md` for layout, combat, power, and Space Age questions |

### Factory State JSON Schema

Claude maintains this object in conversation context, updating it after every
player message:

```jsonc
{
  "save_name": "My Factory",
  "dataset": "vanilla",           // "vanilla" | "space-age"
  "assembler": 3,                 // 1 | 2 | 3
  "furnace": "electric",          // "stone" | "steel" | "electric"
  "prod_module": 0,               // 0–3
  "speed_bonus": 0.0,

  "recipe_overrides": {           // item-id → recipe-key; --recipe flags on every CLI call
    "heavy-oil": "coal-liquefaction"
  },
  "machine_overrides": {          // recipe-category → machine-key; --machine flags on every CLI call
    "organic-or-assembling": "assembling-machine-3"
  },
  "preferred_belt": "blue",       // "yellow"|"red"|"blue"|"turbo"; lead with this tier in answers

  "targets": {                    // science-pack (or any item) target rates/min
    "automation-science-pack": 45
  },

  "lines": [
    {
      "item": "electronic-circuit",
      "target_rate": 60.0,
      "effective_rate": 52.0,     // derived from actual_machines
      "cli_result": { /* full cli.py JSON output */ },
      "actual_machines": {        // placed counts as told by player
        "assembling-machine-3": 3
      },
      "player_notes": "still need furnaces"
    }
  ],

  "bottlenecks": [
    "iron-plate: need 60/min, actual ~45/min — add 1 electric furnace"
  ],
  "next_steps": [
    "Build copper-plate smelting: 3 electric furnaces for 90/min"
  ],
  "chat_log": [
    { "from": "player", "text": "just placed 12 electric furnaces on copper" },
    { "from": "claude", "text": "Copper-plate line can now produce 120/min …" }
  ]
}
```

### skill/assets/dashboard.jsx

A self-contained React component (no external dependencies, dark theme) that
reads from an injected `FACTORY_STATE` const. Rendered by Claude as a
`application/vnd.ant.react` artifact.

**Header:** compact one-line brand label (`10x Factorio Engineer`) left +
config pills right (`[Space Age]` when applicable, `[Assembler 3]`,
`[Electric Furnace]`, `[Productivity N]`). Save name is a subtle subtitle.

**Features:**

| Section | Contents |
|---------|----------|
| Science Packs | Gradient progress bar per target pack — actual vs target rate, colour-coded by pack. Vanilla and all 5 Space Age packs (Metallurgic/Agricultural/Electromagnetic/Cryogenic/Promethium) have distinct colours. Bars sorted in canonical research-tree order. |
| Bottleneck banner | Red alert strip, shown only when issues exist |
| Overview tab | Compact line list with % completion + Next Steps |
| Lines tab | Expandable `LineCard` per production line: machine table (placed/needed), raw resource rates, miners/extractors section (`N× Mining Drill` or `X% yield Pumpjack`), belt lane counts |
| Issues tab | Bottlenecks + next steps with traffic-light colours |
| Chat Log tab | Player/Claude message bubbles |

**ID humanisation:** `humanizeText()` converts any kebab-case machine or item
ID to a friendly name everywhere it appears — machine column, miners section,
bottleneck/next-step free-text strings. Known machines use a handcrafted map
(`assembling-machine-3` → `Assembler 3`); everything else falls back to
title-cased label conversion.

**Local preview:** run `python dev/generate_preview.py` to produce
`skill/assets/preview.html` — a single self-contained file (React + Babel from
CDN) that opens directly in any browser without a dev server.

**FACTORY_STATE injection pattern** (Claude prepends this before the JSX):

```js
const FACTORY_STATE = { /* state JSON */ };
// … full dashboard.jsx follows …
```

Every dashboard update is a full paste (not a diff) — the artifact is always
self-contained.
