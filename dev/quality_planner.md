# Quality Planner

A separate stdlib-only Python tool that answers:

> *"Given my research and module tier, what's the cheapest way to make N legendary `<item>` per minute?"*

Lives at `dev/quality_planner.py` (~2600 LoC) alongside `10x-factorio-engineer/assets/cli.py`. Imports `cli.py` as a library; does not modify it.

This document is the single source of truth — supersedes the original `quality_planner_v1.md` and `quality_planner_v2.md` specs (deleted). The history of how features evolved is in git; this doc only covers what exists today and what's planned.

---

## Status

**Last updated:** 2026-05-14. Tests: `python -m unittest dev.test_quality_planner -v` — **245 tests, all passing, ~1.4 s.**

Currently shipped:
- DP kernels for four loop types (asteroid reprocessing, mined-raw self-recycle, cross-item shuffle, self-recycle target)
- Multi-planet support (`--planets`)
- Per-stage assembly module optimization (`--assembly-modules`)
- Machine-quality plumbing (`--machine-quality`)
- **Generic cross-item shuffle enumeration (`--enable-shuffle NAME` / `--enable-shuffles all`)** — auto-discovers ~195 candidate recipes from the dataset including buildings (`biochamber`, `agricultural-tower`, `lab`, `capture-robot-rocket`), modules (T1/T2/T3 prod/speed/quality/efficiency), military (turrets, tank, spidertron, ammo, armor), end-game power (nuclear/fusion/heat-exchanger), logistics (roboport, robots).
- Self-recycle targets: tungsten-carbide, superconductor, holmium-plate, fusion-power-cell, lithium, biolab, captive-biter-spawner
- **Auto-compare cost gate (V3 item 4)** — for any item in `SELF_RECYCLE_TARGETS`, the planner runs both Path A (self-recycle target loop) and Path B (ingredient-upcycle via tree walk) and picks the lower `total_machine_count`. Surfaces the choice in `notes`. Often Path B wins (e.g. tungsten-carbide, holmium-plate, superconductor with intermediate dispatch), often Path A wins when Path B's chain hits a self-recycling intermediate that the dispatcher can't unblock.
- **Self-recycling intermediate dispatch (post-2026-05-08 audit)** — items in `SELF_RECYCLING_BLOCKLIST` (tungsten-carbide, superconductor, holmium-plate) hit as INTERMEDIATES in another chain now dispatch to `choose_path_self_recycle` instead of fail-fasting. Unblocks 14 previously-failing endgame targets (`foundry`, `electromagnetic-plant`, `fusion-reactor`, `mech-armor`, `quality-module-3`, every endgame science pack, etc.). The dispatcher is the **same mechanism** the top-level auto-comparator uses — one DP serves both. A per-`plan()` `_DispatchCache` memoizes solver kernel calls and Path A/B decisions so deep chains don't re-solve the same comparison.
- Gleba bio-raws (yumako, jellynut, pentapod-egg) — **no spoilage timing**
- Per-stage power accounting (`total_power_mw`)
- `--no-asteroids` early-game gating
- Stage cost summary (`summary.by_role`) + hot-spot advisor notes
- **Tech-state gating (`--tech NAME=LEVEL`)** — locks recycler / foundry / EM-plant / cryo-plant / biochamber / quality-module tier. **Default is LOCKED**: a bare `python dev/quality_planner.py ...` call now fails-fast on the recycler check; users must list their unlocked tech with `--tech recycling=1 --tech tungsten-carbide=1 ...`.
- **Incidental co-product credit (2026-05-14)** — non-primary SOLID outputs of walker-activated assembly recipes are credited against existing chain demand.  `molten-iron-from-lava` / `molten-copper-from-lava` give stone byproducts; Gleba `*-processing` recipes give seeds; `iron-bacteria` / `copper-bacteria` give spoilage; centrifuge recipes give the other uranium isotope.  Surplus surfaces as `incidental_byproduct_overflow`.
- **Driven co-product activation (`--enable-driver RECIPE_KEY` / `--enable-drivers all`, 2026-05-14)** — for any leaf raw R demanded via mined-recycle, the planner can activate a recipe that produces R as a non-primary solid (e.g. `molten-iron-from-lava` for stone) purely to harvest R, accepting the recipe's primary as overflow.  Driver ingredients are walked through the standard legendary chain (asteroid → calcite, etc.).  `--enable-drivers all` is cost-gated against the no-driver baseline.  Headline impact: `stone-wall @ 60/min --planets nauvis,vulcanus --enable-drivers all` drops from 2244 to ~65 machines (35× reduction).

