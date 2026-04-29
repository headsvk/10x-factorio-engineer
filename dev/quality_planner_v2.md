# Quality Planner V2 — Multi-Planet + Mined-Raw Self-Recycle

Follow-up to `quality_planner_v1.md`. Expands the planner's reachable item scope without changing the DP kernel or output contract.

---

## Handoff (start here)

**Entry points:**
- Tests: `python dev/test_quality_planner.py` — 73 tests, ~0.07s, must be green before/after any change.
- Smoke: `python dev/quality_planner.py --item processing-unit --rate 60 --planets nauvis` — should print ~620 machines.
- Code: `dev/quality_planner.py`, ~1500 LoC, stdlib-only, imports `cli.py` as a library.

**Code map** (line numbers, 2026-04-21):
- `solve_recycle_loop` @ 480, `solve_asteroid_reprocessing_loop` @ 571 — V1 DP kernels, unchanged in V2.
- `solve_lds_shuffle_loop` @ 633 — V2 addition, library-only (not called from `plan()`).
- `solve_mined_raw_self_recycle_loop` @ 741 — V2 addition, called from `plan()`.
- `_combined_planet_props` @ 833, `_planet_unlocks_item` @ 824 — planet-aware helpers.
- `_pick_recipe_fluid_preferred` @ 856 — recipe selection, now takes `planets`.
- `walk_recipe_tree` @ 917 — builds the stage DAG, routes leaves by raw type.
- `plan` @ 1124 — top-level orchestrator.
- `format_human` @ 1373, `parse_args` @ 1478, `main` @ 1499.

**Regression anchors** (60/min legendary, module-quality=legendary, no research):
| target | planets | total machines | asteroid chunks/min | mined/min | fluid/min |
|---|---|---|---|---|---|
| `iron-plate` | — | 18.3 | metallic 281, oxide 28 | — | — |
| `processing-unit` | nauvis | 620.2 | metallic 1406, carbonic 703, oxide 59 | coal 321874 | crude-oil 5333 |
| `artillery-shell` | nauvis,vulcanus | 4945.7 | carbonic 5625, oxide 1842 | coal 643749, tungsten-ore 2574996 | lava 9300 |

These numbers are sanity anchors, not committed expectations — if a refactor moves them, investigate. Exact coal/oil counts are high because assembly stages still run modules-off.

**Pending tasks (not in V3 roadmap — these are V2 leftovers):**
- `10x-factorio-engineer/SKILL.md` — add a "Legendary planning" pointer to `dev/quality_planner.py` with the `--planets` flag.
- `README.md` — add a usage example for `--planets`.
- Neither was updated in the V2 commit; a next session should pick these up before starting V3.

**Gotchas discovered during V2:**
- V1 `RAW_TO_CHUNK` listed `coal` and `stone` but no crushing recipe produces them — latent bug that masked `plastic-bar` failing for a different reason. V2's `RAW_TO_CHUNK` is restricted to actual crushing outputs; mined-only raws live in `MINED_RAW_PLANETS`.
- V1 `ASTEROID_CRUSHING_RECIPES` pointed at basic crushing (single-ore output). Copper-plate plans silently got 0 copper-ore. V2 uses `advanced-*-asteroid-crushing` (both ores per recipe).
- Fulgora's `build_raw_set` does NOT include `holmium-ore` — holmium-ore is a scrap-recycling byproduct, not a direct resource. The walker has a second pass that adds `MINED_RAW_PLANETS` entries when any of their planets is unlocked, to cover this.
- Many "obvious" V2 test targets are self-recycling and fail fast: `superconductor`, `holmium-plate`, `tungsten-carbide`, `fusion-power-cell`, `supercapacitor`, `teslagun`, `mech-armor`, `lithium`. Use `electrolyte`, `low-density-structure`, `battery`, `artillery-shell`, `processing-unit`, `tungsten-plate` as test targets instead.
- The `test_fulgora_unlocks_scrap` test previously used `battery` expecting coal — but battery's only chemistry raw is sulfur (asteroid-reachable), so coal isn't needed. V2 swapped to `electrolyte` which genuinely needs holmium-ore.
- `basic-oil-processing` is the chosen oil recipe because it has fewer fluid byproducts (picks lowest-complexity path in `_pick_recipe_fluid_preferred`).

