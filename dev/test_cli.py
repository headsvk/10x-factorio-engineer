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
            "data":          data,
            "raw_set":       cli.build_raw_set(data),
            "recipe_idx":    cli.build_recipe_index(data),
            "resource_info": cli.build_resource_info(data),
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
        fluid_set = cli.build_fluid_set(_DATA["vanilla"]["data"])

        args = argparse.Namespace(
            item="solid-fuel", rate=10, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            belt=None, pump=None,
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None, recipe_belt_overrides=None,
            recipe_pump_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"],
                                fluid_set=fluid_set)
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

class TestSpaceAgeTurboBelt(unittest.TestCase):
    """Space Age includes a 'turbo' belt tier (3600/min); vanilla does not."""

    def test_turbo_belt_in_space_age(self):
        out = _fmt_new("space-age", "iron-plate", 60, belt="turbo")
        self.assertEqual(out["belt"], "turbo")
        self.assertAlmostEqual(out["belts_needed"], 60 / 3600, places=6)

    def test_blue_belt_in_vanilla(self):
        out = _fmt_new("vanilla", "iron-plate", 60, belt="blue")
        self.assertEqual(out["belt"], "blue")
        self.assertAlmostEqual(out["belts_needed"], 60 / 2700, places=6)


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
        recipe_idx             = kwargs.get("recipe_idx",             d["recipe_idx"]),
        raw_set                = kwargs.get("raw_set",                d["raw_set"]),
        assembler_level        = kwargs.get("assembler_level",        3),
        furnace_type           = kwargs.get("furnace_type",           "electric"),
        module_configs         = kwargs.get("module_configs",         None),
        beacon_configs         = kwargs.get("beacon_configs",         None),
        machine_quality        = kwargs.get("machine_quality",        "normal"),
        beacon_quality         = kwargs.get("beacon_quality",         "normal"),
        recipe_overrides       = kwargs.get("recipe_overrides",       None),
        recipe_machine_overrides = kwargs.get("recipe_machine_overrides", None),
        recipe_module_overrides  = kwargs.get("recipe_module_overrides",  None),
        recipe_beacon_overrides  = kwargs.get("recipe_beacon_overrides",  None),
        bus_items              = kwargs.get("bus_items",              None),
    )


