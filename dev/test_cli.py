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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '10x-factorio-engineer', 'assets')))

import cli


# ---------------------------------------------------------------------------
# Module-level fixtures: load datasets once for the whole test run
# ---------------------------------------------------------------------------

_DATA: dict[str, dict] = {}


def setUpModule() -> None:
    for ds in ("vanilla", "space-age"):
        data = cli.load_data(ds)
        _DATA[ds] = {
            "data":                data,
            "raw_set":             cli.build_raw_set(data),
            "recipe_idx":          cli.build_recipe_index(data),
            "resource_info":       cli.build_resource_info(data),
            "machine_module_slots": cli.build_machine_module_slots(data),
        }


def _solver(dataset: str = "vanilla", **kwargs) -> cli.Solver:
    """Convenience factory using the new Solver API; kwargs override defaults."""
    d = _DATA[dataset]
    return cli.Solver(
        recipe_idx               = kwargs.get("recipe_idx",               d["recipe_idx"]),
        raw_set                  = kwargs.get("raw_set",                  d["raw_set"]),
        assembler_level          = kwargs.get("assembler_level",          3),
        furnace_type             = kwargs.get("furnace_type",             "electric"),
        module_configs           = kwargs.get("module_configs",           None),
        beacon_configs           = kwargs.get("beacon_configs",           None),
        machine_module_slots     = kwargs.get("machine_module_slots",     d["machine_module_slots"]),
        machine_quality          = kwargs.get("machine_quality",          "normal"),
        beacon_quality           = kwargs.get("beacon_quality",           "normal"),
        recipe_overrides         = kwargs.get("recipe_overrides",         None),
        recipe_machine_overrides = kwargs.get("recipe_machine_overrides", None),
        recipe_module_overrides  = kwargs.get("recipe_module_overrides",  None),
        recipe_beacon_overrides  = kwargs.get("recipe_beacon_overrides",  None),
        bus_items                = kwargs.get("bus_items",                None),
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
            items=["solid-fuel"], item="solid-fuel", rates=[10], rate=10,
            dataset="vanilla", assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"])
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
        # 4× prod-3-normal on assembling-machine-3 → +40% output → fewer machines.
        base = _solver()
        base.solve("electronic-circuit", Fraction(60))

        prod = _solver(module_configs={"assembling-machine-3": [_mspec(4, "prod", 3)]})
        prod.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            base.steps["electronic-circuit"]["machine_count"],
            prod.steps["electronic-circuit"]["machine_count"],
        )

    def test_zero_slot_machine_ignores_prod(self):
        # stone-furnace has 0 slots → prod module makes no difference.
        base = _solver(furnace_type="stone")
        base.solve("iron-plate", Fraction(60))

        prod = _solver(
            furnace_type="stone",
            module_configs={"stone-furnace": [_mspec(4, "prod", 3)]},
        )
        prod.solve("iron-plate", Fraction(60))

        self.assertEqual(
            base.steps["iron-plate"]["machine_count"],
            prod.steps["iron-plate"]["machine_count"],
        )

    def test_electric_furnace_two_slots(self):
        # electric-furnace has 2 slots → 4 prod-3 specs capped to 2 → +20%, not +40%.
        prod = _solver(
            furnace_type="electric",
            module_configs={"electric-furnace": [_mspec(4, "prod", 3)]},
        )
        prod.solve("iron-plate", Fraction(60))

        base = _solver(furnace_type="electric")
        base.solve("iron-plate", Fraction(60))

        ratio = base.steps["iron-plate"]["machine_count"] / prod.steps["iron-plate"]["machine_count"]
        self.assertAlmostEqual(float(ratio), 1.20, places=6)

    def test_speed_reduces_machine_count(self):
        # 1× speed-3-normal in electric-furnace → +50% speed → fewer machines.
        base = _solver(furnace_type="electric")
        base.solve("iron-plate", Fraction(120))

        fast = _solver(
            furnace_type="electric",
            module_configs={"electric-furnace": [_mspec(1, "speed", 3)]},
        )
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

# ===========================================================================
# NEW API HELPERS
# Solver constructor will change: prod_module_tier/speed_bonus are removed.
# These helpers use the new parameter names. Old _solver() stays for existing
# tests; _solver_new() drives all new test classes below.
# ===========================================================================

def _mspec(count: int, mtype: str, tier: int, quality: str = "normal") -> dict:
    """Build a ModuleSpec dict."""
    return {"count": count, "type": mtype, "tier": tier, "quality": quality}


def _bspec(count: int, tier: int, quality: str = "normal") -> dict:
    """Build a BeaconSpec dict (speed modules assumed)."""
    return {"count": count, "tier": tier, "quality": quality}


def _solver_new(dataset: str = "vanilla", **kwargs) -> cli.Solver:
    """Convenience factory using the new Solver API."""
    d = _DATA[dataset]
    return cli.Solver(
        recipe_idx               = kwargs.get("recipe_idx",               d["recipe_idx"]),
        raw_set                  = kwargs.get("raw_set",                  d["raw_set"]),
        assembler_level          = kwargs.get("assembler_level",          3),
        furnace_type             = kwargs.get("furnace_type",             "electric"),
        module_configs           = kwargs.get("module_configs",           None),
        beacon_configs           = kwargs.get("beacon_configs",           None),
        machine_module_slots     = kwargs.get("machine_module_slots",     d["machine_module_slots"]),
        machine_quality          = kwargs.get("machine_quality",          "normal"),
        beacon_quality           = kwargs.get("beacon_quality",           "normal"),
        recipe_overrides         = kwargs.get("recipe_overrides",         None),
        recipe_machine_overrides = kwargs.get("recipe_machine_overrides", None),
        recipe_module_overrides  = kwargs.get("recipe_module_overrides",  None),
        recipe_beacon_overrides  = kwargs.get("recipe_beacon_overrides",  None),
        bus_items                = kwargs.get("bus_items",                None),
    )


def _fmt_new(
    dataset: str,
    item: str,
    rate: float,
    *,
    solver: "cli.Solver | None" = None,
) -> dict:
    """
    Run solver + format_output with new-style args.
    Builds a solver internally unless one is passed in.
    """
    import argparse
    d = _DATA[dataset]
    if solver is None:
        s = _solver_new(dataset)
        s.solve(item, Fraction(rate))
        s.resolve_oil(d["data"])
    else:
        s = solver
    args = argparse.Namespace(
        items=[item], item=item, rates=[rate], rate=rate,
        dataset=dataset, assembler=3, furnace="electric", miner="electric",
        machine_quality="normal", beacon_quality="normal",
        module_configs=None, beacon_configs=None,
        recipe_machine_overrides=None, recipe_module_overrides=None,
        recipe_beacon_overrides=None,
    )
    return cli.format_output(args, s, d["resource_info"])


# ---------------------------------------------------------------------------
# Module config (replaces TestProductivityBonus for new API)
# ---------------------------------------------------------------------------
#
# Key constants used in expected values:
#   assembling-machine-3: speed=5/4, slots=4
#   electric-furnace:     speed=2,   slots=2
#   stone-furnace:        speed=1,   slots=0
#   prod-3 normal bonus per slot  : 10/100
#   prod-3 legendary bonus per slot: 10/100 × 5/2 = 25/100
#   speed-3 normal bonus per slot : 50/100
# ---------------------------------------------------------------------------