---

## Status (2026-04-26)

**V2 shipped.** **V3-partial shipped:** items 1 (LDS shuffle), 3
(self-recycle targets), 4 (Gleba bio-raws, no spoilage), 5 (per-stage
assembly module optimization), and per-stage power accounting.
`dev/test_quality_planner.py` now at 109 tests (7 new in
`TestLDSShuffleWiring`, 8 new in `TestSelfRecycleTarget`, 8 new in
`TestAssemblyModules`, 8 new in `TestGlebaPartial`, 8 new in
`TestStagePower`, 3 obsolete `TestFailFast` tests removed for the
items that V3 now supports as targets). Zero new dependencies.

Power accounting: every stage gains a `power_kw` field (electric
machines only; burner machines like biochamber report 0).  Output gains
`total_power_mw`.  Compound stages split power between machine types
(self-recycle: craft + recycler; cross-item-shuffle: foundry + recycler).
Helper `_stage_power_kw` dispatches on stage role.

Machine quality: `--machine-quality {normal,uncommon,rare,epic,legendary}`
applies `cli.MACHINE_QUALITY_SPEED` to every assembly / crusher /
recycler machine speed.  Legendary machines (+150% speed) reduce
machine count by 1/2.5; total power scales linearly.  Each assembly
stage is annotated with the chosen `machine_quality` tag.

V3 item 3 (self-recycle targets): items whose recycle returns themselves
(`tungsten-carbide`, `superconductor`, `holmium-plate`, `fusion-power-cell`,
`lithium`) can now be used as planner targets. New solver
`solve_self_recycle_target_loop` runs the recycler-only DP (distinct from
the shuffle-style `solve_recycle_loop` that re-crafts). Ingredients are
consumed at NORMAL quality (quality rolls happen during craft+recycle), so
they go into `normal_solid_input` / `normal_fluid_input`. Output adds the
`self-recycle-target` stage role. Items still fail-fast when used as
INTERMEDIATE ingredients in another chain (must be supplied externally).

V3-partial adds the `--enable-lds-shuffle` flag (default off): when on, the
plastic-bar leg of any chain is replaced by an LDS-shuffle stage
(foundry-cast LDS + recycle for legendary plastic-bar + copper/steel
byproducts). Coal moves from `mined_input` (legendary self-recycle) to
`normal_solid_input` (chem-plant input). Petgas goes through a normal-quality
oil-processing leg (`normal_fluid_input`).

`walk_recipe_tree` now accepts `extra_raws` (treat items as supplied
externally, skip recursion) and `byproduct_credits` (subtract from initial
demand, propagates downward through the chain). The shuffle wiring uses both:
re-walks main chain with plastic-bar as extra_raw, then re-walks again with
capped byproduct credits applied. Surplus byproducts (when downstream demand
< emitted) are flagged in `notes` and reported in
`shuffle_byproduct_overflow`.

Output additions: `normal_solid_input`, `normal_fluid_input`,
`shuffle_byproduct_legendary`, `shuffle_byproduct_credited`,
`shuffle_byproduct_overflow`. New stage role: `cross-item-shuffle` (with
foundry/recycler split, yield%, byproduct dict).

**What V2 unlocks:**
- Items whose chain needs planet-specific raws and fluids: `plastic-bar`, `sulfur`, `processing-unit`, `artillery-shell`, `low-density-structure`, `battery`, `electrolyte`, `holmium-plate`-ingredient items that aren't themselves self-recycling (e.g. `fusion-power-cell` inputs via the chain), `tungsten-plate`, etc.
- Cross-planet chains: items that mix Nauvis chemistry with Vulcanus tungsten or Fulgora holmium.
- Quality source for mined solids that lack an asteroid path: coal, stone, tungsten-ore, holmium-ore, scrap, uranium-ore — all via the recycler self-loop with miner-side quality modules.

