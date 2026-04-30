# Quality Planner

A separate stdlib-only Python tool that answers:

> *"Given my research and module tier, what's the cheapest way to make N legendary `<item>` per minute?"*

Lives at `dev/quality_planner.py` (~2600 LoC) alongside `10x-factorio-engineer/assets/cli.py`. Imports `cli.py` as a library; does not modify it.

This document is the single source of truth — supersedes the original `quality_planner_v1.md` and `quality_planner_v2.md` specs (deleted). The history of how features evolved is in git; this doc only covers what exists today and what's planned.

---

## Status

**Last updated:** 2026-04-30. Tests: `python -m unittest dev.test_quality_planner -v` — **142 tests, all passing, ~0.07 s.**

Currently shipped:
- DP kernels for four loop types (asteroid reprocessing, mined-raw self-recycle, cross-item shuffle, self-recycle target)
- Multi-planet support (`--planets`)
- Per-stage assembly module optimization (`--assembly-modules`)
- Machine-quality plumbing (`--machine-quality`)
- LDS cross-item shuffle (`--enable-lds-shuffle`)
- Self-recycle targets (superconductor, holmium-plate, tungsten-carbide, fusion-power-cell, lithium)
- Gleba bio-raws (yumako, jellynut, pentapod-egg) — **no spoilage timing**
- Per-stage power accounting (`total_power_mw`)
- `--no-asteroids` early-game gating
- Stage cost summary (`summary.by_role`) + hot-spot advisor notes