class TestModuleConfig(unittest.TestCase):

    def test_prod_reduces_machine_count(self):
        # 4× prod-3-normal in assembler-3:  prod_bonus = 4×10% = 40%
        # effective_result = 7/5  →  machine_count = 2/7  (vs 2/5 without)
        no_mod = _solver_new()
        no_mod.solve("electronic-circuit", Fraction(60))

        prod = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "prod", 3)]
        })
        prod.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            no_mod.steps["electronic-circuit"]["machine_count"],
            prod.steps["electronic-circuit"]["machine_count"],
        )

    def test_prod_exact_machine_count(self):
        # assembler-3 (speed=5/4), electronic-circuit (time=0.5s, yield=1)
        # prod_bonus = 4 × 10/100 = 2/5
        # effective_result = 1 × (1 + 2/5) = 7/5
        # cycles/min = 60 / (7/5) = 300/7
        # machines = (300/7 × 1/2) / (60 × 5/4) = (150/7) / 75 = 2/7
        s = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "prod", 3)]
        })
        s.solve("electronic-circuit", Fraction(60))
        self.assertEqual(
            s.steps["electronic-circuit"]["machine_count"],
            Fraction(2, 7),
        )

    def test_speed_reduces_machine_count(self):
        # 4× speed-3-normal: speed_bonus = 4×50% = 200%
        # effective_speed = 5/4 × 3 = 15/4  →  fewer machines
        no_mod = _solver_new()
        no_mod.solve("electronic-circuit", Fraction(60))

        speed = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "speed", 3)]
        })
        speed.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            no_mod.steps["electronic-circuit"]["machine_count"],
            speed.steps["electronic-circuit"]["machine_count"],
        )

    def test_zero_slot_machine_ignores_modules(self):
        # stone-furnace has 0 slots — module config must have zero effect.
        base = _solver_new(furnace_type="stone")
        base.solve("iron-plate", Fraction(60))

        with_mod = _solver_new(
            furnace_type="stone",
            module_configs={"stone-furnace": [_mspec(4, "prod", 3)]},
        )
        with_mod.solve("iron-plate", Fraction(60))

        self.assertEqual(
            base.steps["iron-plate"]["machine_count"],
            with_mod.steps["iron-plate"]["machine_count"],
        )

    def test_two_slot_machine_caps_at_slots(self):
        # electric-furnace has 2 slots; specifying 4 prod-3-normal must only
        # apply 2 slots worth of bonus (+20%), not 4 (+40%).
        base = _solver_new(furnace_type="electric")
        base.solve("iron-plate", Fraction(60))

        prod = _solver_new(
            furnace_type="electric",
            module_configs={"electric-furnace": [_mspec(4, "prod", 3)]},
        )
        prod.solve("iron-plate", Fraction(60))

        ratio = (
            base.steps["iron-plate"]["machine_count"]
            / prod.steps["iron-plate"]["machine_count"]
        )
        self.assertAlmostEqual(float(ratio), 1.20, places=6)

    def test_module_quality_scales_prod_bonus(self):
        # prod-3-legendary: 4 × 10% × 2.5 = 100%  →  machine_count = 1/5
        # prod-3-normal:    4 × 10% × 1.0 =  40%  →  machine_count = 2/7
        # ratio normal/legendary = (1+1.0)/(1+0.4) = 2.0/1.4 = 10/7
        leg = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "prod", 3, "legendary")]
        })
        leg.solve("electronic-circuit", Fraction(60))

        norm = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "prod", 3, "normal")]
        })
        norm.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            norm.steps["electronic-circuit"]["machine_count"],
            leg.steps["electronic-circuit"]["machine_count"],
        )
        ratio = (
            norm.steps["electronic-circuit"]["machine_count"]
            / leg.steps["electronic-circuit"]["machine_count"]
        )
        self.assertEqual(ratio, Fraction(10, 7))

    def test_mixed_prod_and_speed_modules(self):
        # 1× prod-3-rare + 3× speed-3-uncommon (4 slots total, assembler-3)
        # Both prod and speed contributions apply — count must be less than
        # no-modules baseline.
        no_mod = _solver_new()
        no_mod.solve("electronic-circuit", Fraction(60))

        mixed = _solver_new(module_configs={
            "assembling-machine-3": [
                _mspec(1, "prod",  3, "rare"),
                _mspec(3, "speed", 3, "uncommon"),
            ]
        })
        mixed.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            no_mod.steps["electronic-circuit"]["machine_count"],
            mixed.steps["electronic-circuit"]["machine_count"],
        )

    def test_mixed_exact_machine_count(self):
        # 1× prod-3-rare + 3× speed-3-uncommon in assembler-3
        # prod_bonus  = 1 × 10/100 × 8/5  = 4/25
        # speed_bonus = 3 × 50/100 × 13/10 = 39/20
        # effective_result = 29/25
        # effective_speed  = 5/4 × (1 + 39/20) = 5/4 × 59/20 = 59/16
        # cycles/min = 60 / (29/25) = 1500/29
        # machines = (1500/29 × 1/2) / (60 × 59/16)
        #          = (750/29) / (3540/16)
        #          = (750 × 16) / (29 × 3540)
        #          = 12000 / 102660 = 200 / 1711
        s = _solver_new(module_configs={
            "assembling-machine-3": [
                _mspec(1, "prod",  3, "rare"),
                _mspec(3, "speed", 3, "uncommon"),
            ]
        })
        s.solve("electronic-circuit", Fraction(60))
        self.assertEqual(
            s.steps["electronic-circuit"]["machine_count"],
            Fraction(200, 1711),
        )

    def test_efficiency_modules_do_not_affect_count(self):
        # Efficiency modules have no speed or productivity effect.
        # Machine count with efficiency modules == count without any modules.
        base = _solver_new()
        base.solve("electronic-circuit", Fraction(60))

        eff = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "efficiency", 3)]
        })
        eff.solve("electronic-circuit", Fraction(60))

        self.assertEqual(
            base.steps["electronic-circuit"]["machine_count"],
            eff.steps["electronic-circuit"]["machine_count"],
        )

    def test_recipe_module_override(self):
        # Global: no modules. Per-recipe override for electronic-circuit.
        # electronic-circuit should get prod bonus; other steps should not.
        s = _solver_new(recipe_module_overrides={
            "electronic-circuit": [_mspec(4, "prod", 3, "normal")]
        })
        s.solve("electronic-circuit", Fraction(60))
        # electronic-circuit step gets the 40% prod bonus → 2/7 machines
        self.assertEqual(
            s.steps["electronic-circuit"]["machine_count"],
            Fraction(2, 7),
        )
        # copper-cable (a dependency, no override) uses no prod bonus.
        # However, the prod bonus on electronic-circuit reduces its cycle rate:
        #   e-circuit cycles/min = 60 / (7/5) = 300/7
        #   copper-cable demand = 300/7 × 3 = 900/7 /min
        # copper-cable: time=0.5s, yield=2, assembler-3 speed=5/4
        #   cycles/min = (900/7) / 2 = 450/7
        #   machines = (450/7 × 0.5) / (60 × 5/4) = (225/7) / 75 = 3/7
        self.assertEqual(
            s.steps["copper-cable"]["machine_count"],
            Fraction(3, 7),
        )

    def test_recipe_module_override_in_json_output(self):
        import argparse
        overrides = {"electronic-circuit": [_mspec(4, "prod", 3)]}
        s = _solver_new(recipe_module_overrides=overrides)
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])

        args = argparse.Namespace(
            items=["electronic-circuit"], item="electronic-circuit",
            rates=[60], rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None,
            recipe_module_overrides=overrides,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"])
        self.assertEqual(out["recipe_module_overrides"], overrides)


# ---------------------------------------------------------------------------
# Beacon config  (--beacon MACHINE=COUNT:TIER:QUALITY)
# ---------------------------------------------------------------------------
#
# Beacon speed formula (Factorio 2.0 diminishing returns):
#   beacon_speed = effectivity × sqrt(count) × BEACON_SLOTS × speed_per_slot
#
# BEACON_EFFECTIVITY: normal=1.5, uncommon=1.7, rare=1.9, epic=2.1, legendary=2.5
# BEACON_SLOTS = 2
# SPEED_MODULE_BONUS: tier-3 normal = 0.5 per slot
#
# Example: 1 beacon, speed-3-normal, normal beacon quality:
#   1.5 × sqrt(1) × 2 × 0.5 = 1.5
# Example: 4 beacons (same):
#   1.5 × sqrt(4) × 2 × 0.5 = 1.5 × 2 × 1 = 3.0
# ---------------------------------------------------------------------------

class TestBeaconConfig(unittest.TestCase):

    def test_beacon_speed_bonus_value_single(self):
        # 1 beacon, speed-3-normal, normal beacon quality → bonus = 1.5
        s = _solver_new(beacon_configs={
            "assembling-machine-3": _bspec(1, 3, "normal")
        })
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            1.5, places=6,
        )

    def test_beacon_speed_bonus_value_four(self):
        # 4 beacons: 1.5 × sqrt(4) × 2 × 0.5 = 3.0
        s = _solver_new(beacon_configs={
            "assembling-machine-3": _bspec(4, 3, "normal")
        })
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            3.0, places=6,
        )

    def test_diminishing_returns_not_linear(self):
        # Doubling beacon count does NOT double the bonus (sqrt scaling).
        # 4 beacons / 1 beacon = sqrt(4)/sqrt(1) = 2, not 4.
        s1 = _solver_new(beacon_configs={"assembling-machine-3": _bspec(1, 3)})
        s1.solve("electronic-circuit", Fraction(60))

        s4 = _solver_new(beacon_configs={"assembling-machine-3": _bspec(4, 3)})
        s4.solve("electronic-circuit", Fraction(60))

        b1 = s1.steps["electronic-circuit"]["beacon_speed_bonus"]
        b4 = s4.steps["electronic-circuit"]["beacon_speed_bonus"]
        self.assertAlmostEqual(b4 / b1, 2.0, places=6)   # sqrt(4)/sqrt(1)

    def test_beacon_reduces_machine_count(self):
        no_beacon = _solver_new()
        no_beacon.solve("electronic-circuit", Fraction(60))

        with_beacon = _solver_new(beacon_configs={
            "assembling-machine-3": _bspec(1, 3)
        })
        with_beacon.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            float(no_beacon.steps["electronic-circuit"]["machine_count"]),
            with_beacon.steps["electronic-circuit"]["machine_count"],
        )

    def test_machine_count_is_float_with_beacon(self):
        # sqrt(count) is irrational → machine_count must be float
        s = _solver_new(beacon_configs={
            "assembling-machine-3": _bspec(1, 3)
        })
        s.solve("electronic-circuit", Fraction(60))
        self.assertIsInstance(
            s.steps["electronic-circuit"]["machine_count"], float
        )

    def test_machine_count_is_fraction_without_beacon(self):
        # Without beacons all arithmetic stays exact Fraction
        s = _solver_new()
        s.solve("electronic-circuit", Fraction(60))
        self.assertIsInstance(
            s.steps["electronic-circuit"]["machine_count"], Fraction
        )

    def test_beacon_speed_bonus_zero_without_config(self):
        # Steps with no beacon config must report beacon_speed_bonus = 0.0
        s = _solver_new()
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            0.0, places=6,
        )

    def test_beacon_quality_effectivity_normal(self):
        # beacon_quality="normal"  → effectivity=1.5
        # 1 beacon, speed-3-normal: 1.5 × 1 × 2 × 0.5 = 1.5
        s = _solver_new(
            beacon_quality="normal",
            beacon_configs={"assembling-machine-3": _bspec(1, 3)},
        )
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            1.5, places=6,
        )

    def test_beacon_quality_effectivity_rare(self):
        # beacon_quality="rare"  → effectivity=1.9
        # 1 beacon, speed-3-normal: 1.9 × 1 × 2 × 0.5 = 1.9
        s = _solver_new(
            beacon_quality="rare",
            beacon_configs={"assembling-machine-3": _bspec(1, 3)},
        )
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            1.9, places=6,
        )

    def test_beacon_quality_effectivity_legendary(self):
        # beacon_quality="legendary" → effectivity=2.5
        # 1 beacon, speed-3-normal: 2.5 × 1 × 2 × 0.5 = 2.5
        s = _solver_new(
            beacon_quality="legendary",
            beacon_configs={"assembling-machine-3": _bspec(1, 3)},
        )
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            2.5, places=6,
        )

    def test_beacon_module_quality_scales_speed(self):
        # speed-3-legendary in beacon: per-slot bonus = 0.5 × 2.5 = 1.25
        # 1 normal beacon: 1.5 × 1 × 2 × 1.25 = 3.75
        s = _solver_new(
            beacon_quality="normal",
            beacon_configs={"assembling-machine-3": _bspec(1, 3, "legendary")},
        )
        s.solve("electronic-circuit", Fraction(60))
        self.assertAlmostEqual(
            s.steps["electronic-circuit"]["beacon_speed_bonus"],
            3.75, places=6,
        )

    def test_recipe_beacon_override_disables_beacon(self):
        # Global: assembler-3 gets 4 beacons.
        # Per-recipe override for electronic-circuit: 0 beacons.
        # electronic-circuit must have no beacon bonus and Fraction machine_count.
        s = _solver_new(
            beacon_configs={"assembling-machine-3": _bspec(4, 3)},
            recipe_beacon_overrides={"electronic-circuit": _bspec(0, 3)},
        )
        s.solve("electronic-circuit", Fraction(60))
        step = s.steps["electronic-circuit"]
        self.assertAlmostEqual(step["beacon_speed_bonus"], 0.0, places=6)
        self.assertIsInstance(step["machine_count"], Fraction)

    def test_recipe_beacon_override_different_count(self):
        # Global: 4 beacons. Override for electronic-circuit: 1 beacon.
        global_s = _solver_new(
            beacon_configs={"assembling-machine-3": _bspec(4, 3)},
        )
        global_s.solve("electronic-circuit", Fraction(60))

        override_s = _solver_new(
            beacon_configs={"assembling-machine-3": _bspec(4, 3)},
            recipe_beacon_overrides={"electronic-circuit": _bspec(1, 3)},
        )
        override_s.solve("electronic-circuit", Fraction(60))

        # 1-beacon bonus = 1.5; 4-beacon bonus = 3.0 → more machines with 1 beacon
        self.assertGreater(
            override_s.steps["electronic-circuit"]["machine_count"],
            global_s.steps["electronic-circuit"]["machine_count"],
        )


