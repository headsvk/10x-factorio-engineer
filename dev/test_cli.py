"""
Unit / integration tests for cli.py.

Run with:
    python -m pytest dev/test_cli.py -v
  or
    python -m unittest dev.test_cli -v
"""

import math
import unittest
from fractions import Fraction
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'skill', 'assets')))

import cli


# ---------------------------------------------------------------------------
# Module-level fixtures: load datasets once for the whole test run
# ---------------------------------------------------------------------------

_DATA: dict[str, dict] = {}


def setUpModule() -> None:
    for ds in ("vanilla", "space-age"):
        data = cli.load_data(ds)
        _DATA[ds] = {
            "data":          data,
            "raw_set":       cli.build_raw_set(data),
            "recipe_idx":    cli.build_recipe_index(data),
            "resource_info": cli.build_resource_info(data),
        }


def _solver(dataset: str = "vanilla", **kwargs) -> cli.Solver:
    """Convenience factory; kwargs override Solver defaults."""
    d = _DATA[dataset]
    return cli.Solver(
        recipe_idx       = kwargs.get("recipe_idx",       d["recipe_idx"]),
        raw_set          = kwargs.get("raw_set",          d["raw_set"]),
        assembler_level  = kwargs.get("assembler_level",  3),
        furnace_type     = kwargs.get("furnace_type",     "electric"),
        prod_module_tier = kwargs.get("prod_module_tier", 0),
        speed_bonus      = kwargs.get("speed_bonus",      Fraction(0)),
        recipe_overrides = kwargs.get("recipe_overrides", None),
        machine_overrides = kwargs.get("machine_overrides", None),
    )


# ---------------------------------------------------------------------------
# pick_recipe
# ---------------------------------------------------------------------------

class TestPickRecipe(unittest.TestCase):

    def setUp(self):
        self.idx = _DATA["vanilla"]["recipe_idx"]

    def test_exact_key_match(self):
        # electronic-circuit has a recipe whose key == 'electronic-circuit'
        r = cli.pick_recipe("electronic-circuit", self.idx)
        assert r is not None
        self.assertEqual(r["key"], "electronic-circuit")

    def test_order_sort_fallback(self):
        # solid-fuel has no recipe keyed 'solid-fuel', so order-sort wins.
        # Sorted by order: petroleum-gas variant (order …-c[…]) < light-oil (…-d) < heavy-oil (…-e)
        r = cli.pick_recipe("solid-fuel", self.idx)
        assert r is not None
        self.assertEqual(r["key"], "solid-fuel-from-petroleum-gas")

    def test_override_takes_priority(self):
        # Explicit override should beat both exact-key and order-sort.
        r = cli.pick_recipe("solid-fuel", self.idx,
                            overrides={"solid-fuel": "solid-fuel-from-light-oil"})
        assert r is not None
        self.assertEqual(r["key"], "solid-fuel-from-light-oil")

    def test_override_for_exact_key_item(self):
        # Can override even when an exact-key recipe exists.
        sa_idx = _DATA["space-age"]["recipe_idx"]
        # iron-plate has both 'iron-plate' (smelting) and 'casting-iron' (foundry)
        r = cli.pick_recipe("iron-plate", sa_idx,
                            overrides={"iron-plate": "casting-iron"})
        assert r is not None
        self.assertEqual(r["key"], "casting-iron")

    def test_unknown_override_falls_through(self):
        # If the override key doesn't match any candidate, normal selection applies.
        r = cli.pick_recipe("electronic-circuit", self.idx,
                            overrides={"electronic-circuit": "nonexistent-recipe"})
        assert r is not None
        self.assertEqual(r["key"], "electronic-circuit")

    def test_no_recipe_returns_none(self):
        self.assertIsNone(cli.pick_recipe("iron-ore", self.idx))


# ---------------------------------------------------------------------------
# Basic circuits
# ---------------------------------------------------------------------------

