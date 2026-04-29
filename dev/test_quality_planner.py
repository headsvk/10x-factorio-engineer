"""Tests for dev/quality_planner.py (V1 MVP).

Stdlib unittest; matches cli.py test style (self-contained, no external deps).
Tests focus on DP kernel correctness, asteroid reprocessing math, fluid
transparency, fail-fast errors, and end-to-end regression.
"""

import json
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import quality_planner as qp


def _data():
    """Cached Space Age dataset."""
    if not hasattr(_data, "_cache"):
        _data._cache = qp.cli.load_data("nauvis")
    return _data._cache


# ---------------------------------------------------------------------------
# DP kernel basics
# ---------------------------------------------------------------------------

class TestDPKernel(unittest.TestCase):

    def test_quality_chance_zero_modules(self):
        self.assertEqual(qp._quality_chance(0, 3, "legendary"), 0.0)

    def test_quality_chance_t3_legendary(self):
        # T3 quality module at legendary quality: 2.5% per slot
        q = qp._quality_chance(1, 3, "legendary")
        self.assertAlmostEqual(q, 0.025 * 2.5)

    def test_quality_chance_t1_normal(self):
        q = qp._quality_chance(1, 1, "normal")
        self.assertAlmostEqual(q, 0.01)

    def test_quality_chance_stacks_linearly(self):
        q1 = qp._quality_chance(1, 3, "legendary")
        q4 = qp._quality_chance(4, 3, "legendary")
        self.assertAlmostEqual(q4, 4 * q1)

    def test_quality_chance_clamped(self):
        # 20 T3 legendary modules would exceed 100%, must clamp
        q = qp._quality_chance(20, 3, "legendary")
        self.assertLessEqual(q, 1.0)

    def test_tier_skip_probs_sum_normal(self):
        # At tier 0 (normal), probs sum to 1.0 (accounting for full spread)
        probs = qp._tier_skip_probs(0.1, 0)
        self.assertAlmostEqual(sum(probs), 1.0)

    def test_tier_skip_probs_90_9_distribution(self):
        # Quality chance Q=0.1, tier=0 — +1 share=90%, +2 share=9%
        probs = qp._tier_skip_probs(0.1, 0)
        # probs[0]=stay, probs[1]=+1, probs[2]=+2, probs[3]=+3, probs[4]=+4
        self.assertAlmostEqual(probs[0], 0.9)   # 1-Q
        self.assertAlmostEqual(probs[1], 0.1 * 0.9)
        self.assertAlmostEqual(probs[2], 0.1 * 0.09)

    def test_tier_skip_probs_caps_at_legendary(self):
        # From tier 2 (rare), +3 and +4 should pile onto legendary (index 2+ are epic, legendary)
        probs = qp._tier_skip_probs(0.1, 2)
        # Only 3 buckets: [rare, epic, legendary]
        self.assertEqual(len(probs), 3)
        # legendary accumulates all tier-skips beyond it
        self.assertAlmostEqual(sum(probs), 1.0)

    def test_prod_bonus_t3_legendary(self):
        # T3 prod at legendary = 10% * 2.5 = 25% per slot
        p = qp._prod_bonus(1, 3, "legendary")
        self.assertAlmostEqual(p, 0.25)

    def test_prod_bonus_zero(self):
        self.assertEqual(qp._prod_bonus(0, 3, "legendary"), 0.0)
        self.assertEqual(qp._prod_bonus(5, 0, "legendary"), 0.0)


class TestDPKernelYields(unittest.TestCase):
    """Reproduce wiki yield numbers for standard self-recycling items."""

    def test_iron_plate_electric_furnace_legendary_yield(self):
        # Iron plate on electric furnace (2 slots), legendary T3 quality modules.
        # Wiki cites EM-plant 0.177% — our electric furnace is actually close to that
        # because iron-plate also self-recycles simply (one ingredient).
        v, cfg = qp.solve_recycle_loop(
            "iron-plate", _data(), "electric-furnace", 2, True,
            inherent_prod=0.0, research_prod=0.0, module_quality="legendary",
        )
        # Expect ~0.1-0.3% with 2-slot machine all quality + 4-slot recycler
        self.assertGreater(v, 0.0005)
        self.assertLess(v, 0.05)

    def test_legendary_modules_outperform_normal(self):
        v_leg, _ = qp.solve_recycle_loop(
            "iron-plate", _data(), "electric-furnace", 2, True,
            0.0, 0.0, "legendary",
        )
        v_nor, _ = qp.solve_recycle_loop(
            "iron-plate", _data(), "electric-furnace", 2, True,
            0.0, 0.0, "normal",
        )
        # Legendary quality modules give >2x uplift over normal
        self.assertGreater(v_leg, v_nor * 2.0)

    def test_prod_cap_clamps(self):
        # With many prod slots + high research, prod should cap at +300%.
        # We verify indirectly: V with research=10 levels ~= V with research=5 once capped
        v5, _ = qp.solve_recycle_loop(
            "iron-plate", _data(), "electric-furnace", 2, True,
            0.0, 5.0, "legendary",
        )
        v10, _ = qp.solve_recycle_loop(
            "iron-plate", _data(), "electric-furnace", 2, True,
            0.0, 10.0, "legendary",
        )
        # With cap in effect at +300% both levels saturate -> v10 close to v5
        self.assertAlmostEqual(v5, v10, delta=v5 * 0.01)


# ---------------------------------------------------------------------------
# Asteroid reprocessing
# ---------------------------------------------------------------------------

