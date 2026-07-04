# Quality Planning Roadmap (Q1–Q9)

Specs for the missing quality-planning features identified in the 2026-07-04
CLI review. Each item is written to be implementable standalone. Naming
follows the `fulgora-realism-plan.md` convention (C1–C5, completed and
deleted); these are Q1–Q9.

**Priority order:** Q1+Q5 (one combined milestone — post-2.1.8 quality
sourcing), Q2, Q4, Q7, Q6, Q8, Q3, Q9. Q1 and Q2 are *correctness* fixes —
today's plans are optimistic in ways players will notice. The rest are new
capability.

| # | Item | Tool | Size | Kind |
|---|------|------|------|------|
| Q1 | Post-2.1.8 asteroid quality redesign | quality_planner | L | correctness |
| Q2 | Minimum-ingredient-quality rule (tier-matched sets) | quality_planner | L | correctness |
| Q3 | Gleba spoilage timing | quality_planner | M | correctness |
| Q4 | Quality-module placement optimizer | quality_planner | M | capability |
| Q5 | Quality mining on all planets | quality_planner | S/M | capability |
| Q6 | Mixed-tier demand, mid-tier harvest, tool composition | both | M | capability |
| Q7 | Beacons in the planner | quality_planner | M | capability |
| Q8 | Objective function + multi-target | both | M | capability |
| Q9 | Ergonomics batch | both | S | polish |

Every item that changes flags or solver behaviour triggers the standard
maintenance rules in `claude.md`: update the module docstring Usage block,
`dev/quality_planner.md` (CLI surface + relevant sections), SKILL.md §11
invocation block (planner) or §2 (cli.py), add tests to the matching test
file, and refresh test counts in `README.md` / `claude.md` /
`dev/quality_planner.md`. That checklist is not repeated per item below.

---

## Q1 — Post-2.1.8 asteroid quality redesign

**Problem.** Since 2.1.8, asteroid *reprocessing* recipes drop `quality` from
`allowed_effects` — the chunk-tier climb the planner models
(`solve_asteroid_reprocessing_loop`) is impossible in-game. Crushing recipes
(`advanced-*-asteroid-crushing`) still allow quality (and prod). Current
plans carry a known-limitation note (added 2026-07-04); this item removes the
limitation.

**Game rules.**
- Reprocessing: no quality, no prod modules (consumption/speed/pollution only).
  Still useful for chunk-type *rebalancing* (0.8 aggregate retention,
  cross-feeding chunk types), quantity only.
- Crushing: crusher, 2 module slots, quality + prod allowed → one quality
  roll per craft on the ore outputs.
- Raw ores (`iron-ore-recycling`, etc.) self-recycle at 25 % retention with
  4 recycler quality slots — same mechanics as the existing
  `solve_mined_raw_self_recycle_loop`.

**Design.** Replace the "legendary chunks → quality-transparent crushing"
model with "normal chunks → quality roll at crushing → ore self-recycle
upcycle":

1. Gate `solve_asteroid_reprocessing_loop` on
   `cli.recipe_allows_quality(rep_recipe)` (returns 0 yield on 2.1.9 data;
   keeps working on datasets/mods where reprocessing allows quality).
2. New yield math per asteroid-routed raw `R` with chunk `K`:
   `target_R_per_chunk = ore_per_crush × (1 + crush_prod) ×
   Σ_t crush_dist[t] × V_ore[t]`, where `crush_dist` =
   `_tier_skip_probs(q_crusher, 0)` (q from 2 crusher slots) and `V_ore[t]` =
   per-tier value vector from the ore's recycler self-loop (the C3 scrap
   seeding already built exactly this convolution:
   `_compose_miner_and_recycler_rolls` + `V_loop` in `scrap_target_yield`).
   Reuse that machinery, not new code.
3. `plan()` asteroid section: drop `reprocessing_stages` (or keep them
   quantity-only behind a `--chunk-rebalance` flag, deferred); emit
   `raw-crushing` stages sized on *total* crushes (now much larger — they
   feed the upcycle loop, not just convert), plus a new
   `asteroid-ore-upcycle` stage per ore (role reuses the
   `mined-raw-self-recycle` shape: recycler machine count, per-tier configs).
