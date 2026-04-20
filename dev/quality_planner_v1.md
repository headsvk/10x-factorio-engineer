# Quality Planner V1 — MVP Plan

A separate Python tool that answers:

> *"Given my research and module tier, what's the cheapest way to make N legendary `<item>` per minute?"*

Lives alongside `10x-factorio-engineer/assets/cli.py`, does not modify it. Uses the same Space Age dataset.

---

## Status (2026-04-20)

**V1 shipped.** Implementation in `dev/quality_planner.py` (~900 LoC) and `dev/test_quality_planner.py` (50 tests, all passing). Builds on top of `cli.py` as a library.

**What works:**
- DP kernel (backward induction over tiers) with per-tier module config optimization
- Asteroid reprocessing loop (80% retention) as the canonical legendary raw source
- Crushing stage (legendary chunks → legendary ores)
- Fluid-transparent recipe preference (prefers foundry casting for iron/copper/steel plates and cable)
- `--item`, `--rate`, `--module-quality`, `--research NAME=LEVEL`, `--assembler-level`, `--format json|human`
- Fail-fast errors for unsupported chains (planet exclusives, self-recycling, no asteroid path)

**Current item scope — narrower than originally planned.** Because Nauvis chemistry requires petroleum-gas for plastic-bar and sulfur, the following asteroid-only chain items fail fast in V1: `plastic-bar`, `sulfur`, `processing-unit`, `artillery-shell`, `low-density-structure`, most Space Age modules, military items using any of those. V1 currently works cleanly for: iron-plate, copper-plate, iron-gear-wheel, copper-cable, electronic-circuit, steel-plate, stone-brick, and items whose ingredients are subsets of these.

**Deviations from original plan:**
1. The plan cited artillery-shell and processing-unit as V1 examples — they don't work because plastic/sulfur aren't asteroid-reachable on Nauvis alone. See V2 items below for paths that would cover them.
2. Assembly stages run with no modules (conservative baseline). Per-stage module optimization deferred to V2.
3. Hardcoded `load_data("nauvis")` — no multi-planet support yet (see V2).

---

## Scope

### In V1

- **Nauvis-style assembly items** whose raws are all obtainable via **asteroid reprocessing** (iron ore, copper ore, coal → plastic/sulfur, stone, calcite, ice → water) — e.g. electronic circuits, processing units, artillery shells, modules, military items
- **DP-based quality loop solver** (backward induction over tiers; see `dev/quality_planner_v1_algorithm.md` — inlined below)
- **Asteroid reprocessing as the canonical legendary raw source** (80% retention vs 25% recycler)
- **Fluid quality transparency** (foundry plate casting, chemical-plant fluid recipes — fluids carry no quality; solids carry it)
- **Multi-ingredient assembly correctness**: all solid ingredients must be legendary for a legendary output craft to run
- **Productivity research per recipe family** (casting, processing-unit, plastic-bar, asteroid-productivity, etc.) with the +300% cap applied per-tier
- **Single objective**: minimize total asteroid input per legendary output per minute
- **Output**: asteroid chunk rates, per-stage machine + module counts, yield %, human-readable summary

### Deferred to V2+

**High-value next (unlocks items blocked by V1):**

- **Multi-planet unlock flag** (`--planets nauvis,vulcanus,...`). Broadens surface-condition filtering so recipes gated to specific planets become available. Cheap to add (~20 LoC) but buys little on its own — most quality-relevant recipes (foundry casting, EM-plant) aren't actually planet-gated once the machine is built. Real value comes paired with the items below.
- **Indirect upgrade loops ("LDS shuffle" and siblings).** Cross-item quality loops where one item's recycle output upgrades another item. The classic: cast `low-density-structure` in foundry with quality modules → recycle legendary LDS → recover legendary `plastic-bar` + `copper-plate` + `steel-plate`. This unlocks legendary plastic/sulfur/processing-unit/artillery-shell on pure-Nauvis + asteroid. Structurally different from V1's single-item loops — needs a graph-search phase (find quality-bearing recipes whose ingredient set intersects the target, solve jointly). Similar shuffles exist for blue circuits, rails, and other multi-ingredient solid-output items. ~200–300 LoC + new solver logic.
- **Planet exclusives as quality sources**: tungsten (Vulcanus — drill quality modules + tungsten-carbide self-recycle), holmium (Fulgora — scrap recycling with quality modules), fluorine / lithium brine (Aquilo), Gleba biolocals (yumako, jellynut, bioflux, pentapod eggs). Each needs its own quality loop specialization.

**Other deferred:**