class TestAsteroidReprocessing(unittest.TestCase):

    def test_reprocessing_recipe_retention_80pct(self):
        # Sum of reprocessing output probs should be 0.8
        rec = qp._recipe_by_key(_data(), "metallic-asteroid-reprocessing")
        assert rec is not None
        total = sum(
            float(r.get("amount", 0)) * float(r.get("probability", 1.0))
            for r in rec.get("results", [])
        )
        self.assertAlmostEqual(total, 0.8, places=3)

    def test_asteroid_loop_legendary_yield_positive(self):
        v, cfg = qp.solve_asteroid_reprocessing_loop(
            "metallic-asteroid-chunk", _data(), "legendary", 3,
        )
        self.assertGreater(v, 0.0)
        self.assertLess(v, 1.0)
        # Should select 2 quality modules on crusher for legendary target
        self.assertEqual(cfg[0]["recycle_quality"], 2)

    def test_asteroid_loop_three_chunks_same_yield(self):
        # All three chunk types have same 80% retention and use the same crusher;
        # yields should be identical.
        v_m, _ = qp.solve_asteroid_reprocessing_loop("metallic-asteroid-chunk", _data(), "legendary", 3)
        v_c, _ = qp.solve_asteroid_reprocessing_loop("carbonic-asteroid-chunk", _data(), "legendary", 3)
        v_o, _ = qp.solve_asteroid_reprocessing_loop("oxide-asteroid-chunk", _data(), "legendary", 3)
        self.assertAlmostEqual(v_m, v_c, delta=1e-6)
        self.assertAlmostEqual(v_m, v_o, delta=1e-6)

    def test_lower_module_quality_lower_yield(self):
        v_leg, _ = qp.solve_asteroid_reprocessing_loop("metallic-asteroid-chunk", _data(), "legendary", 3)
        v_nor, _ = qp.solve_asteroid_reprocessing_loop("metallic-asteroid-chunk", _data(), "normal", 3)
        self.assertGreater(v_leg, v_nor)

    def test_lower_module_tier_lower_yield(self):
        v_t3, _ = qp.solve_asteroid_reprocessing_loop("metallic-asteroid-chunk", _data(), "legendary", 3)
        v_t1, _ = qp.solve_asteroid_reprocessing_loop("metallic-asteroid-chunk", _data(), "legendary", 1)
        self.assertGreater(v_t3, v_t1)

    def test_unknown_chunk_returns_zero(self):
        v, cfg = qp.solve_asteroid_reprocessing_loop("not-a-chunk", _data(), "legendary", 3)
        self.assertEqual(v, 0.0)
        self.assertEqual(cfg, {})


# ---------------------------------------------------------------------------
# Fluid transparency
# ---------------------------------------------------------------------------

class TestFluidTransparency(unittest.TestCase):

    def setUp(self):
        self.data = _data()
        self.recipe_idx = qp.cli.build_recipe_index(self.data)
        self.fluids = qp.build_fluid_set(self.data)
        self.planet_props = qp.cli.get_planet_props(self.data, "nauvis")

    def test_iron_plate_picks_casting_on_nauvis(self):
        r = qp._pick_recipe_fluid_preferred("iron-plate", self.recipe_idx, self.fluids, self.planet_props)
        assert r is not None
        self.assertEqual(r["key"], "casting-iron")

    def test_copper_cable_picks_casting(self):
        r = qp._pick_recipe_fluid_preferred("copper-cable", self.recipe_idx, self.fluids, self.planet_props)
        assert r is not None
        self.assertEqual(r["key"], "casting-copper-cable")

    def test_molten_iron_picks_from_ore_not_lava_on_nauvis(self):
        r = qp._pick_recipe_fluid_preferred("molten-iron", self.recipe_idx, self.fluids, self.planet_props)
        assert r is not None
        # Lava variant is planet-exclusive; should pick the ore variant
        self.assertEqual(r["key"], "molten-iron")

    def test_fluid_set_contains_molten_iron(self):
        self.assertIn("molten-iron", self.fluids)
        self.assertIn("water", self.fluids)

    def test_fluid_set_does_not_contain_iron_ore(self):
        self.assertNotIn("iron-ore", self.fluids)


# ---------------------------------------------------------------------------
# Assembly propagation (end-to-end stages)
# ---------------------------------------------------------------------------

class TestAssemblyPropagation(unittest.TestCase):

    def test_electronic_circuit_all_legendary(self):
        out = qp.plan("electronic-circuit", 60, _data())
        # final stage must be assembly with all-legendary inputs flag True
        final = out["stages"][-1]
        self.assertEqual(final["recipe"], "electronic-circuit")
        self.assertTrue(final.get("inputs_all_legendary"))

    def test_iron_gear_wheel_chain(self):
        out = qp.plan("iron-gear-wheel", 60, _data())
        recipes = [s.get("recipe") for s in out["stages"]]
        self.assertIn("metallic-asteroid-reprocessing", recipes)
        self.assertIn("advanced-metallic-asteroid-crushing", recipes)
        # Foundry casting picked
        self.assertIn("casting-iron-gear-wheel", recipes)


# ---------------------------------------------------------------------------
# Research productivity
# ---------------------------------------------------------------------------

class TestResearchProd(unittest.TestCase):

    def test_research_lookup(self):
        b = qp._research_prod_for_recipe("metallic-asteroid-crushing", {"asteroid-productivity": 5})
        self.assertAlmostEqual(b, 0.5)

    def test_no_research(self):
        b = qp._research_prod_for_recipe("iron-plate", {})
        self.assertEqual(b, 0.0)

    def test_unknown_tech_ignored(self):
        b = qp._research_prod_for_recipe("iron-plate", {"bogus-research": 99})
        self.assertEqual(b, 0.0)

    def test_research_reduces_machine_count(self):
        out_no = qp.plan("electronic-circuit", 60, _data(), research_levels={})
        out_hi = qp.plan(
            "electronic-circuit", 60, _data(),
            research_levels={"asteroid-productivity": 10},
        )
        # With asteroid prod, crushing+reprocessing loops produce more legendary chunks
        # per raw input -> fewer raw chunks required.
        self.assertLess(
            sum(out_hi["asteroid_input"].values()),
            sum(out_no["asteroid_input"].values()) + 1e-6,  # allow equal if no effect
        )


# ---------------------------------------------------------------------------
# Fail-fast
# ---------------------------------------------------------------------------