**What V2 still doesn't do** (deferred to V3):
- **LDS shuffle / cross-item quality loops** — implemented as a standalone library function (`solve_lds_shuffle_loop`) with full DP but not yet wired into the planner. When attached, it would give a more efficient legendary-plastic path than the new mined-coal self-recycle (especially at high `plastic-bar-productivity` research). See "LDS shuffle — partial" below.
- **Research-state tracking** — the planner still assumes all recipes, module tiers, and machines are unlocked. If the user only has level-1 quality modules or no access to asteroids yet, the planner gives answers that require unavailable tech. Would need a `--unlocked-techs` or `--research-gate` input.
- **Self-recycling items as targets** (`superconductor`, `holmium-plate`, `tungsten-carbide`, `fusion-power-cell`) — still fail fast. Needs a dedicated self-recycle target solver.
- **Gleba spoilage**, per-stage assembly module optimization, beacon effects, alternate objectives, blueprint output — all still deferred.

---

## Scope changes from V1

### Added

1. **`--planets nauvis,vulcanus,fulgora,gleba,aquilo,space-platform`** CLI flag.
   - Widens the raw set by merging per-planet raws (from `cli.build_raw_set`) plus a static `MINED_RAW_PLANETS` table.
   - Fluids discovered from a planet's raw set are added to the fluid raw set (quality-transparent).
   - Solids from a planet's raw set go through the mined-raw self-recycle path below, not the asteroid chain.
   - Surface-condition filter is a max per-property over unlocked planets (e.g. Nauvis ≤ 18 pressure unions with Vulcanus ≤ 4000 pressure = the ceiling of both).

2. **Mined-raw self-recycle loop** (`solve_mined_raw_self_recycle_loop`):
   - Miners accept quality modules → normal ore enters the system at a small quality-upgraded rate.
   - The raw has no asteroid recipe and no reprocessing recipe, so the only loop is: **recycle self → get back a fraction (typically 25%, sometimes 0 for scrap) → reprocess with quality modules**.
   - DP identical to asteroid reprocessing except: retention comes from the recycling recipe's self-output amount, 4 slots instead of 2, no productivity (recycler is quality-only).
   - Covers: `coal`, `stone`, `tungsten-ore`, `scrap` (special: 0 self-retention → one-shot bonus only), `holmium-ore`, `uranium-ore`.

3. **Advanced-crushing recipe table**:
   - V1 used basic `metallic-asteroid-crushing` etc., which only produce a single ore. V2 switches to `advanced-metallic-asteroid-crushing` which produces both iron + copper ore (and analogously both carbon + sulfur, both ice + calcite). Fixes a latent V1 bug where copper-plate silently produced 0 asteroid input.

4. **`mined_input`** and **`fluid_input`** top-level keys in the JSON output, complementing `asteroid_input`.

5. **`mined-raw-self-recycle`** and **`crushing`** stage roles in the stages list, with the same shape as V1 asteroid stages.

### Removed / Fixed

- V1 error message `"not supported — requires planet X"` is now `"add --planets X"` (actionable).
- V1 `RAW_TO_CHUNK` had `coal` and `stone` pointing at chunks that don't produce them (latent bug) — now restricted to actual crushing-recipe outputs (iron-ore, copper-ore, carbon, sulfur, ice, calcite, water).
- V1 `PLANET_EXCLUSIVE_RAWS: dict[str, str]` (single planet per raw) replaced with `PLANET_UNLOCKS: dict[str, tuple[str, ...]]` because tungsten, for example, is only available on Vulcanus but coal/stone are available on Nauvis + Vulcanus + Fulgora.

---

## Data model additions

```python
KNOWN_PLANETS = ("nauvis", "vulcanus", "fulgora", "gleba", "aquilo", "space-platform")

PLANET_UNLOCKS: dict[str, tuple[str, ...]] = {
    # tungsten only on vulcanus
    "tungsten-ore": ("vulcanus",),
    "tungsten-carbide": ("vulcanus",),
    # holmium only on fulgora (via scrap recycling)
    "holmium-ore": ("fulgora",),
    # scrap only on fulgora
    "scrap": ("fulgora",),
    # lava / sulfuric-acid / etc. go through fluid branch
}

MINED_RAW_PLANETS: dict[str, tuple[str, ...]] = {
    "coal":          ("nauvis", "vulcanus"),
    "stone":         ("nauvis", "vulcanus", "fulgora"),
    "tungsten-ore":  ("vulcanus",),
    "scrap":         ("fulgora",),        # self-recycle retention = 0 (byproduct-only)
    "holmium-ore":   ("fulgora",),        # scrap-recycling byproduct, not a direct resource
    "uranium-ore":   ("nauvis",),
}

ASTEROID_CRUSHING_RECIPES = {
    "metallic-asteroid-chunk":  "advanced-metallic-asteroid-crushing",
    "carbonic-asteroid-chunk":  "advanced-carbonic-asteroid-crushing",
    "oxide-asteroid-chunk":     "advanced-oxide-asteroid-crushing",
}
```

