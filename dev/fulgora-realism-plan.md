# Fulgora Realism Plan — quality planner

**Status:** DRAFT — not started. **Temporary doc**: delete when all chunks land
and the content is folded into `dev/quality_planner.md`.

## Why

For a sub-legendary target built on Fulgora (`--location fulgora`), the quality
planner's headline numbers are unrealistic in three independent ways, all
pulling the same direction — the plan **understates the real factory** while
**overstating the scrap requirement**:

1. **No miner counting.** The planner reports raw *rates* (`scrap/min`,
   `mined/min`) but never converts them to drills. `total_machine_count` and
   `total_power_mw` exclude the entire mining fleet (e.g. ~13 big drills +
   ~3.9 MW for the rare quality-module-2 plan are invisible).
2. **No quality scrap.** Quality modules in scrap miners produce quality
   *scrap*, which recycles into the whole output basket at tier in one step.
   Neither tool models this — the planner assumes normal scrap; `cli.py` models
   only the drill *speed penalty* of a quality module, never its output.
3. **No upcycle loop.** `build_scrap_cascade` stops at ores
   (`if k in mined_raws: continue`), forbidding the plate↔ore re-roll loop that
   is the actual quality-grind mechanic. `scrap_target_yield` counts only the
   thin rare tail of a *single* forward pass, so the scrap figure is a
   pessimistic upper bound.

Goal: make `--location fulgora` plans reflect a factory someone would actually
build — honest machine/power totals (miners included) and a scrap number that
assumes a real quality grind.

## Scope & non-goals

- **In scope:** miner counting + power; mining-prod research pass-through;
  `--miner electric|big`; quality-scrap seeding; recycler upcycle loop; drill
  machine-quality (cli-side); doc/test upkeep per `CLAUDE.md`.
- **Non-goals (for now):** spoilage timing; non-Fulgora locations' sourcing
  (untouched); a full cli.py quality-ore model for the *recursive* solver
  (optional appendix only — the planner can model scrap quality itself).
- **Invariant for every chunk:** both suites green
  (`python -m unittest dev.test_quality_planner dev.test_cli`) before moving on;
  each chunk independently shippable; non-Fulgora behaviour unchanged.

## Gap → chunk map

| Gap | Chunk |
|-----|-------|
| 1 miner counting + mining-prod pass-through + `--miner` | **C1** |
| drill `--machine-quality` speed (cli-side accuracy) | **C2** |
| 2 quality scrap seeding | **C3** [COMPLETE] |
| 3 recycler upcycle loop | **C4** [COMPLETE] |
| validation + doc consolidation | **C5** |
| (optional) cli.py quality-ore output for recursive solver | **Appendix A** |

Sequence: **C1 → C2 → C3 → C4 → C5**. C1+C2 deliver the "honest footprint"
value even if C3/C4 never land; C3+C4 deliver the "scrap isn't absurd" value.

---

## C1 — Miner counting in the planner (low risk, mechanical) — ✅ DONE (2026-06-30)

**Shipped:** `--miner electric|big`; `cli.compute_miners` call with the
mining-prod pass-through; drills as `mining` stages in `out["stages"]` folded
into `total_machine_count` / `total_power_mw` / `summary.by_role`; `[mining]`
render branch; hot-spot advisor insulated (measures production-only share);
`TestPlannerMiners` (8 tests, planner suite now 336). **Known limitation
(deferred):** only the main `plan()` body counts miners — the
`_plan_self_recycle_target` / `_plan_self_feed_target` / `choose_path_self_recycle`
early-return paths don't yet (a bare `tungsten-carbide` target shows no miners).
Revisit when those paths matter or in C5.



**Goal:** size drills/pumpjacks for `scrap_input` + `mined_input`, fold counts +
power into the totals, expose a `--miner` flag and the mining-prod research
pass-through.

**Files:** `dev/quality_planner.py`, `dev/test_quality_planner.py`, docs.

**Changes**
- Add `--miner electric|big` (default `electric`), mirroring `cli.py` exactly
  (`choices=["electric","big"]`). Thread `args.miner` into `plan()` as
  `miner_type`.
- In `plan()`, after `scrap_input`/`mined_input` are final, build solid raw
  rates as `Fraction` and call:
  ```python
  miners = cli.compute_miners(
      raw_rates_fraction,                 # scrap_input + mined_input
      cli.build_resource_info(data),
      miner_type,
      machine_power_w=machine_power_w,    # already built for stage power
      mining_productivity_level=research_levels.get("mining-productivity", 0),
  )
  ```
- Convert each solid-raw miner entry to a stage dict
  `{role:"mining", item, machine, machine_count, power_kw}` and **append to
  `out["stages"]`** (keeps the `total == sum(stages)` invariant that
  `test_fluid_chain_folds_into_totals` relies on; `summary.by_role` then picks
  up the `mining` role for free).
- `total_machine_count` / `all_stages_for_power` already iterate `out["stages"]`
  / the stage blocks — confirm `mining` stages are included.