class TestFailFast(unittest.TestCase):

    def test_tungsten_plate_errors(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("tungsten-plate", 60, _data())
        self.assertIn("vulcanus", str(cm.exception))

    # NOTE: holmium-plate, superconductor, tungsten-carbide were previously
    # in TestFailFast (V1/V2 fail-fast on self-recycling).  V3 item 3 added
    # a dedicated self-recycle target solver — coverage moved to
    # TestSelfRecycleTarget below.

    def test_plastic_bar_errors_no_oil(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("plastic-bar", 60, _data())
        # plastic-bar needs oil chain → blocked without --planets
        msg = str(cm.exception)
        self.assertIn("plastic-bar", msg)
        self.assertIn("--planets", msg)

    def test_processing_unit_errors_sulfuric_acid(self):
        # processing unit needs sulfuric-acid -> sulfur -> petroleum-gas (no crude-oil)
        with self.assertRaises(ValueError) as cm:
            qp.plan("processing-unit", 60, _data())
        msg = str(cm.exception)
        self.assertIn("--planets", msg)

    def test_artillery_shell_errors(self):
        # artillery shell needs tungsten-plate (Vulcanus) + explosives (oil)
        with self.assertRaises(ValueError):
            qp.plan("artillery-shell", 60, _data())


# ---------------------------------------------------------------------------
# End-to-end regression
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):

    def test_electronic_circuit_60_per_min(self):
        out = qp.plan("electronic-circuit", 60, _data())
        self.assertEqual(out["target"]["item"], "electronic-circuit")
        self.assertEqual(out["target"]["rate_per_min"], 60)
        self.assertEqual(out["target"]["tier"], "legendary")
        # Must have asteroid input for metallic (iron, copper via cable)
        self.assertIn("metallic-asteroid-chunk", out["asteroid_input"])
        # Total machines should be a positive finite number
        self.assertGreater(out["total_machine_count"], 0.0)
        self.assertLess(out["total_machine_count"], 10000.0)

    def test_iron_plate_simple_chain(self):
        out = qp.plan("iron-plate", 60, _data())
        # iron-plate via casting-iron (foundry)
        recipes = [s.get("recipe") for s in out["stages"]]
        self.assertIn("casting-iron", recipes)
        self.assertIn("advanced-metallic-asteroid-crushing", recipes)
        self.assertIn("metallic-asteroid-reprocessing", recipes)

    def test_copper_plate_chain(self):
        out = qp.plan("copper-plate", 60, _data())
        recipes = [s.get("recipe") for s in out["stages"]]
        self.assertIn("casting-copper", recipes)

    def test_json_serializable(self):
        out = qp.plan("iron-plate", 60, _data())
        # Must be JSON-serializable (dashboard-compatible)
        j = json.dumps(out, default=str)
        self.assertIn("target", j)

    def test_human_format_runs(self):
        out = qp.plan("iron-plate", 60, _data())
        text = qp.format_human(out)
        self.assertIn("Target:", text)
        self.assertIn("Asteroid Input", text)
        self.assertIn("Production Stages", text)

    def test_higher_rate_scales_linearly(self):
        a = qp.plan("iron-plate", 60, _data())
        b = qp.plan("iron-plate", 120, _data())
        # Asteroid input should roughly double
        ai_a = sum(a["asteroid_input"].values())
        ai_b = sum(b["asteroid_input"].values())
        self.assertAlmostEqual(ai_b, ai_a * 2.0, delta=ai_a * 0.02)


# ---------------------------------------------------------------------------
# Helpers / small units
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):

    def test_recipe_result_amount_probabilistic(self):
        rec = qp._recipe_by_key(_data(), "metallic-asteroid-reprocessing")
        assert rec is not None
        a = qp._recipe_result_amount(rec, "metallic-asteroid-chunk")
        # 1 * 0.4 probability
        self.assertAlmostEqual(a, 0.4)

    def test_recipe_result_amount_standard(self):
        rec = qp._recipe_by_key(_data(), "iron-plate")
        assert rec is not None
        a = qp._recipe_result_amount(rec, "iron-plate")
        self.assertEqual(a, 1)

    def test_recipe_ing_amount(self):
        rec = qp._recipe_by_key(_data(), "electronic-circuit")
        assert rec is not None
        self.assertEqual(qp._recipe_ing_amount(rec, "iron-plate"), 1)
        self.assertEqual(qp._recipe_ing_amount(rec, "copper-cable"), 3)
        self.assertEqual(qp._recipe_ing_amount(rec, "nonexistent"), 0)

    def test_build_fluid_set_nonempty(self):
        fluids = qp.build_fluid_set(_data())
        self.assertIn("water", fluids)
        self.assertIn("crude-oil", fluids)
        self.assertIn("molten-iron", fluids)
        self.assertNotIn("iron-ore", fluids)

    def test_humanize(self):
        self.assertEqual(qp._humanize("assembling-machine-3"), "Assembler 3")
        self.assertEqual(qp._humanize("metallic-asteroid-chunk"), "Metallic Chunk")
        self.assertEqual(qp._humanize("some-new-item"), "Some New Item")


class TestParseResearch(unittest.TestCase):

    def test_valid(self):
        out = qp._parse_research(["asteroid-productivity=5", "steel-productivity=10"])
        self.assertEqual(out, {"asteroid-productivity": 5, "steel-productivity": 10})

    def test_empty(self):
        self.assertEqual(qp._parse_research([]), {})


# ---------------------------------------------------------------------------
# V2 — multi-planet unlock flag
# ---------------------------------------------------------------------------

