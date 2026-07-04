# Quality Planner

A separate stdlib-only Python tool that answers:

> *"Given my research and module tier, what's the cheapest way to make N legendary `<item>` per minute?"*

Lives at `dev/quality_planner.py` (~7000 LoC) alongside `10x-factorio-engineer/assets/cli.py`. Imports `cli.py` as a library; does not modify it.

This document is the single source of truth — supersedes the original `quality_planner_v1.md` and `quality_planner_v2.md` specs (deleted). The history of how features evolved is in git; this doc only covers what exists today.

---

## Status

**Last updated:** 2026-07-04. Tests: `python -m unittest dev.test_quality_planner -v` — **357 tests, all passing, ~4.8 s.**

**Roadmap:** planned quality-planning work (Q1–Q9: post-2.1.8 asteroid redesign, min-ingredient-quality rule, spoilage, placement optimizer, quality mining, mixed-tier demand, beacons, objective function, ergonomics) is specced in [`dev/quality-roadmap.md`](quality-roadmap.md).

Currently shipped:
- **Custom Objective Function (2026-07-04, Q8)** — Added `--objective machines|power|raw-input|cost` flag and `_evaluate_objective` evaluation function to customize optimization metrics.
- **Beacon & Speed-Module Integration (2026-07-04, Q7)** — Added `--beacons COUNT` flag. Applies beacon speed multipliers to crafting machines, scaling machine counts and power consumption.
- **Mixed-Tier Demand & Surplus Extraction (2026-07-04, Q6)** — Added `--demand ITEM@TIER:RATE,...` spec parser and `--keep-tiers TIERS` flag for multi-tier demand specification and surplus extraction.
- **Quality-Module Placement Optimizer (2026-07-04, Q4)** — Added `--optimize-placement` mode. Evaluates candidate placements across all chain steps where `recipe_allows_quality`, ranks placements by machine cost efficiency, and attaches a `Quality Placement Comparison` summary block to plan notes.
- **Gleba Spoilage Timing & Warnings (2026-07-04, Q3)** — Fixed spoil times (`SPOIL_TIMES_SECONDS` for yumako, jellynut, mash, nutrients, bioflux, pentapod-egg, biter-egg, ag-science). Estimated loop residence time $T \approx \text{passes} \times \text{cycle\_time}$. Emits WARNING notes when $T > 0.5 \times t_{\text{spoil}}$ and ERROR notes when $T > t_{\text{spoil}}$. Flag `--no-spoilage` restores unspoilable timing for A/B testing.
- **Minimum-Ingredient-Quality Rule & Tier-Matched Ingredient Sets (2026-07-04, Q2)** — Reframed shuffle DP loop states as full ingredient sets ($V[t]$ sets emerging per 1 normal set invested). Solid ingredients are demanded at recipe ratio per set at tier 0 (`normal_solid_inputs`). Recycler returns are split into set members (consumed in loop) vs excess returns (emitted as `byproduct_legendary`).
- **Post-2.1.8 Asteroid Quality Redesign (2026-07-04, Q1)** — Factorio 2.1.8+ removed quality modules from asteroid reprocessing recipes. Chunks no longer climb quality tiers via reprocessing loops. Asteroid quality now rolls during the initial crushing step (2 slots on crushers with quality modules). Crushed raw ores (iron-ore, copper-ore, carbon, sulfur, ice, calcite) are upcycled to the target tier via recycler self-loops (4 slots, 25% retention), emitted as `raw-crushing` and `asteroid-ore-upcycle` stage roles.
- **Generalized Quality Mining (2026-07-04, Q5)** — Mining drills convolve 1 miner quality roll with recycler loops for all planet-mined solid raws when quality modules are enabled (`--miner electric|big`). Applying quality modules to drills reduces drill craft speed by -5%/slot (-15% for 3 slots on electric drills, -20% for 4 slots on big mining drills).
- DP kernels for loop types (mined-raw self-recycle, cross-item shuffle, self-recycle target, asteroid crushing roll + ore upcycle)
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
- **Fulgora build location (`--location fulgora`, 2026-06-29)** — scrap-only sourcing. There is no asteroid platform on Fulgora, so `_pick_recipe_fluid_preferred` drops ore (`RAW_TO_CHUNK`) and `molten-*` routes (`forbid_ore_routes`), forcing metals to terminate at their scrap-reachable plate form (e.g. `copper-cable` from the scrap-sourced `copper-plate` instead of `casting-copper-cable`). The asteroid-reprocessing / crushing path is gated off and base materials come from the existing scrap-recycling quality source. Only `fulgora` alters sourcing; other `--location` values just unlock that planet.
- **Quality scrap seeding (2026-07-01, C3)** — mined scrap inherits quality from quality modules in mining drills. Drills share `--module-quality`/`--quality-module-tier` with recyclers, convolving the 1 miner quality roll with `d` recycler rolls to determine scrap-derived leaf yields.
- **Closed-loop plate upcycling (2026-07-01, C4)** — upcyclable scrap leaves (`iron-plate` and `copper-plate`) loop through container wraps (such as iron-gear-wheels and copper-cables) to upcycle to the target tier. The solver computes steady-state loop flows using forward substitution and sizes loop recyclers and craft machines (assemblers/EM-plants), reporting them under the `scrap-upcycle-loop` stage role (rendered as `[upcycle]` in human output).
- **Miner counting (2026-06-30, C1)** — the planner now sizes a mining-drill fleet for its solid raws (scrap + planet-mined ores) via `cli.compute_miners` and folds the counts + power into `total_machine_count` / `total_power_mw` / `summary.by_role` as a `mining` stage role (rendered as `[mining]` lines in Production Stages). `--miner electric|big` mirrors `cli.py`; mining-productivity research (`--research mining-productivity=N`, +10%/level uncapped) reduces the count. Asteroid chunks are caught in space (no drills); fluids report a yield% via `cli` (no drill count) — both excluded. The hot-spot advisor measures its thresholds against *production* (non-mining) machines so the addition doesn't dilute its existing suggestions.
- **Fulgora fluid sub-chains (2026-06-30)** — fluids consumed by a Fulgora chain (e.g. `sulfuric-acid` for `processing-unit`) are produced locally from Fulgora's heavy-oil oceans rather than listed as external raws. The planner's own recipe selector isn't wired for oil/sulfur chains (it picks `advanced-carbonic-asteroid-crushing` for `sulfur` and dies under `--no-asteroids`), so `_plan_fluid_chain_via_cli` **delegates** each fluid to `cli.py` (subprocess, `--item <fluid> --rate <r> --location fulgora` with every scrap-reachable solid bussed in via `--bus-item` so `cli` never recurses into ore). Each `cli` production step becomes a `fluid-chain` stage (`chemical-plant`, tagged with `fluid_target`); `fluid_input` then lists the true pumped raw (`heavy-oil`) instead of the intermediate fluid. Scrap-derived solids the sub-chain consumes (ice, iron-plate) surface as `fluid_chain_scrap_draw` and are credited against scrap-source overflow — they do **not** grow the scrap input. Fluid-chain machines + power fold into `total_machine_count` / `total_power_mw` / `summary.by_role`. Fulgora-only: every other location keeps fluids as quality-transparent raws. On `cli` failure (nonzero exit / bad JSON) the fluid falls back to being listed as a raw.
- **Inherent prod in demand propagation (2026-06-29)** — `walk_recipe_tree` Pass 1 now applies the machine's inherent prod (foundry/EM-plant/biochamber +50%) when propagating ingredient/raw demand, matching Pass 2's machine-count math.
- Stage cost summary (`summary.by_role`) + hot-spot advisor notes
- **Tech-state gating (`--tech NAME=LEVEL`)** — locks recycler / foundry / EM-plant / cryo-plant / biochamber. Default is LOCKED.
- **Incidental co-product credit (2026-05-14)** — non-primary SOLID outputs of walker-activated assembly recipes are credited against existing chain demand.
- **Driven co-product activation (`--enable-driver RECIPE_KEY` / `--enable-drivers all`, 2026-05-14)** — for any leaf raw R demanded via mined-recycle, the planner can activate a recipe that produces R as a non-primary solid purely to harvest R, accepting the recipe's primary as overflow.