4. `asteroid_input` stays "normal chunks/min" (semantics unchanged).
5. Update `_baseline_cost_for_leaf` (asteroid branch) and the hot-spot
   advisor (`asteroid-reprocessing` role disappears; add
   `asteroid-ore-upcycle` guidance).
6. Delete the 2026-07-04 known-limitation note and the header caveats.

**Tests.** Rewrite `TestAsteroidReprocessing` (gated kernel → 0 on 2.1.9
data), add crushing-roll yield tests (hand-computed for 2 × T3-legendary
slots), end-to-end iron-plate plan shape (no reprocessing stage; upcycle
stage present). Refresh regression anchors in `quality_planner.md` — expect
large shifts; investigate rather than rubber-stamp, per the spec's own rule.

**Risks.** Heavy test churn (~20 tests reference reprocessing); anchors move
for every asteroid-routed target. Do together with Q5 (same convolution
machinery, one anchor refresh).

---

## Q2 — Minimum-ingredient-quality rule (tier-matched ingredient sets)

**Problem.** In-game, a craft's output quality = the **lowest** ingredient
quality (fluids ignored); quality modules roll upward *from that tier*. Two
solver paths violate this:

- **Multi-solid shuffle loops** (e.g. `advanced-circuit` = cable + EC +
  plastic): the DP climbs only the "primary" and implicitly assumes co-solids
  match its tier. With normal co-solids the output is dragged back to normal
  and the climb never happens. Only single-solid candidates (LDS, concrete)
  are correct today. Co-solid resupply is also not costed.
- **Multi-ingredient wraps** (holmium-plate via supercapacitor): `co_solids`
  are registered as *normal* input, but the climb needs tier-matched
  batteries/circuits at every rung. Yield is optimistic AND the co-ingredient
  bill is understated.

**Key game insight that makes this tractable:** recycling one tier-t item
returns *all* its ingredients at tier t (recycler rolls go up from there).
So inside a closed craft→recycle loop, ingredient tiers are self-matching —
the loop's state is naturally an **ingredient set** (the solids for one
craft), not a single item. A set shrinks uniformly at
`retention = 0.25 × (1 + cast_prod)` per pass, so the set-based DP has the
same shape as today's primary-only DP.

