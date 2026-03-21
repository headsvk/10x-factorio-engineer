# 10x Factorio Engineer — Claude Context

Kept up-to-date so Claude can understand the full project without needing conversation history.

---

## Project Overview

Two components that work together to act as a Factorio factory co-pilot:

**Component 1 — CLI Calculator** (`10x-factorio-engineer/assets/cli.py`)
Single-file zero-dependency Python CLI. Takes an item + target rate and emits
precise JSON covering machine counts, raw resource rates, miner counts, and belt
requirements. Based on KirkMcDonald's recipe data. Claude calls this for all
production math — it never does the recursive recipe tree in its head.

```
python 10x-factorio-engineer/assets/cli.py --item <item-id> --rate <N> [options]
```

**Component 2 — Claude Skill + Dashboard** (`10x-factorio-engineer/`)
A `SKILL.md` that tells Claude how to behave as a planning assistant: when and
how to call the CLI, how to track the player's factory conversationally, and how
to output a `FACTORY_STATE` for import into the dashboard. The dashboard is a
published `application/vnd.ant.html` artifact — a single vanilla HTML file with
no build dependencies. State is encoded as base64 and stored in `window.storage`
(Anthropic server-side, cross-device) with `localStorage` fallback. An in-artifact
chat panel is powered by `window.claude.complete()`. Strategy references
in `10x-factorio-engineer/references/` are loaded on demand per topic.

---

## Maintenance Rules

**These rules apply every time you edit any file in this repo.**

| Trigger | Required follow-up action |
|---------|--------------------------|
| `dev/dashboard.html` is modified | Run `python dev/build_dashboard.py` from the repo root to rebuild `10x-factorio-engineer/assets/dashboard.html`. Never edit the built artifact directly — it is overwritten on every build. To preview: run `python dev/preview.py` then use the Claude Preview MCP tool (server name `dashboard-preview`, config at `.claude/launch.json`) — **never** open the file in a browser via `--open` or `subprocess`. |
| `10x-factorio-engineer/assets/cli.py` output shape changes (new fields, renamed keys) | Update the JSON output example and field table in `10x-factorio-engineer/SKILL.md` §2. The JSON example must include every field that appears in real CLI output — run the CLI and copy actual values rather than inventing them. Then check whether the factory-state schema (SKILL.md §3) needs updating — if yes, follow the factory-state rule below. Verify by grepping SKILL.md for each new field name and confirming it appears in both the example block and the field table. |
| CLI flag added, removed, or changed | 1. Update the module-level docstring at the top of `cli.py` (Usage block). 2. Update the flags table in `10x-factorio-engineer/SKILL.md` §2. If it affects factory-state tracking, also update `10x-factorio-engineer/SKILL.md` §3 schema and follow the factory-state rule below. |
| `10x-factorio-engineer/assets/cli.py` output shape changes (new fields, renamed keys) OR `--format human` output layout changes | Update the sample `--format human` output block in `README.md`. Run the CLI with `--format human` and copy actual output rather than editing manually. |
| Factory state schema changes (SKILL.md §3 fields added/removed/renamed) | 1. Update `10x-factorio-engineer/SKILL.md` §3. 2. Update `dev/dashboard.html` to reflect the new schema. 3. Update `dev/sample-state.json` to match the new schema. 4. Run `python dev/gen_sample_state.py` to regenerate `dev/sample-state.b64`. 5. Run `python dev/build_dashboard.py` to rebuild the artifact. |
| New CLI flag or solver behaviour added | Add tests to `dev/test_cli.py` covering the new feature. Run `python -m unittest dev.test_cli -v` and fix any failures before finishing. Update the test count in `README.md` and in the Tests section of `CLAUDE.md`. |
| Any `.py` file is created or edited | Run `get_errors` on the file afterwards and fix all Pylance errors before finishing. Prefer `assert x is not None` over `assertIsNotNone(x)` when the result is used afterward — Pylance uses the former as a type-narrowing guard but not the latter. |
| Before making a commit | Review `README.md` and update it to reflect any changes made (test counts, new features, changed behaviour, etc.). |
| Before spawning a subagent to implement CLI or dashboard changes | Include in the subagent prompt: (1) an instruction to read and follow all maintenance rules in `CLAUDE.md` before finishing, and (2) an explicit end-of-task checklist derived from those rules — e.g. "grep SKILL.md for every new JSON field added to cli.py output and confirm each appears in both the example block and the field table in §2". Subagents do not automatically load `CLAUDE.md`. |
| Every 30 days | Run the wiki maintenance workflow (see below) to update the split reference files in `10x-factorio-engineer/references/`. The MediaWiki RecentChanges API only goes back 30 days — running less frequently means changes fall out of the window undetected. |

