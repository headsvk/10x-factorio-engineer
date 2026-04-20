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
        self.assertIn("metallic-asteroid-crushing", recipes)
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

    def test_holmium_plate_errors(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("holmium-plate", 60, _data())
        # holmium-plate is in SELF_RECYCLING_BLOCKLIST
        self.assertTrue(
            "self-recycling" in str(cm.exception) or "fulgora" in str(cm.exception)
        )

    def test_superconductor_errors(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("superconductor", 60, _data())
        self.assertIn("self-recycling", str(cm.exception))

    def test_tungsten_carbide_errors(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("tungsten-carbide", 60, _data())
        msg = str(cm.exception)
        self.assertTrue("self-recycling" in msg or "vulcanus" in msg)

    def test_plastic_bar_errors_no_oil(self):
        with self.assertRaises(ValueError) as cm:
            qp.plan("plastic-bar", 60, _data())
        # plastic-bar needs oil chain → blocked in V1
        self.assertIn("not supported", str(cm.exception))

    def test_processing_unit_errors_sulfuric_acid(self):
        # processing unit needs sulfuric-acid -> sulfur -> petroleum-gas (no crude-oil)
        with self.assertRaises(ValueError) as cm:
            qp.plan("processing-unit", 60, _data())
        self.assertIn("not supported", str(cm.exception))

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
        self.assertIn("metallic-asteroid-crushing", recipes)
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


if __name__ == "__main__":
    unittest.main()