# ---------------------------------------------------------------------------
# Machine quality  (--machine-quality QUALITY)
# ---------------------------------------------------------------------------
#
# MACHINE_QUALITY_SPEED bonus (additive to base crafting speed):
#   normal=0, uncommon=+30%, rare=+60%, epic=+90%, legendary=+150%
#
# assembler-3 base speed = 5/4
# legendary effective speed = 5/4 × (1 + 3/2) = 5/4 × 5/2 = 25/8
# ratio legendary/normal = (25/8) / (5/4) = 5/2  →  2.5× fewer machines
# ---------------------------------------------------------------------------

class TestMachineQuality(unittest.TestCase):

    def test_legendary_faster_than_normal(self):
        normal = _solver_new(machine_quality="normal")
        normal.solve("electronic-circuit", Fraction(60))

        legendary = _solver_new(machine_quality="legendary")
        legendary.solve("electronic-circuit", Fraction(60))

        self.assertGreater(
            normal.steps["electronic-circuit"]["machine_count"],
            legendary.steps["electronic-circuit"]["machine_count"],
        )

    def test_legendary_speed_ratio_exact(self):
        # normal speed = 5/4; legendary = 5/4 × 5/2 = 25/8
        # machine_count ∝ 1/speed → ratio = 5/2
        normal = _solver_new(machine_quality="normal")
        normal.solve("electronic-circuit", Fraction(60))

        legendary = _solver_new(machine_quality="legendary")
        legendary.solve("electronic-circuit", Fraction(60))

        ratio = (
            normal.steps["electronic-circuit"]["machine_count"]
            / legendary.steps["electronic-circuit"]["machine_count"]
        )
        self.assertEqual(ratio, Fraction(5, 2))

    def test_all_quality_tiers_strictly_ordered(self):
        # Each successive tier must produce strictly fewer machines.
        counts = {}
        for q in ("normal", "uncommon", "rare", "epic", "legendary"):
            s = _solver_new(machine_quality=q)
            s.solve("iron-plate", Fraction(60))
            counts[q] = s.steps["iron-plate"]["machine_count"]

        self.assertGreater(counts["normal"],    counts["uncommon"])
        self.assertGreater(counts["uncommon"],  counts["rare"])
        self.assertGreater(counts["rare"],      counts["epic"])
        self.assertGreater(counts["epic"],      counts["legendary"])

    def test_machine_quality_exact_uncommon(self):
        # uncommon: speed bonus = +30%  →  quality_mult = 13/10
        # electric-furnace base speed=2, uncommon: 2 × 13/10 = 13/5
        # iron-plate: energy_required=3.2s (= 16/5), yield=1
        # cycles/min = 60; machines = (60 × 16/5) / (60 × 13/5) = (16/5) / (13/5) = 16/13
        s = _solver_new(machine_quality="uncommon", furnace_type="electric")
        s.solve("iron-plate", Fraction(60))
        self.assertEqual(
            s.steps["iron-plate"]["machine_count"],
            Fraction(16, 13),
        )