def _fmt_new(
    dataset: str,
    item: str,
    rate: float,
    *,
    belt: str | None = None,
    pump: str | None = None,
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
    fluid_set = cli.build_fluid_set(d["data"])
    args = argparse.Namespace(
        item=item, rate=rate, dataset=dataset,
        assembler=3, furnace="electric", miner="electric",
        machine_quality="normal", beacon_quality="normal",
        belt=belt, pump=pump,
        module_configs=None, beacon_configs=None,
        recipe_machine_overrides=None, recipe_module_overrides=None,
        recipe_beacon_overrides=None,
        recipe_belt_overrides=None, recipe_pump_overrides=None,
    )
    return cli.format_output(args, s, d["resource_info"], fluid_set=fluid_set)


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
        fluid_set = cli.build_fluid_set(_DATA["vanilla"]["data"])

        args = argparse.Namespace(
            item="electronic-circuit", rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            belt=None, pump=None,
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None,
            recipe_module_overrides=overrides,
            recipe_beacon_overrides=None,
            recipe_belt_overrides=None, recipe_pump_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"],
                                fluid_set=fluid_set)
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

class TestBeltOutput(unittest.TestCase):

    def test_belt_produces_single_fields(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60, belt="blue")
        self.assertIn("belt", out)
        self.assertIn("belts_needed", out)
        self.assertNotIn("belts_for_output", out)

    def test_belt_echoes_tier(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60, belt="blue")
        self.assertEqual(out["belt"], "blue")

    def test_belt_blue_correct_value(self):
        # blue belt: 2700/min  →  60/2700 = 1/45
        out = _fmt_new("vanilla", "electronic-circuit", 60, belt="blue")
        self.assertAlmostEqual(out["belts_needed"], 60 / 2700, places=6)

    def test_belt_yellow_correct_value(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60, belt="yellow")
        self.assertAlmostEqual(out["belts_needed"], 60 / 900, places=6)

    def test_belt_red_correct_value(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60, belt="red")
        self.assertAlmostEqual(out["belts_needed"], 60 / 1800, places=6)

    def test_belt_turbo_space_age(self):
        out = _fmt_new("space-age", "electronic-circuit", 60, belt="turbo")
        self.assertAlmostEqual(out["belts_needed"], 60 / 3600, places=6)

    def test_no_belt_flag_omits_fields(self):
        out = _fmt_new("vanilla", "electronic-circuit", 60, belt=None)
        self.assertNotIn("belt", out)
        self.assertNotIn("belts_needed", out)

    def test_fluid_item_gets_no_belt_field(self):
        # lubricant is a fluid — even with --belt set, no belts_needed
        out = _fmt_new("vanilla", "lubricant", 60, belt="blue")
        self.assertNotIn("belts_needed", out)
        self.assertNotIn("belt", out)


# ---------------------------------------------------------------------------
# Pump output  (--pump QUALITY)
# ---------------------------------------------------------------------------
#
# PUMP_THROUGHPUT: normal=72000, uncommon=93600, rare=115200,
#                  epic=136800, legendary=180000  (fluid/min)
# ---------------------------------------------------------------------------

class TestPumpOutput(unittest.TestCase):

    def test_pump_produces_single_fields(self):
        out = _fmt_new("vanilla", "lubricant", 60, pump="normal")
        self.assertIn("pump", out)
        self.assertIn("pumps_needed", out)
        self.assertNotIn("belts_needed", out)
        self.assertNotIn("belt", out)

    def test_pump_echoes_quality(self):
        out = _fmt_new("vanilla", "lubricant", 60, pump="legendary")
        self.assertEqual(out["pump"], "legendary")

    def test_pump_all_quality_throughputs(self):
        throughputs = {
            "normal":    72_000,
            "uncommon":  93_600,
            "rare":      115_200,
            "epic":      136_800,
            "legendary": 180_000,
        }
        for quality, tput in throughputs.items():
            out = _fmt_new("vanilla", "lubricant", 60, pump=quality)
            self.assertAlmostEqual(
                out["pumps_needed"], 60 / tput, places=8,
                msg=f"pump quality={quality}",
            )

    def test_pump_quality_strictly_fewer(self):
        # Higher pump quality → higher throughput → fewer pumps needed
        pumps = {}
        for q in ("normal", "uncommon", "rare", "epic", "legendary"):
            out = _fmt_new("vanilla", "lubricant", 60, pump=q)
            pumps[q] = out["pumps_needed"]

        self.assertGreater(pumps["normal"],    pumps["uncommon"])
        self.assertGreater(pumps["uncommon"],  pumps["rare"])
        self.assertGreater(pumps["rare"],      pumps["epic"])
        self.assertGreater(pumps["epic"],      pumps["legendary"])

    def test_no_pump_flag_omits_fields(self):
        out = _fmt_new("vanilla", "lubricant", 60, pump=None)
        self.assertNotIn("pump", out)
        self.assertNotIn("pumps_needed", out)

    def test_solid_item_gets_no_pump_field(self):
        # Solid item with --pump set → no pump fields (pump ignored for solids)
        out = _fmt_new("vanilla", "electronic-circuit", 60, pump="normal")
        self.assertNotIn("pump", out)
        self.assertNotIn("pumps_needed", out)


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
        fluid_set = cli.build_fluid_set(_DATA["vanilla"]["data"])

        args = argparse.Namespace(
            item="iron-gear-wheel", rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            belt=None, pump=None,
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=rm_overrides,
            recipe_module_overrides=None,
            recipe_beacon_overrides=None,
            recipe_belt_overrides=None, recipe_pump_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"],
                                fluid_set=fluid_set)
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
        fluid_set = cli.build_fluid_set(_DATA["vanilla"]["data"])
        args = argparse.Namespace(
            item="electronic-circuit", rate=60, dataset="vanilla",
            assembler=3, furnace="electric", miner="electric",
            machine_quality="normal", beacon_quality="normal",
            belt=None, pump=None,
            module_configs=None, beacon_configs=None,
            recipe_machine_overrides=None, recipe_module_overrides=None,
            recipe_beacon_overrides=None, recipe_belt_overrides=None,
            recipe_pump_overrides=None,
        )
        out = cli.format_output(args, s, _DATA["vanilla"]["resource_info"],
                                fluid_set=fluid_set)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