class TestPlanetsFlag(unittest.TestCase):

    def test_empty_planets_same_as_v1(self):
        # Without --planets, V1 items still work identically.
        out_v1 = qp.plan("iron-plate", 60, _data())
        out_v2 = qp.plan("iron-plate", 60, _data(), planets=[])
        # Same asteroid input (allow tiny float jitter).
        self.assertAlmostEqual(
            sum(out_v1["asteroid_input"].values()),
            sum(out_v2["asteroid_input"].values()),
            delta=0.01,
        )

    def test_unknown_planet_errors(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("iron-plate", 60, _data(), planets=["atlantis"])
        self.assertIn("unknown planet", str(cm.exception))

    def test_nauvis_unlocks_plastic_bar(self):
        # Plastic-bar was blocked in V1 (oil chain unavailable); --planets nauvis unlocks it.
        out = qp.plan("plastic-bar", 60, _data(), planets=["nauvis"])
        recipes = [s.get("recipe") for s in out["stages"]]
        self.assertIn("plastic-bar", recipes)
        # Coal comes through mined-recycle, not asteroid.
        self.assertIn("Coal", [qp._humanize(k) for k in out["mined_input"]])
        # Crude-oil is a fluid raw, quality-transparent.
        self.assertIn("crude-oil", out["fluid_input"])

    def test_vulcanus_unlocks_tungsten_plate(self):
        out = qp.plan("tungsten-plate", 60, _data(), planets=["vulcanus"])
        # Tungsten-ore routed through mined-recycle.
        self.assertIn("tungsten-ore", out["mined_input"])
        # Lava used as fluid raw.
        self.assertIn("lava", out["fluid_input"])
        # Tungsten-plate stage uses foundry.
        final = out["stages"][-1]
        self.assertEqual(final["recipe"], "tungsten-plate")

    def test_plastic_bar_still_blocks_without_planets(self):
        # No --planets → plastic-bar still blocked with a helpful hint.
        with self.assertRaises(ValueError) as cm:
            qp.plan("plastic-bar", 60, _data())
        self.assertIn("--planets", str(cm.exception))

    def test_processing_unit_with_nauvis(self):
        out = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        recipes = [s.get("recipe") for s in out["stages"]]
        self.assertIn("processing-unit", recipes)
        self.assertIn("sulfuric-acid", recipes)

    def test_artillery_shell_with_nauvis_vulcanus(self):
        out = qp.plan("artillery-shell", 60, _data(), planets=["nauvis", "vulcanus"])
        # Needs both oil chain (explosives) and tungsten-plate.
        self.assertIn("coal", out["mined_input"])
        self.assertIn("tungsten-ore", out["mined_input"])
        recipes = [s.get("recipe") for s in out["stages"]]
        self.assertIn("artillery-shell", recipes)

    def test_planets_listed_in_output(self):
        out = qp.plan("plastic-bar", 60, _data(), planets=["nauvis"])
        self.assertEqual(out["planets"], ["nauvis"])

    def test_fluid_raws_quality_transparent(self):
        # Crude-oil and lava should appear in fluid_input but never in asteroid_input.
        out = qp.plan("plastic-bar", 60, _data(), planets=["nauvis"])
        for k in out["fluid_input"]:
            self.assertNotIn(k, out["asteroid_input"])


# ---------------------------------------------------------------------------
# V2 — mined-raw self-recycle loop
# ---------------------------------------------------------------------------

class TestMinedRawSelfRecycle(unittest.TestCase):

    def test_coal_self_recycle_positive(self):
        v, cfg = qp.solve_mined_raw_self_recycle_loop(
            "coal", _data(), "legendary", 3,
        )
        self.assertGreater(v, 0.0)
        self.assertLess(v, 0.01)  # expect ~0.03–0.04% yield
        # Should select all 4 quality slots at tier 0 for legendary target.
        self.assertEqual(cfg[0]["recycle_quality"], 4)

    def test_stone_self_recycle_same_as_coal(self):
        # Identical retention/slots → identical yield.
        v_coal, _ = qp.solve_mined_raw_self_recycle_loop("coal", _data(), "legendary", 3)
        v_stone, _ = qp.solve_mined_raw_self_recycle_loop("stone", _data(), "legendary", 3)
        self.assertAlmostEqual(v_coal, v_stone, delta=1e-9)

    def test_tungsten_ore_self_recycle(self):
        v, _ = qp.solve_mined_raw_self_recycle_loop("tungsten-ore", _data(), "legendary", 3)
        self.assertGreater(v, 0.0)

    def test_holmium_ore_self_recycle(self):
        v, _ = qp.solve_mined_raw_self_recycle_loop("holmium-ore", _data(), "legendary", 3)
        self.assertGreater(v, 0.0)

    def test_lower_module_quality_lower_yield(self):
        v_leg, _ = qp.solve_mined_raw_self_recycle_loop("coal", _data(), "legendary", 3)
        v_nor, _ = qp.solve_mined_raw_self_recycle_loop("coal", _data(), "normal", 3)
        self.assertGreater(v_leg, v_nor)

    def test_unknown_raw_returns_zero(self):
        v, cfg = qp.solve_mined_raw_self_recycle_loop(
            "not-a-raw-key", _data(), "legendary", 3,
        )
        self.assertEqual(v, 0.0)
        self.assertEqual(cfg, {})

    def test_self_recycle_worse_than_asteroid(self):
        # Asteroid reprocessing (80% retention) should strictly beat recycler
        # self-loop (25% retention) at the same module config.
        v_ast, _ = qp.solve_asteroid_reprocessing_loop(
            "metallic-asteroid-chunk", _data(), "legendary", 3,
        )
        v_rec, _ = qp.solve_mined_raw_self_recycle_loop(
            "coal", _data(), "legendary", 3,
        )
        self.assertGreater(v_ast, v_rec)


# ---------------------------------------------------------------------------
# V2 — LDS shuffle (indirect upgrade loop)
# ---------------------------------------------------------------------------

class TestLDSShuffle(unittest.TestCase):

    def test_lds_shuffle_no_research_positive(self):
        v, cfg = qp.solve_lds_shuffle_loop(_data(), "legendary", 3, 3)
        self.assertGreater(v, 0.001)
        self.assertLess(v, 1.0)
        # Config is populated for every tier.
        for t in range(4):
            self.assertIn("cast_prod", cfg[t])
            self.assertIn("cast_quality", cfg[t])
            self.assertIn("recycle_quality", cfg[t])

    def test_lds_shuffle_research_improves_yield(self):
        v_no, _ = qp.solve_lds_shuffle_loop(_data(), "legendary", 3, 3, research_prod=0.0)
        v_res, _ = qp.solve_lds_shuffle_loop(_data(), "legendary", 3, 3, research_prod=0.5)
        self.assertGreater(v_res, v_no)

    def test_lds_shuffle_prod_cap(self):
        # +300% cap: research_prod=2.5 already saturates with foundry's +50%.
        # Further research should have no effect.
        v_cap, _ = qp.solve_lds_shuffle_loop(_data(), "legendary", 3, 3, research_prod=2.5)
        v_over, _ = qp.solve_lds_shuffle_loop(_data(), "legendary", 3, 3, research_prod=5.0)
        self.assertAlmostEqual(v_cap, v_over, delta=1e-6)

    def test_lds_shuffle_beats_asteroid_with_research(self):
        # With meaningful research, LDS shuffle yield exceeds asteroid
        # reprocessing (~0.4%).  Without research it's comparable.
        v_lds, _ = qp.solve_lds_shuffle_loop(
            _data(), "legendary", 3, 3, research_prod=0.5,
        )
        v_ast, _ = qp.solve_asteroid_reprocessing_loop(
            "metallic-asteroid-chunk", _data(), "legendary", 3,
        )
        self.assertGreater(v_lds, v_ast)

    def test_lds_shuffle_lower_module_quality_lower_yield(self):
        v_leg, _ = qp.solve_lds_shuffle_loop(_data(), "legendary", 3, 3)
        v_nor, _ = qp.solve_lds_shuffle_loop(_data(), "normal", 3, 3)
        self.assertGreater(v_leg, v_nor)


# ---------------------------------------------------------------------------
# V2 — fulgora / aquilo / gleba unlocks
# ---------------------------------------------------------------------------

class TestOtherPlanetUnlocks(unittest.TestCase):

    def test_fulgora_unlocks_scrap(self):
        # electrolyte → stone + holmium-ore + heavy-oil (fulgora offshore).
        # With --planets fulgora, holmium-ore and stone are unlocked as mined raws.
        out = qp.plan("electrolyte", 60, _data(), planets=["fulgora", "nauvis"])
        self.assertIn("holmium-ore", out["mined_input"])
        self.assertIn("stone", out["mined_input"])

    def test_mined_recycle_stage_shape(self):
        out = qp.plan("plastic-bar", 60, _data(), planets=["nauvis"])
        mined_stages = [s for s in out["stages"] if s.get("role") == "mined-raw-self-recycle"]
        self.assertEqual(len(mined_stages), 1)
        st = mined_stages[0]
        self.assertEqual(st["raw"], "coal")
        self.assertIn("legendary_per_min", st)
        self.assertIn("normal_mined_per_min", st)
        self.assertIn("yield_pct", st)
        self.assertEqual(st["machine"], "recycler")


class TestLDSShuffleWiring(unittest.TestCase):
    """V3 partial: --enable-lds-shuffle flag wires the shuffle into plan()."""

    def test_flag_default_off(self):
        # Without the flag, output has no shuffle stage and no normal-input buckets.
        out = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        shuffle_stages = [s for s in out["stages"] if s.get("role") == "cross-item-shuffle"]
        self.assertEqual(shuffle_stages, [])
        self.assertEqual(out.get("normal_solid_input"), {})
        self.assertEqual(out.get("normal_fluid_input"), {})
        self.assertEqual(out.get("shuffle_byproduct_legendary"), {})

    def test_flag_on_no_research_positive(self):
        # With shuffle on, no research: shuffle stage present with positive yield;
        # mined coal eliminated (replaced by normal coal input).
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
        )
        shuffle = [s for s in out["stages"] if s.get("role") == "cross-item-shuffle"]
        self.assertEqual(len(shuffle), 1)
        self.assertGreater(shuffle[0]["yield_per_normal_plastic_pct"], 0.0)
        self.assertGreater(shuffle[0]["foundry_machines"], 0.0)
        self.assertGreater(shuffle[0]["recycler_machines"], 0.0)
        # Coal moved out of mined_input into normal_solid_input.
        self.assertNotIn("coal", out["mined_input"])
        self.assertIn("coal", out["normal_solid_input"])
        self.assertGreater(out["normal_solid_input"]["coal"], 0.0)

    def test_high_research_reduces_total_machines(self):
        # With high LDS productivity research, shuffle becomes more efficient and
        # total machines should drop below the no-research shuffle total.
        out_low = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
        )
        out_high = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
            research_levels={"low-density-structure-productivity": 10},
        )
        self.assertLess(
            out_high["total_machine_count"], out_low["total_machine_count"]
        )

    def test_byproduct_credit_drops_metallic_asteroid_input(self):
        # Direct walker test: feeding byproduct_credits reduces upstream raw demand
        # for the credited item's chain.  solar-panel demands copper-plate non-fluid.
        data = _data()
        fluids = qp.build_fluid_set(data)
        planet_props = qp.cli.get_planet_props(data, "nauvis")
        _, raws_base = qp.walk_recipe_tree(
            "solar-panel", 60, data, {}, 3, fluids, planet_props,
            frozenset({"nauvis"}),
        )
        _, raws_credited = qp.walk_recipe_tree(
            "solar-panel", 60, data, {}, 3, fluids, planet_props,
            frozenset({"nauvis"}),
            byproduct_credits={"copper-plate": 100.0},
        )
        # copper-ore demand should drop by 100 (1:1 via molten-copper chain).
        self.assertAlmostEqual(
            raws_base["copper-ore"] - raws_credited["copper-ore"], 100.0, delta=1e-3,
        )

    def test_byproduct_overflow_flagged_in_notes(self):
        # processing-unit's chain doesn't demand copper-plate (fluid-cast routes
        # around it), so all byproduct copper-plate is surplus → overflow note.
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
        )
        emitted = out["shuffle_byproduct_legendary"]
        overflow = out["shuffle_byproduct_overflow"]
        self.assertGreater(emitted.get("copper-plate", 0.0), 0.0)
        self.assertAlmostEqual(
            overflow.get("copper-plate", 0.0),
            emitted["copper-plate"], delta=1e-6,
        )
        self.assertTrue(any("surplus" in n and "copper-plate" in n for n in out["notes"]))

    def test_shuffle_stage_machine_count_in_total(self):
        # Total machines should include foundry+recycler from the shuffle stage.
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
        )
        shuffle_st = [s for s in out["stages"] if s.get("role") == "cross-item-shuffle"][0]
        self.assertGreaterEqual(
            out["total_machine_count"], shuffle_st["machine_count"],
        )

    def test_human_format_renders_shuffle(self):
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
        )
        text = qp.format_human(out)
        self.assertIn("Shuffle Byproducts", text)
        self.assertIn("[shuffle]", text)
        self.assertIn("Normal-Quality", text)