# ---------------------------------------------------------------------------
# Belt output  (--belt TIER)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Recipe-level overrides  (--recipe-machine, appended to TestMachineOverride)
# ---------------------------------------------------------------------------

class TestRecipeMachineOverride(unittest.TestCase):
    """
    --recipe-machine RECIPE=MACHINE overrides the machine for a specific recipe
    key, independent of category routing.
    """

    def test_recipe_machine_overrides_category_default(self):
        # iron-gear-wheel normally routes to assembling-machine-3 (crafting cat).
        # Override to foundry → foundry appears in step.
        s = _solver_new(
            recipe_machine_overrides={"iron-gear-wheel": "foundry"}
        )
        s.solve("iron-gear-wheel", Fraction(60))
        self.assertEqual(s.steps["iron-gear-wheel"]["machine"], "foundry")

    def test_recipe_machine_override_changes_count(self):
        # foundry speed=4 >> assembler-3 speed=5/4 → fewer machines
        default_s = _solver_new()
        default_s.solve("iron-gear-wheel", Fraction(60))

        foundry_s = _solver_new(
            recipe_machine_overrides={"iron-gear-wheel": "foundry"}
        )
        foundry_s.solve("iron-gear-wheel", Fraction(60))

        self.assertGreater(
            default_s.steps["iron-gear-wheel"]["machine_count"],
            foundry_s.steps["iron-gear-wheel"]["machine_count"],
        )

    def test_recipe_machine_override_only_affects_target(self):
        # Only iron-gear-wheel changes; automation-science-pack (also crafting)
        # stays on assembler-3 because it has no recipe override.
        # Note: in Factorio 2.0.55 ASP uses copper-plate + iron-gear-wheel.
        s = _solver_new(
            recipe_machine_overrides={"iron-gear-wheel": "foundry"}
        )
        s.solve("automation-science-pack", Fraction(60))
        self.assertEqual(s.steps["iron-gear-wheel"]["machine"], "foundry")
        self.assertEqual(s.steps["automation-science-pack"]["machine"], "assembling-machine-3")

    def test_recipe_machine_override_in_json_output(self):
        import argparse
        rm_overrides = {"iron-gear-wheel": "foundry"}
        s = _solver_new(recipe_machine_overrides=rm_overrides)
        s.solve("iron-gear-wheel", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])

        args = argparse.Namespace(
            items=["iron-gear-wheel"], item="iron-gear-wheel",
            rates=[60], rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=rm_overrides,
            recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"])
        self.assertEqual(out["recipe_machine_overrides"], rm_overrides)


class TestBusItem(unittest.TestCase):
    """
    --bus-item ITEM-ID stops recursion at that item and records demand in
    solver.bus_inputs (separate from raw_resources).  format_output emits a
    "bus_inputs" dict; raw_resources contains only true raws (ores, etc.).
    """

    def test_bus_item_stops_recursion(self):
        # With --bus-item iron-plate, no furnace step and no iron-ore in raw_resources.
        s = _solver_new(bus_items=frozenset(["iron-plate"]))
        s.solve("electronic-circuit", Fraction(60))
        self.assertNotIn("iron-plate", s.steps)
        self.assertNotIn("iron-ore", s.raw_resources)

    def test_bus_item_goes_to_bus_inputs_not_raw(self):
        # Bus items must appear in bus_inputs, NOT raw_resources.
        s = _solver_new(bus_items=frozenset(["iron-plate"]))
        s.solve("electronic-circuit", Fraction(60))
        self.assertIn("iron-plate", s.bus_inputs)
        self.assertNotIn("iron-plate", s.raw_resources)
        # electronic-circuit needs 1 iron-plate per circuit → 60/min
        self.assertEqual(s.bus_inputs["iron-plate"], Fraction(60))

    def test_multiple_bus_items(self):
        # Both iron-plate and copper-plate as bus items: only assembler steps remain.
        s = _solver_new(bus_items=frozenset(["iron-plate", "copper-plate"]))
        s.solve("electronic-circuit", Fraction(60))
        recipe_keys = set(s.steps.keys())
        self.assertIn("electronic-circuit", recipe_keys)
        self.assertIn("copper-cable", recipe_keys)
        self.assertNotIn("iron-plate", recipe_keys)
        self.assertNotIn("copper-plate", recipe_keys)
        # raw_resources must be empty — no ores needed when all plates come from bus
        self.assertNotIn("iron-ore", s.raw_resources)
        self.assertNotIn("copper-ore", s.raw_resources)
        self.assertNotIn("iron-plate", s.raw_resources)
        self.assertNotIn("copper-plate", s.raw_resources)

    def test_bus_item_rates_are_correct(self):
        # electronic-circuit @ 60/min needs 60 iron-plate/min and 90 copper-plate/min.
        s = _solver_new(bus_items=frozenset(["iron-plate", "copper-plate"]))
        s.solve("electronic-circuit", Fraction(60))
        self.assertEqual(s.bus_inputs["iron-plate"],   Fraction(60))
        self.assertEqual(s.bus_inputs["copper-plate"], Fraction(90))

    def test_bus_inputs_in_json_output(self):
        import argparse
        bus = frozenset(["iron-plate", "copper-plate"])
        s = _solver_new(bus_items=bus)
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])
        args = argparse.Namespace(
            items=["electronic-circuit"], item="electronic-circuit",
            rates=[60], rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"])
        self.assertIn("bus_inputs", out)
        self.assertEqual(set(out["bus_inputs"].keys()), {"copper-plate", "iron-plate"})
        self.assertNotIn("bus_items", out)
        # raw_resources must be empty
        self.assertEqual(out["raw_resources"], {})

    def test_no_bus_inputs_absent_from_output(self):
        # bus_inputs key must be absent when no --bus-item flags are given.
        out = _fmt_new("vanilla", "electronic-circuit", 60)
        self.assertNotIn("bus_inputs", out)

    def test_bus_item_not_in_miners(self):
        # miners_needed is derived from raw_resources, so bus items never appear there.
        s = _solver_new(bus_items=frozenset(["iron-plate", "copper-plate"]))
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])
        resource_info = _DATA["vanilla"]["resource_info"]
        miners = cli.compute_miners(s.raw_resources, resource_info, "electric")
        self.assertNotIn("iron-plate", miners)
        self.assertNotIn("copper-plate", miners)
        self.assertEqual(miners, {})


# ---------------------------------------------------------------------------
# --machines flag
# ---------------------------------------------------------------------------

class TestMachinesFlag(unittest.TestCase):
    """
    rate_for_machines(item, N) must invert the machine_count formula in solve(),
    so that solve(item, rate_for_machines(item, N)) gives back exactly N machines
    for the top-level step.
    """

    def test_round_trip_integer(self):
        # 2 assembler-2 running transport-belt → solve should give back 2 machines.
        s = _solver_new(assembler_level=2)
        rate = s.rate_for_machines("transport-belt", 2)
        s2 = _solver_new(assembler_level=2)
        s2.solve("transport-belt", rate)
        self.assertEqual(s2.steps["transport-belt"]["machine_count"], Fraction(2))

    def test_round_trip_fractional(self):
        # 0.5 machines is a valid fractional input.
        s = _solver_new(assembler_level=3)
        rate = s.rate_for_machines("electronic-circuit", 0.5)
        s2 = _solver_new(assembler_level=3)
        s2.solve("electronic-circuit", rate)
        self.assertEqual(s2.steps["electronic-circuit"]["machine_count"], Fraction(1, 2))

    def test_rate_is_fraction_without_beacons(self):
        # Without beacons the returned rate must be an exact Fraction.
        s = _solver_new()
        rate = s.rate_for_machines("iron-gear-wheel", 4)
        self.assertIsInstance(rate, Fraction)

    def test_round_trip_with_prod_modules(self):
        # Productivity modules reduce input usage and increase effective output.
        # The round-trip must still return exactly N machines.
        mods = {"assembling-machine-3": [_mspec(4, "prod", 3)]}
        s = _solver_new(module_configs=mods)
        rate = s.rate_for_machines("electronic-circuit", 3)
        s2 = _solver_new(module_configs=mods)
        s2.solve("electronic-circuit", rate)
        self.assertEqual(s2.steps["electronic-circuit"]["machine_count"], Fraction(3))

    def test_round_trip_with_beacons(self):
        # Beacons introduce float arithmetic (sqrt); use assertAlmostEqual.
        bcfg = {"assembling-machine-3": _bspec(8, 3)}
        s = _solver_new(beacon_configs=bcfg)
        rate = s.rate_for_machines("electronic-circuit", 5)
        s2 = _solver_new(beacon_configs=bcfg)
        s2.solve("electronic-circuit", rate)
        self.assertAlmostEqual(
            float(s2.steps["electronic-circuit"]["machine_count"]), 5.0, places=4
        )

    def test_no_recipe_raises(self):
        s = _solver_new()
        with self.assertRaises(ValueError):
            s.rate_for_machines("iron-ore", 1)  # raw resource, no recipe

    def test_assembler_level_respected(self):
        # assembler-2 (speed 0.75) is slower than assembler-3 (speed 1.25),
        # so it produces a lower rate for the same machine count.
        s2 = _solver_new(assembler_level=2)
        s3 = _solver_new(assembler_level=3)
        rate2 = s2.rate_for_machines("electronic-circuit", 1)
        rate3 = s3.rate_for_machines("electronic-circuit", 1)
        self.assertLess(rate2, rate3)