The goal is that `claude.md` always accurately describes the codebase.

---

## Strategy Reference Maintenance (Every 30 Days)

The split reference files in `10x-factorio-engineer/references/` embed facts crawled from the
Factorio wiki, and `dev/wiki/` holds the full per-page corpus (417 pages, gitignored).
The wiki is actively updated — run this workflow monthly to pick up changes.

### Workflow

**Step 1 — Fetch recently changed pages via MediaWiki API:**
```
https://wiki.factorio.com/api.php?action=query&list=recentchanges&rcnamespace=0&rclimit=500&rcdays=30&rctype=edit|new&format=json
```
This returns all English main-namespace pages edited in the last 30 days. Filter out
translations (`/zh`, `/ru`, `/de`, etc.) and non-article pages (`Special:`, `File:`, etc.).

**Step 2 — Cross-reference against our crawled page list:**
Our 417-page list is in `dev/wiki_crawl_urls.json`. Check which recently-changed wiki pages
appear in that list — those are the ones to re-crawl.

Also check which split reference files embed facts from those changed pages — if any of those changed,
update the embedded summaries too (Step 4).

**Step 3 — Re-crawl changed pages using `dev/wiki.py`:**
```bash
python dev/wiki.py update [--days 30] [--dry-run]
```
This automates Steps 1–3: queries RecentChanges, cross-references against
`wiki_crawl_urls.json`, deletes stale files, and re-crawls via Cloudflare.
Credentials come from env vars `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`.

> **Note:** Do NOT use Cloudflare's `modifiedSince` parameter for this — tested and confirmed
> that the Factorio wiki does not serve `Last-Modified` headers that Cloudflare can use.
> All pages are returned as "completed" regardless of whether they changed. Use the
> MediaWiki RecentChanges API (Step 1) to determine what actually changed.

**Step 4 — Update the relevant split reference file(s) for changed embedded pages:**
Compare newly crawled content against what's embedded in the split reference files in `10x-factorio-engineer/references/`.
Update any facts that changed. Focus on **mechanics, strategic constraints, and planning guidance** — not raw stats or recipe ingredients (the CLI provides those on demand). Prioritise: spoilage timers, planet-specific constraints, combat mechanics, circuit patterns, and infrastructure ratios (solar/nuclear/fusion) that the CLI doesn't model.

**Step 5 — Also check for new high-value pages:**
Filter the full RecentChanges list for pages not yet in `wiki_crawl_urls.json` but relevant
to players (new buildings, mechanics, Space Age content). Add them to `wiki_crawl_urls.json`
and run `python dev/wiki.py crawl` to fetch them.