---

## Algorithm changes

### Recipe-tree walker

- Signature now takes `planets: frozenset[str]`.
- Raw set starts with the V1 asteroid raws (output of `RAW_TO_CHUNK`), adds `water`, then:
  - Unions in each unlocked planet's fluids from `cli.build_raw_set(data, planet)`.
  - Unions in mined solids from `MINED_RAW_PLANETS` whose planet list intersects `planets`.
- Recipe pick uses `_combined_planet_props(data, planets)` (max per-property) so a foundry-cast recipe that's legal on Vulcanus becomes legal globally once Vulcanus is unlocked.

### Planner routing

For each leaf raw:
- If it's a fluid or water → `fluid_input` (quality-transparent).
- If it's a chunk-derivable raw (`RAW_TO_CHUNK`) → asteroid reprocessing path (V1 behavior).
- If it's in `MINED_RAW_PLANETS` and the user unlocked one of its planets → `mined-raw-self-recycle` stage.
- Otherwise → the V1 fail-fast error, but now with an actionable `add --planets X` hint.

### DP for mined-raw self-recycle

Identical shape to V1's `solve_asteroid_reprocessing_loop`, with constants swapped:

```python
retention = amount_of_raw_in_own_recycling_recipe   # e.g. coal-recycling → 1 coal in → 0.25 coal out
slots     = 4                                       # recycler
prod_allowed = False                                # recycler is quality-only
```

For `scrap` (retention = 0) the DP degenerates to a one-shot: tier-1 → quality distribution from miner quality modules, no loop. We model this as `V[1] = Σ p_upgrade[s]·V[s]` with no self-multiplier.

### LDS shuffle — partial

`solve_lds_shuffle_loop(data, module_quality, quality_module_tier, prod_module_tier, research_prod, foundry_inherent_prod=0.5)` is in the library:

- Foundry cast of `low-density-structure` has only one solid ingredient: plastic-bar. Fluids (molten-copper + molten-steel) are quality-transparent.
- One foundry cast (4 slots, prod+quality mix allowed, inherent +50% prod): `5 × plastic-bar → 1 × LDS`.
- Recycle LDS (4 slots, quality-only, 25% retention): `1 × LDS → 1.25 × plastic-bar` per legendary in.
- Nested DP over both stages gives per-plastic-bar legendary yield.

**Not wired to `plan()`** — when the planner sees `plastic-bar` as a leaf it routes to the asteroid chain, not LDS shuffle. Wiring needs a joint solve because LDS shuffle also produces legendary copper-plate + steel-plate as byproducts, which must be credited against those leaves. That's the V3 cross-item solver.

---

## CLI surface

```
python dev/quality_planner.py --item processing-unit --rate 60 \
    --planets nauvis \
    --module-quality legendary
```

New flag: `--planets P1,P2,...`. Empty → V1 behavior (asteroid-only). Unknown planet name → fail-fast.

Everything else unchanged from V1.

---

## Output additions

```json
{
  "target": {...},
  "asteroid_input": {...},
  "mined_input": {"coal": 321874.5},
  "fluid_input": {"crude-oil": 5333.3, "water": "fluid-transparent"},
  "stages": [
    ...,
    {
      "role": "mined-raw-self-recycle",
      "raw": "coal",
      "machine": "recycler",
      "machine_count": 447.05,
      "yield_pct": 0.0373,
      "normal_mined_per_min": 321874.5,
      "legendary_per_min": 120.0
    }
  ]
}
```