# ---------------------------------------------------------------------------
# Power consumption  (build_machine_power_w, _compute_step_power, miners)
# ---------------------------------------------------------------------------
#
# Key machine power draws (vanilla, electric only):
#   assembling-machine-3: 375 kW
#   electric-furnace:     180 kW
#   electric-mining-drill: 90 kW
#   stone-furnace:        burner → 0 W in power dict
#
# MODULE_CONSUMPTION_PENALTY (NOT quality-scaled):
#   speed-3: +0.70 per slot
#   prod-3:  +0.80 per slot
# MODULE_EFFICIENCY_REDUCTION (IS quality-scaled):
#   eff-3-normal:    0.50 per slot
#   eff-3-legendary: 0.50 × 2.5 = 1.25 per slot
# Efficiency floor: max(energy_bonus, -0.80)
# ---------------------------------------------------------------------------

def _fmt_power(
    dataset: str,
    item: str,
    rate: float,
    *,
    solver: "cli.Solver | None" = None,
    **solver_kwargs,
) -> dict:
    """Run solver + format_output including machine_power_w."""
    import argparse
    d = _DATA[dataset]
    machine_power_w = cli.build_machine_power_w(d["data"])
    if solver is None:
        s = _solver_new(dataset, **solver_kwargs)
        s.solve(item, Fraction(rate))
        s.resolve_oil(d["data"])
    else:
        s = solver
    args = argparse.Namespace(
        items=[item], item=item, rates=[rate], rate=rate,
        dataset=dataset, assembler=3, furnace="electric", miner="electric",
        machine_quality="normal", beacon_quality="normal",
        module_configs=None, beacon_configs=None,
        recipe_machine_overrides=None, recipe_module_overrides=None,
        recipe_beacon_overrides=None,
    )
    return cli.format_output(args, s, d["resource_info"],
                             machine_power_w=machine_power_w)