- Self-recycling items: superconductor, holmium-plate, quality asteroid chunks fed directly
- Asymmetric recipe pairs: fuel cell ↔ U-238 (centrifuge), biolab / captive spawner exotic loops
- Spoilage modeling (Gleba time constraints)
- Module bootstrap / staging recommendations (V1 assumes target module tier is already available)
- Beacon speed-module quality penalties (V1 assumes no beacons in loops)
- Per-stage assembly module optimization (V1 leaves assembly stages modules-off as conservative baseline)
- Alternative objectives (fewest machines, fewest modules, smallest footprint, UPS)
- Target tiers below legendary (epic-only, rare-only loops)
- Probabilistic output recipes with quality propagation (uranium processing)
- Circuit-conditions / blueprint output
- Vanilla+quality-mod support (no Space Age, no asteroids) — would need a different raw-source strategy entirely

### V1 failure modes

Fail loud, not silent. If the target item requires any deferred capability, error out with a specific message:

- `ERROR: item '<x>' requires '<raw>', which needs planet '<P>' — not supported in V1`
- `ERROR: recipe '<r>' is self-recycling (output recycles to itself) — not supported in V1`
- `ERROR: no asteroid path to required raw '<raw>'`

---

## Input

```
python dev/quality_planner.py \
    --item <item-id> \
    --rate <N> \
    --module-quality <normal|uncommon|rare|epic|legendary> \
    [--research <NAME=LEVEL> ...] \
    [--assembler-level <2|3>] \
    [--format <json|human>]
```

Defaults:
- `--module-quality legendary`
- `--assembler-level 3`
- `--format human`
- Always Space Age (quality requires it); no `--location` flag (asteroid path is location-independent, and planet exclusives are V2).

---

## Output

```json
{
  "target": {"item": "artillery-shell", "rate_per_min": 60, "tier": "legendary"},
  "asteroid_input": {
    "metallic-asteroid-chunk": 412.3,
    "carbonic-asteroid-chunk": 187.5,
    "oxide-asteroid-chunk": 28.1
  },
  "stages": [
    {
      "role": "asteroid-reprocessing",
      "chunk": "metallic-asteroid-chunk",
      "machine": "crusher",
      "machine_count": 38,
      "yield_pct": 3.14,
      "module_config_per_tier": {
        "normal":   {"craft": "n/a", "recycle": "2x quality-3-legendary"},
        "uncommon": {"craft": "n/a", "recycle": "2x quality-3-legendary"},
        "rare":     {"craft": "n/a", "recycle": "2x quality-3-legendary"},
        "epic":     {"craft": "n/a", "recycle": "2x quality-3-legendary"}
      }
    },
    {
      "role": "raw-crushing",
      "recipe": "metallic-asteroid-crushing",
      "machine": "crusher",
      "machine_count": 4,
      "output": "iron-ore@legendary: 60/min, copper-ore@legendary: 30/min"
    },
    {
      "role": "casting",
      "recipe": "casting-iron",
      "machine": "foundry",
      "machine_count": 2,
      "inputs": {"molten-iron": "fluid-transparent", "iron-ore@legendary": 60},
      "output": "iron-plate@legendary: 60/min",
      "note": "fluid-transparent: molten-iron does not require quality"
    },
    {
      "role": "assembly",
      "recipe": "artillery-shell",
      "machine": "assembling-machine-3",
      "machine_count": 5,
      "inputs_all_legendary": true
    }
  ],
  "total_machine_count": 87,
  "notes": ["chain uses foundry casting for legendary plates (fluid-transparent path)"]
}
```

Human format is a terminal-friendly rendering of the same data.

---

## Architecture

```
┌───────────────────────────────────────────────┐
│ CLI entry (dev/quality_planner.py)            │
└─────────────────┬─────────────────────────────┘
                  ▼
┌───────────────────────────────────────────────┐
│ Planner                                       │
│  - walk recipe tree for target item           │
│  - prefer fluid-transparent recipes           │
│  - attach quality loop at asteroid sources    │
│  - scale stages to target rate                │
└─────────────────┬─────────────────────────────┘
                  ▼
┌───────────────────────────────────────────────┐
│ DP Loop Solver (core kernel)                  │
│  - back-substitution over tiers               │
│  - per-tier module optimization (brute per    │
│    tier, constant-time inner eval)            │
│  - productivity cap (+300%) per-tier          │
└─────────────────┬─────────────────────────────┘
                  ▼
┌───────────────────────────────────────────────┐
│ Recipe / data layer                           │
│  - reuse cli.py loader, recipe index, raw set │
│  - fluid detection (existing build_fluid_set) │
│  - asteroid recipe table (new)                │
└───────────────────────────────────────────────┘
```

