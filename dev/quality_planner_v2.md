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

## Status (2026-04-21)

**V2 shipped.** Same `dev/quality_planner.py` file (~1200 LoC now), same `dev/test_quality_planner.py` (73 tests, all passing). Zero new dependencies.

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

**Status (2026-04-26): partial — sizing helper landed; wiring + byproduct
credit + CLI flag still pending.**

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

Still pending (in order):
- Wire `compute_lds_shuffle_stage` into `plan()` behind `--enable-lds-shuffle`
  flag. Default off so the 73 baseline tests stay untouched.
- Replace `plastic-bar` walker expansion with the shuffle stage when the
  flag is set. Keep the normal chem-plant chain available for the
  "normal-plastic-bar input" leg.
- Credit `byproduct_legendary["copper-plate"]` and `["steel-plate"]`
  against the demand of those items downstream — reduces metallic-asteroid
  input. Cap the credit at the demanded rate (no negative inputs).
- Add `cross-item-shuffle` stage role to `out["stages"]` and to
  `format_human`.
- New `TestLDSShuffleWiring` class in `dev/test_quality_planner.py`:
  flag default off; flag on with no research = positive but suboptimal;
  flag on with `plastic-bar-productivity=10` reduces total machines vs
  default; byproduct credit observed in metallic-asteroid input drop;
  byproduct overflow flagged in notes when it exceeds demand.

Generic shuffle enumeration (rail shuffle, etc.) is V3.1 — wire LDS-only
first, validate the byproduct/credit/notes UX, then generalise.

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

### 2. Research-state tracking

User brought this up mid-V2: *"what if I can't use asteroids yet"*. V2 assumes everything is unlocked.

Gating surface:
- **Quality module tier**: quality-module-1 available after `quality-module` tech; t2/t3 after `quality-module-2`/`-3`. V2 takes `--quality-module-tier {1,2,3}` but doesn't check if it's actually researched.
- **Recycler**: locked behind `recycling`. No recycler → asteroid-reprocessing + mined-raw-self-recycle both impossible → no quality at all.
- **Foundry / EM plant / cryogenic plant**: gated by `metallurgic-science-pack`, `electromagnetic-science-pack`, `cryogenic-science-pack`. Blocks fluid-transparent recipes → chain falls back to furnace/assembler/chem-plant paths.
- **Asteroid collection**: requires `space-platform-thruster` + `asteroid-collector`. No platform → `asteroid_input` section is empty, all quality must come from mined-raw self-recycle.
- **Per-planet landing**: Vulcanus / Fulgora / Gleba / Aquilo each gated by their science-pack tech. Narrower than `--planets` (which V2 already has) because `--planets vulcanus` today implies the user already landed there.

Proposed input: `--tech NAME=LEVEL` repeated, or `--tech-preset {early,mid,late,all}`. Fail-fast with a specific message naming the missing tech. Defaults to `late` (current V2 behavior).

Estimated size: ~150 LoC + a `TestResearchGating` test class.

### 3. Self-recycling target items

`superconductor`, `holmium-plate`, `tungsten-carbide`, `fusion-power-cell` — the target itself appears in its own recycle. The V1/V2 generic loop errors out (`output recycles to itself`).

A dedicated solver: model the target as a self-loop with productivity+quality modules in the craft stage, 25% retention via recycler, and a per-tier DP identical in shape to `solve_asteroid_reprocessing_loop` but with the target item replacing the chunk. External inputs (non-self ingredients) still need legendary upstream.

Estimated size: ~100 LoC + test class.

### 4. Gleba biolocals + spoilage

Yumako, jellynut, bioflux, pentapod eggs, nutrients — each has a spoilage timer. Quality loops that take more than the spoilage window are infeasible. Needs a time-budget constraint layered over the DP. Complex because spoilage applies at multiple stages.

Estimated size: ~400 LoC + a new timing model.

### 5. Per-stage assembly module optimization

V1/V2 run assembly stages with no modules. This means every foundry casting legendary iron-plate runs at base speed/prod; a 4-slot foundry with 4 legendary prod-3 modules gives +40% prod and reduces upstream demand by ~28%. Implementing this requires per-recipe module-config DP identical to what the quality loop solver already does, just without the quality dimension. Should be a straightforward extension of `_unused_solve_loop_reference`.

Estimated size: ~100 LoC.

### 6. Alternate objectives

Fewest machines, smallest footprint, lowest power, UPS-sensitive. Each is a different objective on the same DP; requires swapping the "minimize asteroid input" objective for a weighted cost function.

---

## Non-goals (still)

Same as V1. Not a replacement for `cli.py`. Not a blueprint generator. Not a modded-recipe tool.