class TestElectronicCircuit(unittest.TestCase):

    def test_raw_resources_exact(self):
        s = _solver()
        s.solve("electronic-circuit", Fraction(60))
        self.assertEqual(s.raw_resources["iron-ore"],   Fraction(60))
        self.assertEqual(s.raw_resources["copper-ore"], Fraction(90))

    def test_no_extra_raw_resources(self):
        s = _solver()
        s.solve("electronic-circuit", Fraction(60))
        self.assertEqual(set(s.raw_resources.keys()), {"iron-ore", "copper-ore"})


# ---------------------------------------------------------------------------
# Oil chain — no double-counting
# ---------------------------------------------------------------------------

class TestOilChainNoDoubleCounting(unittest.TestCase):
    """
    processing-unit demands both lubricant (heavy-oil) and plastic-bar
    (petroleum-gas).  Both come from the same AOP run, so crude-oil must
    be counted exactly once via the linear system.
    """

    def setUp(self):
        self.solver = _solver()
        self.solver.solve("processing-unit", Fraction(10))
        self.solver.resolve_oil(_DATA["vanilla"]["data"])

    def test_crude_oil_rate(self):
        # Expected: 487.1795... ≈ 487.18 (validated against Factorio wiki / FactorioLab)
        crude = float(self.solver.raw_resources["crude-oil"])
        self.assertAlmostEqual(crude, 487.18, places=1)

    def test_aop_appears_once(self):
        # advanced-oil-processing should appear exactly once in steps (not duplicated)
        aop_count = sum(
            1 for k in self.solver.steps if "oil-processing" in k
        )
        self.assertEqual(aop_count, 1)

    def test_no_raw_oil_products(self):
        # petroleum-gas / light-oil / heavy-oil should NOT end up in raw_resources
        for oil in cli.OIL_PRODUCTS:
            self.assertNotIn(oil, self.solver.raw_resources)


# ---------------------------------------------------------------------------
# Pumpjack yield %
# ---------------------------------------------------------------------------

class TestPumpjackYield(unittest.TestCase):

    def test_required_yield_pct(self):
        s = _solver()
        s.solve("processing-unit", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])
        miners = cli.compute_miners(
            s.raw_resources, _DATA["vanilla"]["resource_info"], "electric"
        )
        self.assertIn("crude-oil", miners)
        entry = miners["crude-oil"]
        self.assertEqual(entry["machine"], "pumpjack")
        self.assertAlmostEqual(entry["required_yield_pct"], 81.2, places=1)

    def test_water_uses_offshore_pump(self):
        # Water is mined by offshore-pump (category='offshore')
        s = _solver()
        s.solve("steam", Fraction(60))   # steam needs water + heat
        miners = cli.compute_miners(
            s.raw_resources, _DATA["vanilla"]["resource_info"], "electric"
        )
        if "water" in miners:
            self.assertEqual(miners["water"]["machine"], "offshore-pump")


# ---------------------------------------------------------------------------
# Recipe override flag (--recipe)
# ---------------------------------------------------------------------------

