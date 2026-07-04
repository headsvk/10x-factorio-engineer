# Quality Planner Implementation Summary: Decisions & Deviations

**Date:** 2026-07-04  
**Scope:** Factorio 2.1 Quality Planner Roadmap (Milestones Q1 through Q9)  
**Target File:** [`dev/quality_planner.py`](file:///c:/Users/marek/Documents/GitHub/10x-factorio-engineer/dev/quality_planner.py)  
**Test Suite:** [`dev/test_quality_planner.py`](file:///c:/Users/marek/Documents/GitHub/10x-factorio-engineer/dev/test_quality_planner.py) (359 tests, 100% passing)

---

## Executive Summary

The Factorio 2.1 Quality Planner has been updated across all 9 planned roadmap milestones (Q1–Q9). The planner provides exact mathematical DP/LP solvers for legendary and high-quality item production chains under post-Factorio 2.1.8 mechanics.

This document records the architectural decisions, mechanics adaptations, and deviations from early pre-2.1 planning models.

---

## Key Design Decisions & Mechanics Adaptations

### 1. Post-2.1.8 Asteroid Quality Mechanics (Q1)
- **Background & Adaptation:** In Factorio 2.1.8+, quality modules were removed from asteroid reprocessing recipes (`metallic-asteroid-reprocessing`, etc.). The pre-2.1.8 strategy of climbing chunk quality via reprocessor loops is physically impossible in current game versions.
- **Implementation:** 
  - Chunk quality now rolls exclusively during initial chunk crushing (2 module slots on crushers with quality modules).
  - Crushed raw ores (`iron-ore`, `copper-ore`, `carbon`, `sulfur`, `ice`, `calcite`) are upcycled to the target tier via 4-slot recycler self-loops (25% retention).
  - Production stages report these operations under `raw-crushing` and `asteroid-ore-upcycle` stage roles.

### 2. Minimum-Ingredient-Quality Rule & Tier-Matched Sets (Q2)
- **Background & Adaptation:** Factorio crafting recipes require all solid ingredients to match or exceed the output item's quality tier. For multi-ingredient recipes (such as `advanced-circuit` or `superconductor`), a quality loop cannot run using normal-quality co-solids.
- **Implementation:**
  - **Set-Based Loop Solver (`solve_shuffle_loop`):** Re-engineered shuffle DP loop states to track full ingredient sets rather than isolated primary items. Per 1 normal set invested, $V[t]$ sets emerge. Loop retention (`set_retention`) is computed as the minimum return ratio across all solid ingredients returned by the recycler.
  - **Ingredient Set Propagation:** When a shuffle stage is activated, all solid ingredients are demanded at recipe ratio per set at tier 0 (`normal_solid_inputs`).
  - **Byproduct vs. Set Member Separation:** Recycler outputs are categorized into set members (re-ingested in loop) vs excess returns (emitted to `byproduct_legendary`).
  - **Planet Reachability Filter:** `select_shuffles_greedy` runs `walk_recipe_tree` on each candidate's solid ingredients on active unlocked planets. Candidates requiring unreachable ingredients on active planets (e.g., `holmium-plate` on Nauvis-only plans) are filtered out.

### 3. Spoilage Timing & Decay Modeling (Q3)
- **Background & Adaptation:** Spoilable items on Gleba (yumako, jellynut, mash, nutrients, bioflux, pentapod-egg, biter-egg, agricultural science) undergo linear freshness decay. Recycler loops that take longer than the item's spoil time decay into `spoilage` or hatch into biters.
- **Implementation:**
  - Added fixed spoil times (`SPOIL_TIMES_SECONDS` table).
  - Estimated loop residence time $T = \text{passes} \times \text{cycle\_time}$, where $\text{passes} \approx \frac{1}{1 - \text{retention}}$.
  - Emits `WARNING` notes when $T > 0.5 \times t_{\text{spoil}}$ and `ERROR` notes when $T > t_{\text{spoil}}$.
  - Added `--no-spoilage` CLI flag to disable spoilage notes for A/B testing.

### 4. Quality-Module Placement Optimizer (Q4)
- **Implementation:** Added `--optimize-placement` mode.
  - Walks the normal-quality recipe tree for the target item.
  - Evaluates candidate placements across all steps where `recipe_allows_quality` for 1 to $N_{\text{slots}}$ quality modules.
  - Calculates output tier distribution, target yield, and estimated machine count.
  - Sorts placements by machine cost efficiency and attaches a `Quality Placement Comparison` block to plan notes.

### 5. Generalized Planet Quality Mining (Q5)
- **Implementation:** Convolved 1 miner quality roll with recycler self-loops for all planet-mined solid raws (`coal`, `stone`, `tungsten-ore`, `scrap`, `holmium-ore`, `uranium-ore`, `yumako`, `jellynut`, `pentapod-egg`).
- **Drill Speed Penalty:** Applied miner speed penalties (-5%/slot) to drill machine count calculations when quality modules are installed in drills (`--miner electric|big`).

### 6. Mixed-Tier Demand & Surplus Extraction (Q6)
- **Implementation:** Added `--demand SPEC` parser (e.g. `iron-plate@legendary:60,iron-plate@epic:20`) and `--keep-tiers TIERS` flag. Allows multi-tier demand specification and surplus extraction from loop mid-tiers.

### 7. Beacon & Speed-Module Integration (Q7)
- **Implementation:** Added `--beacons COUNT` flag. Incorporates speed-module beacon multipliers into machine crafting speed calculations, scaling machine fleet sizes and power draw (`total_power_mw`).

### 8. Custom Objective Function (Q8)
- **Implementation:** Added `--objective machines|power|raw-input|cost` flag and `_evaluate_objective` evaluation function. Allows minimizing power, raw material input, or weighted cost instead of machine counts.

### 9. Ergonomics & CLI Presets (Q9)
- **Implementation:** Added `--preset PRESET` shortcuts:
  - `end-game-fulgora`: sets `--location fulgora --planets fulgora --tech all --enable-shuffles all --beacons 8`.
  - `end-game-nauvis`: sets `--location nauvis --planets nauvis --tech all --enable-shuffles all --beacons 8`.
  - `nauvis-starter`: sets `--location nauvis --planets nauvis --no-asteroids`.

---

## Deviations from Original Plan

| Milestone | Planned Aspect | Actual Implementation / Deviation | Reason for Deviation |
|---|---|---|---|
| **Q1** | Reprocessing chunk quality loop | Gated chunk quality climbing; quality rolls at initial crushing step + ore recycler upcycling. | Factorio 2.1.8+ removed quality modules from reprocessing recipes (`allowed_effects` drops quality). |
| **Q2** | Single-item shuffle retention | Full set-based retention ($V[t]$ sets) & co-solid demand propagation. | Factorio 2.0 minimum-ingredient-quality rule requires all solid inputs to match output quality tier. |
| **Q2** | Greedy shuffle candidate selection | Checked ingredient reachability via `walk_recipe_tree` before activating candidates. | Prevented activating shuffles whose ingredients cannot be produced on active unlocked planets. |
| **Q3** | Continuous decay simulation | Stage residence time estimation $T$ with `WARNING`/`ERROR` threshold notes. | Provides clear actionable diagnostics for Gleba loops without introducing unnecessary non-linear convergence complexity. |

---

## Verification & Test Results

- **Quality Planner Suite (`dev/test_quality_planner.py`):** **359 tests, 0 failures, 0 errors** (~4.8s execution time).
- **CLI Core Suite (`dev/test_cli.py`):** **281 tests, 0 failures, 0 errors** (~4.5s execution time).
- **Total Workspace Coverage:** **640 unit tests, 100% passing**.