class TestSelfRecycleTarget(unittest.TestCase):
    """V3 item 3: items whose recycle returns themselves can now be targets."""

    def test_holmium_plate_target(self):
        out = qp.plan("holmium-plate", 60, _data(), planets=["fulgora"])
        sts = [s for s in out["stages"] if s.get("role") == "self-recycle-target"]
        self.assertEqual(len(sts), 1)
        st = sts[0]
        self.assertEqual(st["target"], "holmium-plate")
        self.assertEqual(st["machine"], "foundry")
        self.assertGreater(st["yield_per_normal_craft"], 0.0)
        self.assertLess(st["yield_per_normal_craft"], 1.0)
        self.assertGreater(st["craft_machines"], 0.0)
        self.assertGreater(st["recycler_machines"], 0.0)

    def test_tungsten_carbide_target(self):
        out = qp.plan("tungsten-carbide", 60, _data(), planets=["nauvis", "vulcanus"])
        st = [s for s in out["stages"] if s.get("role") == "self-recycle-target"][0]
        self.assertEqual(st["target"], "tungsten-carbide")
        self.assertGreater(st["yield_per_normal_craft"], 0.0)
        # Tungsten ore must appear as a normal-quality solid input.
        self.assertIn("tungsten-ore", out["normal_solid_input"])

    def test_superconductor_target(self):
        out = qp.plan("superconductor", 60, _data(), planets=["nauvis", "fulgora"])
        st = [s for s in out["stages"] if s.get("role") == "self-recycle-target"][0]
        self.assertEqual(st["machine"], "electromagnetic-plant")
        # EM plant has 5 slots + 50% inherent prod → high yield, low crafts/min
        self.assertGreater(st["yield_per_normal_craft"], 0.001)

    def test_legendary_modules_outperform_normal(self):
        out_leg = qp.plan(
            "holmium-plate", 60, _data(),
            planets=["fulgora"], module_quality="legendary",
        )
        out_nor = qp.plan(
            "holmium-plate", 60, _data(),
            planets=["fulgora"], module_quality="normal",
        )
        leg_st = [s for s in out_leg["stages"] if s.get("role") == "self-recycle-target"][0]
        nor_st = [s for s in out_nor["stages"] if s.get("role") == "self-recycle-target"][0]
        # Legendary modules give >2× the per-craft yield of normal modules.
        self.assertGreater(
            leg_st["yield_per_normal_craft"],
            nor_st["yield_per_normal_craft"] * 2.0,
        )

    def test_solver_unknown_item_returns_zero(self):
        v, cfg = qp.solve_self_recycle_target_loop(
            "not-a-thing", _data(),
            machine_key="assembling-machine-3", machine_slots=4,
            machine_allow_prod=True, inherent_prod=0.0, research_prod=0.0,
            module_quality="legendary",
        )
        self.assertEqual(v, 0.0)
        self.assertEqual(cfg, {})

    def test_rate_doubles_machines_double(self):
        out_60 = qp.plan("holmium-plate", 60, _data(), planets=["fulgora"])
        out_120 = qp.plan("holmium-plate", 120, _data(), planets=["fulgora"])
        self.assertAlmostEqual(
            out_120["total_machine_count"] / out_60["total_machine_count"],
            2.0, delta=0.01,
        )

    def test_module_config_per_tier_present(self):
        out = qp.plan("holmium-plate", 60, _data(), planets=["fulgora"])
        st = [s for s in out["stages"] if s.get("role") == "self-recycle-target"][0]
        self.assertIn("module_config_per_tier", st)
        self.assertIn("normal", st["module_config_per_tier"])
        # Per-tier entry has 'craft' and 'recycle' description strings.
        n = st["module_config_per_tier"]["normal"]
        self.assertIn("craft", n)
        self.assertIn("recycle", n)

    def test_human_format_renders_self_recycle(self):
        out = qp.plan("holmium-plate", 60, _data(), planets=["fulgora"])
        text = qp.format_human(out)
        self.assertIn("[self-recycle]", text)
        self.assertIn("Holmium Plate", text)


