# Quality Planner V2 — Multi-Planet + Mined-Raw Self-Recycle

Follow-up to `quality_planner_v1.md`. Expands the planner's reachable item scope without changing the DP kernel or output contract.

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

1. **Cross-item quality solver** (LDS shuffle, rail shuffle, sibling loops). Graph-search over recipes whose output-recycle intersects the target's ingredient set. Joint DP over the subgraph. Byproduct crediting against other leaves.
2. **Research-state tracking**. `--unlocked-techs T1,T2,...` or `--tech-level NAME=LEVEL` that gates: quality-module tier availability, recycler access, foundry / EM-plant / cryoplant access, asteroid collection (space platform), per-planet landing.
3. **Self-recycling target items** (superconductor, holmium-plate, tungsten-carbide, fusion-power-cell). Dedicated solver — can't use the generic loop because output is itself the target.
4. **Gleba biolocals** with spoilage budgets (yumako, jellynut, bioflux, pentapod eggs, nutrients).
5. **Per-stage assembly module optimization**. V1/V2 leave assembly stages modules-off; a lot of legendary-output throughput on the table.
6. **Alternate objectives**. Fewest machines, smallest footprint, lowest power, UPS-sensitive.

---

## Non-goals (still)

Same as V1. Not a replacement for `cli.py`. Not a blueprint generator. Not a modded-recipe tool.