Zero new dependencies. Stdlib only. Share data files with `cli.py`.

---

## Core algorithm: DP loop solver

**Insight**: quality transitions are monotonic (tier only goes up or stays) → the transition matrix is upper-triangular → solve by back-substitution from tier 5 downward. Per-tier module config is chosen independently.

```python
def solve_loop(recipe, machine, research_bonus, module_quality,
               is_asteroid_reprocessing=False):
    """
    Returns (legendary_yield_per_tier1_input, module_configs_per_tier).

    For a standard craft+recycle loop:
        - craft step has N module slots, prod modules allowed if recipe allows
        - recycle step has recycler's 4 slots, prod modules not allowed

    For asteroid reprocessing:
        - "craft" is a no-op (identity)
        - "recycle" is the reprocessing recipe: 80% productivity retention,
          2-slot crusher, quality modules only
    """
    V = {5: 1.0}
    configs = {}
    for t in (4, 3, 2, 1):
        best_v = 0.0
        best_cfg = None
        for cfg in enumerate_tier_configs(t, machine, is_asteroid_reprocessing):
            p = transition_probs(t, cfg, recipe, research_bonus, module_quality)
            # p[s] for s in (t..5) = fraction of a tier-t unit landing at tier-s
            # remainder (1 - sum p[s]) is destroyed
            v_numer = sum(p[s] * V[s] for s in range(t + 1, 6))
            v_denom = 1.0 - p[t]  # closed-form geometric sum over self-loops
            v = v_numer / v_denom if v_denom > 1e-12 else 0.0
            if v > best_v:
                best_v = v
                best_cfg = cfg
        V[t] = best_v
        configs[t] = best_cfg
    return V[1], configs
```

**Complexity**: 4 tiers × `(slots_craft + 1) × (slots_recycle_if_prod_allowed + 1)` inner evals. EM plant: 4 × 6 × 1 = 24 evals. Each eval: O(5) arithmetic. Sub-millisecond per loop.

**Cap enforcement**: `prod_eff = min(4.0, inherent × (1 + building + research + module_prod))` applied per-tier before computing `p`.

**Tier-skip probabilities** (game-fixed, not configurable): 90% +1, 9% +2, 0.9% +3, 0.1% +4.

---

## Planner logic