- `_stage_power_kw`: add a `role=="mining"` branch returning the
  `compute_miners`-supplied `power_kw` (it already accounts for prod/efficiency;
  don't recompute via the default branch).
- `format_human`: add a "Miners Needed" section (solid raws → count; fluid raws →
  `required_yield_pct`, matching `cli.py`, no machine count) and a
  `role=="mining"` stage-render branch.

**Gotchas**
- `scrap_input`/`mined_input` are `float` in the planner; `compute_miners` does
  `Fraction` arithmetic — wrap rates in `Fraction(str(rate))` first.
- Fluids (`fluid_input`, e.g. heavy-oil) → `compute_miners` returns
  `required_yield_pct`, **no** `machine_count`; they must NOT add to
  `total_machine_count`. Only solid raws contribute drill counts.
- Mining-prod is **uncapped** and climbs fast — at prod 0 the rare qm2 plan is
  ~13 big drills; at prod 20+ it's a fraction. The pass-through is what makes
  the count honest.
- Drills are sized at **normal** quality speed until C2 (note it in output).

**Test plan** — new `TestPlannerMiners`:
- solid raw (scrap) yields a `mining` stage with `machine_count > 0`; big vs
  electric differ by the speed ratio; `--research mining-productivity=N` lowers
  the count; default (no research) matches a hand-computed value.
- miner power present and included in `total_power_mw`; `mining` role in
  `summary.by_role`; `total_machine_count == sum(stage machine_counts)` still
  holds.
- fluid raw (heavy-oil) appears as `required_yield_pct`, contributes no machine
  count.
- non-Fulgora plan with mined raws also counts miners (feature isn't
  Fulgora-gated — it's general); confirm an asteroid-only plan with no mined/scrap
  raws emits no `mining` stage.

**Maintenance (CLAUDE.md — new planner flag):** update the `quality_planner.py`
docstring Usage block; the CLI-surface table in `quality_planner.md`; the
invocation block in `SKILL.md` §11. New behaviour: add tests, bump the test
count in `quality_planner.md` (Status + Tests), `CLAUDE.md`, `README.md`.

**Done when:** rare qm2 Fulgora plan shows a Miners Needed section with ~13 big
drills (at prod 0), the total machine/power figures include them, both suites
green, docs updated.

---

## C2 — Drill machine-quality in cli.py (medium risk, shared file) — ✅ DONE (2026-07-01)

**Goal:** apply `--machine-quality` to drill speed so a legendary big drill uses
its `6.25` mining-speed (vs `2.5` normal), shrinking counts. The planner (C1)
already passes `machine_quality` through once cli accepts it.

**Files:** `10x-factorio-engineer/assets/cli.py`, `dev/test_cli.py`, docs.

**Changes**
- `MINER_SPEED` is currently read at index 0 (`_quality_value(mining_speed, 0)`).
  Either store the full per-quality array for drills or re-read by quality
  index inside `compute_miners`.
- Add `machine_quality: str = "normal"` param to `compute_miners`; index drill
  base speed by `QUALITY_INDEX[machine_quality]`. Pass `solver.machine_quality`
  at the call site in `main()`/`format_output`.
- Planner (C1 call site) passes its `machine_quality` through.

**Gotchas**
- Pumpjack/offshore throughput is also a per-quality array (`PUMP_THROUGHPUT`
  already keyed by quality) — decide whether `--machine-quality` should lift
  those too for consistency, or leave pumps as-is (document the choice).
- `MINER_SPEED` is module-global and populated once; if other code reads it as a
  scalar, keep a normal-quality scalar alias to avoid breakage.

**Test plan:** legendary drill count < normal for the same rate by the speed
ratio; existing `TestBigMiningDrill` / `TestPowerConsumption` still pass (they
assume normal quality — verify defaults unchanged). Add a `TestMinerQuality`
case.

**Maintenance:** `cli.py` behaviour change → update `SKILL.md` §2 if the flags
table/notes mention miner quality; bump cli test count in `README.md` +
`CLAUDE.md`.

**Done when:** `--machine-quality legendary` reduces drill counts in both tools;
suites green; defaults unchanged.

---

## C3 — Quality scrap seeding (planner scrap source, high risk — moves headline) [COMPLETE]

**Goal:** let scrap miners carry quality modules so mined scrap has a quality
tier distribution; quality scrap recycles into the basket at tier, slashing the
scrap needed. This is the single biggest Fulgora lever.

**Files:** `dev/quality_planner.py`, `dev/test_quality_planner.py`, docs.

**Design**
- Way to specify miner quality modules (mirror recycler config; likely reuse the
  existing module-quality/tier knobs rather than a brand-new flag — decide:
  do drills share `--module-quality`/`--quality-module-tier`, or get their own?).
- Compute mined-scrap tier distribution: one quality roll per mine using the
  drill's quality slots (`quality_chance_from_specs` / `quality_tier_probs` /
  `_compose_quality_rolls` with the drill slot count; big drill = 4 slots).
- Feed input tier into the scrap-source yield: today `scrap_target_yield`
  assumes normal scrap (depth-d rolls only from recyclers). Generalize so a
  fraction of scrap already enters at uncommon/rare/…, raising the rare-tail
  yield per scrap and lowering `scrap_per_min`.
- Recyclers preserve quality; recycler quality modules still add rolls on top
  (already modelled). The two compound.

**Gotchas**
- This **changes the headline scrap number** → `TestLocationFulgora`
  expectations (scrap rate, machine counts) will shift. Update them with care;
  re-anchor against a reference (see C5).
- Plastic-bar was the binding leaf precisely because it only appears at depth 1
  with one recycler roll — quality scrap is exactly what relieves it. Verify the
  binding leaf changes / scrap drops materially in tests.
- Keep it Fulgora-only; don't perturb asteroid/other-planet paths.

**Test plan:** with drill quality modules, `scrap_per_min` strictly drops vs C1
baseline; higher drill quality → larger drop; zero drill quality reproduces the
C1 number (faithfulness self-check); binding-leaf assertion updated.

**Maintenance:** new flag (if added) → full flag-doc trio; behaviour → tests +
counts; update the Fulgora notes in `quality_planner.md`.

**Done when:** quality-scrap modelled, scrap figure realistic and monotonic in
drill quality, suites green.

---

## C4 — Recycler upcycle loop (planner scrap source, highest risk) — ✅ DONE (2026-07-01)

**Goal:** replace the single-pass rare-tail skim with a closed quality loop —
sub-target outputs are recycled and re-rolled (plate↔ore where legal) until they
reach the target tier, then pulled out. Reuses the planner's existing loop DP.

**Files:** `dev/quality_planner.py`, `dev/test_quality_planner.py`, docs.

**Design**
- The machinery already exists: `solve_asteroid_reprocessing_loop`,
  `solve_self_recycle_target_loop`, `_compose_quality_rolls`. Build a scrap-leaf
  upcycle solver in the same shape: per leaf, model recycle→re-roll→re-craft to
  the target tier and count the loop recyclers/furnaces.
- Decide per-item routability: plates upcycle via plate→ore (quality recycler
  re-roll)→re-smelt; items with no useful self-loop (e.g. plastic-bar) fall back
  to C3's seeded single-pass. Encode a routing table / predicate.
- The cascade's `mined_raws` cutoff in `build_scrap_cascade` is a *forward-DAG*
  guard; the loop solver layers on top rather than removing that guard (don't
  reintroduce infinite forward recursion).
- Size loop recyclers/furnaces and fold into `total_machine_count` /
  `summary.by_role` (new role e.g. `scrap-upcycle-loop`).

**Gotchas**
- Highest regression surface: rewrites the dominant cost stage. Many
  `TestLocationFulgora` numbers move. Land behind careful re-anchoring.
- Watch loop convergence / steady-state correctness (reuse the proven DP, don't
  hand-roll a new fixed-point).
- Furnaces have no quality slots by default — quality is *preserved* through
  smelting but rolled only in the recycler; model accordingly.

**Test plan:** upcycle loop yields more rare per scrap than C3 alone; scrap drops
again; loop recyclers appear in totals/by_role; non-upcyclable leaf
(plastic-bar) still routes via seeded single-pass; faithfulness check (disabling
the loop reproduces C3).

**Done when:** scrap number reflects a real grind, loop machines counted, suites
green, numbers re-anchored.

---

## C5 — Validation & doc consolidation

- Re-anchor the headline Fulgora numbers against a reference (FactorioLab, the
  wiki quality pages in `references/quality`, or the user's in-game figures).
  Record the anchor in tests so future regressions are caught.
- Fold the shipped behaviour from this doc into `dev/quality_planner.md`
  (Status + Fulgora section + Tests table + roadmap).
- Update `CLAUDE.md`, `README.md` (feature blurbs + test counts), `SKILL.md`
  §11 as needed.
- Delete this file.

---

## Appendix A (optional, independent) — cli.py quality-ore output

Model a quality module in a drill producing quality *ore/scrap* in `cli.py`'s
recursive solver (per-resource quality split, analogous to crafting-step
`quality_output`). Bigger change to cli's quality model (raws are currently
terminal); **not required** for C3/C4 since the planner models scrap quality
itself. Pursue only if cli users want it. Keep separate from the Fulgora chunks.

---

## Open decisions (confirm before the relevant chunk)

1. **C1:** miners as entries inside `out["stages"]` (role `mining`) vs a separate
   `miners_needed` section. **DECIDED (Option A): in-stages** — drills render as
   `[mining]` lines in Production Stages and are summed into the total like any
   other stage; preserves the `total == sum(stages)` invariant.
2. **C2:** does `--machine-quality` also lift pumpjack/offshore throughput, or
   only drills?
3. **C3:** do drills share `--module-quality`/`--quality-module-tier` with
   recyclers, or get a dedicated `--miner-modules` surface?
4. **C4:** routing table for which scrap leaves can upcycle (plate↔ore) vs fall
   back to seeded single-pass — enumerate explicitly.
5. **DECIDED (general):** miner counting runs for any plan with solid mined/scrap
   raws, not just Fulgora — it's correct everywhere; Fulgora exercises it hardest.