class TestPowerConsumption(unittest.TestCase):

    def test_electric_machine_has_power(self):
        # electric-furnace @ 60 iron-plate/min: machines=8/5, 180 kW each
        # power_kw = 1.6 × 180 = 288.0
        out = _fmt_power("vanilla", "iron-plate", 60)
        step = next(s for s in out["production_steps"] if s["recipe"] == "iron-plate")
        self.assertGreater(step["power_kw"], 0.0)
        self.assertAlmostEqual(step["power_kw"], 288.0, places=2)

    def test_burner_machine_power_zero(self):
        # stone-furnace is a burner → power_kw must be 0.0
        s = _solver_new(
            furnace_type="stone",
            recipe_machine_overrides={"iron-plate": "iron-plate"},
        )
        # Use stone furnace directly via furnace_type
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])
        s2 = _solver_new(furnace_type="stone")
        s2.solve("iron-plate", Fraction(60))
        args = argparse.Namespace(
            items=["iron-plate"], item="iron-plate", rates=[60], rate=60,
            dataset="vanilla", assembler=3, furnace="stone", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s2, d["resource_info"],
                                machine_power_w=machine_power_w)
        step = next(s for s in out["production_steps"] if s["recipe"] == "iron-plate")
        self.assertEqual(step["power_kw"], 0.0)
        self.assertEqual(step["power_kw_ceil"], 0.0)

    def test_efficiency_modules_reduce_power(self):
        # 1× eff-3-normal in electric-furnace (2 slots, 1 effective slot used):
        # energy_bonus = −0.5  →  power = 1.6 × 180 × 0.5 = 144 kW
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])
        s_eff = _solver_new(
            furnace_type="electric",
            module_configs={"electric-furnace": [_mspec(1, "efficiency", 3)]},
        )
        s_eff.solve("iron-plate", Fraction(60))
        args = argparse.Namespace(
            items=["iron-plate"], item="iron-plate", rates=[60], rate=60,
            dataset="vanilla", assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs={"electric-furnace": [_mspec(1, "efficiency", 3)]},
            beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out_eff = cli.format_output(args, s_eff, d["resource_info"],
                                    machine_power_w=machine_power_w)

        out_base = _fmt_power("vanilla", "iron-plate", 60)

        step_eff  = next(s for s in out_eff["production_steps"]  if s["recipe"] == "iron-plate")
        step_base = next(s for s in out_base["production_steps"] if s["recipe"] == "iron-plate")
        self.assertLess(step_eff["power_kw"], step_base["power_kw"])
        self.assertAlmostEqual(step_eff["power_kw"], 144.0, places=2)

    def test_efficiency_quality_scaled(self):
        # legendary eff-3 reduces power more than normal eff-3 (before clamping).
        # electric-furnace has 2 slots.
        # normal eff-3 (1 slot):    energy_bonus = −0.5   → factor 0.5
        # legendary eff-3 (1 slot): energy_bonus = −0.5×2.5 = −1.25 → clamped to −0.8, factor 0.2
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])

        def _make(quality: str) -> dict:
            s = _solver_new(
                furnace_type="electric",
                module_configs={"electric-furnace": [_mspec(1, "efficiency", 3, quality)]},
            )
            s.solve("iron-plate", Fraction(60))
            args = argparse.Namespace(
                items=["iron-plate"], item="iron-plate", rates=[60], rate=60,
                dataset="vanilla", assembler=3, furnace="electric", miner="electric",
                machine_quality="normal", beacon_quality="normal",
                module_configs={"electric-furnace": [_mspec(1, "efficiency", 3, quality)]},
                beacon_configs=None,
                recipe_machine_overrides=None, recipe_module_overrides=None,
                recipe_beacon_overrides=None,
            )
            return cli.format_output(args, s, d["resource_info"],
                                     machine_power_w=machine_power_w)

        out_norm = _make("normal")
        out_leg  = _make("legendary")
        step_norm = next(s for s in out_norm["production_steps"] if s["recipe"] == "iron-plate")
        step_leg  = next(s for s in out_leg["production_steps"]  if s["recipe"] == "iron-plate")
        # legendary reduces power more (or equal if both hit floor)
        self.assertLessEqual(step_leg["power_kw"], step_norm["power_kw"])
        # Confirm: 1 slot normal → 0.5 factor, legendary → 0.2 factor (clamped to 0.2)
        self.assertAlmostEqual(step_norm["power_kw"], 144.0, places=2)
        self.assertAlmostEqual(step_leg["power_kw"],  57.6,  places=2)

    def test_speed_modules_not_quality_scaled(self):
        # Speed module consumption penalty is NOT quality-scaled.
        # Call _compute_step_power directly with identical machine_count to isolate
        # the power draw factor from any speed-induced machine count change.
        # electric-furnace 180 kW; 1 slot speed-3-normal vs speed-3-legendary
        # Both apply +0.7 consumption penalty → same energy_bonus → same factor.
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])
        machine_count = Fraction(8, 5)  # fixed count (same as 60/min baseline)

        pwr_n, _, _ = cli._compute_step_power(
            "electric-furnace", machine_count,
            [_mspec(1, "speed", 3, "normal")],
            None, "normal", machine_power_w,
        )
        pwr_l, _, _ = cli._compute_step_power(
            "electric-furnace", machine_count,
            [_mspec(1, "speed", 3, "legendary")],
            None, "normal", machine_power_w,
        )
        # Penalty is not quality-scaled: both should be identical
        self.assertAlmostEqual(pwr_n, pwr_l, places=6)

    def test_prod_modules_increase_power(self):
        # prod-3 modules add a consumption penalty; power must be higher than base.
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])

        s_prod = _solver_new(module_configs={
            "assembling-machine-3": [_mspec(4, "prod", 3)]
        })
        s_prod.solve("electronic-circuit", Fraction(60))
        args = argparse.Namespace(
            items=["electronic-circuit"], item="electronic-circuit",
            rates=[60], rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs={"assembling-machine-3": [_mspec(4, "prod", 3)]},
            beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out_prod = cli.format_output(args, s_prod, d["resource_info"],
                                     machine_power_w=machine_power_w)
        out_base = _fmt_power("vanilla", "electronic-circuit", 60)

        step_prod = next(s for s in out_prod["production_steps"] if s["recipe"] == "electronic-circuit")
        step_base = next(s for s in out_base["production_steps"] if s["recipe"] == "electronic-circuit")
        # Per-machine power draw must be higher with prod modules
        mc_prod = step_prod["machine_count"]
        mc_base = step_base["machine_count"]
        assert mc_prod > 0 and mc_base > 0
        factor_prod = step_prod["power_kw"] / mc_prod
        factor_base = step_base["power_kw"] / mc_base
        self.assertGreater(factor_prod, factor_base)

    def test_efficiency_floor_80pct(self):
        # electric-furnace has 2 slots; max 2 eff-3-normal slots.
        # 2 × 0.5 = 1.0 reduction → clamped to -0.8 → factor = 0.2
        # power_kw = 1.6 × 180 × 0.2 = 57.6
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])

        s = _solver_new(
            furnace_type="electric",
            module_configs={"electric-furnace": [_mspec(4, "efficiency", 3)]},
        )
        s.solve("iron-plate", Fraction(60))
        args = argparse.Namespace(
            items=["iron-plate"], item="iron-plate", rates=[60], rate=60,
            dataset="vanilla", assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs={"electric-furnace": [_mspec(4, "efficiency", 3)]},
            beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, d["resource_info"],
                                machine_power_w=machine_power_w)
        step = next(x for x in out["production_steps"] if x["recipe"] == "iron-plate")
        # Floor at 20% of base (288 kW base)
        self.assertAlmostEqual(step["power_kw"], 57.6, places=2)

    def test_beacon_power_sharing_size3(self):
        # assembling-machine-3 is size 3 → sharing factor = 4
        # electronic-circuit @ 60/min: machines = 2/5 = 0.4
        # ceil(0.4) = 1; physical = 1 * beacon_count / 4
        # With 4 beacons: physical = 1 * 4 / 4 = 1
        # beacon_power_kw = 1 * BEACON_POWER_KW["normal"] = 480
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])
        s = _solver_new(beacon_configs={
            "assembling-machine-3": _bspec(4, 3, "normal")
        })
        s.solve("electronic-circuit", Fraction(60))
        args = argparse.Namespace(
            items=["electronic-circuit"], item="electronic-circuit",
            rates=[60], rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None,
            beacon_configs={"assembling-machine-3": _bspec(4, 3, "normal")},
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, d["resource_info"],
                                machine_power_w=machine_power_w)
        step = next(x for x in out["production_steps"] if x["recipe"] == "electronic-circuit")
        # ceil(machines) = 1, beacon_count=4, sharing=4 → 1 physical beacon × 480 kW
        self.assertAlmostEqual(step["beacon_power_kw"], 480.0, places=2)

    def test_beacon_power_sharing_size5(self):
        # oil-refinery is size 5 → sharing factor = 2
        # Use AOP (advanced-oil-processing); give it a beacon config.
        import argparse
        d = _DATA["vanilla"]
        machine_power_w = cli.build_machine_power_w(d["data"])
        s = _solver_new(beacon_configs={
            "oil-refinery": _bspec(4, 3, "normal")
        })
        s.solve("heavy-oil", Fraction(100))
        s.resolve_oil(d["data"])
        args = argparse.Namespace(
            items=["heavy-oil"], item="heavy-oil", rates=[100], rate=100,
            dataset="vanilla", assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs=None,
            beacon_configs={"oil-refinery": _bspec(4, 3, "normal")},
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, d["resource_info"],
                                machine_power_w=machine_power_w)
        aop_step = next(x for x in out["production_steps"]
                        if x["recipe"] == "advanced-oil-processing")
        mc_ceil = aop_step["machine_count_ceil"]
        # sharing=2 → physical = mc_ceil * 4 / 2 = mc_ceil * 2
        expected_bpwr = mc_ceil * 4 / 2 * 480
        self.assertAlmostEqual(aop_step["beacon_power_kw"], expected_bpwr, places=1)

    def test_total_power_mw_in_output(self):
        # top-level total_power_mw must equal sum of per-step power / 1000
        out = _fmt_power("vanilla", "electronic-circuit", 60)
        step_sum = sum(s["power_kw"] + s["beacon_power_kw"]
                       for s in out["production_steps"])
        miner_sum = sum(
            v["power_kw"] for v in out["miners_needed"].values()
            if isinstance(v, dict) and "power_kw" in v
        )
        expected_mw = round((step_sum + miner_sum) / 1000, 4)
        self.assertIn("total_power_mw", out)
        self.assertAlmostEqual(out["total_power_mw"], expected_mw, places=4)

    def test_miner_power_kw_present(self):
        # electric-mining-drill: 90 kW each
        # iron-plate @ 60/min → iron-ore at 60/min
        # rate_each = (0.5/1) × 1 × 60 = 30/min → 2 drills → 2 × 90 = 180 kW
        out = _fmt_power("vanilla", "iron-plate", 60)
        self.assertIn("iron-ore", out["miners_needed"])
        entry = out["miners_needed"]["iron-ore"]
        self.assertIn("power_kw", entry)
        self.assertGreater(entry["power_kw"], 0.0)
        self.assertAlmostEqual(entry["power_kw"], 180.0, places=2)

    def test_miner_efficiency_reduces_power(self):
        # 1× eff-3-normal in electric-mining-drill (4 slots):
        # MODULE_EFFICIENCY_REDUCTION[3] = 0.5, qual_mult = 1.0
        # energy_bonus = -(1 × 0.5 × 1.0) = -0.5
        # power_factor = 0.5  →  2 drills × 90 kW × 0.5 = 90.0 kW (vs 180.0 baseline)
        out = _fmt_power("vanilla", "iron-plate", 60,
                         module_configs={"electric-mining-drill": [_mspec(1, "efficiency", 3)]})
        entry = out["miners_needed"]["iron-ore"]
        self.assertIn("power_kw", entry)
        self.assertAlmostEqual(entry["power_kw"], 90.0, places=2)

    def test_miner_efficiency_quality_scaled(self):
        # 1× eff-3-legendary: MODULE_EFFICIENCY_REDUCTION[3]=0.5, qual_mult=2.5
        # energy_bonus = -(1 × 0.5 × 2.5) = -1.25 → clamped to -0.8
        # power_factor = 0.2  →  2 × 90 × 0.2 = 36.0 kW
        # 1× eff-3-normal gives 90.0 kW — legendary must be strictly less
        out_normal = _fmt_power("vanilla", "iron-plate", 60,
                                module_configs={"electric-mining-drill": [_mspec(1, "efficiency", 3, "normal")]})
        out_legend = _fmt_power("vanilla", "iron-plate", 60,
                                module_configs={"electric-mining-drill": [_mspec(1, "efficiency", 3, "legendary")]})
        entry_n = out_normal["miners_needed"]["iron-ore"]
        entry_l = out_legend["miners_needed"]["iron-ore"]
        self.assertLess(entry_l["power_kw"], entry_n["power_kw"])
        self.assertAlmostEqual(entry_l["power_kw"], 36.0, places=2)

    def test_miner_efficiency_floor_80pct(self):
        # 4× eff-3-normal: energy_bonus = -(4 × 0.5 × 1.0) = -2.0 → clamped to -0.8
        # power_factor = 0.2  →  2 × 90 × 0.2 = 36.0 kW (same as legendary above)
        out = _fmt_power("vanilla", "iron-plate", 60,
                         module_configs={"electric-mining-drill": [_mspec(4, "efficiency", 3)]})
        entry = out["miners_needed"]["iron-ore"]
        self.assertAlmostEqual(entry["power_kw"], 36.0, places=2)

    def test_miner_beacon_power_kw(self):
        # electric-mining-drill is 3×3 (≤4-tile) → sharing factor = 4
        # beacon config: 4 beacons, tier 3, normal (480 kW each)
        # iron-plate @ 60/min → 2 drills; beacons boost speed so count < 2
        # physical beacons = ceil(count) × 4 / 4 = ceil(count) × 1
        # beacon_power_kw = ceil(count) × 480
        out_no_beacon = _fmt_power("vanilla", "iron-plate", 60)
        out_beacon    = _fmt_power("vanilla", "iron-plate", 60,
                                   beacon_configs={"electric-mining-drill": _bspec(4, 3)})
        entry = out_beacon["miners_needed"]["iron-ore"]
        self.assertIn("beacon_power_kw", entry)
        self.assertGreater(entry["beacon_power_kw"], 0.0)
        # total_power_mw must include beacon power — must exceed the no-beacon total
        self.assertGreater(out_beacon["total_power_mw"], out_no_beacon["total_power_mw"])