### Notes
- The 30-day window is a hard limit of the MediaWiki API — do not skip months
- `render: false` crawls won't follow links between unrelated pages — crawl each target URL directly
- `findings.md` in the repo root tracks crawl history
- Cloudflare paid plan: no daily job limit, 600 req/min REST API; use 30 workers
- `dev/wiki/` is gitignored — regenerate with `python dev/wiki.py crawl` (~15 min)

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `10x-factorio-engineer/assets/cli.py` | Calculator — entire implementation, stdlib only |
| `10x-factorio-engineer/assets/vanilla-2.0.55.json` | KirkMcDonald dataset — base game |
| `10x-factorio-engineer/assets/space-age-2.0.55.json` | KirkMcDonald dataset — Space Age DLC |
| `10x-factorio-engineer/SKILL.md` | Skill definition — Claude gameplay assistant behaviour |
| `10x-factorio-engineer/references/` | Split strategy reference files (11 topic files): early-game, factory-layouts, trains, megabase, planets, space-platforms, power, combat-defense, logistics-circuits, quality, resources |
| `dev/dashboard.html` | Dashboard source — single vanilla HTML file, no build dependencies |
| `dev/build_dashboard.py` | Build script — minifies `dev/dashboard.html` → `10x-factorio-engineer/assets/dashboard.html` |
| `dev/preview.py` | Opens `dev/dashboard.html` in browser with `dev/sample-state.b64` pre-loaded into localStorage; writes `dev/preview.tmp.html` |
| `10x-factorio-engineer/assets/dashboard.html` | Built artifact — run `python dev/build_dashboard.py` to regenerate; paste into claude.ai as `application/vnd.ant.html` and publish |
| `dev/sample-state.b64` | Sample factory state base64-encoded — paste into the Import dialog to test |
| `dev/sample-state.json` | Source JSON for the sample state — edit this, then run `python dev/gen_sample_state.py` to rebuild `sample-state.b64` |
| `dev/gen_sample_state.py` | Encodes `dev/sample-state.json` → `dev/sample-state.b64` (minified JSON → UTF-8 → base64) |
| `dev/wiki_crawl_urls.json` | Curated list of 417 English gameplay wiki page titles to crawl |
| `dev/wiki.py` | Two subcommands: `crawl` (full crawl, resume-safe) and `update` (monthly maintenance via RecentChanges API); 30 workers, 9 req/sec rate limiter |
| `dev/wiki/` | Per-page wiki corpus (417 `.md` files); **gitignored** — regenerate with `python dev/wiki.py crawl` (~15 min) |
| `dev/test_cli.py` | `unittest` suite (148 tests, stdlib only) — dev only |
| `dev/artifact-api-test.html` | claude.ai runtime API test suite — paste as `application/vnd.ant.html` to verify `window.claude` / `window.storage` / localStorage after platform updates |
| `dev/artifact-api.md` | Field research doc for the claude.ai artifact runtime API; compare against test suite output to diagnose breakage |

Dataset files are vendored. Auto-downloaded from KirkMcDonald's GitHub if missing.

---

## Architecture

CLI flags and JSON output shape: see `10x-factorio-engineer/SKILL.md` §2.

### Key functions

| Function | Role |
|----------|------|
| `load_data(dataset)` | Load JSON; auto-download if missing |
| `build_raw_set(data)` | Items with no recipe (ores, crude-oil, water, etc.) |
| `build_recipe_index(data)` | `{item_key: [recipe, ...]}`, skips recycling + barrel subgroups |
| `build_resource_info(data)` | `{item: {mining_time, yield, category}}` using `Fraction` |
| `build_machine_power_w(data)` | `{machine_key: watts}` for electric machines only (burners excluded); scans `crafting_machines`, `agricultural_tower`, `rocket_silo`, `mining_drills` |
| `_beacon_sharing_factor(machine_key)` | Returns how many machines share each physical beacon (4 for ≤4-tile machines, 2 for 5–7-tile, 1 for ≥8-tile) |
| `_compute_step_power(...)` | Returns `(power_kw, power_kw_ceil, beacon_power_kw)` for a production step using module/beacon config |
| `get_machine(cat, assembler_level, furnace_type)` | Maps recipe category → `(machine_key, speed)` |
| `pick_recipe(item_key, recipe_idx, overrides)` | Picks canonical recipe (see selection logic below) |
| `_gauss2 / _gauss3` | Exact `Fraction` Gaussian elimination (2×2 and 3×3) |
| `solve_oil_system(...)` | Joint linear solve for refinery recipe (AOP / CL / simple-CL) + cracking |
| `Solver.solve(item_key, rate)` | Recursive tree walk; defers oil products |
| `Solver.resolve_oil(data)` | Injects oil linear-system results into steps/raw_resources |
| `compute_miners(...)` | Per-resource miner/pump counts |
| `format_output(...)` | Assembles final JSON dict |

### `Solver` class state

