#!/usr/bin/env python3
"""
Quality Planner V1 (MVP)

Separate tool that answers:
  "Given my research and module tier, what's the cheapest way to make
   N legendary <item> per minute?"

Scope (V1):
  * Nauvis-style assembly items whose raws are all reachable via
    asteroid reprocessing (iron-ore, copper-ore, coal, stone, calcite, ice).
  * DP-based quality loop solver (backward induction over tiers).
  * Asteroid reprocessing as the canonical legendary raw source.
  * Fluid quality transparency (foundry casting preferred when available).
  * Productivity research per recipe family, capped at +300 %.

Fails fast on planet exclusives (tungsten / holmium / fluorine / Gleba biolocals)
and self-recycling items (tungsten-carbide, superconductor, holmium-plate).

Usage
-----
    python dev/quality_planner.py --item <item-id> --rate <N>
        [--module-quality normal|uncommon|rare|epic|legendary]
        [--assembler-level 2|3]
        [--research NAME=LEVEL ...]
        [--format json|human]

Stdlib only.  Shares the Space Age dataset with cli.py.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict

# Import from cli.py (sibling directory)
_CLI_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "10x-factorio-engineer",
    "assets",
)
sys.path.insert(0, os.path.abspath(_CLI_DIR))
import cli  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUALITY_TIERS = ("normal", "uncommon", "rare", "epic", "legendary")
QUALITY_INDEX = {q: i for i, q in enumerate(QUALITY_TIERS)}

# Base quality chance per quality-module slot at normal module quality
# (game source: quality module T1 = +1%, T2 = +1.5%, T3 = +2.5%; multiplied
# by MODULE_QUALITY_MULT for uncommon/rare/epic/legendary modules).
QUALITY_MODULE_BONUS: dict[int, float] = {
    1: 0.01,
    2: 0.015,
    3: 0.025,
}

# Tier-skip distribution when a quality roll succeeds.
# Of the total quality chance Q: 90% goes to +1 tier, 9% to +2, 0.9% to +3, 0.1% to +4.
TIER_SKIP_DIST: tuple[float, ...] = (0.9, 0.09, 0.009, 0.001)

# Asteroid reprocessing: crusher processes chunk -> (mostly) chunk with some quality chance.
# Data is in the recipe file; these are the canonical loop recipes.
ASTEROID_REPROCESSING_RECIPES: dict[str, str] = {
    "metallic-asteroid-chunk":  "metallic-asteroid-reprocessing",
    "carbonic-asteroid-chunk":  "carbonic-asteroid-reprocessing",
    "oxide-asteroid-chunk":     "oxide-asteroid-reprocessing",
}

# Crushing recipe that converts a chunk to raw items.  These are normal
# crafting recipes (allow_productivity=True), run on a crusher (2 slots).
ASTEROID_CRUSHING_RECIPES: dict[str, str] = {
    "metallic-asteroid-chunk":  "metallic-asteroid-crushing",
    "carbonic-asteroid-chunk":  "carbonic-asteroid-crushing",
    "oxide-asteroid-chunk":     "oxide-asteroid-crushing",
}

# Chunk -> raw items it yields (used to know which chunk to allocate for a raw).
RAW_TO_CHUNK: dict[str, str] = {
    "iron-ore":    "metallic-asteroid-chunk",
    "copper-ore":  "metallic-asteroid-chunk",
    "coal":        "carbonic-asteroid-chunk",
    "carbon":      "carbonic-asteroid-chunk",
    "sulfur":      "carbonic-asteroid-chunk",   # carbonic advanced
    "stone":       "oxide-asteroid-chunk",
    "calcite":     "oxide-asteroid-chunk",
    "ice":         "oxide-asteroid-chunk",
    "water":       "oxide-asteroid-chunk",      # via ice-melting
}

# Raws that cannot be sourced from asteroids (V1 fails fast on these).
# Oil-chain fluids (crude-oil, petroleum-gas, light-oil, heavy-oil, steam) are
# listed here so that any item requiring them (plastic-bar, sulfur, rocket-fuel,
# lubricant) fails fast in V1 — the asteroid chain does not reach them.
PLANET_EXCLUSIVE_RAWS: dict[str, str] = {
    "tungsten-ore":     "vulcanus",
    "tungsten-carbide": "vulcanus",
    "lava":             "vulcanus",
    "holmium-ore":      "fulgora",
    "holmium-solution": "fulgora",
    "fluorine":         "aquilo",
    "lithium-brine":    "aquilo",
    "ammoniacal-solution": "aquilo",
    "yumako":           "gleba",
    "yumako-mash":      "gleba",
    "jellynut":         "gleba",
    "jelly":            "gleba",
    "bioflux":          "gleba",
    "pentapod-egg":     "gleba",
    "spoilage":         "gleba",
    "raw-fish":         "nauvis",
    "crude-oil":        "nauvis",
    # Oil-chain fluids — unreachable without crude-oil (Nauvis pumpjacks) in V1
    "petroleum-gas":    "nauvis",
    "light-oil":        "nauvis",
    "heavy-oil":        "nauvis",
    "steam":            "nauvis",
    "sulfuric-acid":    "nauvis",
    # Intermediate items with oil dependency
    "plastic-bar":      "nauvis",
    "sulfur":           "nauvis",
    "lubricant":        "nauvis",
    "rocket-fuel":      "nauvis",
    "solid-fuel":       "nauvis",
    "explosives":       "nauvis",
}

# Self-recycling blocklist (fail fast for V1).
SELF_RECYCLING_BLOCKLIST = frozenset([
    "tungsten-carbide",
    "superconductor",
    "holmium-plate",
])

# Recycler retention (standard recycler; quality-only slots).
RECYCLER_RETENTION = 0.25
RECYCLER_SLOTS = 4
RECYCLER_SPEED = 0.5

# Crusher speed + slots (for reprocessing / crushing).
CRUSHER_SPEED = 1.0
CRUSHER_SLOTS = 2

# Machine speeds (from cli.MACHINE_CRAFTING_SPEED; kept here for float math).
def _machine_speed(machine_key: str) -> float:
    s = cli.MACHINE_CRAFTING_SPEED.get(machine_key)
    if s is None:
        return 1.0
    return float(s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_fluid_set(data: dict) -> frozenset[str]:
    """Return set of item keys whose type == 'fluid'."""
    out: set[str] = set()
    for it in data.get("items", []):
        if it.get("type") == "fluid" and "key" in it:
            out.add(it["key"])
    for fl in data.get("fluids", []):
        if "item_key" in fl:
            out.add(fl["item_key"])
    return frozenset(out)


def _recipe_by_key(data: dict, key: str) -> dict | None:
    for r in data.get("recipes", []):
        if r.get("key") == key:
            return r
    return None


def _recipe_result_amount(recipe: dict, product: str) -> float:
    """Return amount of `product` produced by one craft (includes probability)."""
    total = 0.0
    for res in recipe.get("results", []):
        if res.get("name") != product:
            continue
        amt = res.get("amount")
        if amt is None:
            amt = (res.get("amount_min", 0) + res.get("amount_max", 0)) / 2
        prob = res.get("probability", 1.0)
        total += float(amt) * float(prob)
    return total


def _recipe_ing_amount(recipe: dict, ingredient: str) -> float:
    for ing in recipe.get("ingredients", []):
        if ing.get("name") == ingredient:
            return float(ing.get("amount", 0))
    return 0.0


# ---------------------------------------------------------------------------
# DP kernel
# ---------------------------------------------------------------------------

def _quality_chance(num_q_slots: int, module_tier: int, module_quality: str) -> float:
    """Total per-roll quality chance for num_q_slots quality modules on a machine.

    Clamped to [0, 1].  A roll either stays at the same tier (prob 1-Q) or
    tiers up by (+1, +2, +3, +4) with the game's fixed 90/9/0.9/0.1 split.
    """
    if num_q_slots <= 0 or module_tier <= 0:
        return 0.0
    base = QUALITY_MODULE_BONUS[module_tier]
    mult = float(cli.MODULE_QUALITY_MULT[module_quality])
    q = num_q_slots * base * mult
    if q > 1.0:
        q = 1.0
    if q < 0.0:
        q = 0.0
    return q


def _tier_skip_probs(q_total: float, tier_index: int) -> list[float]:
    """Return p[s] for s in [tier_index..4], where p[s] is probability a craft
    at tier_index lands at tier s.  len=5-tier_index; index 0 is same-tier.
    """
    remaining = 5 - tier_index   # number of tiers at or above current
    probs = [0.0] * remaining
    probs[0] = 1.0 - q_total     # stay
    # spread q_total across +1..+4 via TIER_SKIP_DIST; cap at legendary
    for delta, share in enumerate(TIER_SKIP_DIST, start=1):
        target = tier_index + delta
        if target >= 5:
            target = 4  # pile onto legendary
        # offset into probs[]
        probs[target - tier_index] += q_total * share
    return probs


def _prod_bonus(num_p_slots: int, prod_module_tier: int, module_quality: str) -> float:
    """Prod-module bonus as a fraction (0.10 per T3 at normal, etc.)."""
    if num_p_slots <= 0 or prod_module_tier <= 0:
        return 0.0
    base = float(cli.MODULE_PROD_BONUS[prod_module_tier])
    mult = float(cli.MODULE_QUALITY_MULT[module_quality])
    return num_p_slots * base * mult


def _unused_solve_loop_reference(
    craft_recipe: dict | None,
    craft_machine_key: str,
    craft_slots: int,
    craft_product: str,
    recycle_recipe: dict | None,
    recycle_machine_key: str,
    recycle_slots: int,
    recycle_allow_prod: bool,
    inherent_prod: float,
    research_prod: float,
    module_quality: str,
    prod_module_tier: int = 3,
    quality_module_tier: int = 3,
    prod_capped: bool = True,
    *,
    retention_override: float | None = None,
) -> tuple[float, dict]:
    """Backward induction for a standard craft+recycle (or asteroid-reprocessing) loop.

    Returns (V[1], configs_per_tier).

    Standard mode (recycle_recipe is the item's recycling recipe):
        p[t->s] = (craft prod-adjusted retention) * quality roll at craft
                    * (recycle retention) * quality roll at recycle

    Asteroid reprocessing mode (craft_recipe=None, recycle_recipe = reprocessing):
        No craft step; one roll at the reprocessing crusher.
        Retention = self-output probability of the chunk (from recipe data).

    The kernel enumerates per-tier module configs:
      * craft slots: split between prod and quality (prod only if allow_prod)
      * recycle slots: all quality (recycler disallows prod; reprocessing too)

    It computes V[t] = sum(p[s]*V[s] for s>t) / (1-p[t]).
    """
    # Build per-tier configs.
    V = [0.0] * 5
    V[4] = 1.0  # legendary is absorbing
    configs: dict[int, dict] = {}

    # Enumerate craft configs: (p_slots, q_slots) with p_slots+q_slots<=craft_slots
    if craft_recipe is None:
        # Asteroid mode: no craft step
        craft_configs = [(0, 0)]
    else:
        craft_configs = []
        for p in range(craft_slots + 1):
            for q in range(craft_slots - p + 1):
                if p > 0 and not recycle_allow_prod:
                    # Non-prod craft (e.g. reprocessing) — skip prod configs
                    # Actually this flag controls recycler prod; craft prod is
                    # controlled by craft_recipe's allow_productivity.
                    pass
                craft_configs.append((p, q))
        # Filter: if craft recipe disallows prod, zero out prod slots
        if not craft_recipe.get("allow_productivity", True):
            craft_configs = [(0, q) for (_p, q) in craft_configs if _p == 0]
            craft_configs = list(set(craft_configs))

    # Recycle configs: quality only (0 prod)
    if recycle_recipe is None:
        recycle_configs = [0]
    else:
        recycle_configs = list(range(recycle_slots + 1))

    for t in range(3, -1, -1):  # tiers 3,2,1,0 = epic, rare, uncommon, normal
        best_v = -1.0
        best_cfg = None
        for cp, cq in craft_configs:
            for rq in recycle_configs:
                # Compute effective prod in craft step
                prod = inherent_prod + research_prod + _prod_bonus(cp, prod_module_tier, module_quality)
                if prod_capped and prod > 3.0:
                    prod = 3.0
                # Effective retention
                if craft_recipe is None:
                    # asteroid reprocessing: retention is the self-output prob
                    if retention_override is not None:
                        craft_ret = retention_override
                    else:
                        craft_ret = 1.0
                    # Only the recycle step exists; combine: 1 input -> craft_ret*(1+0) -> quality roll
                    # We put the roll on the "recycle" (reprocessing) slot
                    step_ret = craft_ret
                    q_slots_total = rq  # only recycle slots
                    # tier skip uses q_slots_total on recycle_machine_key
                    q_total = _quality_chance(q_slots_total, quality_module_tier, module_quality)
                    probs = _tier_skip_probs(q_total, t)
                    # multiply probs by retention
                    probs = [p * step_ret for p in probs]
                else:
                    # Standard: craft with cp prod + cq quality, then recycle with rq quality
                    # Craft step: 1 item @ tier t -> (1 + prod) * craft_product_amount items,
                    # each with quality roll at craft machine
                    craft_output = _recipe_result_amount(craft_recipe, craft_product)
                    # Per 1 ingredient (for loop the recipe ingests 1 of the craft_product's
                    # feedstock — we track items per-item).  The loop rate we want is
                    # "items-out at tier s per item-in at tier t after one full cycle".
                    # Craft produces craft_output * (1+prod) output items per craft cycle
                    # (consuming its ingredients including the loop item).
                    # To normalise: 1 loop-input -> 1/ing_of_loop_item craft cycles
                    # -> craft_output*(1+prod)/ing output items.  For recycling loops
                    # where the loop item IS both craft input ingredient and craft output,
                    # the per-loop-input item count = craft_output * (1+prod) / ing_count.
                    ing_amt = _recipe_ing_amount(craft_recipe, "__loop__")
                    # The loop works on the output of craft_recipe; ingredient isn't the
                    # loop item in the general case.  But for tests we usually call this
                    # with a self-loop recipe like iron-plate-recycling where input=output.
                    # Simplified model: each craft produces craft_output*(1+prod) items,
                    # each goes through a quality roll; recycling then returns
                    # recycler_retention * item_count_of_loop_item per 1 recycled.
                    # For V computation per *craft-output item*, normalise to 1 item.
                    items_per_craft = craft_output * (1.0 + prod)
                    # per-item: quality roll at craft machine (based on cq slots)
                    q_craft = _quality_chance(cq, quality_module_tier, module_quality)
                    craft_probs = _tier_skip_probs(q_craft, t)  # where item lands after craft
                    # Now each crafted item is recycled.  Recycler returns loop-item with
                    # retention probability, and the recycler also rolls quality.
                    q_rec = _quality_chance(rq, quality_module_tier, module_quality)
                    # Compose: craft lands at tier u (probs[u]); recycle rolls from u.
                    # Final prob at tier s = sum over u of craft_probs[u-t] * recycle_probs[s-u] * retention
                    probs = [0.0] * (5 - t)
                    retention = RECYCLER_RETENTION
                    for u_offset, cp_prob in enumerate(craft_probs):
                        u = t + u_offset
                        rec_probs = _tier_skip_probs(q_rec, u)
                        for s_offset, rp in enumerate(rec_probs):
                            s = u + s_offset
                            probs[s - t] += cp_prob * rp * retention
                    # But each craft produces items_per_craft items from the loop-input
                    # For the loop, items_per_craft represents the "multiplier" on retention:
                    # one loop-input item, consumed by craft recipe as ingredient, produces
                    # items_per_craft output items; each recycles back with retention.
                    # Effective per-loop-input yield: items_per_craft * probs (where probs
                    # already includes retention).
                    # For self-loop like iron-plate-recycling where craft is iron-plate
                    # (ingests iron-ore — but we loop on iron-plate itself), the model is:
                    # 1 iron-plate -> recycler -> RECYCLER_RETENTION iron-plates.  No craft.
                    # That's the "recycle-only" branch we use for wiki yield reproduction.
                    # We keep items_per_craft=1 for recycle-only (caller passes craft=None).
                    probs = [p * items_per_craft / max(1.0, ing_amt or 1.0) for p in probs]

                # Compute V[t] contribution
                stay = probs[0]
                if abs(1.0 - stay) < 1e-15:
                    v = 0.0
                else:
                    numer = sum(probs[k] * V[t + k] for k in range(1, len(probs)))
                    v = numer / (1.0 - stay)
                if v > best_v:
                    best_v = v
                    best_cfg = {"craft_prod": cp, "craft_quality": cq, "recycle_quality": rq}
        V[t] = max(best_v, 0.0)
        configs[t] = best_cfg or {"craft_prod": 0, "craft_quality": 0, "recycle_quality": 0}

    return V[0], configs


def solve_recycle_loop(
    item_key: str,
    data: dict,
    machine_key: str,
    machine_slots: int,
    machine_allow_prod: bool,
    inherent_prod: float,
    research_prod: float,
    module_quality: str,
    prod_module_tier: int = 3,
    quality_module_tier: int = 3,
) -> tuple[float, dict]:
    """Simplified DP for the recycle-only loop on an item.

    Model: each cycle consists of (craft item -> recycle item -> get 25% back).
    Craft machine has `machine_slots` slots (prod allowed per machine_allow_prod
    AND recipe allow_productivity).  Recycler has 4 slots, quality-only.
    Quality rolls happen at BOTH craft and recycle (per game mechanics).

    Returns (legendary-per-normal, configs_per_tier).
    """
    craft_recipe = cli.pick_recipe(item_key, cli.build_recipe_index(data))
    if craft_recipe is None:
        return 0.0, {}

    recycle_recipe_key = f"{item_key}-recycling"
    recycle_recipe = _recipe_by_key(data, recycle_recipe_key)

    V = [0.0] * 5
    V[4] = 1.0
    configs: dict[int, dict] = {}

    recipe_allow_prod = craft_recipe.get("allow_productivity", True) and machine_allow_prod

    # Enumerate craft configs
    craft_configs: list[tuple[int, int]] = []
    for p in range(machine_slots + 1):
        for q in range(machine_slots - p + 1):
            if p > 0 and not recipe_allow_prod:
                continue
            craft_configs.append((p, q))

    recycle_configs = list(range(RECYCLER_SLOTS + 1))

    # Retention: recycler returns recycle_recipe_result_amount of item per 1 recycled.
    if recycle_recipe is not None:
        retention = _recipe_result_amount(recycle_recipe, item_key)
    else:
        retention = RECYCLER_RETENTION  # fallback

    # Craft output amount of item per cycle
    craft_output = _recipe_result_amount(craft_recipe, item_key)

    for t in range(3, -1, -1):
        best_v = -1.0
        best_cfg = None
        for cp, cq in craft_configs:
            for rq in recycle_configs:
                prod = inherent_prod + research_prod + _prod_bonus(cp, prod_module_tier, module_quality)
                if prod > 3.0:
                    prod = 3.0
                items_per_craft = craft_output * (1.0 + prod)

                q_craft = _quality_chance(cq, quality_module_tier, module_quality)
                q_rec = _quality_chance(rq, quality_module_tier, module_quality)

                # Compose craft then recycle quality rolls
                craft_probs = _tier_skip_probs(q_craft, t)
                probs = [0.0] * (5 - t)
                for u_offset, cp_prob in enumerate(craft_probs):
                    u = t + u_offset
                    rec_probs = _tier_skip_probs(q_rec, u)
                    for s_offset, rp in enumerate(rec_probs):
                        s = u + s_offset
                        probs[s - t] += cp_prob * rp * retention * items_per_craft

                stay = probs[0]
                if stay >= 1.0 - 1e-15:
                    v = 0.0
                else:
                    numer = sum(probs[k] * V[t + k] for k in range(1, len(probs)))
                    v = numer / (1.0 - stay)
                if v > best_v:
                    best_v = v
                    best_cfg = {"craft_prod": cp, "craft_quality": cq, "recycle_quality": rq}
        V[t] = max(best_v, 0.0)
        configs[t] = best_cfg or {"craft_prod": 0, "craft_quality": 0, "recycle_quality": 0}

    return V[0], configs


def solve_asteroid_reprocessing_loop(
    chunk_key: str,
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
) -> tuple[float, dict]:
    """DP for legendary-chunk per normal-chunk via reprocessing.

    Reprocessing recipe: 1 chunk in, ~0.4 same-chunk out + 0.2 each of 2
    other chunk types.  Runs on crusher (2 slots, quality-only — reprocessing
    disallows prod).

    We model this as a single-step quality loop:
      retention = self-output probability of `chunk_key` (0.4 typically)
      quality roll: crusher 2 slots with quality modules

    Returns (V[0], configs).
    """
    rep_key = ASTEROID_REPROCESSING_RECIPES.get(chunk_key)
    if rep_key is None:
        return 0.0, {}
    rep = _recipe_by_key(data, rep_key)
    if rep is None:
        return 0.0, {}

    # Effective retention: total output probability across all chunk types
    # (assumes byproduct chunks are cross-fed between reprocessors, which is
    # the standard community setup).  For a single-chunk-type loop this is
    # ~0.80; cli recipe data has 0.4 + 0.2 + 0.2 = 0.8.
    retention = sum(
        float(r.get("amount", 0)) * float(r.get("probability", 1.0))
        for r in rep.get("results", [])
    )
    if retention > 1.0:
        retention = 1.0

    V = [0.0] * 5
    V[4] = 1.0
    configs: dict[int, dict] = {}

    for t in range(3, -1, -1):
        best_v = -1.0
        best_cfg = None
        for q in range(CRUSHER_SLOTS + 1):
            q_total = _quality_chance(q, quality_module_tier, module_quality)
            probs = _tier_skip_probs(q_total, t)
            probs = [p * retention for p in probs]
            stay = probs[0]
            if stay >= 1.0 - 1e-15:
                v = 0.0
            else:
                numer = sum(probs[k] * V[t + k] for k in range(1, len(probs)))
                v = numer / (1.0 - stay)
            if v > best_v:
                best_v = v
                best_cfg = {"craft_prod": 0, "craft_quality": 0, "recycle_quality": q}
        V[t] = max(best_v, 0.0)
        configs[t] = best_cfg or {"craft_prod": 0, "craft_quality": 0, "recycle_quality": 0}

    return V[0], configs


# ---------------------------------------------------------------------------
# Recipe tree walk for planner
# ---------------------------------------------------------------------------

def _research_prod_for_recipe(recipe_key: str, research_levels: dict[str, int]) -> float:
    """Return research-productivity fraction for the given recipe (sum of all
    applicable techs × level × 10%)."""
    bonus = 0.0
    for tech, recipes in cli.PRODUCTIVITY_RESEARCH.items():
        if recipe_key in recipes:
            level = research_levels.get(tech, 0)
            bonus += 0.1 * level
    return bonus


def _pick_recipe_fluid_preferred(
    item_key: str,
    recipe_idx: dict,
    fluids: frozenset[str],
    planet_props: dict | None = None,
) -> dict | None:
    """Like cli.pick_recipe, but prefer recipes whose FLUID ingredients do not
    introduce planet-exclusive raws.

    Picks `casting-iron` (molten-iron input, molten-iron derivable from iron-ore)
    over `iron-plate` (iron-ore input directly).  Rejects `molten-iron-from-lava`
    because lava is Vulcanus-exclusive.
    """
    candidates = recipe_idx.get(item_key, [])
    if not candidates:
        return cli.pick_recipe(item_key, recipe_idx)

    def ingredient_has_planet_exclusive(r: dict) -> bool:
        for ing in r.get("ingredients", []):
            if ing["name"] in PLANET_EXCLUSIVE_RAWS and ing["name"] not in RAW_TO_CHUNK:
                return True
        return False

    def fluid_fraction(r: dict) -> float:
        total = 0.0
        fluid_amt = 0.0
        for ing in r.get("ingredients", []):
            total += float(ing.get("amount", 0))
            if ing.get("name") in fluids:
                fluid_amt += float(ing.get("amount", 0))
        return fluid_amt / total if total > 0 else 0.0

    # Filter out candidates with planet-exclusive raws as direct ingredients.
    viable = [r for r in candidates if not ingredient_has_planet_exclusive(r)]
    # Filter by planet surface_conditions if given
    if planet_props is not None:
        viable = [r for r in viable if cli._recipe_valid_for_planet(r, planet_props)]
    if not viable:
        viable = candidates  # fall back; caller will raise later if unreachable

    canonical = cli.pick_recipe(item_key, recipe_idx)
    # Preference: highest fluid fraction among viable candidates; tie-break by canonical.
    sorted_c = sorted(viable, key=lambda r: (-fluid_fraction(r), r.get("order", "zzz")))
    best = sorted_c[0]
    # Only use fluid preference if it actually has fluid input; else use canonical (if viable)
    if fluid_fraction(best) > 0.0:
        return best
    if canonical in viable:
        return canonical
    return sorted_c[0]


def walk_recipe_tree(
    item_key: str,
    rate: float,
    data: dict,
    research_levels: dict[str, int],
    assembler_level: int,
    fluids: frozenset[str],
    planet_props: dict | None = None,
) -> tuple[list[dict], dict[str, float]]:
    """Walk recipe tree; return (stages, raw_demand_rates).

    Stages are ordered deepest-first-ish for display.  Each stage has:
      {role, recipe, machine, rate_per_min, machine_count, ingredients, fluid_inputs}

    raw_demand_rates maps raw_item_key -> demand per minute (solid raws only;
    fluid raws are tracked but don't flow through quality loops).
    """
    recipe_idx = cli.build_recipe_index(data)
    raw_set = cli.build_raw_set(data, "nauvis") | {"metallic-asteroid-chunk", "carbonic-asteroid-chunk", "oxide-asteroid-chunk"}

    # Accumulate demand per (item) — then we'll resolve recipes / stages per item.
    demand: dict[str, float] = defaultdict(float)
    demand[item_key] = rate
    order: list[str] = [item_key]
    seen: set[str] = set()

    # BFS-like accumulation
    pending = [item_key]
    # Build demand by recursive expansion; stop at raws.
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        if current in raw_set and current not in (item_key,):
            continue
        if current in PLANET_EXCLUSIVE_RAWS and current != item_key:
            planet = PLANET_EXCLUSIVE_RAWS[current]
            if current not in RAW_TO_CHUNK:
                raise ValueError(
                    f"ERROR: item '{item_key}' requires '{current}', which needs planet '{planet}' — not supported in V1"
                )
        if current in SELF_RECYCLING_BLOCKLIST and current != item_key:
            raise ValueError(
                f"ERROR: recipe '{current}' is self-recycling (output recycles to itself) — not supported in V1"
            )
        recipe = _pick_recipe_fluid_preferred(current, recipe_idx, fluids, planet_props)
        if recipe is None:
            if current in raw_set:
                continue
            raise ValueError(f"ERROR: no recipe for '{current}'")
        seen.add(current)
        # Skip expansion if no-ingredients recipe or if this *is* a raw
        per_craft_output = _recipe_result_amount(recipe, current)
        if per_craft_output <= 0:
            continue
        research_prod = _research_prod_for_recipe(recipe["key"], research_levels)
        eff_prod = 1.0 + research_prod
        if eff_prod > 4.0:
            eff_prod = 4.0
        cycles_per_min = demand[current] / (per_craft_output * eff_prod)
        for ing in recipe.get("ingredients", []):
            iname = ing["name"]
            amt = float(ing.get("amount", 0))
            ing_rate = amt * cycles_per_min
            if iname in fluids:
                # fluid-transparent: still track but don't propagate as legendary
                # Note: fluids produced by intermediate recipes; for "molten-iron" we
                # still need to expand to find iron-ore demand upstream.  Walk into fluids.
                demand[iname] += ing_rate
                if iname not in seen:
                    pending.append(iname)
                    order.append(iname)
            else:
                demand[iname] += ing_rate
                if iname not in seen and iname not in raw_set:
                    pending.append(iname)
                    order.append(iname)

    # Build stages from order; also collect all raws seen as demand keys
    stages: list[dict] = []
    raw_demand: dict[str, float] = defaultdict(float)
    for iname, amt in demand.items():
        if iname in raw_set and iname != item_key:
            raw_demand[iname] += amt
    for item in order:
        if item in raw_set and item != item_key:
            continue
        recipe = _pick_recipe_fluid_preferred(item, recipe_idx, fluids, planet_props)
        if recipe is None:
            raw_demand[item] += demand[item]
            continue
        machine_key, machine_speed = cli.get_machine(recipe["category"], assembler_level, "electric")
        machine_speed_f = float(machine_speed)
        research_prod = _research_prod_for_recipe(recipe["key"], research_levels)
        eff_prod = 1.0 + research_prod
        capped = False
        if eff_prod > 4.0:
            eff_prod = 4.0
            capped = True
        per_craft_output = _recipe_result_amount(recipe, item)
        if per_craft_output <= 0:
            continue
        crafts_per_min = demand[item] / (per_craft_output * eff_prod)
        crafting_time = float(recipe.get("energy_required", 1))
        machine_count = crafts_per_min * crafting_time / (machine_speed_f * 60.0)
        inputs: dict[str, float] = {}
        for ing in recipe.get("ingredients", []):
            inputs[ing["name"]] = float(ing.get("amount", 0)) * crafts_per_min
        fluid_inputs = {k: v for k, v in inputs.items() if k in fluids}
        solid_inputs = {k: v for k, v in inputs.items() if k not in fluids}
        stages.append({
            "role": "assembly" if item != item_key else "assembly",
            "recipe": recipe["key"],
            "product": item,
            "machine": machine_key,
            "machine_speed": machine_speed_f,
            "rate_per_min": demand[item],
            "crafts_per_min": crafts_per_min,
            "machine_count": machine_count,
            "inputs": inputs,
            "fluid_inputs": fluid_inputs,
            "solid_inputs": solid_inputs,
            "research_prod": research_prod,
            "prod_capped": capped,
            "inputs_all_legendary": all(k not in fluids for k in inputs) if solid_inputs else True,
        })

    # Filter raws to solid raws only (fluids like water get treated in crushing)
    # Keep only items the asteroid chain produces; error on others.
    asteroid_raws = set(RAW_TO_CHUNK.keys()) | set(ASTEROID_REPROCESSING_RECIPES.keys())
    # Fluid raws that ARE reachable via the asteroid+Nauvis chain (water from ice).
    allowed_fluid_raws = {"water"}
    for raw in list(raw_demand.keys()):
        if raw in fluids:
            if raw in allowed_fluid_raws:
                continue
            # Un-reachable fluid raw (e.g. crude-oil, lava, ammoniacal-solution)
            planet = PLANET_EXCLUSIVE_RAWS.get(raw, "nauvis")
            raise ValueError(
                f"ERROR: item '{item_key}' requires '{raw}', which needs planet '{planet}' — not supported in V1"
            )
        if raw not in asteroid_raws:
            planet = PLANET_EXCLUSIVE_RAWS.get(raw)
            if planet:
                raise ValueError(
                    f"ERROR: item '{item_key}' requires '{raw}', which needs planet '{planet}' — not supported in V1"
                )
            raise ValueError(f"ERROR: no asteroid path to required raw '{raw}'")

    return stages, dict(raw_demand)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

def plan(
    item_key: str,
    rate: float,
    data: dict,
    *,
    module_quality: str = "legendary",
    research_levels: dict[str, int] | None = None,
    assembler_level: int = 3,
    quality_module_tier: int = 3,
) -> dict:
    """Top-level planning: walk tree, attach asteroid reprocessing loops for raws,
    scale stages, assemble full output."""
    research_levels = research_levels or {}
    if item_key in SELF_RECYCLING_BLOCKLIST:
        raise ValueError(
            f"ERROR: recipe '{item_key}' is self-recycling (output recycles to itself) — not supported in V1"
        )
    if item_key in PLANET_EXCLUSIVE_RAWS:
        planet = PLANET_EXCLUSIVE_RAWS[item_key]
        if item_key not in RAW_TO_CHUNK:
            raise ValueError(
                f"ERROR: item '{item_key}' requires '{item_key}', which needs planet '{planet}' — not supported in V1"
            )

    fluids = build_fluid_set(data)
    planet_props = cli.get_planet_props(data, "nauvis")
    stages, raw_demand = walk_recipe_tree(
        item_key, rate, data, research_levels, assembler_level, fluids, planet_props,
    )

    # Group raw demand by chunk type.  Each chunk is produced by one crushing recipe
    # (e.g. metallic-asteroid-crushing -> iron-ore+copper-ore).  We scale to satisfy
    # the max-demanding raw among a chunk's outputs.
    chunk_demand: dict[str, float] = defaultdict(float)
    # Direct chunk demand (e.g. calcite only comes from advanced-oxide-asteroid-crushing
    # which takes oxide-asteroid-chunk — raw_demand already contains the chunk directly).
    for chunk in ASTEROID_REPROCESSING_RECIPES:
        if chunk in raw_demand and raw_demand[chunk] > 0:
            chunk_demand[chunk] += raw_demand[chunk]
    crushing_stages: list[dict] = []
    for chunk, crush_recipe_key in ASTEROID_CRUSHING_RECIPES.items():
        crush = _recipe_by_key(data, crush_recipe_key)
        if crush is None:
            continue
        # For each raw output of this crushing recipe that we demand, compute required
        # crushes_per_min to meet that raw's demand.  Take the max.
        research_prod = _research_prod_for_recipe(crush_recipe_key, research_levels)
        eff_prod = 1.0 + research_prod
        capped = False
        if eff_prod > 4.0:
            eff_prod = 4.0
            capped = True
        max_crushes_per_min = 0.0
        outputs_to_raws: dict[str, float] = {}
        for res in crush.get("results", []):
            rn = res["name"]
            if rn == chunk:
                continue
            amt = res.get("amount", 0)
            if amt == 0:
                continue
            amt_per_craft = float(amt) * float(res.get("probability", 1.0)) * eff_prod
            demand_rate = raw_demand.get(rn, 0.0)
            if demand_rate > 0:
                needed_crushes = demand_rate / amt_per_craft
                if needed_crushes > max_crushes_per_min:
                    max_crushes_per_min = needed_crushes
                outputs_to_raws[rn] = demand_rate
        # Handle ice-melting for water
        if chunk == "oxide-asteroid-chunk" and "water" in raw_demand:
            # Water comes from ice via ice-melting; ensure we have ice demand
            # Approx: 10 water per 1 ice, so ice demand += water/10.  Here we just
            # top up via demand route; the walker already treats water as a raw
            # so water demand appears in raw_demand.  Convert via separate ice-melting
            # stage (not tracked here for simplicity).
            pass
        if max_crushes_per_min > 0:
            chunk_demand[chunk] = max_crushes_per_min
            # machines: crusher speed 1.0, time=2s typically
            crushing_time = float(crush.get("energy_required", 2))
            machine_count = max_crushes_per_min * crushing_time / (CRUSHER_SPEED * 60.0)
            crushing_stages.append({
                "role": "raw-crushing",
                "recipe": crush_recipe_key,
                "chunk": chunk,
                "machine": "crusher",
                "machine_count": machine_count,
                "crafts_per_min": max_crushes_per_min,
                "outputs": outputs_to_raws,
                "research_prod": research_prod,
                "prod_capped": capped,
            })

    # For each chunk demanded, run the reprocessing loop to compute
    # normal-chunk-input needed per legendary-chunk-output.
    reprocessing_stages: list[dict] = []
    asteroid_input: dict[str, float] = {}
    for chunk, demanded_legendary_per_min in chunk_demand.items():
        v, configs = solve_asteroid_reprocessing_loop(
            chunk, data, module_quality, quality_module_tier,
        )
        if v <= 0:
            raise ValueError(
                f"ERROR: asteroid reprocessing for '{chunk}' yields 0 legendary — unreachable"
            )
        normal_input_per_min = demanded_legendary_per_min / v
        asteroid_input[chunk] = normal_input_per_min
        # Machine count estimate: reprocessing time=2s on crusher speed 1.0,
        # aggregated over all tiers.  For MVP, approximate by summing per-tier machines
        # using the final demanded rate × average cycles per chunk.
        # Simplification: machines ≈ normal_input_per_min * avg_cycles * 2s / 60 / 1.0
        # where avg_cycles ≈ 1/(1-retention) per tier.  Compute rough estimate:
        rep_recipe = _recipe_by_key(data, ASTEROID_REPROCESSING_RECIPES[chunk])
        retention = _recipe_result_amount(rep_recipe, chunk) if rep_recipe else 0.4
        # Geometric avg across 4 tiers; in practice use V to back out cycles.
        # Total processing load ≈ normal_input_per_min / (1 - retention) crafts/min.
        total_crafts_per_min = normal_input_per_min / max(1.0 - retention, 1e-6)
        machine_count = total_crafts_per_min * 2.0 / (CRUSHER_SPEED * 60.0)
        reprocessing_stages.append({
            "role": "asteroid-reprocessing",
            "chunk": chunk,
            "recipe": ASTEROID_REPROCESSING_RECIPES[chunk],
            "machine": "crusher",
            "machine_count": machine_count,
            "yield_pct": v * 100.0,
            "legendary_chunks_per_min": demanded_legendary_per_min,
            "normal_chunks_input_per_min": normal_input_per_min,
            "module_config_per_tier": {
                QUALITY_TIERS[t]: {
                    "craft": "n/a",
                    "recycle": f"{configs[t]['recycle_quality']}x quality-{quality_module_tier}-{module_quality}",
                }
                for t in (0, 1, 2, 3)
            },
        })

    # Total machine count
    total_machines = (
        sum(s["machine_count"] for s in stages)
        + sum(s["machine_count"] for s in crushing_stages)
        + sum(s["machine_count"] for s in reprocessing_stages)
    )

    notes: list[str] = []
    # Detect if we used fluid transparency
    for st in stages:
        if st.get("fluid_inputs"):
            notes.append(
                f"stage {st['recipe']} uses fluid-transparent input ({list(st['fluid_inputs'].keys())})"
            )

    out = {
        "target": {"item": item_key, "rate_per_min": rate, "tier": "legendary"},
        "asteroid_input": asteroid_input,
        "stages": reprocessing_stages + crushing_stages + list(reversed(stages)),
        "total_machine_count": total_machines,
        "module_quality": module_quality,
        "assembler_level": assembler_level,
        "research_levels": dict(research_levels),
        "notes": notes,
    }
    return out


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_human(out: dict) -> str:
    L: list[str] = []
    tgt = out["target"]
    L.append(f"Target: {tgt['rate_per_min']}/min of {tgt['item']} at tier {tgt['tier']}")
    L.append(f"Module quality: {out.get('module_quality', 'legendary')}, "
             f"assembler level: {out.get('assembler_level')}")
    if out.get("research_levels"):
        L.append(f"Research: {out['research_levels']}")
    L.append("")
    L.append("=== Asteroid Input (normal chunks/min) ===")
    for chunk, amt in sorted(out["asteroid_input"].items()):
        L.append(f"  {_humanize(chunk)}: {amt:.2f}")
    L.append("")
    L.append("=== Production Stages ===")
    for st in out["stages"]:
        role = st["role"]
        if role == "asteroid-reprocessing":
            L.append(
                f"  [reprocessing] {_humanize(st['chunk'])}: "
                f"{st['normal_chunks_input_per_min']:.2f} normal in -> "
                f"{st['legendary_chunks_per_min']:.2f} legendary out "
                f"({st['machine_count']:.2f} crushers, "
                f"yield {st['yield_pct']:.3f}%)"
            )
        elif role == "raw-crushing":
            outs = ", ".join(f"{_humanize(k)}@leg={v:.1f}/min" for k, v in st["outputs"].items())
            L.append(
                f"  [crushing]      {st['recipe']}: "
                f"{st['crafts_per_min']:.2f} crafts/min -> {outs} "
                f"({st['machine_count']:.2f} crushers)"
            )
        else:
            fluids = f", fluids=[{','.join(st['fluid_inputs'])}]" if st.get("fluid_inputs") else ""
            capped = " [PROD-CAPPED]" if st.get("prod_capped") else ""
            L.append(
                f"  [{role:10s}] {st['recipe']}: "
                f"{st['rate_per_min']:.2f}/min "
                f"({st['machine_count']:.2f} × {_humanize(st['machine'])}){fluids}{capped}"
            )
    L.append("")
    L.append(f"Total machines: {out['total_machine_count']:.2f}")
    if out.get("notes"):
        L.append("")
        L.append("Notes:")
        for n in out["notes"]:
            L.append(f"  - {n}")
    return "\n".join(L)


def _humanize(s: str) -> str:
    special = {
        "assembling-machine-1": "Assembler 1",
        "assembling-machine-2": "Assembler 2",
        "assembling-machine-3": "Assembler 3",
        "electric-furnace": "Electric Furnace",
        "electromagnetic-plant": "EM Plant",
        "metallic-asteroid-chunk": "Metallic Chunk",
        "carbonic-asteroid-chunk": "Carbonic Chunk",
        "oxide-asteroid-chunk":    "Oxide Chunk",
    }
    if s in special:
        return special[s]
    return s.replace("-", " ").title()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_research(raw_list: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for raw in raw_list:
        if "=" not in raw:
            sys.exit(f"Invalid --research '{raw}'; expected NAME=LEVEL")
        name, lvl = raw.split("=", 1)
        try:
            out[name.strip()] = int(lvl)
        except ValueError:
            sys.exit(f"Invalid research level '{lvl}' in --research {raw}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Legendary production planner (V1)")
    p.add_argument("--item", required=True)
    p.add_argument("--rate", required=True, type=float, help="target legendary items per minute")
    p.add_argument("--module-quality", default="legendary", choices=list(QUALITY_TIERS))
    p.add_argument("--quality-module-tier", default=3, type=int, choices=[1, 2, 3])
    p.add_argument("--assembler-level", default=3, type=int, choices=[2, 3])
    p.add_argument("--research", action="append", default=[],
                   help="research-tech=level, repeatable")
    p.add_argument("--format", default="human", choices=["human", "json"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data = cli.load_data("nauvis")
    research = _parse_research(args.research)
    try:
        out = plan(
            args.item, args.rate, data,
            module_quality=args.module_quality,
            research_levels=research,
            assembler_level=args.assembler_level,
            quality_module_tier=args.quality_module_tier,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    if args.format == "json":
        print(json.dumps(out, indent=2, default=str))
    else:
        print(format_human(out))


if __name__ == "__main__":
    main()