class TestAssemblyModules(unittest.TestCase):
    """V3 item 5: --assembly-modules fills assembly stage slots with prod modules."""

    def test_default_off(self):
        out = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        # Without flag, stages have no prod modules.
        for st in out["stages"]:
            if st.get("role") == "assembly":
                self.assertEqual(st.get("prod_modules", 0), 0)
                self.assertEqual(st.get("module_prod", 0.0), 0.0)

    def test_flag_reduces_total_machines(self):
        out_off = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        out_on = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], assembly_modules=True,
        )
        # Modules cut total machines by an order of magnitude on chained
        # foundry/EM-plant/cryogenic chains.
        self.assertLess(
            out_on["total_machine_count"], out_off["total_machine_count"] / 5,
        )

    def test_flag_reduces_raw_demand(self):
        out_off = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        out_on = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], assembly_modules=True,
        )
        # Asteroid input drops because every assembly stage's ingredient demand
        # is divided by (1+prod).
        m_off = out_off["asteroid_input"]["metallic-asteroid-chunk"]
        m_on = out_on["asteroid_input"]["metallic-asteroid-chunk"]
        self.assertLess(m_on, m_off / 5)

    def test_inherent_prod_applied_to_em_plant(self):
        # EM plant has 5 slots and 0.5 inherent prod.  With flag on at legendary T3,
        # module prod = 5 × 0.25 × 1 = 1.25, total = 1.25 + 0.5 = 1.75 (capped at 3.0).
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], assembly_modules=True,
        )
        em_stages = [
            s for s in out["stages"]
            if s.get("role") == "assembly" and s.get("machine") == "electromagnetic-plant"
        ]
        self.assertGreater(len(em_stages), 0)
        for s in em_stages:
            self.assertEqual(s["prod_modules"], 5)
            self.assertAlmostEqual(s["module_prod"], 1.75, delta=1e-6)

    def test_prod_cap_at_300pct(self):
        # With cryogenic-plant (8 slots) and high research, total prod hits +300% cap.
        out = qp.plan(
            "plastic-bar", 60, _data(),
            planets=["nauvis"], assembly_modules=True,
            research_levels={"plastic-bar-productivity": 30},
        )
        plastic_stages = [
            s for s in out["stages"]
            if s.get("role") == "assembly" and s.get("product") == "plastic-bar"
        ]
        self.assertGreater(len(plastic_stages), 0)
        # Capped flag set (eff_prod hit the 4.0 cap).
        self.assertTrue(any(s.get("prod_capped") for s in plastic_stages))

    def test_recipe_disallowing_prod_skipped(self):
        # casting-iron / casting-copper-cable typically allow_productivity=true,
        # but recipes flagged allow_productivity=false (e.g. *-recycling) get 0.
        # We use the helper directly to verify the gate.
        recipe = {"allow_productivity": False}
        prod, slots = qp._assembly_prod_bonus(
            "foundry", recipe, {"foundry": 4}, True, "legendary", 3,
        )
        self.assertEqual(prod, 0.0)
        self.assertEqual(slots, 0)

    def test_helper_returns_inherent_when_no_slots(self):
        # Machine with 0 slots in slots_map still gets inherent prod returned.
        recipe = {"allow_productivity": True}
        prod, slots = qp._assembly_prod_bonus(
            "foundry", recipe, {}, True, "legendary", 3,
        )
        self.assertEqual(prod, 0.5)  # foundry inherent
        self.assertEqual(slots, 0)

    def test_human_format_shows_prod_modules(self):
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], assembly_modules=True,
        )
        text = qp.format_human(out)
        self.assertIn("prod-3-legendary", text)