**Design.**
1. Reframe `solve_shuffle_loop` state as sets: V[t] = target-tier *sets*
   emerging per normal set invested. Math is today's math with retention
   computed on the set (min over per-ingredient return ratios; for recipes
   whose recycler returns exact ingredient ratios — the common case — it
   equals today's number). "Primary" becomes a reporting label only.
2. Fresh input at tier 0 = **full sets**: `normal_solid_input` gains every
   solid ingredient at recipe ratio (today only the primary is walked).
   `byproduct_legendary` only contains recycler returns *in excess of* the
   set ratio (LDS: copper-plate + steel-plate still qualify because the
   foundry cast doesn't consume them; assembler-variant shuffles: no
   byproducts, they're all set members).
3. Wrap DP (`solve_self_recycle_target_loop` wrap path): co-solids must be
   supplied **tier-matched per pass**. Two options:
   - **v1 (recommended):** price tier-t co-solids through the item's own
     quality sources recursively (each co-solid's target-tier cost is already
     computable via `choose_path_self_recycle` / mined-recycle / Q1 paths;
     demand per tier comes from the loop flow vector — `compute_loop_flows`
     already exists). Cache per (item, tier) in `_DispatchCache`.
   - **v0 (stopgap):** restrict the wrap climb to single-solid wraps
     (steel-chest et al.); multi-ingredient wraps fall back to baseline.
     One-line change, honest immediately.
4. `_choose_wrap_route`'s `co_count / 2` heuristic penalty is superseded by
   real co-ingredient pricing (v1) — remove it then.

**Tests.** Unit: set-retention equals legacy retention for LDS (byte-compat
guard); advanced-circuit shuffle `normal_solid_input` contains all three
solids at recipe ratio; holmium-plate wrap yield drops vs today (assert
direction, then pin). End-to-end: `TestWrapDP` totals re-anchored.

---

## Q3 — Gleba spoilage timing

**Problem.** Quality loops on spoilable items (yumako/jellynut mash, jelly,
nutrients, bioflux, pentapod-egg, biter-egg, agricultural science) assume no
decay. Long recycler ladders on eggs/bioflux are optimistic — documented
today as a blanket "NOT modelled" disclaimer.

**Game rules.** Each spoilable has a fixed spoil time; spoilage is linear
per-item freshness decay; a spoiled item becomes `spoilage` (eggs hatch —
worse). Crafting resets freshness only per recipe rules. **Do not trust
remembered spoil-time numbers — source them at implementation time** from
the wiki corpus (`dev/wiki/pages/`) or vendor a `spoil_seconds` field into
the dataset (pattern: `dev/docs/dataset_2.1.8_additions.md`).

**Design (two stages).**
- **v0 — warning-only (ship first):** for each loop stage whose item
  spoils, estimate expected residence time
  `T ≈ passes × (craft_time/speed + recycle_time/speed + buffer_slack)`,
  with `passes ≈ 1/(1−retention)` per tier climbed. Emit a note when
  `T > 0.5 × spoil_seconds` and an ERROR-level note when `T > spoil_seconds`
  ("this loop spoils before it climbs — split into parallel shorter loops").
  `buffer_slack` is a documented constant (default 0: pure processing time —
  optimistic bound, which is the right direction for a warning).
- **v1 — loss modelling:** multiply per-pass retention by a survival factor
  `s = max(0, 1 − cycle_time/spoil_seconds)` (linear death model; document
  that real spoilage is deterministic per item age, so this is an
  approximation). Flag `--no-spoilage` restores v0 behaviour for A/B.

**Tests.** v0: pentapod-egg / bioflux plans carry the warning; iron-plate
does not. v1: yield monotonically decreases with spoil time; `--no-spoilage`
reproduces v0 numbers.

---

## Q4 — Quality-module placement optimizer

**Problem.** The highest-leverage real-world question — "*where* in the
chain do I put quality modules?" — is unanswered. The planner only rolls
quality in dedicated loops; cli.py can evaluate a *given* placement
(`--quality-pickout` + `--recipe-modules`) but nothing searches.

**Design.** New planner mode: `--optimize-placement` (with the usual target
item/rate/tier flags):

1. Build the target's normal-quality chain (existing `walk_recipe_tree`).
2. Candidate placements: each chain step that `recipe_allows_quality`, with
   quality-slot counts `1..slots` (and the prod/quality split for machines
   that allow prod). v1 searches **single-step placements** exhaustively
   (chains are ≤ ~15 steps × ≤ 5 slots → trivial); pairs are v2.
3. For each placement, the roll stage yields a tier distribution on its
   output (`quality_tier_probs`); items at tier > 0 continue **down the
   remaining chain tier-matched** (downstream steps preserve the tier —
   min-rule with single-solid inputs; multi-solid downstream steps need
   tier-matched siblings, which is exactly Q2's set logic — depend on Q2, or
   v1 restricts to placements where the downstream path is single-solid).
   Below-target output at the end feeds the target item's recycler self-loop
   (existing kernel) OR is sold as mid-tier surplus (Q6's `--keep-tiers`).
4. Score by the active objective (Q8; default machines) **and** report
   raw-input consumption per candidate — placement choice often trades
   machines against ore.
5. Output: top-3 placements as a `placement-comparison` note block + the
   winning plan's stages, with the chosen step's `module_config` explicit.

**Non-goal:** joint optimization with shuffles/wraps in v1 — the comparator
already covers those; the optimizer competes as one more candidate through
the existing auto-compare mechanism.

**Tests.** Known result to anchor: for `quality-module-2`-class chains the
roll belongs on the cheapest-per-item step; assert the optimizer prefers a
gear/cable-tier step over the final assembly for a representative chain, and
that reported machine counts match a manual cli.py `--quality-pickout` run
of the same placement.

---

## Q5 — Quality mining on all planets

**Problem.** Drills accept quality modules everywhere (electric drill 3
slots, big drill 4), and miner-seeded ore quality is a mainstream strategy.
The planner models it only for Fulgora scrap (C3). Everywhere else,
mined-raw self-recycle assumes normal input — overstating recycler counts
for coal, stone, tungsten-ore, uranium-ore, holmium-ore.

**Design.** Generalize C3:
1. In `plan()`'s mined-recycle section, compute
   `q_miner = _quality_chance(drill_slots, tier, quality)` (drill from
   `--miner`, slots from `cli.build_machine_module_slots`) — identical to
   `compute_scrap_source`.
2. Convolve the miner roll into the loop entry distribution:
   `dist = _compose_miner_and_recycler_rolls(q_miner, q_rec, 0)` seeds the
   per-tier inflow; yield uses the loop's per-tier `V` (plumbing exists —
   `V_loop` in `scrap_target_yield` is the template).
3. Respect existing `--no-miner-quality-modules` (currently documented as
   Fulgora-only; broaden the doc).
4. Drills already get sized via `cli.compute_miners`; add their module speed
   penalty (−5 %/slot) to the drill count and their `module_specs` echo
   (cli.py already supports quality modules in drills — C2).
5. Agricultural tower stays 0-slot (existing note). Pumpjacks/offshore: no
   quality (fluids) — unchanged.

**Tests.** Coal self-recycle plan: recycler count drops when miner quality
modules on; big > electric drop (4 vs 3 slots); `--no-miner-quality-modules`
reproduces current numbers; Fulgora scrap path unchanged (regression).

---

## Q6 — Mixed-tier demand, mid-tier harvest, tool composition

**Problem.** Three related gaps: (a) the planner answers only "N/min at one
tier"; players want "60 rare + 10 epic + 1 legendary/min". (b) Sub-target
tiers are loop-internal — you can't say "keep the uncommon overflow".
(c) cli.py's `quality_yield` is a dead end: picked-out items can't be fed
into a follow-up plan.

**Design.**
1. **Per-tier demand:** repeatable `--target TIER=RATE` (mutually exclusive
   with `--rate`; `--rate N` ≡ `--target <target-quality>=N`). Solver: run
   the loop flow machinery (`compute_loop_flows` generalization) with
   multiple absorbing tiers — harvest `RATE_t` at each demanded tier `t`,
   re-loop the remainder. Because everything is linear in rate, solve as a
   small LP or greedily harvest top-down (highest tier is the binding
   constraint; lower-tier demands are covered by the flow passing through —
   only shortfalls add fresh input).
2. **`--keep-tiers T1,T2`:** demanded tiers absorb; *kept* tiers absorb and
   report as `tier_surplus {item: {tier: rate}}` instead of re-looping
   (fewer recyclers, more raw input — surface both).
3. **Composition:** planner flag `--supply ITEM:TIER=RATE` (repeatable) —
   pre-existing tiered stock (e.g. cli.py `quality_yield` from a pickout
   line, or accumulated chests) credited against loop inflows at that tier
   before sizing fresh input. Document the workflow in SKILL.md §11: run
   cli.py with `--quality-pickout`, feed its `quality_yield` into the
   planner via `--supply`.

**Tests.** `--target rare=60` ≡ legacy `--target-quality rare --rate 60`
(byte-compat); mixed rare+epic demand sizes ≥ each single-tier run; keep-tiers
reduces recycler count and emits surplus; `--supply` at the entry tier
reduces `mined_input`/`asteroid_input` proportionally.

---

## Q7 — Beacons in the planner

**Problem.** Zero beacon support. The standard quality-farm layout puts
speed beacons on the **cast/craft legs** (rolls happen at the recycler, so
"haste makes waste" doesn't hit the roll) to offset prod-module speed
penalties; quality-carrying machines are left unbeaconed.

**Design.**
1. Flag mirroring cli.py's value format:
   `--beacon [ROLE=]COUNT:MOD_COUNT:TYPE:TIER:QUALITY` where ROLE ∈
   `{cast, assembly, recycler, crusher, all}` (default `cast,assembly` —
   the safe legs). Reuse `cli._parse_beacon_spec`.
2. Speed math: reuse `cli.Solver._compute_beacon_speed` semantics
   (`effectivity × sqrt(count) × Σ slot bonus`, `--beacon-quality` for
   effectivity — add the flag too). Machine counts divide by
   `(1 + beacon_speed)`.
3. Quality interaction: when the user targets `recycler`/`crusher`/`all`,
   fold `cli.Solver._beacon_quality_penalty` into that stage's
   `_quality_chance` so the DP sees the reduced roll — the kernels take a
   `q_penalty` argument, clamped at 0. The DP will then correctly conclude
   recycler beacons are usually bad; that's the point of modelling it.
4. Power: beacon idle draw via `BEACON_POWER_KW` + `_beacon_sharing_factor`,
   added to stage `power_kw`.

**Tests.** Cast-leg beacons cut cast machine counts by the expected factor
and leave loop yield unchanged; recycler beacons reduce yield (assert
direction) and the DP prefers not selecting quality slots to zero;
power totals include beacon draw.

---

## Q8 — Objective function + multi-target planner

**Problem.** All comparators (auto-compare A/B, shuffle/driver cost gates,
wrap selection, Fulgora LP) minimize machine count. Players routinely
optimize for raw throughput (scrap/ore is the scarce input) or power
(Fulgora accumulators). And the planner is single-item — endgame science
packs share upcycle infrastructure but must be planned separately.

**Design.**
1. `--objective machines|power|raw` (default `machines`, today's behaviour).
   Score functions: `total_machine_count`; `total_power_mw`;
   `Σ mined_input + Σ asteroid_input + scrap_input` (item-weighted 1:1 in
   v1; document that weighting is naive). One `_plan_score(out, objective)`
   helper used by **every** comparator — grep for `total_machine_count`
   comparisons and route them all through it.
2. cli.py Fulgora LP: `--objective` swaps the LP cost vector `c`
   (machine_coef → per-activity power coef → scrap-consumption coef).
   Small, self-contained.
3. **Multi-target planner:** repeatable `--item/--rate` pairs (cli.py
   parity). Implementation: run Pass-1 walks per target, sum `raw_demand`
   and stage demands, then size loops/stages once from aggregated demand
   (everything downstream of the walker already keys off aggregate rates).
   Output: `targets: [...]` array (cli.py's shape), shared stages emitted
   once.

**Tests.** Objective=power picks the lower-power branch in a constructed
A/B tie; objective routed through shuffle gate + wrap selection; Fulgora LP
objective swap changes chosen activities on a known case; multi-target
iron-plate + copper-plate shares crusher/upcycle stages vs two separate runs.

---

## Q9 — Ergonomics batch

Small items, one PR:

1. **Planner `--machines N`:** inverse sizing. Everything scales linearly
   with rate, so: solve at rate 1, find the stage the user constrains
   (default: the target's primary stage machine count), scale rate by
   `N / count₁`. Echo `chain_scaled_to_machines: N`.
2. **cli.py per-recipe machine quality:** `--recipe-machine-quality
   RECIPE=QUALITY` (repeatable) — mixed fleets are normal mid-game. Plumbs a
   per-recipe override into the `MACHINE_QUALITY_SPEED` lookup in
   `Solver.solve` / `rate_for_machines` / `_emit_oil_steps`; echoed in JSON.
3. **Variance note (planner):** quality output is an expectation. When the
   target-tier rate < 1/min, emit a note with the Poisson std-dev over an
   hour (`σ ≈ √(rate×60)` items) and a buffering suggestion. Static text +
   one sqrt; prevents "the math said 1/min, I've seen nothing for an hour".
4. **`_compose_quality_rolls` cleanup:** dead since C3 superseded it with
   `_compose_miner_and_recycler_rolls`; delete or fold into a shared helper
   when Q5 lands.

---

## Explicit non-goals (unchanged from quality_planner.md)

Blueprint generation, modded recipes, vanilla-dataset quality (no quality
modules exist there — cli.py treats the tables as empty by design), UPS/belt
layout advice, and freshness-value modelling for spoilables (Q3 models
*losses*, not output freshness).