- `steps`: `{recipe_key: {recipe, machine, machine_count, rate_per_min, beacon_speed_bonus}}` — accumulated across all tree paths; `machine_count` is `float` when beacons active, `Fraction` otherwise
- `raw_resources`: `{item: Fraction}` — total demanded rate for true raws (ores, crude-oil, water); excludes bus items
- `bus_inputs`: `{item: Fraction}` — demanded rate for items sourced from the bus (`--bus-item`); separate from `raw_resources`
- `surplus`: `{item: Fraction}` — co-product credits not yet consumed
- `oil_demands`: `{item: Fraction}` — deferred petroleum-gas/light-oil/heavy-oil demands
- `module_configs`: `{machine_key: [ModuleSpec]}` — global module config per machine (`--modules`)
- `beacon_configs`: `{machine_key: BeaconSpec}` — global beacon config per machine (`--beacon`)
- `recipe_machine_overrides`: `{recipe_key: machine_key}` — per-recipe machine override (`--recipe-machine`)
- `recipe_module_overrides`: `{recipe_key: [ModuleSpec]}` — per-recipe module override (`--recipe-modules`)
- `recipe_beacon_overrides`: `{recipe_key: BeaconSpec}` — per-recipe beacon override (`--recipe-beacon`)
- `bus_items`: `frozenset[str]` — item IDs treated as bus inputs; stops recursion (`--bus-item`)
- `machine_quality`: `str` — quality tier applied to all machines (speed bonus via `MACHINE_QUALITY_SPEED`)
- `beacon_quality`: `str` — quality tier of beacon housings (effectivity via `BEACON_EFFECTIVITY`)

**`ModuleSpec`** (named tuple or dict): `{count: int, type: str, tier: int, quality: str}`
**`BeaconSpec`** (named tuple or dict): `{count: int, tier: int, quality: str}`

---

## Arithmetic

All numeric values use `fractions.Fraction` internally. Only converted to `float` in `format_output()`. This eliminates floating-point accumulation errors.

**Exception:** beacon speed bonus uses `math.sqrt(count)` which is irrational, so `machine_count` becomes `float` for any recipe whose machine has a beacon config. Runs with no beacons remain fully `Fraction`.

### New constant tables

```python
# Quality enum (valid values for all quality flags)
QUALITY_NAMES = frozenset(["normal", "uncommon", "rare", "epic", "legendary"])

# Multiplier applied to positive module stats at each quality tier
MODULE_QUALITY_MULT: dict[str, Fraction] = {
    "normal":    Fraction(1),
    "uncommon":  Fraction(13, 10),   # ×1.3
    "rare":      Fraction(8,  5),    # ×1.6
    "epic":      Fraction(19, 10),   # ×1.9
    "legendary": Fraction(5,  2),    # ×2.5
}

# Additive crafting-speed bonus from machine quality
MACHINE_QUALITY_SPEED: dict[str, Fraction] = {
    "normal":    Fraction(0),
    "uncommon":  Fraction(3, 10),    # +30%
    "rare":      Fraction(3, 5),     # +60%
    "epic":      Fraction(9, 10),    # +90%
    "legendary": Fraction(3, 2),     # +150%
}

# Beacon distribution effectivity by beacon housing quality
# Range 1.5–2.5; verified against FactorioLab
BEACON_EFFECTIVITY: dict[str, Fraction] = {
    "normal":    Fraction(3,  2),    # 1.5
    "uncommon":  Fraction(17, 10),   # 1.7
    "rare":      Fraction(19, 10),   # 1.9
    "epic":      Fraction(21, 10),   # 2.1
    "legendary": Fraction(5,  2),    # 2.5
}

# Base speed bonus per speed-module tier at normal quality
SPEED_MODULE_BONUS: dict[int, Fraction] = {
    1: Fraction(1, 5),    # +20%
    2: Fraction(3, 10),   # +30%
    3: Fraction(1, 2),    # +50%
}

# Base productivity bonus per prod-module tier at normal quality (same as MODULE_PROD_BONUS)
# combined with MODULE_QUALITY_MULT for effective bonus

BEACON_SLOTS = 2   # standard beacon has 2 module slots; supply range = 3 tiles (quality-invariant)

# Pump throughput by pump quality (fluid/min per pump)
PUMP_THROUGHPUT: dict[str, int] = {
    "normal":    72_000,
    "uncommon":  93_600,
    "rare":      115_200,
    "epic":      136_800,
    "legendary": 180_000,
}
```