Human format renders a `Mined Raws` and `Fluid Raws` section alongside `Asteroid Input`.

---

## Tests added

| Test class | Coverage |
|---|---|
| `TestPlanetsFlag` (9) | empty planets = V1; unknown planet errors; nauvis unlocks plastic-bar; vulcanus unlocks tungsten-plate; planets listed in output; fluid raws marked transparent; multi-planet chains (artillery-shell w/ nauvis+vulcanus) |
| `TestMinedRawSelfRecycle` (7) | coal positive yield; stone yield matches coal; tungsten-ore; holmium-ore; normal modules worse than legendary; unknown raw returns zero; self-recycle yield strictly worse than asteroid reprocessing (sanity) |
| `TestLDSShuffle` (5) | no-research positive yield; research improves yield; prod cap at +300%; LDS shuffle beats asteroid reprocessing with high plastic-bar research; normal modules worse than legendary |
| `TestOtherPlanetUnlocks` (2) | fulgora unlocks scrap/holmium-ore (electrolyte chain); mined-recycle stage shape in output |

Total: 23 new tests; 73 tests overall; all passing.

---

## V3 roadmap

In priority order:

### 1. Cross-item quality solver (LDS shuffle, rail shuffle, sibling loops)

**Status (2026-04-26): LDS-only path shipped behind `--enable-lds-shuffle`.
Generic shuffle enumeration (rail shuffle, etc.) remains V3.1.**

What landed:
- `--enable-lds-shuffle` CLI flag wires `compute_lds_shuffle_stage` into
  `plan()`. Default off — V2 baseline tests untouched.
- `plastic-bar` walker expansion is replaced by the shuffle stage when the
  flag is set; the normal chem-plant chain runs separately at the shuffle's
  required normal-plastic input rate.
- Byproduct credits (legendary copper-plate, steel-plate) are capped at
  observed demand and applied via a re-walk with `byproduct_credits`.
  Demand for credited items propagates through the chain (verified on
  solar-panel: copper-plate credit=100 → copper-ore raw drop=100, with
  cascading drop in molten-copper / casting stages).
- Byproduct overflow (when emitted > demanded) is flagged in `notes` and
  recorded in `shuffle_byproduct_overflow`. For Nauvis processing-unit at
  60/min, all 960/min copper-plate + 96/min steel-plate are surplus
  because fluid-preferred recipes (casting-copper-cable, casting-iron)
  route around solid plates entirely — informational, not an error.
- `cross-item-shuffle` stage role and `format_human` rendering for it,
  plus normal-quality input sections.

What's in tree:
- `compute_lds_shuffle_stage(legendary_plastic_per_min, data, ...)` at
  `dev/quality_planner.py:744`. Calls `solve_lds_shuffle_loop` for the
  per-input yield, then sizes a stage: returns `normal_plastic_in_per_min`,
  `foundry_machines`, `recycler_machines`, `byproduct_legendary` map
  (copper-plate, steel-plate — ratio fixed by recipe), and `fluid_demand`
  (molten-iron, molten-copper).
- Smoke check (60/min legendary plastic, no research, legendary T3 modules):
  yield ≈ 1.58%, ~108 foundries + ~122 recyclers, byproducts 240
  copper-plate + 24 steel-plate legendary/min. Numbers scale linearly with
  rate.

Known limitation in the helper:
- When `research_prod` saturates the +300% prod cap, the per-cycle return
  ratio `r = (1+prod) * 1.25 / 5` reaches 1.0 → the recirculating throughput
  diverges (clamped to r=0.999, machine counts ~1500 for 60/min). This is
  mathematically correct in the limit (plastic-bar cycles indefinitely
  while quality slowly tiers up) but practically the planner should split
  into multiple parallel loops with smaller per-tier prod configs. Defer
  to wiring step — comparison vs asteroid total-machine cost will reject
  the saturated config naturally.

Still pending for full V3 cross-item solver:
- Generic shuffle enumeration: detect any recipe R where R's recycling
  returns only solids (fluids are free), all originally non-self
  ingredients can be quality-rolled through R. Auto-select a shuffle
  candidate per chain.