Future additions in the [Roadmap](#roadmap) section below.

---

## Quick start

Every invocation needs `--tech` flags listing what's researched. To save typing, the examples below define `TECH_ALL` for the fully-researched baseline:

```bash
TECH_ALL='--tech recycling=1 --tech tungsten-carbide=1 --tech electromagnetic-plant=1 --tech cryogenic-plant=1 --tech biochamber=1 --tech quality-module-3=1'

# Asteroid-only iron-plate (the simplest plan)
python dev/quality_planner.py --item iron-plate --rate 60 $TECH_ALL

# Recommended for serious planning (all flags on)
python dev/quality_planner.py --item processing-unit --rate 60 \
    --planets nauvis --assembly-modules --machine-quality legendary $TECH_ALL

# Multi-planet chain
python dev/quality_planner.py --item artillery-shell --rate 60 \
    --planets nauvis,vulcanus --assembly-modules $TECH_ALL

# Self-recycle target
python dev/quality_planner.py --item superconductor --rate 60 \
    --planets nauvis,fulgora $TECH_ALL

# Plastic-heavy chain via cross-item shuffle
python dev/quality_planner.py --item processing-unit --rate 60 \
    --planets nauvis --assembly-modules --enable-shuffle low-density-structure $TECH_ALL

# Early-game: no space platform AND no foundry yet
python dev/quality_planner.py --item iron-plate --rate 60 \
    --planets nauvis,vulcanus --no-asteroids \
    --tech recycling=1 --tech quality-module-3=1

# Legendary biolab (Gleba/cryo building) — auto-compare picks ingredient-upcycle
python dev/quality_planner.py --item biolab --rate 1 \
    --planets nauvis,gleba $TECH_ALL

# Legendary T3 prod modules (all need biter-egg)
python dev/quality_planner.py --item productivity-module-3 --rate 60 \
    --planets nauvis,gleba --enable-shuffle productivity-module-3 $TECH_ALL

# Legendary tank
python dev/quality_planner.py --item tank --rate 1 \
    --planets nauvis --enable-shuffle tank $TECH_ALL

# Stone-bound chain rescued by a co-product driver
# (lava casting on Vulcanus harvests stone; molten-iron is voided as overflow)
python dev/quality_planner.py --item stone-wall --rate 60 \
    --planets nauvis,vulcanus --enable-drivers all $TECH_ALL
```

---

## Regression anchors

Sanity numbers (60/min legendary, `--module-quality legendary`, no research, modules-off, fully-researched tech via `$TECH_ALL`):

| target | planets | total machines | asteroid chunks/min | mined/min | fluid/min |
|---|---|---|---|---|---|
| `iron-plate` | — | 18.3 | metallic 281, oxide 28 | — | — |
| `processing-unit` | nauvis | 614.2 | metallic 1406, carbonic 703, oxide 59 | coal 321 874 | crude-oil 5 333 |
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
| `--enable-shuffle NAME` | none | Repeatable. Activate cross-item shuffle by output-item key (e.g. `low-density-structure`). 16 candidates discovered from dataset; see [Shuffle enumeration](#shuffle-enumeration--selection) for the full list. |
| `--enable-shuffles all` | off | Activate every applicable shuffle; greedy selector picks the best primary per legendary leaf. Mutually exclusive with `--enable-shuffle`. |
| `--enable-driver RECIPE` | none | Repeatable. Activate a co-product driver by recipe key (e.g. `molten-iron-from-lava` to harvest stone for `stone-wall @ vulcanus`). Driver primary becomes overflow. See `enumerate_co_product_drivers` for the candidate list. |
| `--enable-drivers all` | off | Try every driver candidate, picking the highest-yield driver per mined-recycle leaf. Cost-gated against the no-driver baseline. Mutually exclusive with `--enable-driver`. |
| `--no-asteroids` | off | Skip asteroid path; route iron-ore/copper-ore/ice/calcite via planet self-recycle |
| `--tech NAME=LEVEL` | empty | Repeatable. Tech research state. **Without any `--tech` flag, NOTHING is researched and the plan fails-fast on the recycler check.** Valid names: `recycling`, `tungsten-carbide`, `electromagnetic-plant`, `cryogenic-plant`, `biochamber`, `quality-module`, `quality-module-2`, `quality-module-3`. To replicate the fully-researched baseline list every tech with `=1`. |
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

  // Incidental co-products from walker-activated multi-output recipes
  // (lava casting → stone, *-processing → seeds, bacteria → spoilage, etc.)
  "incidental_byproduct_legendary": {"stone": 4.8},
  "incidental_byproduct_credited":  {"stone": 4.8},   // capped at observed demand
  "incidental_byproduct_overflow":  {},                // surplus

  // Driver activations (e.g. lava casting run for its stone co-product;
  // primary becomes overflow).
  "driver_overflow": {"molten-iron": 15000.0},

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
| `co-product-driver` | plan() | per recipe | Driven activation: recipe runs purely for its non-primary solid output (e.g. `molten-iron-from-lava` for stone). Has `target`, `co_product_per_min`, `crafts_per_min`, `inputs`, `overflow_outputs` |

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
| `solve_self_recycle_target_loop_memoized` | Cache-aware wrapper around the above; keys by rate-independent params for cross-call reuse |
| `_DispatchCache` | Per-`plan()` memo: `plans` (decision cache), `solver` (kernel cache), `intermediates` (sub-plans for Pass 2) + kernel-call counters for tests |
| `_env_signature` | Frozen tuple of cost-affecting kwargs; used as the secondary key in `_cache.plans` |
| `choose_path_self_recycle` | Dispatcher: picks min(Path A, Path B) for SELF_RECYCLE_TARGETS items at any depth. Cycle-guards via `_in_flight`. Subsumes the top-level auto-comparator AND walker intermediate dispatch |
| `_assembly_prod_bonus` | (machine, recipe, slots, flag, quality, tier) → (prod_fraction, slots_filled). Includes inherent prod for foundry/EM/biochamber |
| `_compute_incidental_byproducts` | Walks activated assembly stages, returns `({item: rate}, {item: [{recipe, primary, rate}, ...]})` of non-primary SOLID outputs.  `eff_prod` reconstructed from stored `research_prod` + `module_prod` on the stage |
| `enumerate_co_product_drivers` | Returns `{co_product: [candidates...]}` — every multi-output recipe (excluding crushing/recycling/captive-spawner) becomes a candidate keyed by each of its solid outputs.  Sorted by descending per-craft yield.  Cached per dataset |
| `_stage_power_kw` | Dispatches per role; compound stages split power between machine types |
| `_hot_spot_suggestions` | Inspects `summary.by_role`, emits actionable notes when one role > 50 % of machines |
| `_pick_recipe_fluid_preferred` | Recipe selection: prefer recipes with most fluid ingredients (foundry casting > furnace); drops candidates whose machine is locked under `tech_state` |
| `_tech_locked_machines` | Returns frozenset of machine keys locked by the given `tech_state` |
| `_tech_quality_tier_cap` | Highest unlocked quality-module tier (0=none) |
| `_machine_for_recipe` | Wraps `cli.get_machine` with `CATEGORY_FALLBACK` routing — returns None when the primary machine is locked AND the recipe category has no fallback |
| `walk_recipe_tree` | Two-pass walker. Builds stage list + raw_demand dict. Accepts `extra_raws`, `byproduct_credits`, `assembly_modules`, `machine_quality`, `no_asteroids`, **`tech_state` (required kwarg)**, plus dispatch-plumbing kwargs `_cache` / `_in_flight` / `_force_tree_walk_for` / `_dispatch_env` / `_dispatch_out` |
| `_plan_self_recycle_target` | Path A implementation. Now threads `_cache` + `_in_flight` so its inner ingredient walks can dispatch deeper blocklist intermediates |
| `plan` | Top-level orchestrator. `tech_state` is a required keyword arg. Internal kwargs: `_force_tree_walk` (top-level Path B re-entry), `_cache` / `_in_flight` / `_force_tree_walk_for` (recursive Path B re-entries from `choose_path_self_recycle`) |
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

### Shuffle enumeration + selection

The planner discovers cross-item shuffle candidates by introspecting the dataset (no hardcoded recipe list).  A candidate is a recipe that:

1. Produces an item I (with `allow_productivity=True`)
2. Has a corresponding `<I>-recycling` recipe that returns 2+ distinct **solid** items (multi-output filter — single-output recyclers are degenerate self-recycles already covered by `solve_self_recycle_target_loop`)
3. The recycler's solid outputs are a subset of the recipe's solid ingredients

When multiple cast-recipe variants exist for the same output (e.g. `casting-low-density-structure` foundry vs `low-density-structure` assembler), `enumerate_shuffle_candidates` picks the **fluid-preferred variant** — most fluid ingredients = most quality-transparent inputs = best legendary efficiency.  For LDS this picks the foundry variant (1 solid input + 2 fluids).

Stock Space Age yields **16 candidates**:

| Output item | Cast recipe | Solid ingredients | Solid recycle returns |
|---|---|---|---|
| `advanced-circuit` | `advanced-circuit` | copper-cable, electronic-circuit, plastic-bar | (same) |
| `artificial-jellynut-soil` | (same) | jellynut-seed, landfill, nutrients | (same) |
| `artificial-yumako-soil` | (same) | landfill, nutrients, yumako-seed | (same) |
| `battery` | `battery` | copper-plate, iron-plate | (same) |
| `concrete` | `concrete-from-molten-iron` | stone-brick | iron-ore, stone-brick |
| `electric-engine-unit` | (same) | electronic-circuit, engine-unit | (same) |
| `electronic-circuit` | `electronic-circuit` | copper-cable, iron-plate | (same) |
| `engine-unit` | (same) | iron-gear-wheel, pipe, steel-plate | (same) |
| `flying-robot-frame` | (same) | battery, electric-engine-unit, electronic-circuit, steel-plate | (same) |
| `low-density-structure` | `casting-low-density-structure` | plastic-bar | copper-plate, plastic-bar, steel-plate |
| `nuclear-fuel` | `nuclear-fuel` | rocket-fuel, uranium-235 | (same) |
| `overgrowth-jellynut-soil` | (same) | artificial-jellynut-soil, biter-egg, jellynut-seed, spoilage | (same) |
| `overgrowth-yumako-soil` | (same) | artificial-yumako-soil, biter-egg, spoilage, yumako-seed | (same) |
| `processing-unit` | `processing-unit` | advanced-circuit, electronic-circuit | (same) |
| `quantum-processor` | `quantum-processor` | carbon-fiber, lithium-plate, processing-unit, superconductor, tungsten-carbide | (same) |
| `supercapacitor` | `supercapacitor` | battery, electronic-circuit, holmium-plate, superconductor | (same) |

**Greedy selection** runs per `plan()` invocation:

1. **Identify legendary solid leaves** from the initial walker pass — assembly products + raws with positive demand, **excluding** the top-level target item (preserves the user's request: don't shuffle the target away).
2. **Iterate leaves by descending demand.**  For each leaf:
   - Find candidates whose recycle returns it (as a primary or byproduct).
   - For each candidate, score by total `machine_count` (cast + recycler) at the scale needed to cover this leaf's demand.
   - Pick the lowest-cost match.
3. **Cumulative byproduct credits** track legendary outputs already produced by activated shuffles; subsequent leaves are checked against credits before scoring (a single LDS activation often covers both plastic-bar and copper-plate demand).
4. **Merge duplicate `(recipe, primary)` selections** — if a leaf's best source is a primary already activated for a different reason, sum the throughputs into one stage.

**Wiring into `plan()`** for each chosen shuffle:

1. Re-walk the main chain with all chosen primaries as `extra_raws`.
2. Cap byproducts at observed demand → `capped_credits`. Surplus → `shuffle_byproduct_overflow` + a note.
3. If any credit > 0, re-walk a third time with `byproduct_credits=capped_credits` so demand for credited items propagates correctly through the chain.
4. Walk each primary's normal-quality leg separately; route its raws into `normal_solid_input` / `normal_fluid_input`.

**Cycle detection:** the greedy processes each leaf once and a chosen shuffle's byproducts can only *remove* leaves from the queue (never re-add them).  Mutually-feeding shuffles (e.g. LDS produces copper, hypothetical copper-shuffle would produce plastic) cannot both activate.  Naturally cycle-free.

**Cost gate (`--enable-shuffles all` only).**  Under `--enable-shuffles all`, the planner runs once with the greedy's chosen shuffles, then again with no shuffles, and keeps whichever has the lower `total_machine_count`.  When the no-shuffle path wins, the result includes a note explaining the fallback (`"--enable-shuffles all: greedy proposed shuffles totalling X machines, but no-shuffle baseline is Y machines — kept baseline"`).  Under explicit `--enable-shuffle NAME`, the user's choice is honoured unconditionally — the gate is not applied.

### Self-recycle target dispatch (V3 item 4 + 2026-05-08 audit)

The dispatcher `choose_path_self_recycle` is invoked at **two sites**:

1. **Top-level**: `plan()` calls it whenever `item_key in SELF_RECYCLE_TARGETS`.
2. **Intermediate**: `walk_recipe_tree` Pass 1 calls it when a transitive ingredient hits `SELF_RECYCLING_BLOCKLIST`. Resolution is deferred until the BFS finishes accumulating demand, then the dispatcher runs at the fully-accumulated rate. Pass 2 reads the cached sub-plan and emits its stages verbatim. Replaces the old fail-fast at this site (which blocked 14 endgame targets).

Both call sites share a per-`plan()` `_DispatchCache` with three layers:

| Layer | Key | Stores |
|---|---|---|
| Solver | `(item, machine, slots, allow_prod, round(inherent,6), round(research_prod,6), module_quality, prod_tier, quality_tier)` | `(V_total, configs)` from `solve_self_recycle_target_loop` (rate-independent) |
| Decision | `(item, env_signature)` where `env_signature` covers all kwargs that affect cost | `"A"` or `"B"` — re-execute chosen branch at the actual rate |
| Sub-plan | `item` | Sub-plan dict consumed by Pass 2 |

The decision cache is rate-independent: both paths scale linearly with rate, so the choice doesn't depend on rate. Stage construction is re-run at the actual rate to size machine counts correctly.

**Path A — `_plan_self_recycle_target`:**
1. `solve_self_recycle_target_loop_memoized` runs (memoized):
   - Outer search: enumerate `(craft_prod, craft_quality, recycle_quality)` configs.
   - One craft produces `items_per_craft = output × (1 + prod)` items distributed across tiers by `q_craft`.
   - Inner DP `V_rec[t]`: per-item legendary yield from a single tier-t item entering a recycler-only chain (converges because retention < 1).
   - Total = `items_per_craft × Σ craft_probs[s] × V_rec[s]`.
2. Ingredients consumed at NORMAL quality (quality rolls happen inside the loop) → `normal_solid_input` / `normal_fluid_input`. Walked through `walk_recipe_tree` as normal-quality production trees.

**Path B — standard tree walk:** `plan()` recursed with internal flag `_force_tree_walk=True` AND `_force_tree_walk_for={item_key}` bypasses the SELF_RECYCLE_TARGETS dispatch for the item itself, but the walker can still dispatch OTHER blocklist intermediates encountered in the chain. The target is crafted from legendary-quality ingredients, each ingredient sourced via the standard quality paths (asteroid, mined-recycle, shuffle, OR — recursively — another self-recycle dispatch).

**Cycle detection** via `_in_flight: frozenset[str]` propagated through kwargs. If `choose_path_self_recycle` is entered with `item in _in_flight`, force Path A — the only branch that doesn't recurse through this dispatcher.

**Auto-comparator** (always-on for SELF_RECYCLE_TARGETS):
- Runs both paths on cache miss.
- If Path B raises a `ValueError`, Path A wins automatically with a note explaining the fallback.
- Otherwise picks whichever has the lower `total_machine_count` and attaches an explanatory note like `auto-compare: ingredient-upcycle (480.1 machines) beats self-recycle loop (1105.9 machines).`

Observed outcomes (60/min legendary, full tech, fully-researched flags):
- **tungsten-carbide** → Path B wins (~480 vs ~1106 machines)
- **holmium-plate** → Path B wins (mined holmium-ore upcycle)
- **superconductor** → Path B wins (post-audit; intermediate dispatch unblocks holmium-plate)
- **fusion-power-cell** / **lithium** / **captive-biter-spawner** / **biolab** → cost-dependent; auto-comparator picks per chain.

Items in `SELF_RECYCLING_BLOCKLIST` used as INTERMEDIATES (not as the target) now route through the same dispatcher rather than fail-fasting.

### Tech-state gating

The planner gates which machines/recipes the player has unlocked via `tech_state: dict[str, int]` (required keyword arg to `plan()` and `walk_recipe_tree()`).

- **CLI default**: no `--tech` flags → `tech_state == {}` (everything locked) → `plan()` fails-fast on the recycler check.
- **Library default**: `tech_state` has no default; callers must pass an explicit dict. `qp.ALL_TECH_UNLOCKED` is the constant for "fully researched" (used by every existing test).

`TECH_GATES` declares what each tech name unlocks: either a list of machines (`recycler`, `foundry`, `electromagnetic-plant`, `cryogenic-plant`, `biochamber`) or a `quality_tier` (1/2/3 for `quality-module`/-2/-3).

When a primary machine is locked, `_machine_for_recipe` consults `CATEGORY_FALLBACK` for an alternative:
- `electronics` / `electronics-with-fluid` / `pressing` → assembler-N (these are categories that assembler-3 natively supports).
- `*-or-assembling` → assembler-N.
- `*-or-chemistry` / `chemistry-or-cryogenics` → chemical-plant.
- Categories without an entry (`metallurgy`, `cryogenics`, `electromagnetics`, `organic`) have no fallback — recipes routing through them fail-fast with an actionable hint naming the missing tech.

Quality-module tier is checked against `_tech_quality_tier_cap(tech_state)`: requesting `quality_module_tier=3` with `quality-module-3` locked fails-fast at `plan()` entry.

### Hot-spot advisor

After computing `summary.by_role`, `_hot_spot_suggestions` emits a note when any role exceeds 50 % of total machines. Maps role → suggestion:

| Dominant role | Condition | Suggestion |
|---|---|---|
| `asteroid-reprocessing` | plastic in chain, shuffle off | `--enable-shuffle low-density-structure` |
| `asteroid-reprocessing` | quality < legendary T3 | upgrade `--module-quality` / `--quality-module-tier` |
| `asteroid-reprocessing` | already at max, no plastic | (no suggestion — nothing actionable) |
| `mined-raw-self-recycle` | plastic in chain | `--enable-shuffle low-density-structure` |
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

`dev/test_quality_planner.py` — **245 tests**, 31 classes.

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
| `TestLDSShuffleWiring` | `--enable-shuffle low-density-structure` end-to-end (formerly `--enable-lds-shuffle`); byproduct credit propagation; overflow notes |
| `TestShuffleEnumeration` | `enumerate_shuffle_candidates` returns 16 candidates with multi-output recyclers; LDS picked with foundry variant; iron-stick / copper-cable excluded; cached per dataset |
| `TestShuffleSolver` | Generic `solve_shuffle_loop` matches legacy LDS solver byte-for-byte; positive yields for advanced-circuit / engine-unit; `compute_shuffle_stage` produces machine counts + byproducts; inherent prod auto-resolved per machine |
| `TestShuffleSelection` | Greedy picks LDS for plastic; no shuffle when no overlap; byproducts cover other leaves (single activation); empty/disjoint inputs handled |
| `TestEnableShufflesAll` | `--enable-shuffles all` sentinel activates every applicable shuffle; target item excluded from primaries (no quantum-processor shuffle for processing-unit target); unknown shuffle name errors; combines with `--assembly-modules` |
| `TestSelfRecycleTarget` | superconductor/holmium-plate/tungsten-carbide as targets; ingredients in normal_solid_input |
| `TestAssemblyModules` | `--assembly-modules` cuts machines >5×; `_assembly_prod_bonus` helper edge cases |
| `TestGlebaPartial` | Gleba bio-targets (bioflux, plastic-bar→bioplastic, sulfur→biosulfur, lubricant→biolubricant). **Spoilage NOT modelled.** |
| `TestStagePower` | Every stage has `power_kw`; compound stages split correctly; biochamber reports 0 (burner) |
| `TestMachineQuality` | `--machine-quality` applies `MACHINE_QUALITY_SPEED` to assembly + crusher + recycler; legendary cuts machine count by 1/2.5 |
| `TestNoAsteroids` | `--no-asteroids` routes via `MINED_RAW_NO_ASTEROID_FALLBACK`; fail-fast names the missing planet |
| `TestStageSummary` | `summary.by_role` aggregates machines/power/stage_count per role; pcts sum to 100 |
| `TestHotSpotAdvisor` | Helper unit tests + end-to-end notes; suppresses suggestions when nothing actionable |
| `TestTechGating` | `--tech NAME=LEVEL` end-to-end: recycler-locked fail-fast, foundry/EM-plant fallback, cryogenic unreachable, `quality-module-3` gate, partial-lock baseline parity, `_parse_tech_state` validation, `tech_state` is a required kwarg |
| `TestGlebaTargets` (V3 item 4) | `biolab`/`captive-biter-spawner` in `SELF_RECYCLE_TARGETS`; auto-comparator picks Path B for tungsten-carbide, plans succeed for captive-biter-spawner (post-audit Path B may now win); explanatory notes always present; shuffle enumeration includes buildings + modules + military + endgame; single-output recyclers excluded; `tank`/`biochamber`/`capture-robot-rocket`/`productivity-module-3` plan as shuffle targets; shuffle DP correctly skips prod-bearing slots when recipe has `allow_productivity=False`. |
| `TestSelfRecycleIntermediate` (post-2026-05-08 audit) | 14 previously-failing endgame targets now plan: `electromagnetic-plant`, `foundry`, `mech-armor`, `fusion-reactor`, `quality-module-3`, `metallurgic-/electromagnetic-/cryogenic-science-pack`. Verifies normal-quality inputs propagate (`holmium-solution` in `normal_fluid_input`). Verifies `summary.by_role` includes `self-recycle-target`. Verifies linear scaling under rate doubling. Verifies Pass 2 deduplicates intermediates so duplicate `order` entries don't re-emit. |
| `TestDispatchMemoization` (post-2026-05-08 audit) | Solver kernel called once per unique `(item, env)` key; Path A/B decision cached and re-used; per-`plan()` cache isolation (no cross-call leak); cycle detection via pre-populated `_in_flight` forces Path A with explanatory note; solver cache keyed by env (epic-quality variant gets a fresh kernel call). |
| `TestCoProductIncidental` (shipped 2026-05-14) | `incidental_byproduct_legendary` / `_credited` / `_overflow` fields always present (empty when no multi-output recipe active).  `iron-plate @ vulcanus` emits stone byproduct as overflow (no stone demand).  `concrete @ vulcanus` emits 4.8 legendary stone/min, all credited, dropping mined-recycle target from 60 to 55.2 stone/min.  Surplus + credit notes appear in `notes`.  Linear scaling under rate doubling.  Fluid byproducts excluded from helper output.  `format_human` renders an `Incidental Co-Products` section when non-empty.  `_plan_self_recycle_target` sub-plan emits the empty fields. |
| `TestCoProductDriven` (shipped 2026-05-14) | `enumerate_co_product_drivers` returns the expected stock candidates (lava casting × 2 for stone, processing recipes for seeds, etc.) sorted by descending per-craft yield.  Default off — no `driver_overflow` and no `co-product-driver` stage.  Explicit `--enable-driver molten-iron-from-lava` on `stone-wall @ vulcanus` activates the foundry stage, eliminates the stone mined-recycle stage, surfaces molten-iron in `driver_overflow`, drops total machines >10×.  `--enable-drivers all` picks the highest-yield candidate (copper variant with 15 stone/craft).  Unknown recipe key fails-fast.  Driver skipped when its fluid ingredient (lava) needs an unlocked planet (vulcanus).  Driver's calcite ingredient routes through the asteroid chain.  Linear rate scaling.  `format_human` renders `[driver]` stage line + `Driver Overflow` section.  Sub-plans (self-recycle target) include empty `driver_overflow` field. |
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
- **`--tech` default is locked.** A bare CLI invocation now produces an empty `tech_state={}` and fails-fast on the recycler check. Library callers (incl. tests) MUST pass `tech_state` — there is no default. Use `qp.ALL_TECH_UNLOCKED` for the legacy "fully researched" baseline. This was a deliberate breaking change to make the user's research state explicit (V3 item 2).
- **Shuffle DP solvers ignore tech_state.** `solve_shuffle_loop` / `compute_shuffle_stage` use `cli.get_machine` directly and do not consult `tech_state`. If the user enables a shuffle whose cast machine is locked (e.g. `--enable-shuffle low-density-structure --tech tungsten-carbide=0`), the shuffle still runs as if the foundry exists. The main-chain walker and `_pick_recipe_fluid_preferred` correctly gate locked machines, so this only matters when the user explicitly opts-in to a shuffle that requires a locked machine.
- **Auto-comparator changes path-A behaviour for existing self-recycle targets** (V3 item 4). Adding `biolab`/`captive-biter-spawner` was easy; the substantial change was always-on auto-compare for ALL items in `SELF_RECYCLE_TARGETS`. Some pre-V3-item-4 plans now route via Path B (ingredient-upcycle) when it's cheaper — `tungsten-carbide` (480 vs 1106) and `holmium-plate` are the visible cases. Existing tests that assumed `self-recycle-target` stage presence had to be updated to use a Path-A-winning target like `superconductor`. Path A still wins when Path B's chain hits a self-recycling intermediate.
- **`enumerate_shuffle_candidates` returns 195 items, not 16.** Dropping the `allow_productivity=True` filter (V3 item 4) broadened it dramatically. Greedy shuffle selection still scales fine because most candidates don't overlap with any given chain's leaves.
- **`_DispatchCache` is per-`plan()` invocation** (not module-level). Different calls have different planet sets / tech / module quality / etc., all of which change costs. Recursive Path B re-entries SHARE the cache (memoization across the chain) — but the cache is fresh on every top-level `plan()` call.
- **Pass 1 defers dispatch to end-of-BFS.** When the walker hits a blocklist intermediate it adds it to `pending_dispatch` and resumes BFS rather than dispatching immediately. Dispatch resolution runs once at the end with fully-accumulated demand. This avoids stale-rate sub-plans when an intermediate is consumed by multiple parents discovered at different BFS depths.
- **Path A is the cycle-fallback.** When `choose_path_self_recycle` is entered with `item in _in_flight`, it forces Path A and tags the result with `forced self-recycle (cycle detected through ...)`. Path A is the only branch that doesn't recurse through the dispatcher, so it always terminates.
- **Walker Pass 2 dedupes `order` entries.** A `pass2_emitted: set[str]` guards against re-emitting the same item if it appears multiple times in `order` (which can happen via interaction between BFS, dispatch, and `seen` in pathological chains). Without this guard, mech-armor and similar wide chains emit duplicate `self-recycle-target` stages.
- **Aggregating intermediate sub-plans uses `_dispatch_out`, not a cache diff.** Walker writes the keys it directly dispatched into a kwarg-passed set. Plan() reads only those, NOT all of `_cache.intermediates` — a recursive Path B plan() has already aggregated its own inner intermediates' `normal_solid_input` into its own, so the outer level reading the full cache would double-count.
- **`_force_tree_walk` (top-level) and `_force_tree_walk_for` (walker) are different.** `_force_tree_walk=True` on `plan()` skips the SELF_RECYCLE_TARGETS dispatch at top level (used by Path B re-entry). `_force_tree_walk_for=frozenset({item})` on `walk_recipe_tree` makes the walker treat `item` as a normal recipe even though it's in the blocklist (used by Path B inside `choose_path_self_recycle` so it can attempt the ingredient-upcycle of its own item without the dispatcher catching it).
- **Decision cache is rate-independent.** Both Path A and Path B scale linearly with rate, so the choice doesn't depend on rate. The cache stores `"A"`/`"B"` keyed by `(item, env_signature)`. On hit, only the chosen branch re-runs at the actual rate. This is the main memoization win for deep chains where the same item appears at different rates.

---

## Roadmap

In rough priority order (fully shipped items removed):

### Co-product credits — incidental sub-case (shipped 2026-05-14)

The byproduct-credit machinery exists (`byproduct_credits` kwarg on `walk_recipe_tree`) and was previously wired only into shuffle activations.  The incidental sub-case ships in `plan()` as a post-shuffle pass that walks the activated assembly stages, computes each stage's non-primary SOLID outputs at full chain rate (`crafts_per_min × amount × probability × eff_prod`), caps each byproduct at observed legendary demand, and re-walks the chain once with the merged credits.

Currently active credits:

- **Lava casting** (`molten-iron-from-lava`, `molten-copper-from-lava`) → stone.  Any Vulcanus chain that ALSO consumes stone (concrete, electric-furnace, landfill via stone-brick, etc.) sheds the credited portion from its mined-recycle stone target.  Example: `concrete @ 60/min --planets nauvis,vulcanus` credits 4.8 legendary stone/min and drops mined-recycle from 60→55.2 stone/min.
- **Gleba `*-processing`** (`yumako-processing`, `jellynut-processing`) → seeds (used for replanting; usually surplus in legendary chains).
- **Gleba bacteria** (`copper-bacteria`, `iron-bacteria`) → spoilage.
- **Centrifuge** (`uranium-processing`, `kovarex-enrichment-process`) → the other uranium isotope.
- **Advanced asteroid crushing** is NOT included here — it lives in the existing `raw-crushing` stage which already routes multiple outputs into the chunk-demand pipeline.

Shape of the credit: `incidental_byproduct_legendary` lists the gross emitted rate; `incidental_byproduct_credited` is the portion absorbed by chain demand; `incidental_byproduct_overflow` is the surplus.  Surplus rows surface as `notes` so users can see they have legendary stone / seeds / spoilage they could route elsewhere.

**Implementation choice — single re-walk vs iteration.**  Credits monotonically reduce demand, never increase it.  Upstream activations (the byproduct producers, e.g. lava casting) sit above their byproduct in the recipe DAG, so their rates don't change when the byproduct credit deactivates a downstream consumer (e.g. stone-brick).  A single re-walk suffices for the realistic Space Age chains.  If a future recipe graph creates a tighter cycle (byproduct producer's recipe consumes the byproduct itself), extend `plan()` to iterate; for now the simpler implementation is correct.

Tests: `TestCoProductIncidental` (11 cases) covers field presence, emitted vs credited vs overflow rates, the concrete @ vulcanus headline case, rate-linearity, fluid filtering, format_human rendering, and `_plan_self_recycle_target` sub-plan parity.

### Co-product credits — driven sub-case (shipped 2026-05-14)

`--enable-driver RECIPE_KEY` (repeatable) activates a recipe FOR its co-product when the chain has demand for the co-product as a mined-recycle leaf raw.  `--enable-drivers all` enumerates every candidate, picks the highest-yield driver per leaf raw, and cost-gates against the no-driver baseline.

How it differs from incidental:
- **Incidental** credits non-primary outputs of recipes ALREADY in the chain (chain-driven activation).
- **Driven** activates recipes NOT otherwise in the chain, purely for their co-product (co-product-driven activation).  The recipe's primary becomes overflow (e.g. molten-iron voided down a pipe).

Driver wiring:
1. After the incidental pass, iterate over `raw_demand` leaf raws.
2. For each raw R, look up `enumerate_co_product_drivers(data)` candidates.
3. Filter by tech / planet reachability + (for explicit `--enable-driver`) by user-named recipes.
4. Pick the candidate with the highest `target_amount × probability` per craft (most efficient driver).
5. Compute crafts/min from R demand; subtract R from `raw_demand`.
6. Walk each non-fluid INGREDIENT through `walk_recipe_tree` so its legendary chain (asteroid / mined-recycle / shuffle / nested-self-recycle) plugs into the main flow.
7. Record the recipe's other outputs as `driver_overflow`.
8. Emit a `co-product-driver` stage (machine = recipe's machine, machine_quality applied via `MACHINE_QUALITY_SPEED`).

Cost-gate (`--enable-drivers all` only): after building the plan, recurse with `active_drivers=None`.  If the no-driver baseline is cheaper, keep the baseline and emit a fallback note.  Explicit `--enable-driver` is honoured unconditionally.

Headline numbers (`stone-wall @ 60/min --planets nauvis,vulcanus`, default modules off):

| Config | Total machines |
|---|---|
| baseline (no driver) | 2244 |
| `--enable-driver molten-iron-from-lava` | ~93 |
| `--enable-drivers all` (picks copper variant: 15 stone/craft) | ~65 |

Stock Space Age driver candidates (excluding `crushing` / `recycling` / `captive-spawner-process`): stone (lava casting × 2), spoilage (iron-bacteria + copper-bacteria), uranium-238 (uranium-processing + kovarex), uranium-235 (kovarex), jelly + yumako-mash + seeds (Gleba `*-processing`), plus a few others (`ammoniacal-solution-separation`, `cryogenic-science-pack`, `quantum-processor`).

Limitations not addressed:
- Driver primary's chain credit not modelled (overflow is always 100 % wasted, even when chain demand for primary exists).  In practice this only matters if the user enables a driver whose primary is ALREADY in the chain — the right move is to leave the driver off and let the incidental pass handle it.
- Per-craft cost search is greedy / first-viable rather than full DP across all candidates; the cost-gate catches the worst false positives but a poorly-chosen explicit driver can over-spend.

Tests: `TestCoProductDriven` (14 cases) covers candidate enumeration, default off, explicit driver activation (stone-wall @ vulcanus), `--enable-drivers all` highest-yield pick, cost-gate fallback shape, unknown-recipe error, non-applicable driver no-op, planet-locked filter (no vulcanus → no lava-cast driver), calcite ingredient routing through asteroid chain, rate linearity, format_human rendering, `_plan_self_recycle_target` sub-plan parity.

### Full research-state tracking (V3 item 2)

**Shipped** as `--tech NAME=LEVEL` (see §Tech-state gating).  Covers recycler, foundry, EM-plant, cryogenic-plant, biochamber, quality-module tiers.  Per-planet-landing distinction (narrower than `--planets`) was deferred — for now `--planets X` continues to imply the user has landed on planet X.

### Gleba quality targets (V3 item 4 — shipped)

Originally framed as "Gleba spoilage timing"; refactored to focus on the more-valuable question: **how do you make legendary buildings/modules?** The shipped solution:
- `enumerate_shuffle_candidates` no longer filters by `allow_productivity=True` → 195 candidates (was 16). Buildings, modules, military equipment, end-game power, logistics all qualify.
- `biolab` and `captive-biter-spawner` added to `SELF_RECYCLE_TARGETS`.
- Auto-comparator (always-on for `SELF_RECYCLE_TARGETS`): runs Path A (self-recycle target loop) and Path B (ingredient-upcycle), picks lower machine count, attaches explanatory note.

Spoilage time-budget modelling was deliberately skipped — when Path B is infeasible because ingredients are too perishable, the DP yield collapses and Path B's machine count goes astronomical, naturally losing the cost gate.

### Pentapod-egg as a self-feed target (V3 item 4 — shipped)

Recipe is `1 pentapod-egg + 30 nutrients + 60 water → 2 pentapod-egg` (Gleba, biochamber, +50% inherent prod, `allow_productivity=true`).  The ingredient is also the output — a "self-feed" / doubling recipe.

`solve_self_recycle_target_loop` doesn't apply: the per-atom value DP `V(q) = max(craft, recycle)` has no positive fixed point whenever `output × p_stay > 1` (always true here).  So a separate solver `solve_self_feed_target_loop` was added with a small **linear flow LP**:

- Per processing tier `q ∈ {0,1,2,3}` (legendary q=4 drains): `x_q` crafts/min and `y_q` recycles/min (≥ 0).
- Balance at each tier: `A_q · x_q + B_q · y_q = I_q` where `A_q = 1 - output_q · cp_q[q→q]` (negative for super-productive), `B_q = 1 - retention · rp_q[q→q]` (positive), `I_q` accumulates from lower tiers, `I_0 = 0`.
- Drain at q=4: `Σ_q [x_q · output_q · cp_q[q→4] + y_q · retention · rp_q[q→4]] = rate`.
- Substitute `y_q = (I_q + |A_q| · x_q) / B_q` to eliminate balance equations → 4-variable LP with 1 equality + non-negativity → **corner-optimal** with exactly one `x_{q*}` positive.  Try all 4 corners, pick min-cost.

Config search is collapsed by exploiting that lower-tier configs are inert when only `x_{q*}` is positive (no atoms at q < q*) and upper-tier configs only need `rq` (no crafts).  Per corner: `25 · 5^(3-q*)` configs.  Total ≤ 4 000 configs in well under a second — no aggressive pruning needed.

Wired in via `SELF_FEED_TARGETS = frozenset(["pentapod-egg"])` and the `_plan_self_feed_target` dispatcher in `plan()`.  **Auto-comparator is intentionally skipped** — Path B (ingredient-upcycle) recurses into the same problem since ingredient = output.

Tests: `TestSelfFeedTarget` in `dev/test_quality_planner.py` (11 cases) covers basic plan shape, planet gating, rate-doubles, ingredient walking, no-auto-compare note, per-tier flows, module config exposure, human-format rendering, and solver edge cases (unknown item, non-self-feed item).

Known limitation: the LP assumes a steady-state pool exists at the chosen `q*` tier (e.g. epic eggs at `q*=3`).  Bootstrapping that pool from a single normal egg requires a finite warm-up period the model does not size.  In practice the warm-up is irrelevant once steady state is reached.

Remaining Gleba work (deferred):
- **Bacteria-cultivation / fish-breeding.** Same self-feed shape as pentapod-egg (`copper-bacteria-cultivation`, `iron-bacteria-cultivation`, `fish-breeding`).  They plug into the same solver — just add to `SELF_FEED_TARGETS` — but they're lower-priority targets (rarely needed at legendary tier).
- **Agricultural quality.** Towers have 0 module slots; harvest is normal-quality only. Constraint already correct but worth surfacing to users.

### Alternate objectives (V3 item 6 — scope TBD)

Switch the implicit "minimize asteroid input" objective to user-selected:
- Fewest machines (current default-ish)
- Lowest power (efficiency modules instead of prod)
- Smallest footprint (different module mix per stage)
- UPS-sensitive

Each is a different objective on the same DP — would require a `--objective` flag and per-objective module-config search. Efficiency modules are currently not modelled; adding them affects per-stage power computation in `_stage_power_kw`.

---

## Considered and deferred

Decisions surfaced by the 2026-05-08 audit that we've consciously chosen not to act on, so future contributors don't re-litigate them:

- **`_pick_recipe_fluid_preferred` → cost-based DP.**  Recipe selection is currently a heuristic ("most fluid ingredients wins") rather than a cost-minimizing search.  Memoizing the heuristic result is trivial and worth doing if profiling shows hot spots; converting to a cost-based DP is a substantially larger refactor and not justified by current outputs (the heuristic produces the right answer in every case observed so far).  Revisit if a future recipe routing turns out to be wrong, or if the [Self-recycling intermediate dispatch](#self-recycling-intermediate-dispatch-high-priority--150-loc) DP makes the cost primitive cheap to share.
- **`_plan_self_feed_target` LP → DP unification.**  The pentapod-egg LP corner search is already optimal per call and does not share structure with the quality DPs — folding it into the dispatch DP would complicate the latter without payoff.  Leave as-is.
- **Raw sourcing branch (asteroid vs mined-recycle vs `--no-asteroids`).**  This is flag-driven, not a cost choice.  No DP needed.

---

## Non-goals

- **Not a replacement for `cli.py`.** That remains the general-purpose calculator for non-quality math (raw/uncommon/rare throughput, bus sizing, bottleneck analysis).
- **Not a blueprint generator.**
- **Not a UI / dashboard feature.** JSON output is consumable by external tooling.
- **Not a modded-recipe tool.** Vanilla + Space Age only.
- **Not a vanilla+quality tool.** Vanilla quality is a deferred design space — needs different raw-source strategy entirely (no asteroids, narrower planet set).