class TestRecipeOverride(unittest.TestCase):

    def test_solid_fuel_override(self):
        overrides = {"solid-fuel": "solid-fuel-from-light-oil"}
        s = _solver(recipe_overrides=overrides)
        s.solve("solid-fuel", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertIn("solid-fuel-from-light-oil", s.steps)
        self.assertNotIn("solid-fuel-from-petroleum-gas", s.steps)

    def test_default_solid_fuel_is_petroleum_gas(self):
        s = _solver()
        s.solve("solid-fuel", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertIn("solid-fuel-from-petroleum-gas", s.steps)

    def test_override_appears_in_json_output(self):
        # recipe_overrides should surface in the JSON when present
        import argparse
        overrides = {"solid-fuel": "solid-fuel-from-light-oil"}
        s = _solver(recipe_overrides=overrides)
        s.solve("solid-fuel", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])

        args = argparse.Namespace(
            item="solid-fuel", rate=10, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            prod_module=0, speed=0.0,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"], overrides)
        self.assertEqual(out["recipe_overrides"], overrides)


# ---------------------------------------------------------------------------
# Space Age machine routing
# ---------------------------------------------------------------------------

class TestSpaceAgeMachineRouting(unittest.TestCase):

    def test_superconductor_machines(self):
        s = _solver("space-age")
        s.solve("superconductor", Fraction(20))
        s.resolve_oil(_DATA["space-age"]["data"])
        machines = {step["machine"] for step in s.steps.values()}
        # superconductor requires all three specialist factories
        self.assertIn("electromagnetic-plant", machines)
        self.assertIn("foundry",               machines)
        self.assertIn("cryogenic-plant",       machines)


# ---------------------------------------------------------------------------
# Big mining drill (Space Age)
# ---------------------------------------------------------------------------

class TestBigMiningDrill(unittest.TestCase):

    def test_tungsten_carbide_big_drill(self):
        s = _solver("space-age")
        s.solve("tungsten-carbide", Fraction(60))
        s.resolve_oil(_DATA["space-age"]["data"])
        miners = cli.compute_miners(
            s.raw_resources, _DATA["space-age"]["resource_info"], "big"
        )
        self.assertIn("tungsten-ore", miners)
        entry = miners["tungsten-ore"]
        self.assertEqual(entry["machine"], "big-mining-drill")
        self.assertEqual(entry["machine_count_ceil"], 4)

    def test_electric_drill_for_iron(self):
        s = _solver()
        s.solve("iron-plate", Fraction(60))
        miners = cli.compute_miners(
            s.raw_resources, _DATA["vanilla"]["resource_info"], "electric"
        )
        self.assertIn("iron-ore", miners)
        self.assertEqual(miners["iron-ore"]["machine"], "electric-mining-drill")


# ---------------------------------------------------------------------------
# Machine category routing (vanilla)
# ---------------------------------------------------------------------------

class TestMachineCategoryVanilla(unittest.TestCase):

    def test_assembler3_is_default(self):
        s = _solver(assembler_level=3)
        s.solve("electronic-circuit", Fraction(60))
        step = s.steps["electronic-circuit"]
        self.assertEqual(step["machine"], "assembling-machine-3")

    def test_electric_furnace(self):
        s = _solver(furnace_type="electric")
        s.solve("iron-plate", Fraction(60))
        step = s.steps["iron-plate"]
        self.assertEqual(step["machine"], "electric-furnace")

    def test_stone_furnace(self):
        s = _solver(furnace_type="stone")
        s.solve("iron-plate", Fraction(60))
        self.assertEqual(s.steps["iron-plate"]["machine"], "stone-furnace")

    def test_chemical_plant(self):
        s = _solver()
        s.solve("sulfuric-acid", Fraction(60))
        self.assertEqual(s.steps["sulfuric-acid"]["machine"], "chemical-plant")

    def test_oil_refinery(self):
        s = _solver()
        s.solve("processing-unit", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertEqual(s.steps["advanced-oil-processing"]["machine"], "oil-refinery")


# ---------------------------------------------------------------------------
# Productivity bonus
# ---------------------------------------------------------------------------

class TestProductivityBonus(unittest.TestCase):

    def test_prod_reduces_machine_count(self):
        # Prod-module-3 fills 4 slots on assembling-machine-3 → +40% output,
        # so fewer machines are needed to hit the same rate.
        base = _solver(prod_module_tier=0)
        base.solve("electronic-circuit", Fraction(60))

        prod = _solver(prod_module_tier=3)   # +40% on assembling-machine-3
        prod.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            base.steps["electronic-circuit"]["machine_count"],
            prod.steps["electronic-circuit"]["machine_count"],
        )

    def test_zero_slot_machine_ignores_prod(self):
        # stone-furnace has 0 slots → prod module makes no difference.
        base  = _solver(furnace_type="stone", prod_module_tier=0)
        base.solve("iron-plate", Fraction(60))

        prod  = _solver(furnace_type="stone", prod_module_tier=3)
        prod.solve("iron-plate", Fraction(60))

        self.assertEqual(
            base.steps["iron-plate"]["machine_count"],
            prod.steps["iron-plate"]["machine_count"],
        )

    def test_electric_furnace_two_slots(self):
        # electric-furnace has 2 slots → prod-3 gives +20%, not +40%.
        prod = _solver(furnace_type="electric", prod_module_tier=3)
        prod.solve("iron-plate", Fraction(60))

        base = _solver(furnace_type="electric", prod_module_tier=0)
        base.solve("iron-plate", Fraction(60))

        ratio = base.steps["iron-plate"]["machine_count"] / prod.steps["iron-plate"]["machine_count"]
        self.assertAlmostEqual(float(ratio), 1.20, places=6)  # (1+0.20) = 1.20x more base machines

    def test_speed_reduces_machine_count(self):
        base  = _solver(speed_bonus=Fraction(0))
        base.solve("iron-plate", Fraction(120))

        fast  = _solver(speed_bonus=Fraction(1, 2))  # +50%
        fast.solve("iron-plate", Fraction(120))

        self.assertGreater(
            base.steps["iron-plate"]["machine_count"],
            fast.steps["iron-plate"]["machine_count"],
        )


# ---------------------------------------------------------------------------
# Exact arithmetic (Fraction internals)
# ---------------------------------------------------------------------------

class TestFractionArithmetic(unittest.TestCase):

    def test_no_float_in_solver_state(self):
        # All solver state values must stay as Fraction, never float
        s = _solver()
        s.solve("processing-unit", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])
        for item, rate in s.raw_resources.items():
            self.assertIsInstance(rate, Fraction, f"{item} rate is not Fraction")
        for rkey, step in s.steps.items():
            self.assertIsInstance(step["machine_count"], Fraction,
                                  f"{rkey} machine_count is not Fraction")


# ---------------------------------------------------------------------------
# Coal Liquefaction — vanilla
# ---------------------------------------------------------------------------
#
# Coal liquefaction recipe (vanilla):
#   inputs:  coal 10 + heavy-oil 25 + steam 50
#   outputs: heavy-oil 90 + light-oil 20 + petroleum-gas 10
#   time:    5 s  |  machine: oil-refinery (speed 1)
#
# Net heavy oil per cycle = 90 − 25 = 65.
# Selecting it: --recipe heavy-oil=coal-liquefaction
# ---------------------------------------------------------------------------

class TestCoalLiquefaction(unittest.TestCase):

    def _solver_cl(self, **kw):
        return _solver(recipe_overrides={"heavy-oil": "coal-liquefaction"}, **kw)

    def test_crude_oil_absent(self):
        """Coal liquefaction requires no crude-oil at all."""
        s = self._solver_cl()
        s.solve("heavy-oil", Fraction(65))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertNotIn("crude-oil", s.raw_resources)

    def test_coal_is_raw_resource(self):
        """coal appears in raw_resources at 10/min per cycle (65/min heavy-oil → 1 cycle/min)."""
        s = self._solver_cl()
        s.solve("heavy-oil", Fraction(65))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertIn("coal", s.raw_resources)
        self.assertAlmostEqual(float(s.raw_resources["coal"]), 10.0, places=4)

    def test_coal_liquefaction_in_steps(self):
        """production_steps must include coal-liquefaction, not advanced-oil-processing."""
        s = self._solver_cl()
        s.solve("heavy-oil", Fraction(65))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertIn("coal-liquefaction", s.steps)
        self.assertNotIn("advanced-oil-processing", s.steps)

    def test_machine_is_oil_refinery(self):
        """Coal liquefaction runs in an oil-refinery."""
        s = self._solver_cl()
        s.solve("heavy-oil", Fraction(65))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertEqual(s.steps["coal-liquefaction"]["machine"], "oil-refinery")

    def test_self_consumption_net_math(self):
        """
        Demanding exactly 65/min heavy-oil (= net output of 1 CL cycle/min)
        should require exactly 1 cycle/min → machine_count = 5/(60*1) = 1/12.
        """
        s = self._solver_cl()
        s.solve("heavy-oil", Fraction(65))
        s.resolve_oil(_DATA["vanilla"]["data"])
        step = s.steps["coal-liquefaction"]
        # energy_required=5, machine_speed=1 → machines = (1 * 5) / 60
        self.assertEqual(step["machine_count"], Fraction(1, 12))

    def test_cracking_engaged_for_petgas_demand(self):
        """
        Requesting only petroleum-gas with CL override should engage
        both HOC and LOC (to crack the excess heavy and light oil).
        No crude-oil in raw resources.
        """
        s = self._solver_cl()
        s.solve("petroleum-gas", Fraction(10))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertIn("coal-liquefaction",  s.steps)
        self.assertIn("heavy-oil-cracking", s.steps)
        self.assertIn("light-oil-cracking", s.steps)
        self.assertNotIn("crude-oil", s.raw_resources)
        self.assertIn("coal", s.raw_resources)

    def test_aop_still_default_without_override(self):
        """Without --recipe override, AOP should be used, not coal-liquefaction."""
        s = _solver()
        s.solve("heavy-oil", Fraction(25))
        s.resolve_oil(_DATA["vanilla"]["data"])
        self.assertIn("advanced-oil-processing", s.steps)
        self.assertNotIn("coal-liquefaction", s.steps)
        self.assertIn("crude-oil", s.raw_resources)


# ---------------------------------------------------------------------------
# Simple Coal Liquefaction — Space Age (Vulcanus)
# ---------------------------------------------------------------------------
#
# Simple coal liquefaction recipe (space-age):
#   inputs:  coal 10 + calcite 2 + sulfuric-acid 25
#   outputs: heavy-oil 50
#   time:    5 s  |  machine: oil-refinery (speed 1)
#
# No self-consumption; only produces heavy oil.
# Selecting it: --recipe heavy-oil=simple-coal-liquefaction
# ---------------------------------------------------------------------------

class TestSimpleCoalLiquefaction(unittest.TestCase):

    def _solver_scl(self, **kw):
        return _solver(
            dataset="space-age",
            recipe_overrides={"heavy-oil": "simple-coal-liquefaction"},
            **kw,
        )

    def test_crude_oil_absent(self):
        """Simple coal liquefaction requires no crude-oil."""
        s = self._solver_scl()
        s.solve("heavy-oil", Fraction(50))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertNotIn("crude-oil", s.raw_resources)

    def test_coal_in_raw_resources(self):
        """50/min heavy-oil = 1 cycle/min; coal = 10/min."""
        s = self._solver_scl()
        s.solve("heavy-oil", Fraction(50))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertIn("coal", s.raw_resources)
        self.assertAlmostEqual(float(s.raw_resources["coal"]), 10.0, places=4)

    def test_simple_cl_in_steps(self):
        """production_steps must contain simple-coal-liquefaction."""
        s = self._solver_scl()
        s.solve("heavy-oil", Fraction(50))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertIn("simple-coal-liquefaction", s.steps)
        self.assertNotIn("advanced-oil-processing", s.steps)
        self.assertNotIn("coal-liquefaction", s.steps)

    def test_machine_count_no_self_consumption(self):
        """
        simple-coal-liquefaction has no self-consuming heavy oil.
        50/min heavy-oil → 1 cycle/min → machines = 5/60 = 1/12.
        """
        s = self._solver_scl()
        s.solve("heavy-oil", Fraction(50))
        s.resolve_oil(_DATA["space-age"]["data"])
        step = s.steps["simple-coal-liquefaction"]
        self.assertEqual(step["machine_count"], Fraction(1, 12))

    def test_cracking_for_petgas(self):
        """
        Requesting petroleum-gas with simple-CL override should use
        simple-CL + HOC + LOC; no crude-oil.
        """
        s = self._solver_scl()
        s.solve("petroleum-gas", Fraction(20))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertIn("simple-coal-liquefaction", s.steps)
        self.assertIn("heavy-oil-cracking",        s.steps)
        self.assertNotIn("crude-oil", s.raw_resources)


# ---------------------------------------------------------------------------
# Gleba machine routing (Space Age)
# ---------------------------------------------------------------------------

class TestGlebaMachineRouting(unittest.TestCase):
    """
    Gleba introduces three new machine categories:
      organic / organic-or-*  → biochamber          (speed 3/2)
      pressing                → agricultural-tower   (speed 1)
      captive-spawner-process → captive-spawner      (speed 1)
    """

    def test_biochamber_for_organic(self):
        # agricultural-science-pack (category: organic) and all its sub-recipes
        # should route exclusively to biochamber in Space Age.
        s = _solver("space-age")
        s.solve("agricultural-science-pack", Fraction(60))
        s.resolve_oil(_DATA["space-age"]["data"])
        machines = {step["machine"] for step in s.steps.values()}
        self.assertIn("biochamber", machines)
        # No assembling-machine should appear — every step is organic-category
        self.assertNotIn("assembling-machine-3", machines)
        self.assertNotIn("assembling-machine-2", machines)
        self.assertNotIn("assembling-machine-1", machines)

    def test_pressing_agricultural_tower(self):
        # transport-belt has category 'pressing' in the Space Age dataset,
        # which should route to agricultural-tower (speed 1).
        s = _solver("space-age")
        s.solve("transport-belt", Fraction(60))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertEqual(s.steps["transport-belt"]["machine"], "agricultural-tower")
        # Exact machine count: recipe yields 2/cycle, time=0.5s, speed=1
        # cycles/min = 60/2 = 30; machines = 30 * 0.5 / 60 = 1/4
        self.assertEqual(s.steps["transport-belt"]["machine_count"], Fraction(1, 4))

    def test_biter_egg_captive_spawner(self):
        # biter-egg has category 'captive-spawner-process' → captive-spawner.
        # Its recipe has no inputs, so raw_resources must be empty.
        s = _solver("space-age")
        s.solve("biter-egg", Fraction(100))
        s.resolve_oil(_DATA["space-age"]["data"])
        step = s.steps["biter-egg"]
        self.assertEqual(step["machine"], "captive-spawner")
        # recipe: 5 biter-eggs per 10 s, speed=1
        # cycles/min = 100/5 = 20; machines = 20 * 10 / 60 = 10/3
        self.assertEqual(step["machine_count"], Fraction(10, 3))
        self.assertEqual(len(s.raw_resources), 0,
                         "captive-spawner has no inputs → raw_resources must be empty")


# ---------------------------------------------------------------------------
# Nutrients recipe selection and overrides (Space Age / Gleba)
# ---------------------------------------------------------------------------

class TestNutrientsRecipes(unittest.TestCase):
    """
    'nutrients' has five recipes; none has key == 'nutrients', so fallback
    selection applies.  The order-sort winner would be nutrients-from-fish,
    but that is un-automatable (raw-fish is not minable) and creates a circular
    dependency (fish-breeding consumes nutrients).

    RECIPE_DEFAULTS maps nutrients → nutrients-from-yumako-mash, so that is
    the default unless overridden by --recipe.
    """

    def test_default_is_yumako_mash(self):
        # RECIPE_DEFAULTS maps nutrients → nutrients-from-yumako-mash, overriding
        # the order-sort winner (nutrients-from-fish) which is un-automatable.
        idx = _DATA["space-age"]["recipe_idx"]
        r = cli.pick_recipe("nutrients", idx)
        assert r is not None
        self.assertEqual(r["key"], "nutrients-from-yumako-mash")

    def test_default_no_circular_dependency(self):
        # With nutrients-from-yumako-mash as default, the solver should produce
        # a clean result: only yumako in raw_resources, nutrients NOT in raw.
        s = _solver("space-age")
        s.solve("nutrients", Fraction(6))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertNotIn("nutrients", s.raw_resources)
        self.assertEqual(set(s.raw_resources.keys()), {"yumako"})

    def test_fish_route_still_selectable_via_override(self):
        # Players can still get nutrients-from-fish explicitly if they want.
        s = _solver("space-age",
                    recipe_overrides={"nutrients": "nutrients-from-fish"})
        s.solve("nutrients", Fraction(40))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertIn("nutrients-from-fish", s.steps)

    def test_yumako_mash_override_is_clean(self):
        # nutrients-from-yumako-mash is a fully automatable Gleba route:
        #   4 yumako-mash → 6 nutrients (biochamber, time=2s)
        # Raw resources: only yumako (from agricultural-tower pressing).
        s = _solver("space-age",
                    recipe_overrides={"nutrients": "nutrients-from-yumako-mash"})
        s.solve("nutrients", Fraction(6))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertIn("nutrients-from-yumako-mash", s.steps)
        self.assertNotIn("nutrients-from-fish", s.steps)
        self.assertEqual(set(s.raw_resources.keys()), {"yumako"})
        self.assertEqual(s.raw_resources["yumako"], Fraction(2))
        for step in s.steps.values():
            self.assertEqual(step["machine"], "biochamber")

    def test_bioflux_override_uses_biochamber(self):
        # Overriding to nutrients-from-bioflux should produce a full
        # biochamber chain (nutrients-from-bioflux → bioflux → yumako/jellynut).
        s = _solver("space-age",
                    recipe_overrides={"nutrients": "nutrients-from-bioflux"})
        s.solve("nutrients", Fraction(40))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertIn("nutrients-from-bioflux", s.steps)
        self.assertNotIn("nutrients-from-fish", s.steps)
        for step in s.steps.values():
            self.assertEqual(step["machine"], "biochamber",
                             f"expected biochamber, got {step['machine']} for {step}")

    def test_bioflux_override_raw_resources(self):
        # 40 nutrients/min via bioflux route:
        #   nutrients-from-bioflux: 5 bioflux → 40 nutrients, time=2s, biochamber speed=3/2
        #   bioflux: 15 yumako-mash + 12 jelly → 4 bioflux, time=6 s
        # Raw resources are only yumako and jellynut (no oil, no ore).
        s = _solver("space-age",
                    recipe_overrides={"nutrients": "nutrients-from-bioflux"})
        s.solve("nutrients", Fraction(40))
        s.resolve_oil(_DATA["space-age"]["data"])
        self.assertEqual(set(s.raw_resources.keys()), {"yumako", "jellynut"})
        self.assertEqual(s.raw_resources["yumako"],   Fraction(75, 8))
        self.assertEqual(s.raw_resources["jellynut"], Fraction(15, 4))


# ---------------------------------------------------------------------------
# Turbo belt (Space Age)
# ---------------------------------------------------------------------------

class TestSpaceAgeTurboBelt(unittest.TestCase):
    """Space Age adds a 'turbo' belt tier (3600/min) to belts_for_output."""

    def _output(self, dataset, item="iron-plate", rate=60):
        import argparse
        d = _DATA[dataset]
        s = cli.Solver(
            recipe_idx       = d["recipe_idx"],
            raw_set          = d["raw_set"],
            assembler_level  = 3,
            furnace_type     = "electric",
            prod_module_tier = 0,
            speed_bonus      = Fraction(0),
            recipe_overrides = None,
        )
        s.solve(item, Fraction(rate))
        s.resolve_oil(d["data"])
        args = argparse.Namespace(
            item=item, rate=rate, dataset=dataset,
            assembler=3, furnace="electric", miner="electric",
            prod_module=0, speed=0.0,
        )
        return cli.format_output(args, s, d["resource_info"], None)

    def test_turbo_belt_present_in_space_age(self):
        out = self._output("space-age")
        self.assertIn("turbo", out["belts_for_output"])
        self.assertEqual(out["belts_for_output"]["turbo"]["throughput_per_belt"], 3600)

    def test_no_turbo_belt_in_vanilla(self):
        out = self._output("vanilla")
        self.assertNotIn("turbo", out["belts_for_output"])
        # Vanilla should still have the three standard tiers
        self.assertEqual(set(out["belts_for_output"].keys()), {"yellow", "red", "blue"})


# ---------------------------------------------------------------------------
# Machine override (--machine CATEGORY=MACHINE)
# ---------------------------------------------------------------------------

class TestMachineOverride(unittest.TestCase):
    """
    --machine CATEGORY=MACHINE lets players redirect recipes to a different
    machine than the category default.  Common use-case: a player who has
    the foundry researched but still wants to see assembler-based costings,
    or vice-versa.
    """

    def test_metallurgy_default_is_foundry(self):
        # casting-iron (category: metallurgy) routes to foundry without override.
        s = _solver("space-age", recipe_overrides={"iron-plate": "casting-iron"})
        s.solve("iron-plate", Fraction(60))
        self.assertEqual(s.steps["casting-iron"]["machine"], "foundry")

    def test_override_foundry_to_assembler3(self):
        # With --machine metallurgy=assembling-machine-3, same recipe → assembler.
        s = _solver("space-age",
                    recipe_overrides={"iron-plate": "casting-iron"},
                    machine_overrides={"metallurgy": "assembling-machine-3"})
        s.solve("iron-plate", Fraction(60))
        self.assertEqual(s.steps["casting-iron"]["machine"], "assembling-machine-3")

    def test_machine_override_increases_count(self):
        # foundry speed=4 >> assembler-3 speed=5/4, so overriding to assembler
        # must require more machines for the same rate.
        foundry = _solver("space-age", recipe_overrides={"iron-plate": "casting-iron"})
        foundry.solve("iron-plate", Fraction(60))

        assembler = _solver("space-age",
                            recipe_overrides={"iron-plate": "casting-iron"},
                            machine_overrides={"metallurgy": "assembling-machine-3"})
        assembler.solve("iron-plate", Fraction(60))

        self.assertGreater(
            assembler.steps["casting-iron"]["machine_count"],
            foundry.steps["casting-iron"]["machine_count"],
        )

    def test_machine_override_in_json_output(self):
        import argparse
        overrides_m = {"metallurgy": "assembling-machine-3"}
        s = _solver("space-age",
                    recipe_overrides={"iron-plate": "casting-iron"},
                    machine_overrides=overrides_m)
        s.solve("iron-plate", Fraction(60))
        s.resolve_oil(_DATA["space-age"]["data"])

        args = argparse.Namespace(
            item="iron-plate", rate=60, dataset="space-age",
            assembler=3, furnace="electric", miner="electric",
            prod_module=0, speed=0.0,
        )
        out = cli.format_output(args, s, _DATA["space-age"]["resource_info"],
                                {"iron-plate": "casting-iron"}, overrides_m)
        self.assertEqual(out["machine_overrides"], overrides_m)

    def test_unknown_machine_falls_through(self):
        # Overriding to a machine not in MACHINE_CRAFTING_SPEED is ignored;
        # the category default (foundry) is used instead.
        s = _solver("space-age",
                    recipe_overrides={"iron-plate": "casting-iron"},
                    machine_overrides={"metallurgy": "nonexistent-machine"})
        s.solve("iron-plate", Fraction(60))
        self.assertEqual(s.steps["casting-iron"]["machine"], "foundry")


# ---------------------------------------------------------------------------
# Prefs file (factorio-prefs.json)
# ---------------------------------------------------------------------------

class TestPrefsFile(unittest.TestCase):
    """load_prefs() reads factorio-prefs.json and returns a plain dict."""

    def test_missing_file_returns_empty_dict(self):
        result = cli.load_prefs("/nonexistent/path/prefs.json")
        self.assertEqual(result, {})

    def test_reads_all_supported_fields(self):
        import json, tempfile, os
        prefs = {
            "dataset": "space-age",
            "assembler": 2,
            "furnace": "stone",
            "miner": "big",
            "prod_module": 1,
            "speed": 0.5,
            "recipe_overrides": {"heavy-oil": "coal-liquefaction"},
            "machine_overrides": {"metallurgy": "assembling-machine-3"},
            "preferred_belt": "blue",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump(prefs, f)
            fname = f.name
        try:
            loaded = cli.load_prefs(fname)
            self.assertEqual(loaded["dataset"],   "space-age")
            self.assertEqual(loaded["assembler"],  2)
            self.assertEqual(loaded["recipe_overrides"]["heavy-oil"], "coal-liquefaction")
            self.assertEqual(loaded["machine_overrides"]["metallurgy"], "assembling-machine-3")
            self.assertEqual(loaded["preferred_belt"], "blue")
        finally:
            os.unlink(fname)


if __name__ == "__main__":
    unittest.main(verbosity=2)