---

## Quick start

Every invocation needs `--tech` flags listing what's researched. To save typing, the examples below define `TECH_ALL` for the fully-researched baseline:

```bash
TECH_ALL='--tech recycling=1 --tech tungsten-carbide=1 --tech electromagnetic-plant=1 --tech cryogenic-plant=1 --tech biochamber=1'

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
    --tech recycling=1

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

Sanity numbers (60/min legendary, `--module-quality legendary`, no research, modules-off, fully-researched tech via `$TECH_ALL`). Refreshed 2026-07-04 after **Post-2.1.8 Asteroid Quality Redesign & Generalized Quality Mining** (Q1+Q5 milestone):

| target | planets | total machines | asteroid chunks/min | mined/min | fluid/min |
|---|---|---|---|---|---|
| `iron-plate` | — | ~709 | metallic 6 437 | — | — |
| `processing-unit` | nauvis | ~22 203 | metallic 154 500 | coal 99 038 | petroleum-gas 2 400, sulfuric-acid 300 |
| `artillery-shell` | nauvis,vulcanus | ~128 895 | carbonic 128 750, oxide 35 907 | coal 198 077, tungsten-ore 528 204 | lava 3 467 |

With `--assembly-modules --machine-quality legendary`, `processing-unit @ nauvis` is **~19.9 machines** (unchanged by the Pass-1 fix — the assembly-modules path already applied inherent prod in demand propagation). Modules-off is the conservative baseline (but inherent machine prod now correctly applies there too). Prod modules carry their −5/−10/−15%-per-slot speed cost (the planner models no speed modules/beacons to offset it).

These are sanity checks, not committed expectations. If a refactor moves them, investigate the cause rather than rubber-stamping.

---

## CLI surface

```
python dev/quality_planner.py --item <id> --rate <N> [flags]
```

| Flag | Default | Description |
|---|---|---|
| `--item ID` | required | Target item (one only) |
| `--rate N` | required | Target items per minute (at `--target-quality`) |
| `--target-quality Q` | `legendary` | Goal quality tier. The quality loops stop here instead of pushing to legendary (e.g. `rare` treats rare-or-better as success — much cheaper than full legendary). Choices: `uncommon,rare,epic,legendary` |
| `--planets P1,P2,…` | empty | Unlocked planets. Empty = asteroid-only. Choices: `nauvis,vulcanus,fulgora,gleba,aquilo,space-platform` |
| `--location P` | none | Single planet the factory is **built on** (mirrors `cli.py --location`). Unlocks that planet's raws. **`--location fulgora` additionally switches to scrap-only sourcing**: no asteroid platform, so base materials come from the scrap-recycling quality source and metals terminate at their scrap-reachable plate form (no casting/molten-ore routes). Only `fulgora` alters sourcing today; other values just unlock that planet. Choices: `nauvis,vulcanus,fulgora,gleba,aquilo,space-platform` |
| `--module-quality Q` | `--target-quality` | Quality of quality-modules in loops. Defaults to (and may not exceed) `--target-quality` — you can't have modules of a quality you haven't researched. Choices: `normal,uncommon,rare,epic,legendary` |
| `--quality-module-tier {1,2,3}` | `3` | Tier of quality modules. Self-declaring — not gated by `--tech` (you'd only request a tier you've researched). |
| `--assembler-level {2,3}` | `3` | Assembler tier for non-categorised recipes |
| `--machine-quality Q` | `normal` | Quality of every assembly / crusher / recycler machine. Applies `cli.MACHINE_QUALITY_SPEED` (+0/+30/+60/+90/+150 %) |
| `--assembly-modules` | off | Fill assembly slots with prod modules at `--module-quality` and `--prod-module-tier`. Inherent +50 % prod (foundry/EM-plant/biochamber) is always applied |
| `--prod-module-tier {1,2,3}` | `3` | Tier of prod modules used by `--assembly-modules` |
| `--research NAME=LEVEL` | empty | Repeatable. Productivity research per recipe family (e.g. `--research asteroid-productivity=5`) |
| `--enable-shuffle NAME` | none | Repeatable. Activate cross-item shuffle by output-item key (e.g. `low-density-structure`). ~197 candidates discovered from dataset; see [Shuffle enumeration](#shuffle-enumeration--selection). |
| `--enable-shuffles all` | off | Activate every applicable shuffle; greedy selector picks the best primary per legendary leaf. Mutually exclusive with `--enable-shuffle`. |
| `--enable-driver RECIPE` | none | Repeatable. Activate a co-product driver by recipe key (e.g. `molten-iron-from-lava` to harvest stone for `stone-wall @ vulcanus`). Driver primary becomes overflow. See `enumerate_co_product_drivers` for the candidate list. |
| `--enable-drivers all` | off | Try every driver candidate, picking the highest-yield driver per mined-recycle leaf. Cost-gated against the no-driver baseline. Mutually exclusive with `--enable-driver`. |
| `--no-asteroids` | off | Skip asteroid path; route iron-ore/copper-ore/ice/calcite via planet self-recycle |
| `--no-miner-quality-modules` | off | Disable quality module seeding in mining drills on Fulgora |
| `--no-scrap-upcycle-loops` | off | Disable closed-loop plate upcycling on Fulgora |
| `--miner {electric,big}` | `electric` | Mining drill used to size the solid-raw fleet (scrap + planet-mined ores). Mirrors `cli.py`. Counts + power fold into the totals as a `mining` stage role; `--research mining-productivity=N` reduces them. Asteroid chunks (caught in space) and fluids (yield%, no count) get no drills |
| `--tech NAME=LEVEL` | empty | Repeatable. Tech research state (machine/building unlocks only). **Without any `--tech` flag, NOTHING is researched and the plan fails-fast on the recycler check.** Valid names: `recycling`, `tungsten-carbide`, `electromagnetic-plant`, `cryogenic-plant`, `biochamber`. To replicate the fully-researched baseline list every tech with `=1`. |
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
| `assembly` | walker | per recipe | Standard craft step. Has `inputs`, `fluid_inputs`, `solid_inputs`, `module_prod` (inherent + modules), `prod_modules`, `allow_productivity`, `machine_quality`, `prod_capped`. `format_human` shows the prod modules, "inherent +X% prod" when only the machine's built-in bonus applies (e.g. accumulator on the EM plant, or any foundry/EM/biochamber recipe with modules off), or "no prod modules" otherwise |
| `asteroid-reprocessing` | plan() | crusher | Quality loop on asteroid chunks (80 % retention, 2 slots). Has `module_config_per_tier` (crusher quality slots per tier) |
| `raw-crushing` | plan() | crusher | Legendary chunk → legendary ore (advanced crushing, 2 outputs per recipe) |
| `mined-raw-self-recycle` | plan() | recycler | Quality loop on planet-mined raws (25 % retention, 4 slots, no prod). Covers coal, stone, tungsten-ore, scrap, holmium-ore, uranium-ore, yumako, jellynut, pentapod-egg, and (with `--no-asteroids`) iron-ore/copper-ore/ice/calcite. Has `module_config_per_tier` (recycler quality slots per tier) |
| `scrap-quality-source` | plan() | recycler | Fulgora scrap → basket of rare/legendary recyclables. Convolved with miner quality modules when `miner_quality_modules` is active. Has `scrap_per_min`, `covered`, `overflow`, `binding_leaf`, `module_config_per_tier` |
| `scrap-upcycle-loop` | `compute_scrap_source` | craft+recycler | Closed-loop upcycling on Fulgora for iron and copper plates. Splits `craft_machines` and `recycler_machines` |
| `cross-item-shuffle` | plan() | foundry+recycler | LDS cast + recycle. Splits machine count between `foundry_machines` and `recycler_machines`. Has `byproduct_legendary`, `byproduct_credited`, `byproduct_overflow`, `fluid_demand` |
| `self-recycle-target` | `_plan_self_recycle_target` | craft+recycler | Recycler-only loop where the target's recycle returns itself. Splits `craft_machines` and `recycler_machines` |
| `co-product-driver` | plan() | per recipe | Driven activation: recipe runs purely for its non-primary solid output (e.g. `molten-iron-from-lava` for stone). Has `target`, `co_product_per_min`, `crafts_per_min`, `inputs`, `overflow_outputs` |
| `fluid-chain` | plan() (Fulgora) | chemical-plant | One `cli.py` production step of a delegated Fulgora fluid sub-chain (e.g. sulfuric-acid for processing-unit). Has `recipe`, `rate_per_min`, `fluid_target` |
| `mining` | plan() | electric/big-mining-drill | Drill fleet for one solid raw (scrap or a planet-mined ore), sized by `cli.compute_miners`. Has `item`, `recipe` (`mine-<item>`), `rate_per_min`. `--miner` picks the drill; mining-prod research reduces the count. Main `plan()` body only (not the self-recycle/self-feed early-return paths) |

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
| `solve_asteroid_reprocessing_loop` | 80 % retention, 2 slots, quality-only. **Known limitation:** still models quality modules in the reprocessing crusher, but 2.1.8 removed `quality` from reprocessing `allowed_effects` — asteroid-sourced counts are optimistic vs current game rules; plans with reprocessing stages carry an explanatory note |
| `solve_lds_shuffle_loop` | LDS foundry-cast + recycle joint DP, returns per-plastic legendary yield |
| `compute_lds_shuffle_stage` | Sizes a LDS shuffle stage from `legendary_plastic_per_min`; returns `foundry_machines`, `recycler_machines`, `byproduct_legendary`, `fluid_demand` |
| `solve_mined_raw_self_recycle_loop` | 25 % retention, 4 slots, quality-only (no prod) |
| `solve_self_recycle_target_loop` | Recycler-only DP: items at tier t enter recycler chain, tier up or vanish via 25 % retention |
| `solve_self_recycle_target_loop_memoized` | Cache-aware wrapper around the above; keys by rate-independent params for cross-call reuse |
| `_DispatchCache` | Per-`plan()` memo: `plans` (decision cache), `solver` (kernel cache), `intermediates` (sub-plans for Pass 2) + kernel-call counters for tests |
| `_env_signature` | Frozen tuple of cost-affecting kwargs; used as the secondary key in `_cache.plans` |
| `choose_path_self_recycle` | Dispatcher: picks min(Path A, Path B) for SELF_RECYCLE_TARGETS items at any depth. Cycle-guards via `_in_flight`. Subsumes the top-level auto-comparator AND walker intermediate dispatch |
| `_assembly_prod_bonus` | (machine, recipe, slots, flag, quality, tier) → (prod_fraction, slots_filled). Includes inherent prod for foundry/EM/biochamber |
| `_module_speed_mult` | (quality_slots, prod_slots, prod_tier) → speed multiplier from module speed penalties (quality −5%/slot flat; prod −5/−10/−15% per tier; floored at 0.2). Multiplied into every stage's effective machine speed. **Self-feed LP not yet covered (its per-config costs are part-2 work).** |
| `_compute_incidental_byproducts` | Walks activated assembly stages, returns `({item: rate}, {item: [{recipe, primary, rate}, ...]})` of non-primary SOLID outputs.  `eff_prod` reconstructed from stored `research_prod` + `module_prod` on the stage |
| `enumerate_co_product_drivers` | Returns `{co_product: [candidates...]}` — every multi-output recipe (excluding crushing/recycling/captive-spawner) becomes a candidate keyed by each of its solid outputs.  Sorted by descending per-craft yield.  Cached per dataset |
| `_stage_power_kw` | Dispatches per role; compound stages split power between machine types |
| `_hot_spot_suggestions` | Inspects `summary.by_role`, emits actionable notes when one role > 50 % of machines |
| `_pick_recipe_fluid_preferred` | Recipe selection: prefer recipes with most fluid ingredients (foundry casting > furnace); drops candidates whose machine is locked under `tech_state` |
| `_tech_locked_machines` | Returns frozenset of machine keys locked by the given `tech_state` |
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
| `solve_asteroid_reprocessing_loop` | 0.80 | 2 (crusher) | no (quality-only) | 0 |
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
- With `--location fulgora` (`forbid_ore_routes`): only the quality-transparent FLUID raws of `RAW_TO_CHUNK` (water) survive; solid ores/chunks are dropped so no metal can route back to a mined ore. Combined with the recipe-selection filter (ore + `molten-*` routes rejected), metals terminate at their scrap-reachable plate form and the scrap source supplies them.

Routing per leaf raw:
- Fluid → `fluid_input` (quality-transparent).
- Asteroid chunk → asteroid-reprocessing path (skipped under `--no-asteroids` / `--location fulgora`).
- Mined raw with planet unlocked → `mined-raw-self-recycle`.
- Scrap-reachable solid (Fulgora) → scrap-quality-source basket.
- Otherwise → fail-fast with actionable `add --planets X` hint.

### Shuffle enumeration + selection

The planner discovers cross-item shuffle candidates by introspecting the dataset (no hardcoded recipe list).  A candidate is a recipe that:

1. Produces an item I (`allow_productivity` is NOT filtered — buildings/modules/military qualify; the flag is forwarded into `solve_shuffle_loop` so prod-bearing slot splits are disabled where disallowed)
2. Has a corresponding `<I>-recycling` recipe that returns 2+ distinct **solid** items (multi-output filter — single-output recyclers are degenerate self-recycles already covered by `solve_self_recycle_target_loop`)

The recycler's solid outputs need **not** be a subset of the recipe's solid ingredients (the recycler returns the assembler-variant ingredients regardless of which cast variant is chosen — e.g. foundry LDS has 1 solid in, 3 solids returned).  The greedy selector derives valid primaries as `solid_ingredients ∩ solid_recycle_returns` and treats the remaining returns as byproducts.

When multiple cast-recipe variants exist for the same output (e.g. `casting-low-density-structure` foundry vs `low-density-structure` assembler), `enumerate_shuffle_candidates` picks the **fluid-preferred variant** — most fluid ingredients = most quality-transparent inputs = best legendary efficiency.  For LDS this picks the foundry variant (1 solid input + 2 fluids).

Stock Space Age yields **~197 candidates** (buildings, modules, military, and end-game gear included since the `allow_productivity` filter was dropped).  The core multi-ingredient picks:

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

`TECH_GATES` declares what each tech name unlocks: a list of machines (`recycler`, `foundry`, `electromagnetic-plant`, `cryogenic-plant`, `biochamber`).  Quality-module *tier* is no longer gated here — `--quality-module-tier` is self-declaring, and module/machine *quality* is bounded by `--target-quality` instead (see below).

When a primary machine is locked, `_machine_for_recipe` consults `CATEGORY_FALLBACK` for an alternative:
- `electronics` / `electronics-with-fluid` / `pressing` → assembler-N (these are categories that assembler-3 natively supports).
- `*-or-assembling` → assembler-N.
- `*-or-chemistry` / `chemistry-or-cryogenics` → chemical-plant.
- Categories without an entry (`metallurgy`, `cryogenics`, `electromagnetics`, `organic`) have no fallback — recipes routing through them fail-fast with an actionable hint naming the missing tech.

Quality ceiling is set by `--target-quality` (the assumption: if you've researched epic/legendary quality you'd be targeting it, not rare).  `--module-quality` defaults to `--target-quality` and `plan()` fails-fast if `--module-quality` or `--machine-quality` exceeds it — you can't have modules or machines of a quality you haven't researched.

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
    "biolab", "captive-biter-spawner",   # V3 item 4 (Gleba/cryo buildings)
    "steel-plate",                       # wrap-and-recycle (steel-chest) target
])

# Self-FEED targets (ingredient = output; LP-based solver, no auto-compare)
SELF_FEED_TARGETS = frozenset(["pentapod-egg", "raw-fish"])

# Inherent prod by machine
MACHINE_INHERENT_PROD = {
    "foundry": 0.5, "electromagnetic-plant": 0.5, "biochamber": 0.5,
    # all others 0
}
```