# ---------------------------------------------------------------------------
# Probabilistic outputs (uranium-processing)
# ---------------------------------------------------------------------------

class TestProbabilisticOutputs(unittest.TestCase):
    """Uranium-processing has U-238 at probability 0.993 and U-235 at 0.007.
    The solver must multiply result amounts by probability so the two outputs
    come out at very different rates rather than the same rate."""

    def test_u238_rate_reflects_probability(self):
        # 8 centrifuges, no modules → base cycles/min = 8 × (60/12) = 40
        # U-238 output = 40 × 0.993 = 39.72/min
        d = _DATA["vanilla"]
        solver = _solver("vanilla")
        solver.solve("uranium-238", Fraction(39.72))
        step = solver.steps.get("uranium-processing")
        assert step is not None
        self.assertAlmostEqual(float(step["machine_count"]), 8.0, places=3)

    def test_u235_rate_much_lower_than_u238(self):
        # Same 8 centrifuges → U-235 = 40 × 0.007 = 0.28/min
        # U-238 would be 40 × 0.993 = 39.72/min — ratio ≈ 141.86×
        d = _DATA["vanilla"]
        solver_238 = _solver("vanilla")
        solver_238.solve("uranium-238", Fraction(1))
        rate_238 = solver_238.steps["uranium-processing"]["rate_per_min"]

        solver_235 = _solver("vanilla")
        solver_235.solve("uranium-235", Fraction(1))
        rate_235 = solver_235.steps["uranium-processing"]["rate_per_min"]

        # rate_per_min for uranium-238 should be 1.0, for uranium-235 also 1.0
        # but machine_count for U-238 should be far fewer than for U-235
        mc_238 = float(solver_238.steps["uranium-processing"]["machine_count"])
        mc_235 = float(solver_235.steps["uranium-processing"]["machine_count"])
        # To produce 1/min U-238 needs ~1/39.72 machines; U-235 needs ~1/0.28 machines
        ratio = mc_235 / mc_238
        self.assertGreater(ratio, 100)   # U-235 needs ~141× more machines

    def test_u235_and_u238_rates_from_machines_flag(self):
        # --machines 8 with no modules: cycles/min = 8 × (60/12) = 40
        # U-238 = 40 × 0.993 = 39.72; U-235 = 40 × 0.007 = 0.28
        for item, expected in [("uranium-238", 39.72), ("uranium-235", 0.28)]:
            solver = _solver("vanilla")
            result = solver.rate_for_machines(item, 8)
            self.assertAlmostEqual(float(result), expected, places=4)


# ---------------------------------------------------------------------------
# Multi-target solve  (--item A --rate X --item B --rate Y ...)
# ---------------------------------------------------------------------------

def _fmt_multi(
    dataset: str,
    targets: list,
    *,
    solver: "cli.Solver | None" = None,
) -> dict:
    """
    Run a multi-target solve and return format_output result.
    targets: list of (item_id, rate_per_min) tuples.
    """
    import argparse
    d = _DATA[dataset]
    s = solver if solver is not None else _solver_new(dataset)
    for item, rate in targets:
        s.solve(item, Fraction(rate))
    s.resolve_oil(d["data"])
    items = [t[0] for t in targets]
    rates = [float(t[1]) for t in targets]
    args = argparse.Namespace(
        items=items, item=items[0],
        rates=rates, rate=rates[0],
        dataset=dataset, assembler=3, furnace="electric", miner="electric",
        machine_quality="normal", beacon_quality="normal",
        module_configs=None, beacon_configs=None,
        recipe_machine_overrides=None, recipe_module_overrides=None,
        recipe_beacon_overrides=None,
    )
    return cli.format_output(args, s, d["resource_info"])


class TestMultiTarget(unittest.TestCase):
    """
    Multi-target solve: --item A --rate X --item B --rate Y
    Shared sub-recipes are merged (counted once); output uses a 'targets'
    array instead of top-level item/rate_per_min.
    """

    def test_single_target_still_has_item_field(self):
        # Single-target output must keep legacy item/rate_per_min keys.
        out = _fmt_new("vanilla", "electronic-circuit", 60)
        self.assertIn("item", out)
        self.assertIn("rate_per_min", out)
        self.assertNotIn("targets", out)

    def test_multi_target_has_targets_array(self):
        # Two targets → targets list, no top-level item/rate_per_min.
        out = _fmt_multi("vanilla", [
            ("electronic-circuit", 60),
            ("automation-science-pack", 30),
        ])
        self.assertIn("targets", out)
        self.assertNotIn("item", out)
        self.assertNotIn("rate_per_min", out)

    def test_targets_array_contents(self):
        out = _fmt_multi("vanilla", [
            ("electronic-circuit", 60),
            ("automation-science-pack", 30),
        ])
        self.assertEqual(len(out["targets"]), 2)
        self.assertEqual(out["targets"][0], {"item": "electronic-circuit", "rate_per_min": 60.0})
        self.assertEqual(out["targets"][1], {"item": "automation-science-pack", "rate_per_min": 30.0})

    def test_overlapping_sub_recipes_merged(self):
        # ec@60 + asp@30 both need iron-plate; the iron-plate step must reflect
        # the combined demand, not be counted twice.
        # ec@60: needs 60 iron-plate/min (1 iron-plate per circuit)
        # asp@30: needs 30 iron-gear-wheel/min → 60 iron-plate/min
        # Total iron-plate: 120/min
        # electric-furnace speed=2, time=3.2s → 37.5/min each → 120/37.5 = 3.2 machines
        out = _fmt_multi("vanilla", [
            ("electronic-circuit", 60),
            ("automation-science-pack", 30),
        ])
        steps = {s["recipe"]: s for s in out["production_steps"]}
        self.assertIn("iron-plate", steps)
        self.assertAlmostEqual(steps["iron-plate"]["machine_count"], 3.2, places=4)

    def test_raw_resources_combined(self):
        # Non-overlapping items: raw_resources must contain both ores.
        out = _fmt_multi("vanilla", [
            ("iron-plate", 30),
            ("copper-plate", 30),
        ])
        self.assertAlmostEqual(out["raw_resources"]["iron-ore"],   30.0, places=4)
        self.assertAlmostEqual(out["raw_resources"]["copper-ore"], 30.0, places=4)

    def test_no_belt_pump_in_multi_target(self):
        # belt/pump fields must never appear in multi-target output.
        out = _fmt_multi("vanilla", [
            ("electronic-circuit", 60),
            ("automation-science-pack", 30),
        ])
        self.assertNotIn("belt", out)
        self.assertNotIn("belts_needed", out)
        self.assertNotIn("pump", out)
        self.assertNotIn("pumps_needed", out)

    def test_target_also_ingredient_accumulates(self):
        # transport-belt is both a target AND consumed by underground-belt.
        # 1 asm-2 → transport-belt 180/min; 1 asm-2 → underground-belt 90/min.
        # underground-belt consumes 225 transport-belt/min as input.
        # The transport-belt step must merge both demands: 405/min, 2.25 machines.
        s = _solver_new("vanilla", assembler_level=2, bus_items=frozenset(["iron-plate"]))
        out = _fmt_multi("vanilla", [
            ("transport-belt", 180),
            ("underground-belt", 90),
        ], solver=s)
        steps = {st["recipe"]: st for st in out["production_steps"]}
        tb = steps["transport-belt"]
        self.assertAlmostEqual(tb["rate_per_min"],  405.0, places=4)
        self.assertAlmostEqual(tb["machine_count"],  2.25, places=4)

    def test_bus_inputs_combined_across_targets(self):
        # Both targets draw iron-plate from the bus; demands accumulate.
        # ec@60 → 60 iron-plate; asp@30 → iron-gear-wheel needs 60 iron-plate
        # Total bus_inputs["iron-plate"] = 120
        s = _solver_new("vanilla", bus_items=frozenset(["iron-plate"]))
        out = _fmt_multi("vanilla", [
            ("electronic-circuit", 60),
            ("automation-science-pack", 30),
        ], solver=s)
        self.assertIn("bus_inputs", out)
        self.assertAlmostEqual(out["bus_inputs"]["iron-plate"], 120.0, places=4)