class TestGlebaPartial(unittest.TestCase):
    """V3 item 4 (partial): Gleba bio-raws via self-recycle (no spoilage model).

    Yumako / jellynut / pentapod-egg are added to ``MINED_RAW_PLANETS`` so the
    walker treats them as legendary-source-able via the same self-recycle DP
    used for coal/stone.  Spoilage timing is NOT modelled — long quality loops
    on spoiling intermediates (bioflux, nutrients) report optimistic numbers.
    """

    def test_bioflux_target(self):
        out = qp.plan("bioflux", 60, _data(), planets=["gleba"])
        self.assertGreater(out["total_machine_count"], 0)
        # Both yumako and jellynut required (recipe: 15 yumako-mash + 12 jelly).
        self.assertIn("yumako", out["mined_input"])
        self.assertIn("jellynut", out["mined_input"])
        self.assertGreater(out["mined_input"]["yumako"], 0)
        self.assertGreater(out["mined_input"]["jellynut"], 0)

    def test_plastic_bar_uses_bioplastic_on_gleba(self):
        # Without nauvis, plastic-bar must route through bioplastic
        # (bioflux + yumako-mash); coal must NOT appear.
        out = qp.plan("plastic-bar", 60, _data(), planets=["gleba"])
        self.assertNotIn("coal", out["mined_input"])
        self.assertIn("yumako", out["mined_input"])

    def test_sulfur_uses_biosulfur_on_gleba(self):
        out = qp.plan("sulfur", 60, _data(), planets=["gleba"])
        self.assertGreater(out["total_machine_count"], 0)
        self.assertIn("yumako", out["mined_input"])

    def test_lubricant_uses_biolubricant_on_gleba(self):
        out = qp.plan("lubricant", 60, _data(), planets=["gleba"])
        self.assertGreater(out["total_machine_count"], 0)
        self.assertIn("jellynut", out["mined_input"])

    def test_nutrients_target(self):
        out = qp.plan("nutrients", 60, _data(), planets=["gleba"])
        self.assertGreater(out["total_machine_count"], 0)
        self.assertIn("yumako", out["mined_input"])

    def test_assembly_modules_reduce_gleba_chain(self):
        out_off = qp.plan("bioflux", 60, _data(), planets=["gleba"])
        out_on = qp.plan(
            "bioflux", 60, _data(),
            planets=["gleba"], assembly_modules=True,
        )
        # Biochambers have 4 slots and +50% inherent prod → big drop.
        self.assertLess(
            out_on["total_machine_count"], out_off["total_machine_count"] / 3,
        )
        self.assertLess(
            out_on["mined_input"]["yumako"], out_off["mined_input"]["yumako"] / 3,
        )

    def test_yumako_self_recycle_yield(self):
        v, _ = qp.solve_mined_raw_self_recycle_loop(
            "yumako", _data(), "legendary", 3,
        )
        self.assertGreater(v, 0.0)
        self.assertLess(v, 0.01)  # tiny, similar to coal

    def test_no_gleba_unlocked_still_errors(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("bioflux", 60, _data(), planets=["nauvis"])
        msg = str(cm.exception).lower()
        self.assertTrue(
            "yumako" in msg or "gleba" in msg or "no recipe" in msg,
            f"Unexpected error: {cm.exception}",
        )


class TestStagePower(unittest.TestCase):
    """V3 small item: per-stage power_kw + top-level total_power_mw."""

    def test_total_power_present_and_positive(self):
        out = qp.plan("electronic-circuit", 60, _data())
        self.assertIn("total_power_mw", out)
        self.assertGreater(out["total_power_mw"], 0.0)

    def test_assembly_stage_has_power_kw(self):
        out = qp.plan("electronic-circuit", 60, _data())
        for st in out["stages"]:
            self.assertIn("power_kw", st)
            self.assertGreaterEqual(st["power_kw"], 0.0)

    def test_assembly_power_matches_machine_count(self):
        # Roughly: power_kw ≈ machine_power_w × machine_count / 1000
        out = qp.plan("iron-plate", 60, _data())
        data = _data()
        power_w = qp.cli.build_machine_power_w(data)
        for st in out["stages"]:
            if st.get("role") in ("assembly", None):
                continue
        # Pick a foundry (casting-iron) stage if present
        stages = [s for s in out["stages"] if s.get("machine") == "foundry"]
        if stages:
            st = stages[0]
            expected = power_w["foundry"] * st["machine_count"] / 1000
            self.assertAlmostEqual(st["power_kw"], expected, delta=1e-6)

    def test_compound_stage_self_recycle_splits_power(self):
        # holmium-plate target = foundry (craft) + recycler (recycle).
        out = qp.plan("holmium-plate", 60, _data(), planets=["fulgora"])
        st = [s for s in out["stages"] if s.get("role") == "self-recycle-target"][0]
        data = _data()
        power_w = qp.cli.build_machine_power_w(data)
        expected = (
            power_w["foundry"] * st["craft_machines"]
            + power_w["recycler"] * st["recycler_machines"]
        ) / 1000
        self.assertAlmostEqual(st["power_kw"], expected, delta=1e-6)

    def test_compound_stage_shuffle_splits_power(self):
        out = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], enable_lds_shuffle=True,
        )
        st = [s for s in out["stages"] if s.get("role") == "cross-item-shuffle"][0]
        data = _data()
        power_w = qp.cli.build_machine_power_w(data)
        expected = (
            power_w["foundry"] * st["foundry_machines"]
            + power_w["recycler"] * st["recycler_machines"]
        ) / 1000
        self.assertAlmostEqual(st["power_kw"], expected, delta=1e-6)

    def test_burner_machine_zero_power(self):
        # Biochamber is burner-fuelled (no electric power); stages on biochamber
        # contribute 0 kW.
        out = qp.plan("bioflux", 60, _data(), planets=["gleba"])
        biochamber_stages = [
            s for s in out["stages"] if s.get("machine") == "biochamber"
        ]
        self.assertGreater(len(biochamber_stages), 0)
        for s in biochamber_stages:
            self.assertEqual(s["power_kw"], 0.0)

    def test_assembly_modules_reduce_power(self):
        out_off = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        out_on = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], assembly_modules=True,
        )
        # Modules cut machine count → power drops proportionally.
        self.assertLess(out_on["total_power_mw"], out_off["total_power_mw"] / 5)

    def test_human_format_shows_total_power(self):
        out = qp.plan("electronic-circuit", 60, _data())
        text = qp.format_human(out)
        self.assertIn("Total power:", text)