### Beacon speed formula

```
beacon_speed(recipe) =
    BEACON_EFFECTIVITY[beacon_quality]
    × sqrt(count)
    × BEACON_SLOTS
    × SPEED_MODULE_BONUS[tier] × MODULE_QUALITY_MULT[module_quality]
```

Effective machine speed:
```
effective_speed = base_speed
                × (1 + MACHINE_QUALITY_SPEED[machine_quality])
                × (1 + beacon_speed(recipe))
```

Effective prod bonus (from machine modules):
```
prod_bonus = sum(
    count_i × MODULE_PROD_BONUS[tier_i] × MODULE_QUALITY_MULT[quality_i]
    for each prod module spec in this recipe's module config
)
```

Recipe module config lookup order (first match wins):
1. `recipe_module_overrides[recipe_key]` — per-recipe override (`--recipe-modules`)
2. `module_configs[machine_key]` — global per-machine default (`--modules`)
3. No modules (zero bonus)

Same lookup order applies to beacon config (`recipe_beacon_overrides` → `beacon_configs` → no beacons).

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
- `electronics*`, `electronics-or-assembling`, `electronics-with-fluid` → electromagnetic-plant (speed 2)
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

`dev/test_cli.py` contains 148 tests covering:

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
| `TestModuleConfig` | `--modules MACHINE=...` reduces machine count (prod); speed modules reduce count; mixed prod+speed; zero-slot machine ignores prod/speed; module quality multiplier scales bonus; per-recipe override via `--recipe-modules` |
| `TestFractionArithmetic` | All `raw_resources` and `machine_count` values remain `Fraction` in beacon-free runs |
| `TestCoalLiquefaction` | `coal-liquefaction` via `--recipe heavy-oil=coal-liquefaction`; net heavy-oil math (65/cycle); coal+steam in raw; AOP not used; cracking engaged for petgas demand |
| `TestSimpleCoalLiquefaction` | `simple-coal-liquefaction` (Space Age); coal+calcite+sulfuric-acid in raw; no crude-oil; cracking for petgas |
| `TestGlebaMachineRouting` | `organic` → biochamber (no assembler); `pressing` → agricultural-tower (count=1/4 for transport-belt); `captive-spawner-process` → captive-spawner with zero inputs |
| `TestNutrientsRecipes` | Default picks `nutrients-from-yumako-mash` via `RECIPE_DEFAULTS` (not fish); no circular dependency; fish route still available via `--recipe` override; bioflux override full biochamber chain |
| `TestBeaconConfig` | `--beacon MACHINE=COUNT:TIER:QUALITY` computes speed via sqrt formula; `beacon_speed_bonus` in step output; `machine_count` becomes float; beacon quality effectivity (1.5/1.7/1.9/2.1/2.5); per-recipe override via `--recipe-beacon` |
| `TestMachineQuality` | `--machine-quality` applies `MACHINE_QUALITY_SPEED` bonus; legendary assembler-3 faster than normal; reduces machine count |
| `TestMachineOverride` | `--recipe-machine RECIPE=MACHINE` per-recipe redirect; unknown machine falls through; surfaces in JSON output; independence from category override |
| `TestBusItem` | `--bus-item` stops recursion at item; demand goes to `bus_inputs` (not `raw_resources`); rates correct; `bus_inputs` dict in JSON output; absent when unused; `miners_needed` empty for bus-only lines |
| `TestMachinesFlag` | `rate_for_machines` round-trips integer/fractional machine counts; Fraction return type without beacons; prod-module and beacon round-trips; raises on raw resource; assembler level respected |
| `TestPowerConsumption` | Electric machines have `power_kw > 0`; burner machines give 0; efficiency modules reduce power (quality-scaled); speed/prod penalty not quality-scaled; efficiency floor at −80%; beacon sharing (3×3 = ÷4, 5×5 = ÷2); `total_power_mw` in output; miner `power_kw` present; miner efficiency reduces power (quality-scaled, −80% floor); miner `beacon_power_kw` emitted and included in `total_power_mw` |
| `TestProbabilisticOutputs` | `uranium-processing` U-238 output reflects 0.993 probability; U-235 reflects 0.007 probability; `rate_for_machines` returns correct probability-weighted rates for both isotopes; ratio U-235/U-238 machine count ≈ 141× |
| `TestMultiTarget` | Two-item solve merges shared sub-recipes; `targets` array replaces top-level `item`/`rate_per_min`; raw_resources and bus_inputs accumulate across all targets; belt/pump fields absent in multi-target output |
| `TestStepInputs` | `inputs` dict present on every production step; ingredient consumption rates correct; reduced by productivity modules; bus items appear in step inputs; oil steps have crude-oil input; multi-target inputs accumulate |
| `TestStepConfig` | `machine_quality` always present per step; `module_specs` present only when modules configured (global or per-recipe override); `beacon_spec`+`beacon_quality` present only when beacon configured; per-recipe override wins over global |
| `TestHumanReadableOutput` | `format_human_readable()` returns non-JSON text; header contains item+rate; sections present (Production Steps, Raw Resources, Miners Needed, Power); machine names in steps; module/beacon config in header and detail lines; machine quality in step label; pumpjack shows yield%; bus inputs section when bus items present |

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