1. **Walk target recipe tree** (reuse `cli.py`'s `Solver` as a library, or reimplement the walk). At each node collect the ingredient set.
2. **Recipe selection per node**: when multiple recipes exist, prefer the one with the **largest fluid-input fraction** (foundry casting > furnace smelting for plates, chemical-plant fluid routes > solid routes where applicable). This collapses the "must be legendary" input surface to the smallest solid subset.
3. **Terminal check**: every leaf must be a raw reachable from asteroid crushing. If not → fail with specific error.
4. **Attach quality loops only at asteroid-reprocessing stages**. All downstream stages receive legendary solids and run straight-through (assembly with all-legendary inputs produces legendary output with no additional quality roll needed — though any quality rolls from modules still fire as a bonus, which V1 ignores for simplicity).
5. **Scale**: walk back from target rate, propagate required rates upstream. At each reprocessing stage, `required_reprocessed_chunks / yield = required_raw_chunks`.
6. **Machine counts**: standard rate / (machine_speed × effective_prod).

**Why loops only at asteroid sources (V1 simplification)**: because all solid raws come from asteroids and fluids are quality-transparent, upgrading raws once upstream is sufficient. Mid-chain upcycle loops become unnecessary for the V1 target scope. This is what Reddit consensus has landed on and matches the actual meta.

---

## Data model additions

Reuse from `cli.py`:
- `load_data("nauvis")` — Space Age dataset loader
- `build_fluid_set(data)` — item keys where `type == "fluid"`
- `build_recipe_index(data)` — item → recipes
- `RECIPE_DEFAULTS`, `RECIPE_DEFAULTS_BY_LOCATION` — recipe preference maps

New module-level tables in `dev/quality_planner.py`:

```python
# Asteroid reprocessing loop recipes (chunk → itself, with quality chance)
ASTEROID_REPROCESSING_RECIPES = {
    "metallic-asteroid-chunk":  "metallic-asteroid-reprocessing",
    "carbonic-asteroid-chunk":  "carbonic-asteroid-reprocessing",
    "oxide-asteroid-chunk":     "oxide-asteroid-reprocessing",
}

# Chunk → crushing recipe that yields raws (consuming the chunk)
ASTEROID_CRUSHING_RECIPES = {
    "metallic-asteroid-chunk":  "metallic-asteroid-crushing",
    "carbonic-asteroid-chunk":  "carbonic-asteroid-crushing",
    "oxide-asteroid-chunk":     "oxide-asteroid-crushing",
}

# Crusher productivity retention constants
CRUSHER_INHERENT_PROD = 1.00        # crushing recipe gives full productivity
REPROCESSING_RETENTION = 0.80       # reprocessing: 80% chance to keep chunk
RECYCLER_RETENTION     = 0.25       # recycler: 25% of ingredients returned

# Items known to be self-recycling (V1: blocklist, fail fast)
SELF_RECYCLING_BLOCKLIST = frozenset([
    "tungsten-carbide", "superconductor", "holmium-plate",
])
```

---

## CLI surface

```
python dev/quality_planner.py --item artillery-shell --rate 60 \
    --module-quality legendary \
    --research asteroid-productivity=5 \
    --research processing-unit-productivity=13
```

Output: `--format human` by default (printable table). `--format json` for downstream tooling / dashboard integration.

Separate entry point from `cli.py`. No changes to existing CLI.

---

## Tests (`dev/test_quality_planner.py`, new file)

| Test class | Coverage |
|---|---|
| `TestDPKernel` | Reproduces wiki yield numbers within ±1% (EM plant 0.177%, assembler-3 0.046%, foundry 0.134%, chem-plant 0.034%); prod cap clamps at +300%; legendary modules give ~7× uplift over normal |
| `TestAsteroidReprocessing` | 80% retention math; metallic/carbonic/oxide yields; production of legendary chunks → legendary raws via crushing |
| `TestFluidTransparency` | Planner picks `casting-iron` (foundry) over `iron-plate` (furnace) when foundry available; fluid inputs not counted in legendary solid requirement |
| `TestAssemblyPropagation` | Legendary inputs → legendary output; mixed-quality inputs would fail (not tested here, game-level constraint) |
| `TestResearchProd` | Research bonus shifts per-tier prod; cap phase transition flips optimal config from prod+quality to all-quality |
| `TestFailFast` | Tungsten/holmium target items produce specific error messages; no asteroid path errors; self-recycling items blocked |
| `TestEndToEnd` | Legendary artillery shell / processing unit / module @ 60/min — asteroid rates + machine counts within reasonable bounds; regression snapshot |

~40–60 new tests targeted.

---

## Implementation order

1. **DP kernel** (`solve_loop`) + unit tests reproducing wiki yields
2. **Asteroid reprocessing mode** + tests for 80% retention math
3. **Recipe tree walker** (can port from cli.py `Solver` or call cli.py as library) with fluid-transparency recipe preference
4. **Terminal raw check + fail-fast errors** for planet exclusives / self-recycling
5. **Stage assembly + rate scaling**
6. **JSON output** + **human format**
7. **End-to-end regression tests** (legendary artillery shell, legendary processing unit, legendary module)
8. **README entry** + **SKILL.md reference** (new section: "Legendary planning via asteroid reprocessing")

Estimated size: ~600–900 LoC in `dev/quality_planner.py`, ~400–600 LoC in `dev/test_quality_planner.py`.

---

## Open design questions

1. **Reuse cli.py Solver or reimplement tree walk?** Leaning reuse via import — `cli.py` is stdlib-only and already handles recipe selection, surface-condition filtering, and oil systems. Planner adds the quality layer on top.
2. **How strict on "fluid transparency" recipe preference?** Foundry casting requires a molten intermediate that itself requires upstream casting (molten-iron from iron-ore, molten-copper from copper-ore) — does this break the asteroid-only raw assumption? **Answer: no**, because molten-iron casting takes iron-ore as ingredient and iron-ore comes from asteroid crushing. Chain remains asteroid-sourced; the molten intermediate is quality-transparent so it doesn't need its own loop.
3. **Quality rolls during assembly (bonus)?** Assemblers with quality modules still roll quality on final assembly even with legendary inputs (output can only stay at legendary — it's the absorbing state — so extra rolls are wasted). V1 assumes assembly uses prod+speed modules only, no quality, which matches community practice and avoids modeling wasted rolls.

---

## Non-goals (explicitly)

- Not a replacement for `cli.py` — that remains the general-purpose calculator
- Not a full optimizer over objectives — V1 optimizes asteroid input only
- Not a blueprint generator
- Not a UI / dashboard feature (V2 may integrate with the dashboard)
- Not a modded-recipe tool — vanilla + Space Age only