Future additions in the [Roadmap](#roadmap) section below.

---

## Quick start

```bash
# Default — Nauvis-only, asteroid-reprocessing path, modules off
python dev/quality_planner.py --item iron-plate --rate 60

# Recommended for serious planning (all flags on)
python dev/quality_planner.py --item processing-unit --rate 60 \
    --planets nauvis --assembly-modules --machine-quality legendary

# Multi-planet chain
python dev/quality_planner.py --item artillery-shell --rate 60 \
    --planets nauvis,vulcanus --assembly-modules

# Self-recycle target
python dev/quality_planner.py --item superconductor --rate 60 \
    --planets nauvis,fulgora

# Plastic-heavy chain via cross-item shuffle
python dev/quality_planner.py --item processing-unit --rate 60 \
    --planets nauvis --assembly-modules --enable-lds-shuffle

# Early game (no space platform)
python dev/quality_planner.py --item iron-plate --rate 60 \
    --planets nauvis,vulcanus --no-asteroids
```

---

## Regression anchors

Sanity numbers (60/min legendary, `--module-quality legendary`, no research, modules-off):

| target | planets | total machines | asteroid chunks/min | mined/min | fluid/min |
|---|---|---|---|---|---|
| `iron-plate` | — | 18.3 | metallic 281, oxide 28 | — | — |
| `processing-unit` | nauvis | 620.2 | metallic 1406, carbonic 703, oxide 59 | coal 321 874 | crude-oil 5 333 |
| `artillery-shell` | nauvis,vulcanus | ~5 000 | carbonic 5 625, oxide 1 842 | coal 643 749, tungsten-ore 2.5M | lava 9 300 |

With `--assembly-modules --machine-quality legendary`, `processing-unit @ nauvis` drops from 620 machines to **~12.6 machines** (50× drop) — modules off is the conservative baseline.

These are sanity checks, not committed expectations. If a refactor moves them, investigate the cause rather than rubber-stamping.

---

## CLI surface

```
python dev/quality_planner.py --item <id> --rate <N> [flags]
```

| Flag | Default | Description |
|---|---|---|
| `--item ID` | required | Target item (one only) |
| `--rate N` | required | Legendary items per minute |
| `--planets P1,P2,…` | empty | Unlocked planets. Empty = asteroid-only. Choices: `nauvis,vulcanus,fulgora,gleba,aquilo,space-platform` |
| `--module-quality Q` | `legendary` | Quality of quality-modules in loops. Choices: `normal,uncommon,rare,epic,legendary` |
| `--quality-module-tier {1,2,3}` | `3` | Tier of quality modules |
| `--assembler-level {2,3}` | `3` | Assembler tier for non-categorised recipes |
| `--machine-quality Q` | `normal` | Quality of every assembly / crusher / recycler machine. Applies `cli.MACHINE_QUALITY_SPEED` (+0/+30/+60/+90/+150 %) |
| `--assembly-modules` | off | Fill assembly slots with prod modules at `--module-quality` and `--prod-module-tier`. Inherent +50 % prod (foundry/EM-plant/biochamber) is always applied |
| `--prod-module-tier {1,2,3}` | `3` | Tier of prod modules used by `--assembly-modules` |
| `--research NAME=LEVEL` | empty | Repeatable. Productivity research per recipe family (e.g. `--research asteroid-productivity=5`) |
| `--enable-lds-shuffle` | off | Replace plastic-bar leg with LDS cross-item shuffle |
| `--no-asteroids` | off | Skip asteroid path; route iron-ore/copper-ore/ice/calcite via planet self-recycle |
| `--format {human,json}` | `human` | Output format |

---

## Output schema

```jsonc
{
  "target": {"item": "processing-unit", "rate_per_min": 60, "tier": "legendary"},

  // Quality-bearing inputs
  "asteroid_input":     {"metallic-asteroid-chunk": 1406, ...},
  "mined_input":        {"coal": 321874.5},
  "fluid_input":        {"crude-oil": 5333.3, "water": "fluid-transparent"},

  // Normal-quality inputs (LDS shuffle leg, self-recycle target ingredients)
  "normal_solid_input": {"plastic-bar": 540.0},
  "normal_fluid_input": {"petroleum-gas": 1080.0},

  // LDS shuffle byproducts
  "shuffle_byproduct_legendary": {"copper-plate": 240, "steel-plate": 24},
  "shuffle_byproduct_credited":  {"copper-plate": 240},  // capped at observed demand
  "shuffle_byproduct_overflow":  {"steel-plate": 24},    // surplus

  "stages": [/* see roles below */],

  "total_machine_count": 31.52,
  "total_power_mw":      17.71,

  "summary": {
    "by_role": {
      "mined-raw-self-recycle": {
        "machines": 19.7, "machines_pct": 62.5,
        "power_kw": 3548, "power_pct": 20.0,
        "stage_count": 1
      },
      // ...
    }
  },

  "module_quality":   "legendary",
  "assembler_level":  3,
  "research_levels":  {},
  "planets":          ["nauvis"],
  "notes":            ["hot spot: ...", "stage X uses fluid-transparent input ..."]
}
```

### Stage roles

| Role | Emitted by | Machine | Notes |
|---|---|---|---|
| `assembly` | walker | per recipe | Standard craft step. Has `inputs`, `fluid_inputs`, `solid_inputs`, `module_prod`, `prod_modules`, `machine_quality`, `prod_capped` |
| `asteroid-reprocessing` | plan() | crusher | Quality loop on asteroid chunks (80 % retention, 2 slots) |
| `raw-crushing` | plan() | crusher | Legendary chunk → legendary ore (advanced crushing, 2 outputs per recipe) |
| `mined-raw-self-recycle` | plan() | recycler | Quality loop on planet-mined raws (25 % retention, 4 slots, no prod). Covers coal, stone, tungsten-ore, scrap, holmium-ore, uranium-ore, yumako, jellynut, pentapod-egg, and (with `--no-asteroids`) iron-ore/copper-ore/ice/calcite |
| `cross-item-shuffle` | plan() | foundry+recycler | LDS cast + recycle. Splits machine count between `foundry_machines` and `recycler_machines`. Has `byproduct_legendary`, `byproduct_credited`, `byproduct_overflow`, `fluid_demand` |
| `self-recycle-target` | `_plan_self_recycle_target` | craft+recycler | Recycler-only loop where the target's recycle returns itself. Splits `craft_machines` and `recycler_machines` |

---

## Architecture

```
┌────────────────────────────────────────────────────┐
│ CLI entry (parse_args, main)                       │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ plan() — top-level orchestrator                    │
│  - dispatches to _plan_self_recycle_target if      │
│    target ∈ SELF_RECYCLE_TARGETS                   │
│  - calls walk_recipe_tree to build the stage DAG   │
│  - optionally re-walks with byproduct credits      │
│    (LDS shuffle wiring)                            │
│  - attaches asteroid / mined-recycle / shuffle     │
│    stages for each leaf raw                        │
│  - aggregates power + summary.by_role              │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ DP kernels                                         │
│  solve_asteroid_reprocessing_loop                  │
│  solve_mined_raw_self_recycle_loop                 │
│  solve_lds_shuffle_loop / compute_lds_shuffle_stage│
│  solve_self_recycle_target_loop                    │
│  solve_recycle_loop (shuffle-style; library only)  │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ walker (walk_recipe_tree)                          │
│  - two passes: demand accumulation + stage build   │
│  - fluid-transparent recipe selection              │
│  - planet filtering via _combined_planet_props     │
│  - byproduct_credits propagation                   │
│  - _assembly_prod_bonus called consistently in     │
│    both passes so demand lines up                  │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ Recipe / data layer (cli.py reused)                │
│  build_recipe_index, build_raw_set,                │
│  build_machine_module_slots, build_machine_power_w │
└────────────────────────────────────────────────────┘
```

Stdlib only. Zero new deps. Shares the Space Age dataset with `cli.py`.

### Code map (function → role)

| Function | Role |
|---|---|
| `_quality_chance` | Per-slot quality chance (2.5 % × tier × quality multiplier) |
| `_tier_skip_probs` | 90/9/0.9/0.1 tier-jump distribution |
| `_prod_bonus` | Module-prod fraction at given tier+quality |
| `solve_recycle_loop` | Shuffle-style DP (recycler returns ingredient → re-craft). Library only |
| `solve_asteroid_reprocessing_loop` | 80 % retention, 2 slots, prod allowed |
| `solve_lds_shuffle_loop` | LDS foundry-cast + recycle joint DP, returns per-plastic legendary yield |
| `compute_lds_shuffle_stage` | Sizes a LDS shuffle stage from `legendary_plastic_per_min`; returns `foundry_machines`, `recycler_machines`, `byproduct_legendary`, `fluid_demand` |
| `solve_mined_raw_self_recycle_loop` | 25 % retention, 4 slots, quality-only (no prod) |
| `solve_self_recycle_target_loop` | Recycler-only DP: items at tier t enter recycler chain, tier up or vanish via 25 % retention |
| `_assembly_prod_bonus` | (machine, recipe, slots, flag, quality, tier) → (prod_fraction, slots_filled). Includes inherent prod for foundry/EM/biochamber |
| `_stage_power_kw` | Dispatches per role; compound stages split power between machine types |
| `_hot_spot_suggestions` | Inspects `summary.by_role`, emits actionable notes when one role > 50 % of machines |
| `_pick_recipe_fluid_preferred` | Recipe selection: prefer recipes with most fluid ingredients (foundry casting > furnace) |
| `walk_recipe_tree` | Two-pass walker. Builds stage list + raw_demand dict. Accepts `extra_raws`, `byproduct_credits`, `assembly_modules`, `machine_quality`, `no_asteroids` |
| `_plan_self_recycle_target` | Dedicated path for self-recycle-target items |
| `plan` | Top-level orchestrator |
| `format_human` | Terminal-friendly rendering |

---

## Algorithms

### Quality DP — common shape

All four loops follow a backward-induction DP over quality tiers (normal=0, uncommon=1, rare=2, epic=3, legendary=4):

- Tier-skip distribution is game-fixed: 90 % +1, 9 % +2, 0.9 % +3, 0.1 % +4. Caps at legendary.
- Per-tier quality chance: `q_total = 2.5 % × num_q_slots × tier × MODULE_QUALITY_MULT[quality]`. Capped at 100 %.
- Per-tier module config (count of prod vs quality slots) is chosen by the DP; it can differ per tier.
- Productivity cap: `eff_prod = min(4.0, 1 + research_prod + module_prod + inherent_prod)`. Per-tier.

The four kernels differ only in retention, slot count, and whether prod modules are allowed:

| Kernel | Retention | Slots | Prod allowed | Inherent prod |
|---|---|---|---|---|
| `solve_asteroid_reprocessing_loop` | 0.80 | 2 (crusher) | yes | 0 |
| `solve_mined_raw_self_recycle_loop` | 0.25 | 4 (recycler) | no | 0 |
| `solve_self_recycle_target_loop` (recycle leg) | 0.25 | 4 (recycler) | no | 0 |
| `solve_self_recycle_target_loop` (craft leg) | n/a | varies | varies | foundry/EM/biochamber +50 % |
| `solve_lds_shuffle_loop` (foundry leg) | n/a | 4 | yes | 0.5 |
| `solve_lds_shuffle_loop` (recycle leg) | 0.25 | 4 | no | 0 |
| `solve_recycle_loop` (shuffle-style — library only) | 0.25 | 4 | depends | depends |

### Recipe-tree walker

Two passes:

1. **Demand accumulation.** Walk the tree from the target item; at each node compute `eff_prod` and add `(amount × cycles_per_min)` to each ingredient's demand.
2. **Stage construction.** Iterate items in order, build assembly stages with the same `eff_prod` (consistency is critical — if the two passes disagree, ingredient demand and stage `inputs` diverge).

Recipe selection (`_pick_recipe_fluid_preferred`):
- Prefer recipes with more fluid ingredients (e.g. `casting-iron` over `iron-plate`). Reduces the legendary-required solid surface to ingredients only.
- Filter by combined planet `surface_conditions` (max-per-property union over unlocked planets).
- Skip self-recycling recipes (output recycles to itself).

Raw set:
- Always: asteroid chunks + chunk-derived raws (`RAW_TO_CHUNK`) + water.
- With `--planets`: union in each unlocked planet's fluids + mined solids from `MINED_RAW_PLANETS`.
- With `--no-asteroids`: substitute `MINED_RAW_NO_ASTEROID_FALLBACK` (iron-ore, copper-ore, ice, calcite per planet) for the asteroid raws.

Routing per leaf raw:
- Fluid → `fluid_input` (quality-transparent).
- Asteroid chunk → asteroid-reprocessing path (skipped under `--no-asteroids`).
- Mined raw with planet unlocked → `mined-raw-self-recycle`.
- Otherwise → fail-fast with actionable `add --planets X` hint.

### LDS shuffle wiring

When `--enable-lds-shuffle` and `plastic-bar` is in the chain:

1. Compute legendary-plastic demand from the initial walker pass.
2. `compute_lds_shuffle_stage` returns `normal_plastic_in_per_min`, `foundry_machines`, `recycler_machines`, `byproduct_legendary`, `fluid_demand`.
3. Re-walk with `extra_raws={'plastic-bar'}` so the chain treats plastic as supplied externally.
4. Cap `byproduct_legendary` at observed demand → `capped_credits`. Surplus → `shuffle_byproduct_overflow` + a note.
5. If any credit > 0, re-walk a third time with `byproduct_credits=capped_credits` so demand for credited items propagates correctly through the chain.
6. Walk the normal-quality plastic-bar leg separately at `normal_plastic_in_per_min`; route its raws into `normal_solid_input` / `normal_fluid_input`.

### Self-recycle target

When the target is in `SELF_RECYCLE_TARGETS` (`tungsten-carbide`, `superconductor`, `holmium-plate`, `fusion-power-cell`, `lithium`):

1. `solve_self_recycle_target_loop` runs:
   - Outer search: enumerate `(craft_prod, craft_quality, recycle_quality)` configs.
   - One craft produces `items_per_craft = output × (1 + prod)` items distributed across tiers by `q_craft`.
   - Inner DP `V_rec[t]`: per-item legendary yield from a single tier-t item entering a recycler-only chain (converges because retention < 1).
   - Total = `items_per_craft × Σ craft_probs[s] × V_rec[s]`.
2. Ingredients consumed at NORMAL quality (quality rolls happen inside the loop) → `normal_solid_input` / `normal_fluid_input`. Walked through `walk_recipe_tree` as normal-quality production trees.

These items still fail-fast when used as INTERMEDIATE ingredients in another chain — they must be the target, or supplied externally.

### Hot-spot advisor

After computing `summary.by_role`, `_hot_spot_suggestions` emits a note when any role exceeds 50 % of total machines. Maps role → suggestion:

| Dominant role | Condition | Suggestion |
|---|---|---|
| `asteroid-reprocessing` | plastic in chain, shuffle off | `--enable-lds-shuffle` |
| `asteroid-reprocessing` | quality < legendary T3 | upgrade `--module-quality` / `--quality-module-tier` |
| `asteroid-reprocessing` | already at max, no plastic | (no suggestion — nothing actionable) |
| `mined-raw-self-recycle` | plastic in chain | `--enable-lds-shuffle` |
| `mined-raw-self-recycle` | vulcanus locked | `--planets vulcanus` (lava casting) |
| `assembly` | `--assembly-modules` off | `--assembly-modules` |
| `assembly` | modules on, machine-quality < legendary | `--machine-quality legendary` |

---

## Data tables (selected)

```python
KNOWN_PLANETS = ("nauvis", "vulcanus", "fulgora", "gleba", "aquilo", "space-platform")

# Asteroid chunk → reprocessing recipe (used in DP loop)
ASTEROID_REPROCESSING_RECIPES = {
    "metallic-asteroid-chunk":  "metallic-asteroid-reprocessing",
    "carbonic-asteroid-chunk":  "carbonic-asteroid-reprocessing",
    "oxide-asteroid-chunk":     "oxide-asteroid-reprocessing",
}

# Asteroid chunk → advanced crushing (2 outputs per recipe)
ASTEROID_CRUSHING_RECIPES = {
    "metallic-asteroid-chunk":  "advanced-metallic-asteroid-crushing",
    "carbonic-asteroid-chunk":  "advanced-carbonic-asteroid-crushing",
    "oxide-asteroid-chunk":     "advanced-oxide-asteroid-crushing",
}

# Raws produced by crushing recipes (chunk-derivable)
RAW_TO_CHUNK = {
    "iron-ore": "metallic-asteroid-chunk", "copper-ore": "metallic-asteroid-chunk",
    "carbon": "carbonic-asteroid-chunk",   "sulfur":     "carbonic-asteroid-chunk",
    "ice": "oxide-asteroid-chunk",         "calcite":    "oxide-asteroid-chunk",
    "water": "oxide-asteroid-chunk",  # via ice-melting
}

# Solid raws mined on a planet, with self-recycle quality path
MINED_RAW_PLANETS = {
    "coal":          ("nauvis", "vulcanus"),
    "stone":         ("nauvis", "vulcanus", "gleba"),
    "tungsten-ore":  ("vulcanus",),
    "scrap":         ("fulgora",),         # retention = 0 (one-shot)
    "holmium-ore":   ("fulgora",),
    "uranium-ore":   ("nauvis",),
    "yumako":        ("gleba",),
    "jellynut":      ("gleba",),
    "pentapod-egg":  ("gleba",),
}

# --no-asteroids fallback: route asteroid-chain raws via planet self-recycle
MINED_RAW_NO_ASTEROID_FALLBACK = {
    "iron-ore":   ("nauvis",),
    "copper-ore": ("nauvis",),
    "ice":        ("aquilo",),
    "calcite":    ("vulcanus",),
}

# Items whose recipe self-recycles (target-only allowlist below)
SELF_RECYCLING_BLOCKLIST = frozenset(["tungsten-carbide", "superconductor", "holmium-plate"])

# Items that can be used as legendary targets via the dedicated solver
SELF_RECYCLE_TARGETS = frozenset([
    "tungsten-carbide", "superconductor", "holmium-plate",
    "fusion-power-cell", "lithium",
])

# Inherent prod by machine
MACHINE_INHERENT_PROD = {
    "foundry": 0.5, "electromagnetic-plant": 0.5, "biochamber": 0.5,
    # all others 0
}
```

---

## Tests

`dev/test_quality_planner.py` — **142 tests**, 11 classes.

| Class | Coverage |
|---|---|
| `TestDPKernel` (+ Yields) | `_quality_chance`, `_tier_skip_probs`, `_prod_bonus`; reproduces wiki yield numbers within ±5 % for iron-plate self-loop |
| `TestAsteroidReprocessing` | 80 % retention math; metallic/carbonic/oxide yields; chunk → ore conversion |
| `TestFluidTransparency` | Planner picks foundry casting over furnace where available |
| `TestAssemblyPropagation` | Legendary inputs → legendary output |
| `TestResearchProd` | Research bonus shifts per-tier prod; cap engages |
| `TestFailFast` | Self-recycling intermediates / unreachable raws produce specific errors |
| `TestEndToEnd` | Smoke targets (iron-plate, copper-plate, electronic-circuit) |
| `TestPlanetsFlag` | `--planets` widens reachable raws; unknown planet errors |
| `TestMinedRawSelfRecycle` | Mined-raw 25 % loop; positive yield for coal/stone/tungsten-ore/holmium-ore |
| `TestLDSShuffle` | Library-level LDS DP; research / cap / module-quality scaling |
| `TestOtherPlanetUnlocks` | Fulgora unlocks scrap/holmium-ore (electrolyte chain) |
| `TestLDSShuffleWiring` | `--enable-lds-shuffle` end-to-end; byproduct credit propagation; overflow notes |
| `TestSelfRecycleTarget` | superconductor/holmium-plate/tungsten-carbide as targets; ingredients in normal_solid_input |
| `TestAssemblyModules` | `--assembly-modules` cuts machines >5×; `_assembly_prod_bonus` helper edge cases |
| `TestGlebaPartial` | Gleba bio-targets (bioflux, plastic-bar→bioplastic, sulfur→biosulfur, lubricant→biolubricant). **Spoilage NOT modelled.** |
| `TestStagePower` | Every stage has `power_kw`; compound stages split correctly; biochamber reports 0 (burner) |
| `TestMachineQuality` | `--machine-quality` applies `MACHINE_QUALITY_SPEED` to assembly + crusher + recycler; legendary cuts machine count by 1/2.5 |
| `TestNoAsteroids` | `--no-asteroids` routes via `MINED_RAW_NO_ASTEROID_FALLBACK`; fail-fast names the missing planet |
| `TestStageSummary` | `summary.by_role` aggregates machines/power/stage_count per role; pcts sum to 100 |
| `TestHotSpotAdvisor` | Helper unit tests + end-to-end notes; suppresses suggestions when nothing actionable |
| `TestParseResearch`, `TestHelpers` | Argument parsing and helper functions |

Targeted bands not committed expectations — the wiki-yield tests use a 5 % tolerance because module/probability rounding accumulates differently from FactorioLab's reference numbers.

---

## Gotchas (institutional knowledge)

- **`RAW_TO_CHUNK` ≠ all raws.** It only contains items actually produced by crushing recipes. Mined-only raws (coal, stone, tungsten-ore, scrap, holmium-ore, uranium-ore, gleba bio-raws) live in `MINED_RAW_PLANETS`.
- **Use `advanced-*-asteroid-crushing` (2 outputs), not basic.** A V1 bug silently produced 0 copper-ore because `metallic-asteroid-crushing` only outputs iron-ore.
- **Self-recycling items as test targets:** many "obvious" V2 candidates are self-recycling and fail fast as intermediates. Use `electrolyte`, `low-density-structure`, `battery`, `artillery-shell`, `processing-unit`, `tungsten-plate` as test targets when `superconductor`/`holmium-plate`/`tungsten-carbide` are wrong (they only work as TARGETS via `_plan_self_recycle_target`).
- **Holmium-ore is not in `cli.build_raw_set("fulgora")`** — it's a scrap-recycling byproduct. The walker has a second pass that adds `MINED_RAW_PLANETS` entries when any of their planets is unlocked.
- **Fulgora `battery` test gotcha:** battery's only chemistry raw is sulfur (asteroid-reachable), so coal isn't needed. Use `electrolyte` to genuinely exercise holmium-ore.
- **Oil-recipe selection picks `basic-oil-processing`** because it has fewer fluid byproducts (`_pick_recipe_fluid_preferred` picks lowest-complexity).
- **`--prod-module-tier` defaults to 3.** No speed modules — speed doesn't reduce ingredient demand, and the planner sizes by throughput.
- **Walker passes must use the SAME `eff_prod`.** `_assembly_prod_bonus` is called identically in both passes — if they diverge, demand propagation upstream and stage `inputs` rates will not match.
- **LDS shuffle saturation:** when `research_prod` saturates the +300 % cap, per-cycle return ratio `r → 1.0` and machine count diverges. Clamped to `r=0.999` (~1500 machines for 60/min). Mathematically correct in the limit; practically a tell that the planner should split into multiple parallel loops with smaller per-tier prod configs (deferred — see [Roadmap](#roadmap)).
- **Argparse % escaping.** Help strings containing `%` must escape as `%%` — argparse format-substitutes them otherwise (`--assembly-modules` and `--machine-quality` flags both have `%%`).

---

## Roadmap

In rough priority order (fully shipped items removed):

### Generic shuffle enumeration (V3 item 1.x — ~300–400 LoC)

LDS-only path is shipped behind `--enable-lds-shuffle`. The remaining work is auto-enumeration of shuffle candidates beyond LDS:

- Detect any recipe R where R's recycling returns only solids (fluids are free) and all originally non-self ingredients can be quality-rolled through R. Pre-compute the candidate list.
- Per-shuffle yield: same shape as `solve_lds_shuffle_loop`.
- LP / objective-aware selection between asteroid path and shuffle paths per chain. Currently shuffle is unconditionally used when the flag is on and plastic-bar is in the chain — could be objectively worse at low research.
- Cycle-detection guard between mutually-feeding shuffles (LDS shuffle produces copper, hypothetical copper-shuffle produces plastic — guard required).
- Candidate shuffles to investigate: rails (iron-stick), concrete, green-circuits, red-circuits.

### Full research-state tracking (V3 item 2 — ~150 LoC)

`--no-asteroids` is shipped (the most-requested gating subset). Remaining surface:

- **Quality module tier:** `--quality-module-tier` already exists but doesn't check whether the tech is researched.
- **Recycler:** locked behind `recycling`. Missing → no quality at all → fail fast.
- **Foundry / EM-plant / cryogenic-plant:** gated by science-pack tech. Missing → fall back to furnace/assembler/chem-plant routes.
- **Per-planet landing:** narrower than `--planets` (which today implies the user already landed there).

Proposed input: `--tech NAME=LEVEL` repeated, or `--tech-preset {early,mid,late,all}`. Fail-fast naming the missing tech. Defaults to `late`.

### Gleba spoilage timing (V3 item 4 finish — ~250 LoC)

Bio-raw self-recycle math is in tree. Missing pieces:

- **Spoilage timing.** Self-recycle yields ~0.04 % per cycle → thousands of cycles to reach legendary. Bioflux spoils in 1 hour, nutrients in 5 minutes. Real builds need short loops + spoilage-research investment + accepted legendary loss to spoilage. Planner currently reports machine counts as if there's no spoilage budget — wrong for Gleba.
- **Pentapod-egg as target.** Recipe is `1 egg + 30 nutrients + 60 water → 2 eggs` (doubling self-loop where input = output). `solve_self_recycle_target_loop` assumes external ingredients; doesn't handle ingredient = output yet.
- **Agricultural quality.** Towers have 0 module slots; harvest is normal-quality only. Constraint already correct but worth surfacing to users.

### Alternate objectives (V3 item 6 — scope TBD)

Switch the implicit "minimize asteroid input" objective to user-selected:
- Fewest machines (current default-ish)
- Lowest power (efficiency modules instead of prod)
- Smallest footprint (different module mix per stage)
- UPS-sensitive

Each is a different objective on the same DP — would require a `--objective` flag and per-objective module-config search. Efficiency modules are currently not modelled; adding them affects per-stage power computation in `_stage_power_kw`.

---

## Non-goals

- **Not a replacement for `cli.py`.** That remains the general-purpose calculator for non-quality math (raw/uncommon/rare throughput, bus sizing, bottleneck analysis).
- **Not a blueprint generator.**
- **Not a UI / dashboard feature.** JSON output is consumable by external tooling.
- **Not a modded-recipe tool.** Vanilla + Space Age only.
- **Not a vanilla+quality tool.** Vanilla quality is a deferred design space — needs different raw-source strategy entirely (no asteroids, narrower planet set).