class TestStepInputs(unittest.TestCase):
    """inputs dict present on every production step, values correct."""

    def _ec_step(self, out: dict) -> dict:
        steps = {s["recipe"]: s for s in out["production_steps"]}
        return steps["electronic-circuit"]

    def test_inputs_present_on_every_step(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60)
        for step in out["production_steps"]:
            self.assertIn("inputs", step, f"step {step['recipe']} missing 'inputs'")

    def test_electronic_circuit_inputs(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60)
        ec = self._ec_step(out)
        self.assertAlmostEqual(ec["inputs"]["iron-plate"],   60.0, places=4)
        self.assertAlmostEqual(ec["inputs"]["copper-cable"], 180.0, places=4)

    def test_inputs_reduced_by_productivity(self):
        # 4×prod-3 modules → prod_bonus = 0.4 → cycles_per_min = 60/1.4 ≈ 42.857
        import argparse
        d = _DATA["vanilla"]
        s = _solver_new("vanilla", module_configs={"assembling-machine-3": [_mspec(4, "prod", 3)]})
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(d["data"])
        args = argparse.Namespace(
            items=["electronic-circuit"], item="electronic-circuit",
            rates=[60.0], rate=60.0, machines_list=[],
            dataset="vanilla", assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            module_configs={"assembling-machine-3": [_mspec(4, "prod", 3)]},
            beacon_configs=None, recipe_machine_overrides=None,
            recipe_module_overrides=None, recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, d["resource_info"])
        ec = self._ec_step(out)
        self.assertAlmostEqual(ec["inputs"]["iron-plate"],   300 / 7, places=4)
        self.assertAlmostEqual(ec["inputs"]["copper-cable"], 900 / 7, places=4)

    def test_bus_item_appears_in_inputs(self):
        # iron-plate on bus; recursion stops, but it still shows in ec step inputs
        s = _solver_new("vanilla", bus_items=frozenset(["iron-plate"]))
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])
        out = _fmt_new("vanilla", "electronic-circuit", 60, solver=s)
        ec = self._ec_step(out)
        self.assertIn("iron-plate", ec["inputs"])
        self.assertAlmostEqual(ec["inputs"]["iron-plate"], 60.0, places=4)

    def test_oil_step_has_inputs(self):
        # processing-unit chain triggers AOP; crude-oil must appear in its inputs
        out = _fmt_new("vanilla", "processing-unit", 10)
        steps = {s["recipe"]: s for s in out["production_steps"]}
        aop = steps.get("advanced-oil-processing")
        assert aop is not None
        self.assertIn("crude-oil", aop["inputs"])
        self.assertGreater(aop["inputs"]["crude-oil"], 0)

    def test_multi_target_inputs_accumulate(self):
        # ec@60 + asp@30 both use iron-plate; iron-plate step inputs show combined iron-ore draw
        # iron-plate step is shared; its iron-ore input must reflect both demands
        out = _fmt_multi("vanilla", [
            ("electronic-circuit", 60),
            ("automation-science-pack", 30),
        ])
        steps = {s["recipe"]: s for s in out["production_steps"]}
        ip = steps.get("iron-plate")
        assert ip is not None
        # Combined iron-ore input must be greater than ec-only demand (60)
        self.assertGreater(ip["inputs"]["iron-ore"], 60.0)


class TestStepConfig(unittest.TestCase):
    """Per-step config fields: machine_quality, module_specs, beacon_spec, beacon_quality."""

    def _steps(self, out: dict) -> dict:
        return {s["recipe"]: s for s in out["production_steps"]}

    def test_machine_quality_always_present(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60)
        for step in out["production_steps"]:
            self.assertIn("machine_quality", step)
            self.assertEqual(step["machine_quality"], "normal")

    def test_machine_quality_legendary(self):
        import argparse
        d = _DATA["vanilla"]
        s = _solver_new("vanilla", machine_quality="legendary")
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(d["data"])
        args = argparse.Namespace(
            items=["electronic-circuit"], item="electronic-circuit",
            rates=[60.0], rate=60.0, machines_list=[],
            dataset="vanilla", assembler=3, furnace="electric", miner="electric",
            machine_quality="legendary", beacon_quality="normal",
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None,
        )
        out = cli.format_output(args, s, d["resource_info"])
        for step in out["production_steps"]:
            self.assertEqual(step["machine_quality"], "legendary")

    def test_module_specs_absent_when_no_modules(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60)
        for step in out["production_steps"]:
            self.assertNotIn("module_specs", step)

    def test_module_specs_present_global(self):
        # Global --modules assembling-machine-3=4:prod:3:normal
        # ec step uses assembler-3 → gets module_specs
        # iron-plate step uses electric-furnace → no module_specs
        s = _solver_new("vanilla", module_configs={
            "assembling-machine-3": [_mspec(4, "prod", 3)],
        })
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])
        out = _fmt_new("vanilla", "electronic-circuit", 60, solver=s)
        steps = self._steps(out)
        ec = steps["electronic-circuit"]
        self.assertIn("module_specs", ec)
        self.assertEqual(ec["module_specs"], [{"count": 4, "type": "prod", "tier": 3, "quality": "normal"}])
        ip = steps["iron-plate"]
        self.assertNotIn("module_specs", ip)

    def test_recipe_module_override_wins_per_step(self):
        # --recipe-modules electronic-circuit=2:speed:3:normal → only ec step gets specs
        s = _solver_new("vanilla", recipe_module_overrides={
            "electronic-circuit": [_mspec(2, "speed", 3)],
        })
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])
        out = _fmt_new("vanilla", "electronic-circuit", 60, solver=s)
        steps = self._steps(out)
        ec = steps["electronic-circuit"]
        self.assertIn("module_specs", ec)
        self.assertEqual(ec["module_specs"], [{"count": 2, "type": "speed", "tier": 3, "quality": "normal"}])
        ip = steps["iron-plate"]
        self.assertNotIn("module_specs", ip)

    def test_beacon_spec_and_quality_per_step(self):
        # --beacon assembling-machine-3=8:3:legendary → ec step (assembler-3) gets beacon fields
        # iron-plate step (electric-furnace) gets no beacon fields
        s = _solver_new("vanilla", beacon_configs={
            "assembling-machine-3": _bspec(8, 3, "legendary"),
        }, beacon_quality="legendary")
        s.solve("electronic-circuit", Fraction(60))
        s.resolve_oil(_DATA["vanilla"]["data"])
        out = _fmt_new("vanilla", "electronic-circuit", 60, solver=s)
        steps = self._steps(out)
        ec = steps["electronic-circuit"]
        self.assertIn("beacon_spec", ec)
        self.assertEqual(ec["beacon_spec"], {"count": 8, "tier": 3, "quality": "legendary"})
        self.assertIn("beacon_quality", ec)
        self.assertEqual(ec["beacon_quality"], "legendary")
        ip = steps["iron-plate"]
        self.assertNotIn("beacon_spec", ip)
        self.assertNotIn("beacon_quality", ip)


if __name__ == "__main__":
    unittest.main(verbosity=2)