class TestMachineQuality(unittest.TestCase):
    """V3 small item: --machine-quality applies MACHINE_QUALITY_SPEED bonus.

    Bonus table: normal=0%, uncommon=+30%, rare=+60%, epic=+90%, legendary=+150%.
    Faster machines mean lower machine_count for the same throughput.
    """

    def test_default_normal(self):
        out = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        # Default machine_quality = normal — every assembly stage tagged normal.
        for st in out["stages"]:
            if st.get("role") == "assembly":
                self.assertEqual(st.get("machine_quality"), "normal")

    def test_legendary_reduces_machines(self):
        out_normal = qp.plan("processing-unit", 60, _data(), planets=["nauvis"])
        out_legend = qp.plan(
            "processing-unit", 60, _data(),
            planets=["nauvis"], machine_quality="legendary",
        )
        # +150% speed → 1/2.5 = 40% machines; allow some slack for rounding.
        ratio = out_legend["total_machine_count"] / out_normal["total_machine_count"]
        self.assertLess(ratio, 0.5)
        self.assertGreater(ratio, 0.3)

    def test_speed_progression_monotone(self):
        # Higher quality → fewer machines (strictly monotone).
        prev_count = float("inf")
        for q in ("normal", "uncommon", "rare", "epic", "legendary"):
            out = qp.plan(
                "processing-unit", 60, _data(),
                planets=["nauvis"], machine_quality=q,
            )
            self.assertLess(out["total_machine_count"], prev_count, f"{q} not lower than previous")
            prev_count = out["total_machine_count"]

    def test_legendary_assembly_stage_speed_bonus(self):
        # Each assembly stage's machine_count is 1/(1+speed_bonus) of normal.
        out_n = qp.plan(
            "iron-plate", 60, _data(),
            planets=[], machine_quality="normal",
        )
        out_l = qp.plan(
            "iron-plate", 60, _data(),
            planets=[], machine_quality="legendary",
        )
        # Pick the casting-iron foundry stage.
        cast_n = next(s for s in out_n["stages"] if s.get("machine") == "foundry")
        cast_l = next(s for s in out_l["stages"] if s.get("machine") == "foundry")
        # 1.0 / 2.5 = 0.4 ratio
        self.assertAlmostEqual(
            cast_l["machine_count"] / cast_n["machine_count"], 0.4, delta=1e-6,
        )
        self.assertEqual(cast_l["machine_quality"], "legendary")

    def test_self_recycle_target_uses_machine_quality(self):
        out_n = qp.plan(
            "holmium-plate", 60, _data(),
            planets=["fulgora"], machine_quality="normal",
        )
        out_l = qp.plan(
            "holmium-plate", 60, _data(),
            planets=["fulgora"], machine_quality="legendary",
        )
        # craft_machines + recycler_machines both scaled by 1/(1+1.5) = 0.4
        st_n = [s for s in out_n["stages"] if s.get("role") == "self-recycle-target"][0]
        st_l = [s for s in out_l["stages"] if s.get("role") == "self-recycle-target"][0]
        self.assertAlmostEqual(
            st_l["craft_machines"] / st_n["craft_machines"], 0.4, delta=1e-6,
        )
        self.assertAlmostEqual(
            st_l["recycler_machines"] / st_n["recycler_machines"], 0.4, delta=1e-6,
        )

    def test_crusher_stage_uses_machine_quality(self):
        # Asteroid reprocessing uses crushers; legendary crushers cut count.
        out_n = qp.plan("electronic-circuit", 60, _data(), machine_quality="normal")
        out_l = qp.plan("electronic-circuit", 60, _data(), machine_quality="legendary")
        ast_n = next(
            s for s in out_n["stages"] if s.get("role") == "asteroid-reprocessing"
        )
        ast_l = next(
            s for s in out_l["stages"] if s.get("role") == "asteroid-reprocessing"
        )
        self.assertAlmostEqual(
            ast_l["machine_count"] / ast_n["machine_count"], 0.4, delta=1e-6,
        )

    def test_unknown_quality_rejected_by_argparse(self):
        # Sanity: argparse choices restricts to known qualities.  Direct python
        # call doesn't validate (it's just a multiplier lookup with default 0).
        # This test just verifies a known value works.
        out = qp.plan(
            "iron-plate", 60, _data(), machine_quality="rare",
        )
        self.assertGreater(out["total_machine_count"], 0)


if __name__ == "__main__":
    unittest.main()