1. **No quality recycling loops**: Quality tier progression (e.g. recycling normal→legendary) is not modelled. Machine/module/beacon quality multipliers are applied directly but the throughput cost of quality recycling lines is out of scope.


---

## Dependencies

Stdlib only — no `pip install` required: `argparse`, `json`, `math`, `os`, `sys`, `urllib.request`, `collections`, `fractions`.

---

## Component 2: Claude Skill

### Purpose

`10x-factorio-engineer/SKILL.md` is a system-prompt document that turns Claude into an active
Factorio gameplay assistant. It defines three responsibilities:

1. **Precise calculations** — always call `python 10x-factorio-engineer/assets/cli.py`, never compute
   production chains mentally.
2. **Conversational factory tracking** — parse freeform player updates ("just
   placed 12 electric furnaces on copper"), maintain a structured factory-state
   JSON in context, detect bottlenecks, and suggest next steps.
3. **Strategy guidance** — load the relevant file from `10x-factorio-engineer/references/` on demand
   (see SKILL.md §10 routing table) to answer questions about layouts, trains, megabases,
   Space Age planets, power, combat, and more.

### Factory State JSON Schema

See `10x-factorio-engineer/SKILL.md` §3 for the canonical factory-state schema Claude tracks in every gameplay session.

### Dashboard (`dev/dashboard.html` → `10x-factorio-engineer/assets/dashboard.html`)

A single self-contained vanilla HTML file — no React, no build toolchain, no
external dependencies beyond the browser. State is encoded as base64 (minified
JSON → UTF-8 bytes → `btoa`) for compact storage and portability.

**Build:** `python dev/build_dashboard.py` — strips HTML comments and blank
lines, writes `10x-factorio-engineer/assets/dashboard.html`. Use `--open` to open
the result in a browser immediately.

**Header:** compact one-line brand label (`10x Factorio Engineer`) left +
config pills right (`[Space Age]` when applicable, `[Assembler 3]`,
`[Electric Furnace]`, `[Productivity N]`). Save name is a subtle subtitle.

**Features:** see `10x-factorio-engineer/SKILL.md` §5 for section-by-section description.

**Import/Export:** Export produces a base64 string (copy button). Import
accepts base64 or plain JSON (backward-compatible). Storage uses the same
encoding in both `window.storage` and `localStorage`.

**ID humanisation:** `humanizeText()` converts kebab-case IDs to friendly
names everywhere — machine column, miners section, bottleneck/next-step text.
Known machines use a handcrafted map (`assembling-machine-3` → `Assembler 3`);
everything else falls back to title-cased label conversion.