- LP / objective-aware selection between asteroid path and shuffle path
  per chain (currently shuffle is unconditionally used when flag is on
  and plastic-bar is in the chain — could be objectively worse, e.g. on
  Nauvis processing-unit at zero research where the byproducts overflow).
- Cycle detection guard between mutually-feeding shuffles (LDS produces
  copper, hypothetical copper-shuffle produces plastic-bar).

`solve_lds_shuffle_loop` already computes the per-plastic-bar legendary yield of the LDS shuffle. The missing piece is deciding **whether to use it** and **how to credit byproducts** inside `plan()`.

**The decision problem:**
- LDS shuffle consumes `plastic-bar@normal`, produces `plastic-bar@legendary` + byproducts `copper-plate@legendary` + `steel-plate@legendary`.
- Asteroid path produces `plastic-bar@legendary` from carbonic-chunk, and `copper-plate@legendary` from metallic-chunk.
- If the target chain needs N legendary plastic-bar and M legendary copper-plate, should the planner:
  - (a) use asteroid for both? (V2 behavior)
  - (b) use LDS shuffle for plastic-bar, credit byproduct copper-plate against M, fill the remainder from asteroid?
  - (c) scale LDS shuffle so byproduct copper-plate alone covers M (accepting "wasted" legendary steel-plate)?

Answer depends on which recipe loops have productivity research (asteroid-productivity vs lds-productivity vs plastic-bar-productivity) and on the ratio of plastic to copper demand. At zero research the asteroid path wins; at high plastic-bar-productivity + LDS-productivity, LDS shuffle dominates.

**Sketch:**
1. **Enumerate candidate shuffles.** For each recipe R with `allow_productivity=True` where the recycle of R's output returns ingredients that are all solid (fluid byproducts are free): R is a shuffle candidate. Pre-compute this list once. LDS is the canonical example; rails (iron-stick), concrete, green-circuits, red-circuits are others.
2. **Per-shuffle yield.** For each candidate, compute the per-ingredient legendary yield (as `solve_lds_shuffle_loop` does for plastic-bar), and per-byproduct legendary credit.
3. **Linear-program over leaves.** After the walker identifies all solid leaves and their required legendary rates, solve an LP:
    - Variables: `x_asteroid[leaf]`, `x_shuffle[shuffle_id]` (scalar throughputs).
    - Constraints: for each leaf L, `x_asteroid[L]·1 + Σ x_shuffle[s]·byproduct_rate[s,L] ≥ demand[L]`.
    - Objective: minimize total input cost (asteroid chunks + shuffle-input legendary rates + mined raws).
   Stdlib doesn't ship an LP; for 3-5 leaves + 3-5 shuffles a brute-force grid or explicit Karush-Kuhn-Tucker solution is enough.
4. **Stage output.** The planner adds a `"role": "cross-item-shuffle"` stage per active shuffle, with throughput, byproduct credits, and module config per tier.

**Open questions before implementing:**
- Do we want exact minimization or a heuristic "pick the shuffle that dominates X% of demand"? The simpler heuristic catches 95% of meta builds.
- How to surface byproduct overflow (legendary steel-plate produced but not demanded)? Either treat as free output or flag a warning.
- Cycle detection — two shuffles can feed each other (LDS shuffle produces copper-plate, a hypothetical copper-shuffle produces plastic-bar). Need a guard.

Estimated size: ~300-400 LoC + a dedicated test class.

### 2. Research-state tracking — **partially shipped (2026-04-30)**

**`--no-asteroids` shipped:** the most-requested gating subset is now in tree.
When set, the planner skips the asteroid path entirely and routes
iron-ore / copper-ore / ice / calcite through planet self-recycle via
`MINED_RAW_NO_ASTEROID_FALLBACK` (nauvis for iron/copper, aquilo for ice,
vulcanus for calcite). carbon and sulfur fall back to chemistry recipes
(coal+sulfuric-acid / petgas) which require their own planet unlocks.