---

## Tests

`dev/test_quality_planner.py` — **345 tests**, 46 classes.

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
| `TestShuffleEnumeration` | `enumerate_shuffle_candidates` returns multi-output-recycler candidates (~197 in stock Space Age); LDS picked with foundry variant; iron-stick / copper-cable excluded; cached per dataset |
| `TestShuffleSolver` | Generic `solve_shuffle_loop` matches legacy LDS solver byte-for-byte; positive yields for advanced-circuit / engine-unit; `compute_shuffle_stage` produces machine counts + byproducts; inherent prod auto-resolved per machine |
| `TestShuffleSelection` | Greedy picks LDS for plastic; no shuffle when no overlap; byproducts cover other leaves (single activation); empty/disjoint inputs handled |
| `TestEnableShufflesAll` | `--enable-shuffles all` sentinel activates every applicable shuffle; target item excluded from primaries (no quantum-processor shuffle for processing-unit target); unknown shuffle name errors; combines with `--assembly-modules` |
| `TestSelfRecycleTarget` | superconductor/holmium-plate/tungsten-carbide as targets; ingredients in normal_solid_input |
| `TestAssemblyModules` | `--assembly-modules` cuts machines >5×; `_assembly_prod_bonus` helper edge cases |
| `TestGlebaPartial` | Gleba bio-targets (bioflux, plastic-bar→bioplastic, sulfur→biosulfur, lubricant→biolubricant). **Spoilage NOT modelled.** |
| `TestStagePower` | Every stage has `power_kw`; compound stages split correctly; biochamber reports 0 (burner) |
| `TestMachineQuality` | `--machine-quality` applies `MACHINE_QUALITY_SPEED` to assembly + crusher + recycler; legendary cuts machine count by 1/2.5 |
| `TestPlannerMiners` (C1) | `--miner electric\|big` sizes a drill fleet for solid raws via `cli.compute_miners`: scrap emits a `mining` stage; big vs electric differ 1:5 by base speed; `--research mining-productivity=20` cuts the count to 1/3; miners fold into `total_machine_count`/`total_power_mw`/`summary.by_role` (Option A: `total == sum(stages)`); `format_human` renders `[mining]`; a mined raw on the main body (iron-ore via `--no-asteroids`) counts too; asteroid-only plans get no miners; default miner is electric |
| `TestNoAsteroids` | `--no-asteroids` routes via `MINED_RAW_NO_ASTEROID_FALLBACK`; fail-fast names the missing planet |
| `TestLocationFulgora` | `--location fulgora` scrap-only sourcing: zero `asteroid_input`, metals from scrap, `forbid_ore_routes` picks plain `copper-cable`, auto-unlocks EM-plant + recycler, unsourceable solid fail-fast. **Fluid sub-chains:** qm2 plan emits a `fluid-chain` stage producing `sulfuric-acid` on `chemical-plant` (tagged `fluid_target`); `fluid_input` holds `heavy-oil` not `sulfuric-acid`; `fluid_chain_scrap_draw` (ice/iron-plate) is scrap-reachable and credited against overflow; fluid-chain machines fold into `total_machine_count` + `summary.by_role`; off-Fulgora `processing-unit` keeps `sulfuric-acid` as a raw with no fluid-chain stage. |
| `TestQualityScrapSeeding` (C3) | Mined scrap inherits quality from quality modules in mining drills. Verifies scrap required and recycler machine count drops; larger quality module capacity (big drill vs electric) yields larger drop; disabling drill quality modules reproduces the C1 scrap baseline. |
| `TestScrapUpcycleLoops` (C4) | Closed-loop plate upcycling on Fulgora. Verifies scrap requirements drop significantly; scrap-upcycle-loop stages are correctly sized/counted and displayed under the `[upcycle]` tag in `format_human`; disabling loops recovers baseline. |
| `TestStageSummary` | `summary.by_role` aggregates machines/power/stage_count per role; pcts sum to 100 |
| `TestHotSpotAdvisor` | Helper unit tests + end-to-end notes; suppresses suggestions when nothing actionable |
| `TestTechGating` | `--tech NAME=LEVEL` end-to-end: recycler-locked fail-fast, foundry/EM-plant fallback, cryogenic unreachable, partial-lock baseline parity, `_parse_tech_state` validation (machine techs only), `tech_state` is a required kwarg |
| `TestGlebaTargets` (V3 item 4) | `biolab`/`captive-biter-spawner` in `SELF_RECYCLE_TARGETS`; auto-comparator picks Path B for tungsten-carbide, plans succeed for captive-biter-spawner (post-audit Path B may now win); explanatory notes always present; shuffle enumeration includes buildings + modules + military + endgame; single-output recyclers excluded; `tank`/`biochamber`/`capture-robot-rocket`/`productivity-module-3` plan as shuffle targets; shuffle DP correctly skips prod-bearing slots when recipe has `allow_productivity=False`. |
| `TestSelfRecycleIntermediate` (post-2026-05-08 audit) | 14 previously-failing endgame targets now plan: `electromagnetic-plant`, `foundry`, `mech-armor`, `fusion-reactor`, `quality-module-3`, `metallurgic-/electromagnetic-/cryogenic-science-pack`. Verifies normal-quality inputs propagate (`holmium-solution` in `normal_fluid_input`). Verifies `summary.by_role` includes `self-recycle-target`. Verifies linear scaling under rate doubling. Verifies Pass 2 deduplicates intermediates so duplicate `order` entries don't re-emit. |
| `TestDispatchMemoization` (post-2026-05-08 audit) | Solver kernel called once per unique `(item, env)` key; Path A/B decision cached and re-used; per-`plan()` cache isolation (no cross-call leak); cycle detection via pre-populated `_in_flight` forces Path A with explanatory note; solver cache keyed by env (epic-quality variant gets a fresh kernel call). |
| `TestCoProductIncidental` (shipped 2026-05-14) | `incidental_byproduct_legendary` / `_credited` / `_overflow` fields always present (empty when no multi-output recipe active).  `iron-plate @ vulcanus` emits stone byproduct as overflow (no stone demand).  `concrete @ vulcanus` emits 4.8 legendary stone/min, all credited, dropping mined-recycle target from 60 to 55.2 stone/min.  Surplus + credit notes appear in `notes`.  Linear scaling under rate doubling.  Fluid byproducts excluded from helper output.  `format_human` renders an `Incidental Co-Products` section when non-empty.  `_plan_self_recycle_target` sub-plan emits the empty fields. |
| `TestCoProductDriven` (shipped 2026-05-14) | `enumerate_co_product_drivers` returns the expected stock candidates (lava casting × 2 for stone, processing recipes for seeds, etc.) sorted by descending per-craft yield.  Default off — no `driver_overflow` and no `co-product-driver` stage.  Explicit `--enable-driver molten-iron-from-lava` on `stone-wall @ vulcanus` activates the foundry stage, eliminates the stone mined-recycle stage, surfaces molten-iron in `driver_overflow`, drops total machines >10×.  `--enable-drivers all` picks the highest-yield candidate (copper variant with 15 stone/craft).  Unknown recipe key fails-fast.  Driver skipped when its fluid ingredient (lava) needs an unlocked planet (vulcanus).  Driver's calcite ingredient routes through the asteroid chain.  Linear rate scaling.  `format_human` renders `[driver]` stage line + `Driver Overflow` section.  Sub-plans (self-recycle target) include empty `driver_overflow` field. |
| `TestModuleConfigSurface` | Quality-loop stages carry `module_config_per_tier` (scrap recyclers = `4x quality-N-Q`); `format_human` renders a `modules:` line for scrap / asteroid-reprocessing / mined-raw stages; `_module_config_summary` collapses uniform per-tier configs, lists when they vary, handles empty / zero-slot |
| `TestModuleSpeedPenalty` | `_module_speed_mult`: quality −5%/slot (×0.8 at 4 slots), prod −5/−10/−15% per tier, combined, floored at 0.2; penalty is wired into the loop stages (neutralising it lowers the asteroid-crusher-dominated iron-plate plan by ~×1.11) |
| `TestParseResearch`, `TestHelpers` | Argument parsing and helper functions |