When the chain still resolves to an asteroid-crushing recipe (because the
needed leaf raw isn't mineable on any unlocked planet), the planner fails
fast with a message naming the recipe and pointing at the planet flag:

```
ERROR: 'iron-plate' chain needs 'calcite' which resolves to asteroid-
crushing recipe 'advanced-oxide-asteroid-crushing' but --no-asteroids is
set. Unlock the planet that produces 'calcite' natively via --planets
(e.g. --planets vulcanus for calcite, --planets aquilo for ice).
```

Tests: `TestNoAsteroids` (9 tests).

**Still pending (full V3 item 2):**

User brought this up mid-V2: *"what if I can't use asteroids yet"*. V2 assumes everything is unlocked. The `--no-asteroids` answer to that exact question is shipped (above); what's still missing is generic tech-gating for the rest of the surface.

Gating surface:
- **Quality module tier**: quality-module-1 available after `quality-module` tech; t2/t3 after `quality-module-2`/`-3`. V2 takes `--quality-module-tier {1,2,3}` but doesn't check if it's actually researched.
- **Recycler**: locked behind `recycling`. No recycler → asteroid-reprocessing + mined-raw-self-recycle both impossible → no quality at all.
- **Foundry / EM plant / cryogenic plant**: gated by `metallurgic-science-pack`, `electromagnetic-science-pack`, `cryogenic-science-pack`. Blocks fluid-transparent recipes → chain falls back to furnace/assembler/chem-plant paths.
- **Asteroid collection**: requires `space-platform-thruster` + `asteroid-collector`. No platform → `asteroid_input` section is empty, all quality must come from mined-raw self-recycle.
- **Per-planet landing**: Vulcanus / Fulgora / Gleba / Aquilo each gated by their science-pack tech. Narrower than `--planets` (which V2 already has) because `--planets vulcanus` today implies the user already landed there.

Proposed input: `--tech NAME=LEVEL` repeated, or `--tech-preset {early,mid,late,all}`. Fail-fast with a specific message naming the missing tech. Defaults to `late` (current V2 behavior).

Estimated size: ~150 LoC + a `TestResearchGating` test class.

### 3. Self-recycling target items — **SHIPPED (2026-04-27)**

`superconductor`, `holmium-plate`, `tungsten-carbide`, `fusion-power-cell`,
`lithium` — the target item appears in its own recycle. The V1/V2 generic
loop errored out; V3 added a dedicated solver
`solve_self_recycle_target_loop` and the planner branch
`_plan_self_recycle_target`.

**Key insight:** the existing `solve_recycle_loop` was designed for
shuffle-style loops where the recycler's output (an ingredient) is fed
back to a re-craft (correct for LDS shuffle). For self-recycle TARGETS
the recycler returns the SAME ITEM, so the chain is recycler-only:
items are re-recycled until they tier up to legendary or vanish (via
the 25% retention loss). The new DP separates this:
  * Outer search: pick (craft_prod, craft_quality, recycle_quality).
  * One craft produces ``items_per_craft = output × (1+prod)`` items
    distributed across tiers by ``q_craft``.
  * Inner DP ``V_rec[t]``: per-item legendary yield from a single item
    at tier t entering a recycler-only chain (with retention < 1 so it
    converges).
  * Total = items_per_craft × Σ craft_probs[s] × V_rec[s].

**Output additions:** `self-recycle-target` stage role (with
`craft_machines` + `recycler_machines` split, `yield_pct`,
`crafts_per_min`, `module_config_per_tier`).  Ingredients consumed at
NORMAL quality (quality rolls happen during craft+recycle), so they go
into `normal_solid_input` / `normal_fluid_input` and are walked through
`walk_recipe_tree` as normal-quality production trees.

**Constants added:** `MACHINE_INHERENT_PROD` for foundry/EM-plant/
biochamber (+50% inherent), and others (zero).  `SELF_RECYCLE_TARGETS`
allowlist (extends `SELF_RECYCLING_BLOCKLIST` for items that are
allowed as targets but still blocked as intermediates).

**Tests:** `TestSelfRecycleTarget` (8 tests) — holmium-plate / tungsten-
carbide / superconductor work as targets; ingredients show up in
normal_solid_input; legendary modules >2× normal yield; rate doubles =>
machines double; per-tier config exposed; human format renders;
unknown-item solver returns 0.

### 4. Gleba biolocals + spoilage — **partially shipped (2026-04-27)**

What landed:
- `yumako`, `jellynut`, `pentapod-egg` added to `MINED_RAW_PLANETS` keyed
  to `("gleba",)`.  Each has a `*-recycling` recipe with 0.25 retention,
  so `solve_mined_raw_self_recycle_loop` works on them identically to
  coal/stone (~0.04% yield with legendary T3 quality modules).
- Walker now resolves all biochamber chains: `bioflux`, `nutrients`
  (-from-yumako-mash and -from-bioflux), `bioplastic`, `biosulfur`,
  `biolubricant`, `rocket-fuel-from-jelly`, etc.  Recipe selection on
  Gleba-only chains correctly picks bio-* substitutes (no coal/petgas).
- Assembly modules combine cleanly: `--assembly-modules` cuts biochamber
  chain ≥3× because biochambers have 4 slots + 50% inherent prod.
- 8 new tests in `TestGlebaPartial`.

What's still missing (V3.x):
- **Spoilage timing.** Self-recycle yields a tiny fraction (~0.04%) per
  cycle, which means thousands of cycles to reach legendary.  Bioflux
  spoils in 1 hour, nutrients in 5 minutes — many cycles is more time
  than the items have.  The current planner reports machine counts as if
  there's no spoilage budget; real builds need either short loops, deep
  spoilage research, or accept some legendary loss to spoilage.
- **Pentapod-egg as target.** Recipe is `1 egg + 30 nutrients + 60 water
  → 2 eggs` — a doubling self-loop where the input is also the output.
  `solve_self_recycle_target_loop` assumes external ingredients; it
  doesn't handle ingredient = output.  Pentapod-egg as an *ingredient*
  works (treated as raw).
- **Agricultural quality.** Agricultural towers have 0 module slots so
  yumako/jellynut can't be quality-rolled at harvest.  All quality must
  come from self-recycle.

Remaining estimated size for full Gleba: ~250 LoC (down from ~400) — the
big remaining piece is the spoilage timing model.

### 5. Per-stage assembly module optimization — **SHIPPED (2026-04-27)**

V2 ran assembly stages with no modules — the regression-anchor note
("Exact coal/oil counts are high because assembly stages still run
modules-off") was the artefact.  V3 adds `--assembly-modules` (default
off): when on, every assembly stage's machine slots are filled with prod
modules at the planner's `--module-quality` and `--prod-module-tier`,
inherent prod (foundry/EM-plant/biochamber +50%) is always applied, and
the +300% cap engages from total prod (research + module + inherent).

**Implementation:** `_assembly_prod_bonus(machine, recipe, slots_map,
flag, quality, tier) → (prod_fraction, slots_filled)` is called at both
walker passes (demand accumulation + stage construction) so ingredient
demand propagates correctly upstream. Stage dict gains `module_prod`,
`prod_modules`, `prod_module_tier`, `prod_module_quality`. `format_human`
appends `Nx prod-3-legendary (+X%)` to each assembly line.

**Smoke (60/min legendary processing-unit, --planets nauvis):**
- modules off: 620.2 machines, metallic chunks 1406/min, mined coal 322k/min
- modules on:  31.5 machines (≈20× drop), metallic chunks 30/min,
  mined coal 14k/min

The 20× cliff comes from cascading: cryogenic-plant gets 8 prod-3-
legendary modules (+200%, cap), foundry +150% (4 modules + inherent),
EM-plant +175%. Each of ~10 chained stages divides ingredient demand
by 1+prod, compounding.

**Tests:** `TestAssemblyModules` (8 tests).

**Caveat:** `--prod-module-tier` defaults to 3.  No speed modules — speed
doesn't reduce ingredient demand and the planner already sizes by
throughput.  The chosen module config is a heuristic ("fill all slots
with prod"); a per-stage DP that sometimes prefers fewer prod modules
to leave slots free for speed/quality is V3.x.

### 6. Alternate objectives

Fewest machines, smallest footprint, lowest power, UPS-sensitive. Each is a different objective on the same DP; requires swapping the "minimize asteroid input" objective for a weighted cost function.

---

## Non-goals (still)

Same as V1. Not a replacement for `cli.py`. Not a blueprint generator. Not a modded-recipe tool.