Targeted bands not committed expectations — the wiki-yield tests use a 5 % tolerance because module/probability rounding accumulates differently from FactorioLab's reference numbers.

---

## Gotchas (institutional knowledge)

- **Module speed penalties are applied via `_module_speed_mult`, not baked into the SPEED constants.** Recyclers/crushers run all-quality slots (uniform −20%/−10%), assembly/cast legs use the tier-0 (`cfg0`) representative config. The penalty multiplies the *effective speed* (so machine counts rise: recyclers ×1.25, crushers ×1.11). **Known gap:** the self-feed LP (`solve_self_feed_target_loop`, pentapod-egg) does NOT apply the penalty — its costs are per-config; pentapod-egg is the one niche path affected.
- **The `1/(1−retention)` craft-volume estimate is kept deliberately — it's accurate, not just "MVP".** A 2026-05-26 investigation built the exact per-tier expected-crafts recursion `C[t]` (mirrors `V[t]`) and compared: the aggregate is within **≤1.3%** of exact across all targets (recyclers self-retention 0.25; crushers self-retention 0.4 — *not* the kernel's 0.8 yield-retention, which counts cross-fed byproduct chunks and must NOT be used for self-loop craft counting). The exact version was reverted: ≤1.3% gain doesn't justify the DP complexity or the self-vs-total-retention footgun. Don't redo it.
- **`RAW_TO_CHUNK` ≠ all raws.** It only contains items actually produced by crushing recipes. Mined-only raws (coal, stone, tungsten-ore, scrap, holmium-ore, uranium-ore, gleba bio-raws) live in `MINED_RAW_PLANETS`.
- **Use `advanced-*-asteroid-crushing` (2 outputs), not basic.** A V1 bug silently produced 0 copper-ore because `metallic-asteroid-crushing` only outputs iron-ore.
- **Self-recycling items as test targets:** many "obvious" V2 candidates are self-recycling and fail fast as intermediates. Use `electrolyte`, `low-density-structure`, `battery`, `artillery-shell`, `processing-unit`, `tungsten-plate` as test targets when `superconductor`/`holmium-plate`/`tungsten-carbide` are wrong (they only work as TARGETS via `_plan_self_recycle_target`).
- **Holmium-ore is not in `cli.build_raw_set("fulgora")`** — it's a scrap-recycling byproduct. The walker has a second pass that adds `MINED_RAW_PLANETS` entries when any of their planets is unlocked.
- **Fulgora `battery` test gotcha:** battery's only chemistry raw is sulfur (asteroid-reachable), so coal isn't needed. Use `electrolyte` to genuinely exercise holmium-ore.
- **Oil-recipe selection picks `basic-oil-processing`** because it has fewer fluid byproducts (`_pick_recipe_fluid_preferred` picks lowest-complexity).
- **`--prod-module-tier` defaults to 3.** No speed modules — speed doesn't reduce ingredient demand, and the planner sizes by throughput.
- **Walker passes must use the SAME `eff_prod`.** `_assembly_prod_bonus` is called identically in both passes — if they diverge, demand propagation upstream and stage `inputs` rates will not match.
- **LDS shuffle saturation:** when `research_prod` saturates the +300 % cap, per-cycle return ratio `r → 1.0` and machine count diverges. Clamped to `r=0.999` (~1500 machines for 60/min). Mathematically correct in the limit; practically a tell that the planner should split into multiple parallel loops with smaller per-tier prod configs.
- **Argparse % escaping.** Help strings containing `%` must escape as `%%` — argparse format-substitutes them otherwise (`--assembly-modules` and `--machine-quality` flags both have `%%`).
- **`--tech` default is locked.** A bare CLI invocation now produces an empty `tech_state={}` and fails-fast on the recycler check. Library callers (incl. tests) MUST pass `tech_state` — there is no default. Use `qp.ALL_TECH_UNLOCKED` for the legacy "fully researched" baseline. This was a deliberate breaking change to make the user's research state explicit (V3 item 2).
- **Shuffle DP solvers ignore tech_state.** `solve_shuffle_loop` / `compute_shuffle_stage` use `cli.get_machine` directly and do not consult `tech_state`. If the user enables a shuffle whose cast machine is locked (e.g. `--enable-shuffle low-density-structure --tech tungsten-carbide=0`), the shuffle still runs as if the foundry exists. The main-chain walker and `_pick_recipe_fluid_preferred` correctly gate locked machines, so this only matters when the user explicitly opts-in to a shuffle that requires a locked machine.
- **Auto-comparator changes path-A behaviour for existing self-recycle targets** (V3 item 4). Adding `biolab`/`captive-biter-spawner` was easy; the substantial change was always-on auto-compare for ALL items in `SELF_RECYCLE_TARGETS`. Some pre-V3-item-4 plans now route via Path B (ingredient-upcycle) when it's cheaper — `tungsten-carbide` (480 vs 1106) and `holmium-plate` are the visible cases. Existing tests that assumed `self-recycle-target` stage presence had to be updated to use a Path-A-winning target like `superconductor`. Path A still wins when Path B's chain hits a self-recycling intermediate.
- **`enumerate_shuffle_candidates` returns ~197 items, not 16.** Dropping the `allow_productivity=True` filter (V3 item 4) broadened it dramatically. Greedy shuffle selection still scales fine because most candidates don't overlap with any given chain's leaves.
- **`_DispatchCache` is per-`plan()` invocation** (not module-level). Different calls have different planet sets / tech / module quality / etc., all of which change costs. Recursive Path B re-entries SHARE the cache (memoization across the chain) — but the cache is fresh on every top-level `plan()` call.
- **Pass 1 defers dispatch to end-of-BFS.** When the walker hits a blocklist intermediate it adds it to `pending_dispatch` and resumes BFS rather than dispatching immediately. Dispatch resolution runs once at the end with fully-accumulated demand. This avoids stale-rate sub-plans when an intermediate is consumed by multiple parents discovered at different BFS depths.
- **Path A is the cycle-fallback.** When `choose_path_self_recycle` is entered with `item in _in_flight`, it forces Path A and tags the result with `forced self-recycle (cycle detected through ...)`. Path A is the only branch that doesn't recurse through the dispatcher, so it always terminates.
- **Walker Pass 2 dedupes `order` entries.** A `pass2_emitted: set[str]` guards against re-emitting the same item if it appears multiple times in `order` (which can happen via interaction between BFS, dispatch, and `seen` in pathological chains). Without this guard, mech-armor and similar wide chains emit duplicate `self-recycle-target` stages.
- **Aggregating intermediate sub-plans uses `_dispatch_out`, not a cache diff.** Walker writes the keys it directly dispatched into a kwarg-passed set. Plan() reads only those, NOT all of `_cache.intermediates` — a recursive Path B plan() has already aggregated its own inner intermediates' `normal_solid_input` into its own, so the outer level reading the full cache would double-count.
- **`_force_tree_walk` (top-level) and `_force_tree_walk_for` (walker) are different.** `_force_tree_walk=True` on `plan()` skips the SELF_RECYCLE_TARGETS dispatch at top level (used by Path B re-entry). `_force_tree_walk_for=frozenset({item})` on `walk_recipe_tree` makes the walker treat `item` as a normal recipe even though it's in the blocklist (used by Path B inside `choose_path_self_recycle` so it can attempt the ingredient-upcycle of its own item without the dispatcher catching it).
- **Decision cache is rate-independent.** Both Path A and Path B scale linearly with rate, so the choice doesn't depend on rate. The cache stores `"A"`/`"B"` keyed by `(item, env_signature)`. On hit, only the chosen branch re-runs at the actual rate. This is the main memoization win for deep chains where the same item appears at different rates.

---

## Non-goals

- **Not a replacement for `cli.py`.** That remains the general-purpose calculator for non-quality math (raw/uncommon/rare throughput, bus sizing, bottleneck analysis).
- **Not a blueprint generator.**
- **Not a UI / dashboard feature.** JSON output is consumable by external tooling.
- **Not a modded-recipe tool.** Vanilla + Space Age only.
- **Not a vanilla+quality tool.** Vanilla quality is a deferred design space — needs different raw-source strategy entirely (no asteroids, narrower planet set).
