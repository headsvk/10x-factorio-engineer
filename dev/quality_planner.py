#!/usr/bin/env python3
"""
Quality Planner V2

Separate tool that answers:
  "Given my research, module tier, and which planets I've unlocked, what's
   the cheapest way to make N legendary <item> per minute?"

V1 scope (asteroid-only, Nauvis-subset):
  * Nauvis-style assembly items whose raws are all reachable via
    asteroid reprocessing (iron-ore, copper-ore, coal, stone, calcite, ice).
  * DP-based quality loop solver (backward induction over tiers).
  * Asteroid reprocessing as the canonical legendary raw source.
  * Fluid quality transparency (foundry casting preferred when available).
  * Productivity research per recipe family, capped at +300 %.

V2 additions:
  * ``--planets`` multi-planet unlock flag (union of raws + surface props).
    When a planet is unlocked, its local raws (Nauvis crude-oil,
    Vulcanus lava/tungsten/calcite, Fulgora scrap, Gleba bioflux, …)
    become valid terminals in the recipe tree and previously-blocked
    items (plastic-bar, sulfur, processing-unit, artillery-shell) work
    transparently via fluid-transparent chains.
  * LDS shuffle (indirect upgrade loop): cast low-density-structure in
    the foundry with quality modules, recycle it back for legendary
    plastic-bar + copper-plate + steel-plate byproducts. Exposed as
    :func:`solve_lds_shuffle_loop` and used as an alternative quality
    source for plastic-bar when it beats the direct self-recycle loop.
  * Planet-local quality sources: Fulgora scrap-recycling (holmium-ore
    + all the recyclables) and Vulcanus tungsten-carbide self-recycle.

Still fails fast on unsupported chains, but with specific hints about
which ``--planets`` flag would unblock them.

Usage
-----
    python dev/quality_planner.py --item <item-id> --rate <N>
        [--planets nauvis,vulcanus,fulgora,gleba,aquilo]
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

# Crushing recipe that converts a chunk to raw items.  Advanced variants are
# preferred — they yield both ores (copper-ore in addition to iron-ore, sulfur
# alongside carbon, calcite alongside ice).  Research tech
# ``asteroid-productivity`` boosts both basic and advanced variants equally,
# and the advanced recipes are unlocked at a modest research cost in game.
ASTEROID_CRUSHING_RECIPES: dict[str, str] = {
    "metallic-asteroid-chunk":  "advanced-metallic-asteroid-crushing",
    "carbonic-asteroid-chunk":  "advanced-carbonic-asteroid-crushing",
    "oxide-asteroid-chunk":     "advanced-oxide-asteroid-crushing",
}

# Chunk -> raw items it yields (used to know which chunk to allocate for a raw).
# Restricted to items actually produced by the crushing recipes in the dataset:
#   metallic-asteroid-crushing          → iron-ore
#   advanced-metallic-asteroid-crushing → iron-ore + copper-ore
#   carbonic-asteroid-crushing          → carbon
#   advanced-carbonic-asteroid-crushing → carbon + sulfur
#   oxide-asteroid-crushing             → ice
#   advanced-oxide-asteroid-crushing    → ice + calcite
#
# Items NOT asteroid-reachable (coal, stone, tungsten-ore, scrap, holmium-ore,
# uranium-ore) route through a self-recycle quality loop instead (see
# :func:`solve_mined_raw_self_recycle_loop`).
RAW_TO_CHUNK: dict[str, str] = {
    "iron-ore":    "metallic-asteroid-chunk",
    "copper-ore":  "metallic-asteroid-chunk",
    "carbon":      "carbonic-asteroid-chunk",
    "sulfur":      "carbonic-asteroid-chunk",   # via advanced-carbonic-asteroid-crushing
    "ice":         "oxide-asteroid-chunk",
    "calcite":     "oxide-asteroid-chunk",      # via advanced-oxide-asteroid-crushing
    "water":       "oxide-asteroid-chunk",      # via ice-melting
}

# Solid raws that are mined on a planet and have no asteroid-crushing path.
# Legendary versions are produced via the recycler self-loop (25% retention,
# 4 quality slots) applied to the mined raw.  When the user has the relevant
# planet unlocked via ``--planets``, we attach a ``mined-raw-self-recycle``
# stage for these raws.
MINED_RAW_PLANETS: dict[str, tuple[str, ...]] = {
    "coal":         ("nauvis", "vulcanus"),
    "stone":        ("nauvis", "vulcanus", "gleba"),
    "tungsten-ore": ("vulcanus",),
    "scrap":        ("fulgora",),
    "holmium-ore":  ("fulgora",),   # also reachable via scrap-recycling byproduct
    "uranium-ore":  ("nauvis",),
    # V3 partial Gleba support: yumako / jellynut / pentapod-egg are harvested
    # from agricultural towers (0 module slots — no agricultural quality path).
    # The only legendary route is self-recycle: yumako-recycling gives 0.25 of
    # the input back at a quality roll, identical to the coal/stone loop.
    # NOTE: spoilage timing is NOT modelled here; long quality loops on
    # spoiling intermediates (bioflux, nutrients) give optimistic counts.
    "yumako":       ("gleba",),
    "jellynut":     ("gleba",),
    "pentapod-egg": ("gleba",),
}

# Planet key each item/raw is tied to.  An item is usable whenever the user
# has unlocked AT LEAST ONE of the listed planets via ``--planets``.  Without
# the planet, the check fails fast with a hint about which flag would fix it.
#
# The dict has two layers:
#   * Physical raws (pumped/mined on a given planet): crude-oil, lava, scrap,
#     tungsten-ore, holmium-ore, etc.
#   * Intermediate items whose ONLY production chain requires a planet-local
#     raw: plastic-bar (petroleum-gas from crude-oil), sulfur (petroleum-gas),
#     etc.  V2 relaxes these automatically when the corresponding planet is
#     unlocked — e.g. ``--planets nauvis`` unlocks the oil chain so plastic-bar
#     resolves through its normal Nauvis recipe.
#
# An item can be produced on multiple planets.  We list the set of planets
# that satisfy the requirement.  Order matters only for error messages.
PLANET_UNLOCKS: dict[str, tuple[str, ...]] = {
    # Vulcanus raws
    "tungsten-ore":         ("vulcanus",),
    "tungsten-carbide":     ("vulcanus",),
    "lava":                 ("vulcanus",),
    "sulfuric-acid":        ("nauvis", "vulcanus"),  # Nauvis chem-plant OR Vulcanus geyser
    # Fulgora raws
    "holmium-ore":          ("fulgora",),
    "holmium-solution":     ("fulgora",),
    "scrap":                ("fulgora",),
    # Aquilo raws
    "fluorine":             ("aquilo",),
    "lithium-brine":        ("aquilo",),
    "ammoniacal-solution":  ("aquilo",),
    "ammonia":              ("aquilo",),
    "lithium":              ("aquilo",),
    # Gleba raws
    "yumako":               ("gleba",),
    "yumako-mash":          ("gleba",),
    "jellynut":             ("gleba",),
    "jelly":                ("gleba",),
    "bioflux":              ("gleba",),
    "pentapod-egg":         ("gleba",),
    "spoilage":             ("gleba",),
    # Nauvis raws + oil-chain fluids
    "raw-fish":             ("nauvis",),
    "crude-oil":            ("nauvis", "fulgora", "aquilo"),
    "uranium-ore":          ("nauvis",),
    # Oil-derived fluids: reachable anywhere crude-oil/heavy-oil is available.
    "petroleum-gas":        ("nauvis", "fulgora", "aquilo"),
    "light-oil":            ("nauvis", "fulgora", "aquilo"),
    "heavy-oil":            ("nauvis", "fulgora", "aquilo"),
    "steam":                ("nauvis", "vulcanus"),
    # Nauvis-chain intermediates — unlocked alongside crude-oil.
    "plastic-bar":          ("nauvis", "fulgora", "gleba"),
    "sulfur":               ("nauvis", "fulgora", "gleba", "vulcanus"),
    "lubricant":            ("nauvis", "fulgora", "gleba"),
    "rocket-fuel":          ("nauvis", "fulgora", "gleba", "aquilo"),
    "solid-fuel":           ("nauvis", "fulgora"),
    "explosives":           ("nauvis", "fulgora", "gleba", "vulcanus"),
}

# Legacy name kept for in-tree callers and tests; points at the first planet
# listed in PLANET_UNLOCKS (the "canonical" home for error messages).
PLANET_EXCLUSIVE_RAWS: dict[str, str] = {k: v[0] for k, v in PLANET_UNLOCKS.items()}

# All known Space Age planets (for argparse choices / validation).
KNOWN_PLANETS: tuple[str, ...] = ("nauvis", "vulcanus", "fulgora", "gleba", "aquilo", "space-platform")

# Self-recycling blocklist (fail fast for V1).
# As of V3, these CAN be used as TARGETS (legendary self-recycle loop), but
# still fail fast when encountered as INTERMEDIATE ingredients in a chain
# (e.g. superconductor as input — must be supplied externally).
SELF_RECYCLING_BLOCKLIST = frozenset([
    "tungsten-carbide",
    "superconductor",
    "holmium-plate",
])

# V3: items that target-self-recycle.  Same as the blocklist, plus a few that
# don't have direct asteroid/mined paths: fusion-power-cell, lithium.
SELF_RECYCLE_TARGETS = frozenset([
    "tungsten-carbide",
    "superconductor",
    "holmium-plate",
    "fusion-power-cell",
    "lithium",
])

# Inherent productivity bonus per machine type (Space Age).  Cryogenic plant
# has no inherent prod (just 8 slots).  Chem plant / assembler likewise zero.
MACHINE_INHERENT_PROD: dict[str, float] = {
    "foundry": 0.5,
    "electromagnetic-plant": 0.5,
    "biochamber": 0.5,
    "cryogenic-plant": 0.0,
    "chemical-plant": 0.0,
    "assembling-machine-1": 0.0,
    "assembling-machine-2": 0.0,
    "assembling-machine-3": 0.0,
    "oil-refinery": 0.0,
    "centrifuge": 0.0,
    "rocket-silo": 0.0,
    "crusher": 0.0,
}

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


def solve_lds_shuffle_loop(
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
    prod_module_tier: int = 3,
    research_prod: float = 0.0,
    foundry_inherent_prod: float = 0.5,
) -> tuple[float, dict]:
    """DP for legendary-plastic-bar per normal-plastic-bar via the LDS shuffle.

    The LDS shuffle is an indirect quality loop that produces legendary
    plastic-bar (and byproduct legendary copper-plate + steel-plate) at a
    far better yield than direct plastic-bar self-recycling, because the
    foundry's LDS casting recipe:
      * accepts ONLY plastic-bar as a solid input (5 per craft — molten-iron
        and molten-copper are fluids and therefore quality-transparent);
      * has 4 module slots with prod modules allowed and the metallurgy
        inherent +50% productivity (plus the `low-density-structure-productivity`
        research tech, stacking up to the +300% machine cap);
      * its recycling recipe returns 1.25 plastic-bar + 5 copper-plate +
        0.5 steel-plate per LDS.

    Per-cycle rate for plastic-bar (ignoring quality rolls):
        1 plastic-bar invested
          → 1/5 crafts
          → (1+prod)/5 LDS
          → (1+prod)/5 * 1.25 plastic-bar returned
          = (1+prod) * 0.25 plastic-bar per input

    With the inherent +50% foundry prod + prod modules + research capped at
    +300%, the return ratio can approach 1.0, making the loop self-sustaining
    and yielding legendary plastic-bar at high rates.

    Returns (V[0], configs_per_tier).  ``V[0]`` is legendary plastic-bar per
    normal plastic-bar invested.  Caller is responsible for also tracking the
    molten-iron/molten-copper fluid demand and the copper/steel byproducts.
    """
    cast_recipe = _recipe_by_key(data, "casting-low-density-structure")
    rec_recipe = _recipe_by_key(data, "low-density-structure-recycling")
    if cast_recipe is None or rec_recipe is None:
        return 0.0, {}

    # Plastic-bar in per craft, LDS out per craft, plastic-bar returned per LDS
    plastic_in_per_cast = _recipe_ing_amount(cast_recipe, "plastic-bar")  # 5
    lds_out_per_cast = _recipe_result_amount(cast_recipe, "low-density-structure")  # 1
    plastic_back_per_lds = _recipe_result_amount(rec_recipe, "plastic-bar")  # 1.25

    if plastic_in_per_cast <= 0:
        return 0.0, {}

    FOUNDRY_SLOTS = 4  # foundry module slots (quality-independent)

    V = [0.0] * 5
    V[4] = 1.0
    configs: dict[int, dict] = {}

    for t in range(3, -1, -1):
        best_v = -1.0
        best_cfg = None
        # Foundry cast: p prod + q quality (p+q ≤ 4). Prod allowed by metallurgy.
        for cp in range(FOUNDRY_SLOTS + 1):
            for cq in range(FOUNDRY_SLOTS - cp + 1):
                # Recycler: rq quality (0..4), quality-only
                for rq in range(RECYCLER_SLOTS + 1):
                    prod = foundry_inherent_prod + research_prod + _prod_bonus(
                        cp, prod_module_tier, module_quality,
                    )
                    if prod > 3.0:
                        prod = 3.0
                    items_per_craft = lds_out_per_cast * (1.0 + prod)
                    # plastic-bar return per plastic-bar invested, per loop
                    per_input_yield = (
                        items_per_craft / plastic_in_per_cast
                    ) * plastic_back_per_lds

                    q_cast = _quality_chance(cq, quality_module_tier, module_quality)
                    q_rec = _quality_chance(rq, quality_module_tier, module_quality)

                    # Quality compose: starting at tier t, cast-roll places LDS
                    # at tier u ≥ t; recycle-roll from u places plastic at s ≥ u.
                    cast_probs = _tier_skip_probs(q_cast, t)
                    probs = [0.0] * (5 - t)
                    for u_off, cp_prob in enumerate(cast_probs):
                        u = t + u_off
                        rec_probs = _tier_skip_probs(q_rec, u)
                        for s_off, rp in enumerate(rec_probs):
                            s = u + s_off
                            probs[s - t] += cp_prob * rp * per_input_yield

                    stay = probs[0]
                    if stay >= 1.0 - 1e-15:
                        v = 0.0
                    else:
                        numer = sum(probs[k] * V[t + k] for k in range(1, len(probs)))
                        v = numer / (1.0 - stay)
                    if v > best_v:
                        best_v = v
                        best_cfg = {
                            "cast_prod": cp,
                            "cast_quality": cq,
                            "recycle_quality": rq,
                        }
        V[t] = max(best_v, 0.0)
        configs[t] = best_cfg or {"cast_prod": 0, "cast_quality": 0, "recycle_quality": 0}

    return V[0], configs


def compute_lds_shuffle_stage(
    legendary_plastic_per_min: float,
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
    prod_module_tier: int = 3,
    research_prod: float = 0.0,
    foundry_inherent_prod: float = 0.5,
    foundry_speed: float = 4.0,
    recycler_speed: float = RECYCLER_SPEED,
) -> dict | None:
    """Size an LDS-shuffle stage that produces ``legendary_plastic_per_min``.

    Returns a dict describing throughputs, machine counts, and byproduct
    legendary rates (copper-plate, steel-plate) — or ``None`` if the dataset
    is missing the required recipes.

    Math (per normal plastic-bar input across the full quality loop):
      * V = solve_lds_shuffle_loop(...) gives legendary plastic-bar yield.
      * Total foundry crafts ≈ plastic-bar-input / 5 / (1 - retention) where
        retention = (1+prod)/5 * 1.25 ≈ self-feed ratio.  We approximate
        across tiers by using the per-tier configs from the solver.
      * Each casting consumes molten-iron + molten-copper (fluid, transparent)
        and yields 1 LDS, then recycler returns 1.25 plastic-bar + 5 copper +
        0.5 steel.

    Byproduct credits are computed as:
      copper_legendary  = legendary_plastic_per_min * 5.0  / 1.25
      steel_legendary   = legendary_plastic_per_min * 0.5  / 1.25
    (each legendary plastic-bar exits via the same recycler stream as the
    byproducts — the ratio is fixed by the recipe, independent of modules.)
    """
    if legendary_plastic_per_min <= 0:
        return None
    cast_recipe = _recipe_by_key(data, "casting-low-density-structure")
    rec_recipe = _recipe_by_key(data, "low-density-structure-recycling")
    if cast_recipe is None or rec_recipe is None:
        return None

    plastic_in_per_cast = _recipe_ing_amount(cast_recipe, "plastic-bar")  # 5
    lds_out_per_cast = _recipe_result_amount(cast_recipe, "low-density-structure")  # 1
    plastic_back_per_lds = _recipe_result_amount(rec_recipe, "plastic-bar")  # 1.25
    copper_back_per_lds = _recipe_result_amount(rec_recipe, "copper-plate")  # 5
    steel_back_per_lds = _recipe_result_amount(rec_recipe, "steel-plate")  # 0.5
    if plastic_in_per_cast <= 0 or plastic_back_per_lds <= 0:
        return None

    v, configs = solve_lds_shuffle_loop(
        data,
        module_quality,
        quality_module_tier,
        prod_module_tier,
        research_prod,
        foundry_inherent_prod,
    )
    if v <= 0:
        return None

    # Normal plastic-bar invested per minute to produce target legendary.
    normal_plastic_in_per_min = legendary_plastic_per_min / v

    # Approximate machine counts: take the tier-0 (normal) module config as
    # the dominant configuration (most throughput happens at low tiers since
    # the upgrade ladder narrows toward legendary).  Foundry prod from cp0
    # determines per-craft throughput; recycler is purely quality-rolling.
    cfg0 = configs.get(0, {"cast_prod": 0, "cast_quality": 0, "recycle_quality": 4})
    cp0 = cfg0.get("cast_prod", 0)
    prod = foundry_inherent_prod + research_prod + _prod_bonus(
        cp0, prod_module_tier, module_quality,
    )
    if prod > 3.0:
        prod = 3.0
    items_per_craft = lds_out_per_cast * (1.0 + prod)
    plastic_back_per_craft = items_per_craft * plastic_back_per_lds  # plastic in 5 -> back

    # Cycle-count multiplier across all tiers: each plastic-bar normal-input
    # cycles repeatedly until it lands at legendary or escapes via tier-skip.
    # Effective recirculation ratio per craft is plastic_back_per_craft/plastic_in_per_cast;
    # total castings ≈ normal_plastic_in_per_min / plastic_in_per_cast / (1 - r).
    r_per_cycle = plastic_back_per_craft / plastic_in_per_cast
    if r_per_cycle >= 1.0 - 1e-9:
        # Self-sustaining loop — per-cycle throughput is unbounded; clamp.
        # In practice the quality roll always upgrades some fraction out.
        r_per_cycle = 0.999
    total_castings_per_min = (
        normal_plastic_in_per_min / plastic_in_per_cast / (1.0 - r_per_cycle)
    )
    cast_time = float(cast_recipe.get("energy_required", 15.0))
    foundry_machines = total_castings_per_min * cast_time / (foundry_speed * 60.0)

    # Recycler throughput equals casting LDS output rate.
    total_recycles_per_min = total_castings_per_min * items_per_craft
    rec_time = float(rec_recipe.get("energy_required", 0.9375))
    recycler_machines = total_recycles_per_min * rec_time / (recycler_speed * 60.0)

    # Byproduct legendary rates: ratio fixed by recipe (modules don't change
    # the recipe outputs, only quality distribution).  Each legendary plastic-bar
    # exits the recycler alongside copper-plate (5/1.25) and steel-plate (0.5/1.25).
    copper_legendary_per_min = legendary_plastic_per_min * (
        copper_back_per_lds / plastic_back_per_lds
    )
    steel_legendary_per_min = legendary_plastic_per_min * (
        steel_back_per_lds / plastic_back_per_lds
    )

    # Fluid demand (quality-transparent, but caller may want to display it).
    molten_iron_per_cast = _recipe_ing_amount(cast_recipe, "molten-iron")
    molten_copper_per_cast = _recipe_ing_amount(cast_recipe, "molten-copper")
    fluid_demand = {
        "molten-iron": molten_iron_per_cast * total_castings_per_min,
        "molten-copper": molten_copper_per_cast * total_castings_per_min,
    }

    return {
        "yield_per_normal_plastic": v,
        "legendary_plastic_per_min": legendary_plastic_per_min,
        "normal_plastic_in_per_min": normal_plastic_in_per_min,
        "total_castings_per_min": total_castings_per_min,
        "total_recycles_per_min": total_recycles_per_min,
        "foundry_machines": foundry_machines,
        "recycler_machines": recycler_machines,
        "byproduct_legendary": {
            "copper-plate": copper_legendary_per_min,
            "steel-plate": steel_legendary_per_min,
        },
        "fluid_demand": fluid_demand,
        "configs_per_tier": configs,
    }


def solve_mined_raw_self_recycle_loop(
    raw_key: str,
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
) -> tuple[float, dict]:
    """DP for legendary-raw per normal-raw via the recycler self-loop.

    For a mined solid that lacks an asteroid path (coal, stone, tungsten-ore,
    scrap, holmium-ore, uranium-ore) the canonical V2 legendary source is:
      * Mine raw at normal quality (on the appropriate planet).
      * Feed the raw into the recycler with its ``<raw>-recycling`` recipe.
        Recycler has 4 quality slots, 25% retention, no prod modules allowed.
      * Loop until legendary.

    Identical structure to :func:`solve_asteroid_reprocessing_loop` but with
    ``retention = 0.25`` (recycler standard) and ``slots = 4``.

    Scrap is special: its recipe outputs a basket of other items (not scrap
    itself), so the "loop" is actually a one-shot roll.  We still model it
    with this DP using the full output bundle's probability mass; the caller
    is responsible for tracking the byproduct items separately.

    Returns (V[0], configs_per_tier).
    """
    rec_key = f"{raw_key}-recycling"
    rec = _recipe_by_key(data, rec_key)
    if rec is None:
        return 0.0, {}

    # Retention = probability the recycler returns the raw itself (single-chunk
    # loop).  For scrap this is 0 (no scrap in outputs) — in that case the
    # recycler outputs are terminal (one-shot) and we model with retention=0.
    retention = _recipe_result_amount(rec, raw_key)

    V = [0.0] * 5
    V[4] = 1.0
    configs: dict[int, dict] = {}

    for t in range(3, -1, -1):
        best_v = -1.0
        best_cfg = None
        for q in range(RECYCLER_SLOTS + 1):
            q_total = _quality_chance(q, quality_module_tier, module_quality)
            probs = _tier_skip_probs(q_total, t)
            probs = [p * retention for p in probs] if retention > 0 else probs
            if retention > 0:
                stay = probs[0]
            else:
                # One-shot (scrap-like): no self-loop; V[t] = sum(probs[k]*V[...])
                stay = 0.0
            if stay >= 1.0 - 1e-15:
                v = 0.0
            else:
                numer = sum(probs[k] * V[t + k] for k in range(1, len(probs)))
                if retention > 0:
                    v = numer / (1.0 - stay)
                else:
                    v = numer  # one-shot
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


def _stage_power_kw(stage: dict, power_w: dict[str, int]) -> float:
    """Compute electrical power draw (kW) for a stage, dispatching on role.

    Compound stages (cross-item-shuffle has foundry + recycler; self-recycle-
    target has craft + recycler) use the machine-specific counts.  Asteroid /
    crushing stages always run on crushers; mined-raw-self-recycle on recyclers.

    Returns 0.0 when the stage's machine is burner-fuelled (e.g. biochamber)
    or otherwise has no electric power entry.
    """
    role = stage.get("role")

    def _w(machine: str) -> int:
        return int(power_w.get(machine) or 0)

    if role == "cross-item-shuffle":
        return (
            _w("foundry") * float(stage.get("foundry_machines", 0))
            + _w("recycler") * float(stage.get("recycler_machines", 0))
        ) / 1000.0
    if role == "self-recycle-target":
        return (
            _w(stage.get("machine", "")) * float(stage.get("craft_machines", 0))
            + _w("recycler") * float(stage.get("recycler_machines", 0))
        ) / 1000.0
    if role in ("asteroid-reprocessing", "raw-crushing"):
        return _w("crusher") * float(stage.get("machine_count", 0)) / 1000.0
    if role == "mined-raw-self-recycle":
        return _w("recycler") * float(stage.get("machine_count", 0)) / 1000.0
    # default: assembly-style stage
    return _w(stage.get("machine", "")) * float(stage.get("machine_count", 0)) / 1000.0


def _assembly_prod_bonus(
    machine_key: str,
    recipe: dict,
    slots_map: dict[str, int],
    assembly_modules: bool,
    module_quality: str,
    prod_module_tier: int,
) -> tuple[float, int]:
    """Prod bonus from inherent machine prod + N prod modules filling all slots.

    Returns ``(prod_fraction, slots_filled)``.  Slots_filled is the number of
    module slots actually filled with prod modules — 0 if the recipe disallows
    productivity OR ``assembly_modules`` is False.

    Quality of the modules is ``module_quality`` (matches the planner's quality
    config so the user gets internally-consistent module choices).  Tier is
    ``prod_module_tier`` (default 3).
    """
    if not assembly_modules:
        return 0.0, 0
    if not recipe.get("allow_productivity", True):
        return 0.0, 0
    inherent = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
    slots = int(slots_map.get(machine_key, 0))
    if slots <= 0:
        return inherent, 0
    module_bonus = _prod_bonus(slots, prod_module_tier, module_quality)
    return inherent + module_bonus, slots


def _planet_unlocks_item(item_key: str, planets: frozenset[str]) -> bool:
    """True if `item_key` is not planet-gated, OR if at least one of its
    unlocking planets is in the ``planets`` set."""
    allowed = PLANET_UNLOCKS.get(item_key)
    if allowed is None:
        return True  # not planet-gated
    return any(p in planets for p in allowed)


def _combined_planet_props(data: dict, planets: frozenset[str]) -> dict:
    """Return surface-property dict that satisfies every unlocked planet's
    conditions (union).  When multiple planets unlock different recipe sets
    (foundry on Vulcanus requires pressure=4000, recycler on Fulgora requires
    magnetic-field=99), we need a "virtual" surface that admits all of them.
    """
    if not planets:
        # Default: Nauvis only (V1 behaviour).
        return cli.get_planet_props(data, "nauvis")
    props_list = [cli.get_planet_props(data, p) for p in planets]
    merged: dict = {}
    for props in props_list:
        for k, v in props.items():
            merged.setdefault(k, []).append(v)
    # Pick a value per property that satisfies the most permissive range:
    # recipe conditions are `min <= prop <= max`, so pick the value that any
    # unlocked planet would pass.  We use the MAX observed value since most
    # conditions are `min=X, max=X` equality and MAX covers the most recipes.
    # The `_recipe_valid_for_planet` check runs per-recipe downstream so any
    # mismatch still fails there — but we widen here for the union case.
    return {k: max(vals) for k, vals in merged.items()}


def _pick_recipe_fluid_preferred(
    item_key: str,
    recipe_idx: dict,
    fluids: frozenset[str],
    planets: frozenset[str],
    planet_props: dict | None = None,
) -> dict | None:
    """Like cli.pick_recipe, but prefer recipes whose FLUID ingredients do not
    introduce planet-exclusive raws.

    Picks `casting-iron` (molten-iron input, molten-iron derivable from iron-ore)
    over `iron-plate` (iron-ore input directly).  Rejects `molten-iron-from-lava`
    when Vulcanus isn't in ``planets``.

    When multiple recipes remain viable after planet filtering, tie-break by
    fluid fraction (prefer fluid-heavy inputs for quality transparency), then
    by canonical ``cli.pick_recipe`` order.
    """
    candidates = recipe_idx.get(item_key, [])
    if not candidates:
        return cli.pick_recipe(item_key, recipe_idx)

    def ingredient_blocked_by_planets(r: dict) -> bool:
        for ing in r.get("ingredients", []):
            name = ing["name"]
            if name in RAW_TO_CHUNK:
                continue  # asteroid-sourced, always allowed
            if not _planet_unlocks_item(name, planets):
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

    # Filter out candidates with planet-exclusive raws the user hasn't unlocked.
    viable = [r for r in candidates if not ingredient_blocked_by_planets(r)]
    # Filter by planet surface_conditions if given (e.g. foundry recipes need
    # Vulcanus pressure=4000, EM-plant recipes need Fulgora magnetic=99).
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
    planets: frozenset[str] | None = None,
    extra_raws: frozenset[str] | None = None,
    byproduct_credits: dict[str, float] | None = None,
    assembly_modules: bool = False,
    assembly_module_quality: str = "legendary",
    prod_module_tier: int = 3,
) -> tuple[list[dict], dict[str, float]]:
    """Walk recipe tree; return (stages, raw_demand_rates).

    Stages are ordered deepest-first-ish for display.  Each stage has:
      {role, recipe, machine, rate_per_min, machine_count, ingredients, fluid_inputs}

    raw_demand_rates maps raw_item_key -> demand per minute (solid raws only;
    fluid raws are tracked but don't flow through quality loops).
    """
    recipe_idx = cli.build_recipe_index(data)
    planets = planets or frozenset()
    # Start with the V1 asteroid-baseline raw set (Nauvis solid raws + asteroid
    # chunks).  Then extend it with only the FLUID raws from each unlocked
    # planet — fluid inputs are quality-transparent and can be sourced from
    # the planet's pumps/geysers without affecting the legendary chain.
    #
    # Solid planet raws (tungsten-ore, scrap, bioflux, yumako, …) are deliberately
    # NOT added here: legendary solids must come from a dedicated quality source
    # (asteroid chain, scrap recycler, tungsten-carbide self-recycle, …) so we
    # keep them out of the raw_set and let downstream checks route them.
    # Start with the items that the asteroid chain *actually* produces
    # (RAW_TO_CHUNK) + asteroid chunks + Nauvis-offshore water.  We do NOT
    # auto-include every Nauvis resource: items like coal/stone are solids
    # that need a dedicated quality source (self-recycle) to become legendary.
    base_raw_set: set[str] = set(RAW_TO_CHUNK.keys())
    base_raw_set |= {"metallic-asteroid-chunk", "carbonic-asteroid-chunk", "oxide-asteroid-chunk"}
    base_raw_set.add("water")
    # Extend with planet-local raws the user has unlocked.  Fluids always count
    # (quality-transparent).  Solids only count if they have a self-recycle
    # quality path (MINED_RAW_PLANETS) — otherwise legendary isn't producible.
    if planets:
        for p in planets:
            planet_raws = cli.build_raw_set(data, p)
            for r in planet_raws:
                if r in fluids:
                    base_raw_set.add(r)
                elif r in MINED_RAW_PLANETS and p in MINED_RAW_PLANETS[r]:
                    base_raw_set.add(r)
        # Also honour MINED_RAW_PLANETS entries that aren't in cli.build_raw_set
        # (e.g. holmium-ore isn't a direct Fulgora resource — it drops out of
        # scrap-recycling — but the self-recycle loop still works once you have
        # any holmium-ore).
        for raw, raw_planets in MINED_RAW_PLANETS.items():
            if any(p in planets for p in raw_planets):
                base_raw_set.add(raw)
    if extra_raws:
        base_raw_set |= set(extra_raws)
    raw_set = frozenset(base_raw_set)
    slots_map = cli.build_machine_module_slots(data) if assembly_modules else {}

    # Accumulate demand per (item) — then we'll resolve recipes / stages per item.
    demand: dict[str, float] = defaultdict(float)
    demand[item_key] = rate
    if byproduct_credits:
        for k, v in byproduct_credits.items():
            demand[k] -= float(v)
    order: list[str] = [item_key]
    seen: set[str] = set()

    # BFS-like accumulation
    pending = [item_key]
    # Build demand by recursive expansion; stop at raws.
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        if current in raw_set and current != item_key:
            continue
        if current in PLANET_UNLOCKS and current != item_key:
            if not _planet_unlocks_item(current, planets):
                needed = PLANET_UNLOCKS[current]
                hint = f"add --planets {','.join(needed)}"
                raise ValueError(
                    f"ERROR: item '{item_key}' requires '{current}', which needs one of planet(s) "
                    f"{list(needed)} — {hint}"
                )
        if current in SELF_RECYCLING_BLOCKLIST and current != item_key:
            raise ValueError(
                f"ERROR: recipe '{current}' is self-recycling (output recycles to itself) — not supported"
            )
        recipe = _pick_recipe_fluid_preferred(current, recipe_idx, fluids, planets, planet_props)
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
        # Module prod (matches what we'll apply in the second pass — must be
        # consistent so demand propagation upstream lines up).
        if assembly_modules:
            machine_key_p1, _ = cli.get_machine(
                recipe["category"], assembler_level, "electric",
            )
            module_prod_p1, _ = _assembly_prod_bonus(
                machine_key_p1, recipe, slots_map,
                assembly_modules, assembly_module_quality, prod_module_tier,
            )
        else:
            module_prod_p1 = 0.0
        eff_prod = 1.0 + research_prod + module_prod_p1
        if eff_prod > 4.0:
            eff_prod = 4.0
        net_demand = max(0.0, demand[current])
        cycles_per_min = net_demand / (per_craft_output * eff_prod)
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
            if amt > 0:
                raw_demand[iname] += amt
    for item in order:
        if item in raw_set and item != item_key:
            continue
        recipe = _pick_recipe_fluid_preferred(item, recipe_idx, fluids, planets, planet_props)
        if recipe is None:
            raw_demand[item] += demand[item]
            continue
        machine_key, machine_speed = cli.get_machine(recipe["category"], assembler_level, "electric")
        machine_speed_f = float(machine_speed)
        research_prod = _research_prod_for_recipe(recipe["key"], research_levels)
        module_prod, prod_slots_filled = _assembly_prod_bonus(
            machine_key, recipe, slots_map,
            assembly_modules, assembly_module_quality, prod_module_tier,
        )
        eff_prod = 1.0 + research_prod + module_prod
        capped = False
        if eff_prod > 4.0:
            eff_prod = 4.0
            capped = True
        per_craft_output = _recipe_result_amount(recipe, item)
        if per_craft_output <= 0:
            continue
        net_demand_item = max(0.0, demand[item])
        if net_demand_item <= 0.0:
            continue  # fully covered by byproduct credit
        crafts_per_min = net_demand_item / (per_craft_output * eff_prod)
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
            "rate_per_min": net_demand_item,
            "crafts_per_min": crafts_per_min,
            "machine_count": machine_count,
            "inputs": inputs,
            "fluid_inputs": fluid_inputs,
            "solid_inputs": solid_inputs,
            "research_prod": research_prod,
            "module_prod": module_prod,
            "prod_modules": prod_slots_filled,
            "prod_module_tier": prod_module_tier if prod_slots_filled > 0 else 0,
            "prod_module_quality": assembly_module_quality if prod_slots_filled > 0 else "normal",
            "prod_capped": capped,
            "inputs_all_legendary": all(k not in fluids for k in inputs) if solid_inputs else True,
        })

    # Filter raws to solid raws only (fluids like water get treated in crushing)
    # Keep only items the asteroid chain produces OR raws unlocked via --planets.
    asteroid_raws = set(RAW_TO_CHUNK.keys()) | set(ASTEROID_REPROCESSING_RECIPES.keys())
    # Fluid raws that ARE reachable via the asteroid+Nauvis chain (water from ice).
    allowed_fluid_raws = {"water"}
    for raw in list(raw_demand.keys()):
        if extra_raws and raw in extra_raws:
            continue  # supplied externally (e.g. by LDS shuffle)
        if raw in fluids:
            if raw in allowed_fluid_raws:
                continue
            # Accepted if it's a pumpable raw on an unlocked planet.
            if raw in raw_set:
                continue
            if _planet_unlocks_item(raw, planets):
                # Recipe for the fluid was attempted but not expanded (e.g.
                # unknown chain) — accept and let downstream errors surface.
                continue
            needed = PLANET_UNLOCKS.get(raw, ("nauvis",))
            raise ValueError(
                f"ERROR: item '{item_key}' requires '{raw}', which needs one of planet(s) "
                f"{list(needed)} — add --planets {','.join(needed)}"
            )
        if raw in asteroid_raws:
            continue
        if raw in raw_set:
            continue  # unlocked planet raw
        if _planet_unlocks_item(raw, planets):
            continue
        needed = PLANET_UNLOCKS.get(raw)
        if needed:
            raise ValueError(
                f"ERROR: item '{item_key}' requires '{raw}', which needs one of planet(s) "
                f"{list(needed)} — add --planets {','.join(needed)}"
            )
        raise ValueError(f"ERROR: no asteroid path to required raw '{raw}'")

    return stages, dict(raw_demand)


# ---------------------------------------------------------------------------
# Self-recycle target planner (V3 item 3)
# ---------------------------------------------------------------------------

def solve_self_recycle_target_loop(
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
    """DP for legendary yield per ONE craft of a self-recycling target item.

    Differs from :func:`solve_recycle_loop` (which models shuffle-style loops
    where the recycler returns the *ingredients* back to a re-craft).  Here
    the recycler returns the SAME ITEM, so the recycler chain is closed:
    items are re-recycled until they tier up to legendary or vanish.

    Model:
      * One craft produces ``items_per_craft = output_amt * (1 + prod)`` items
        with quality distribution determined by craft-side quality modules
        (``q_craft``).
      * Each item enters a recycler-only chain.  At each pass: with prob
        ``(1 - q_rec) * retention`` the item stays at the same tier; with prob
        ``q_rec * retention * tier_skip_dist`` it tiers up; with prob
        ``1 - retention`` it is destroyed.
      * V_rec[t] = expected legendary items per single item at tier t entering
        the recycler chain.
      * V_total = items_per_craft × Σ_{s} craft_probs[s] × V_rec[s].

    Returns ``(V_total, configs_per_tier)`` — legendary items per fresh craft.
    Configs map ``{0,1,2,3} → {craft_prod, craft_quality, recycle_quality}``
    where the keys 0-3 store the per-tier optimal recycler config (craft side
    is global, optimised once for tier 0 since all crafts start at normal).
    """
    craft_recipe = cli.pick_recipe(item_key, cli.build_recipe_index(data))
    if craft_recipe is None:
        return 0.0, {}
    rec_recipe = _recipe_by_key(data, f"{item_key}-recycling")
    retention = (
        _recipe_result_amount(rec_recipe, item_key) if rec_recipe else RECYCLER_RETENTION
    )
    if retention <= 0 or retention >= 1.0:
        return 0.0, {}

    craft_output = _recipe_result_amount(craft_recipe, item_key)
    if craft_output <= 0:
        return 0.0, {}
    recipe_allow_prod = (
        craft_recipe.get("allow_productivity", True) and machine_allow_prod
    )

    # --- Inner DP: V_rec[t] for a single item at tier t entering recycler ---
    def v_rec_for_q(rq: int) -> list[float]:
        q_rec = _quality_chance(rq, quality_module_tier, module_quality)
        V = [0.0] * 5
        V[4] = 1.0
        for t in range(3, -1, -1):
            rec_probs = _tier_skip_probs(q_rec, t)  # len 5-t
            # Probability item stays at tier t after one recycle pass:
            stay = retention * rec_probs[0]
            # Probability item escapes UP to tier t+k for k>=1:
            up = [retention * rec_probs[k] for k in range(1, len(rec_probs))]
            # Remainder (1 - retention) is item lost.
            if stay >= 1.0 - 1e-15:
                V[t] = 0.0
            else:
                numer = sum(up[k - 1] * V[t + k] for k in range(1, len(rec_probs)))
                V[t] = numer / (1.0 - stay)
        return V

    # --- Outer search: pick (craft_prod, craft_quality, recycle_quality) ---
    best_total = -1.0
    best_cfg: dict | None = None
    best_v_rec: list[float] = [0.0] * 5

    for cp in range(machine_slots + 1):
        for cq in range(machine_slots - cp + 1):
            if cp > 0 and not recipe_allow_prod:
                continue
            prod = inherent_prod + research_prod + _prod_bonus(
                cp, prod_module_tier, module_quality,
            )
            if prod > 3.0:
                prod = 3.0
            items_per_craft = craft_output * (1.0 + prod)
            q_craft = _quality_chance(cq, quality_module_tier, module_quality)
            craft_probs = _tier_skip_probs(q_craft, 0)  # len 5

            for rq in range(RECYCLER_SLOTS + 1):
                v_rec = v_rec_for_q(rq)
                total = items_per_craft * sum(
                    craft_probs[s] * v_rec[s] for s in range(5)
                )
                if total > best_total:
                    best_total = total
                    best_cfg = {
                        "craft_prod": cp,
                        "craft_quality": cq,
                        "recycle_quality": rq,
                    }
                    best_v_rec = v_rec

    if best_cfg is None:
        return 0.0, {}
    # Per-tier configs: in this loop the recycle_quality is global (single
    # config wins).  We expose it in all 4 tiers for symmetry with other loops.
    configs = {t: dict(best_cfg) for t in (0, 1, 2, 3)}
    # Annotate per-tier V_rec for downstream display.
    for t in (0, 1, 2, 3):
        configs[t]["v_rec"] = best_v_rec[t]
    return max(best_total, 0.0), configs



def _plan_self_recycle_target(
    item_key: str,
    rate: float,
    data: dict,
    *,
    module_quality: str,
    research_levels: dict[str, int],
    assembler_level: int,
    quality_module_tier: int,
    planets: frozenset[str],
    assembly_modules: bool = False,
    prod_module_tier: int = 3,
) -> dict:
    """Plan a chain whose target self-recycles (e.g. superconductor).

    Strategy:
      * Pick the target's craft recipe + machine.
      * Run :func:`solve_recycle_loop` to get legendary-per-craft yield V[0].
      * crafts/min = rate / V[0].
      * Walk the recipe's ingredients at NORMAL quality — quality rolls happen
        inside the craft+recycle loop, so ingredients don't need legendary
        upstream supply.  Solid raws go into ``normal_solid_input``, fluids into
        ``normal_fluid_input``.
      * Emit a ``self-recycle-target`` aggregate stage with craft + recycler
        machine counts.
    """
    recipe_idx = cli.build_recipe_index(data)
    fluids = build_fluid_set(data)
    planet_props = _combined_planet_props(data, planets)

    craft_recipe = _pick_recipe_fluid_preferred(
        item_key, recipe_idx, fluids, planets, planet_props,
    )
    if craft_recipe is None:
        raise ValueError(f"ERROR: no craft recipe for '{item_key}'")
    machine_key, machine_speed = cli.get_machine(
        craft_recipe["category"], assembler_level, "electric",
    )
    machine_speed_f = float(machine_speed)
    module_slots_map = cli.build_machine_module_slots(data)
    machine_slots = int(module_slots_map.get(machine_key, 0))
    machine_allow_prod = True  # all crafting machines that allow modules accept prod
    inherent_prod = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
    research_prod = _research_prod_for_recipe(craft_recipe["key"], research_levels)

    v, configs = solve_self_recycle_target_loop(
        item_key, data,
        machine_key=machine_key,
        machine_slots=machine_slots,
        machine_allow_prod=machine_allow_prod,
        inherent_prod=inherent_prod,
        research_prod=research_prod,
        module_quality=module_quality,
        prod_module_tier=3,
        quality_module_tier=quality_module_tier,
    )
    if v <= 0:
        raise ValueError(
            f"ERROR: self-recycle loop for '{item_key}' yields 0 legendary — "
            f"check module/quality config (machine={machine_key}, slots={machine_slots})"
        )

    crafts_per_min = rate / v
    craft_time = float(craft_recipe.get("energy_required", 1.0))
    craft_machines = crafts_per_min * craft_time / (machine_speed_f * 60.0)

    # Recycler: each tier-cycle produces (1+prod)*items_per_craft items at quality
    # distribution; recycler processes these → 0.25 retention back.  Total
    # recycler crafts/min ≈ crafts_per_min * (1+prod) * items_per_craft / (1 - 0.25).
    cfg0 = configs.get(0, {"craft_prod": 0, "craft_quality": 0, "recycle_quality": 0})
    prod0 = inherent_prod + research_prod + _prod_bonus(
        cfg0.get("craft_prod", 0), 3, module_quality,
    )
    if prod0 > 3.0:
        prod0 = 3.0
    items_per_craft = _recipe_result_amount(craft_recipe, item_key) * (1.0 + prod0)
    rec_recipe = _recipe_by_key(data, f"{item_key}-recycling")
    retention = (
        _recipe_result_amount(rec_recipe, item_key) if rec_recipe else RECYCLER_RETENTION
    )
    total_recycle_crafts = crafts_per_min * items_per_craft / max(1.0 - retention, 1e-6)
    rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2
    recycler_machines = total_recycle_crafts * rec_time / (RECYCLER_SPEED * 60.0)

    # Walk ingredients at NORMAL quality.  Each ingredient's demand =
    # amount × crafts_per_min.  Solid raws + intermediates need normal-quality
    # production; fluids are quality-transparent.
    normal_stages: list[dict] = []
    normal_solid_input: dict[str, float] = {}
    normal_fluid_input: dict[str, float] = {}
    for ing in craft_recipe.get("ingredients", []):
        iname = ing["name"]
        amt = float(ing.get("amount", 0))
        ing_rate = amt * crafts_per_min
        if iname in fluids:
            normal_fluid_input[iname] = normal_fluid_input.get(iname, 0.0) + ing_rate
        else:
            # Walk this ingredient as a normal-quality production tree.  We use
            # the same walker but mark the resulting stages as normal-quality
            # and route their leaf raws into normal_input buckets.
            try:
                sub_stages, sub_raws = walk_recipe_tree(
                    iname, ing_rate, data, research_levels, assembler_level,
                    fluids, planet_props, planets,
                    assembly_modules=assembly_modules,
                    assembly_module_quality=module_quality,
                    prod_module_tier=prod_module_tier,
                )
            except ValueError:
                # Ingredient may itself be planet-gated or unreachable — record
                # as a normal solid input and let the user supply it.
                normal_solid_input[iname] = normal_solid_input.get(iname, 0.0) + ing_rate
                continue
            for st in sub_stages:
                st["normal_quality_chain"] = True
            normal_stages.extend(sub_stages)
            for raw, ramt in sub_raws.items():
                if raw in fluids:
                    normal_fluid_input[raw] = normal_fluid_input.get(raw, 0.0) + ramt
                else:
                    normal_solid_input[raw] = normal_solid_input.get(raw, 0.0) + ramt

    self_stage = {
        "role": "self-recycle-target",
        "target": item_key,
        "recipe": craft_recipe["key"],
        "machine": machine_key,
        "machine_count": craft_machines + recycler_machines,
        "craft_machines": craft_machines,
        "recycler_machines": recycler_machines,
        "yield_per_normal_craft": v,
        "yield_pct": v * 100.0,
        "rate_per_min": rate,
        "crafts_per_min": crafts_per_min,
        "module_config_per_tier": {
            QUALITY_TIERS[t]: {
                "craft": (
                    f"{configs[t].get('craft_prod',0)}p+"
                    f"{configs[t].get('craft_quality',0)}q "
                    f"(t{quality_module_tier} {module_quality})"
                ),
                "recycle": (
                    f"{configs[t].get('recycle_quality',0)}q "
                    f"(t{quality_module_tier} {module_quality})"
                ),
            }
            for t in (0, 1, 2, 3)
        },
    }

    total_machines = (
        self_stage["machine_count"]
        + sum(s["machine_count"] for s in normal_stages)
    )

    notes: list[str] = [
        f"self-recycle target '{item_key}' uses {machine_key} (slots={machine_slots}, "
        f"inherent prod={inherent_prod:.2f}); ingredients consumed at normal quality"
    ]

    # Per-stage power + total (V3 power accounting).
    machine_power_w = cli.build_machine_power_w(data)
    all_stages = [self_stage] + normal_stages
    for st in all_stages:
        st["power_kw"] = _stage_power_kw(st, machine_power_w)
    total_power_mw = sum(s["power_kw"] for s in all_stages) / 1000.0

    return {
        "target": {"item": item_key, "rate_per_min": rate, "tier": "legendary"},
        "asteroid_input": {},
        "mined_input": {},
        "fluid_input": {},
        "normal_solid_input": normal_solid_input,
        "normal_fluid_input": normal_fluid_input,
        "shuffle_byproduct_legendary": {},
        "shuffle_byproduct_credited": {},
        "shuffle_byproduct_overflow": {},
        "stages": [self_stage] + list(reversed(normal_stages)),
        "total_machine_count": total_machines,
        "total_power_mw": total_power_mw,
        "module_quality": module_quality,
        "assembler_level": assembler_level,
        "research_levels": dict(research_levels),
        "planets": sorted(planets),
        "notes": notes,
    }


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
    planets: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    enable_lds_shuffle: bool = False,
    assembly_modules: bool = False,
    prod_module_tier: int = 3,
) -> dict:
    """Top-level planning: walk tree, attach asteroid reprocessing loops for raws,
    scale stages, assemble full output.

    ``planets`` is the set of planets the player has unlocked.  An empty or
    ``None`` value reverts to V1 behaviour (asteroid-only, Nauvis baseline).
    """
    research_levels = research_levels or {}
    planets_fs: frozenset[str] = frozenset(planets) if planets else frozenset()
    # Validate planet names against the known list.
    unknown = planets_fs - set(KNOWN_PLANETS)
    if unknown:
        raise ValueError(
            f"ERROR: unknown planet(s) {sorted(unknown)} in --planets; "
            f"valid: {list(KNOWN_PLANETS)}"
        )
    if item_key in SELF_RECYCLING_BLOCKLIST and item_key not in SELF_RECYCLE_TARGETS:
        raise ValueError(
            f"ERROR: recipe '{item_key}' is self-recycling (output recycles to itself) — not supported"
        )

    # V3: dedicated self-recycle target path.  When the user asks for legendary
    # of a self-recycling item, we run the recycle DP and consume the recipe's
    # ingredients at NORMAL quality (quality rolls happen during craft+recycle).
    if item_key in SELF_RECYCLE_TARGETS:
        return _plan_self_recycle_target(
            item_key, rate, data,
            module_quality=module_quality,
            research_levels=research_levels,
            assembler_level=assembler_level,
            quality_module_tier=quality_module_tier,
            planets=planets_fs,
            assembly_modules=assembly_modules,
            prod_module_tier=prod_module_tier,
        )
    if item_key in PLANET_UNLOCKS:
        if not _planet_unlocks_item(item_key, planets_fs) and item_key not in RAW_TO_CHUNK:
            needed = PLANET_UNLOCKS[item_key]
            raise ValueError(
                f"ERROR: item '{item_key}' requires one of planet(s) {list(needed)} "
                f"— add --planets {','.join(needed)}"
            )

    fluids = build_fluid_set(data)
    planet_props = _combined_planet_props(data, planets_fs)
    stages, raw_demand = walk_recipe_tree(
        item_key, rate, data, research_levels, assembler_level, fluids, planet_props, planets_fs,
        assembly_modules=assembly_modules,
        assembly_module_quality=module_quality,
        prod_module_tier=prod_module_tier,
    )

    # ---- LDS shuffle wiring (V3 partial: replace plastic-bar leg) ----
    shuffle_stages: list[dict] = []
    normal_chain_stages: list[dict] = []
    normal_solid_input: dict[str, float] = {}
    normal_fluid_input: dict[str, float] = {}
    shuffle_byproduct_legendary: dict[str, float] = {}
    shuffle_byproduct_credited: dict[str, float] = {}
    shuffle_byproduct_overflow: dict[str, float] = {}
    extra_notes: list[str] = []
    if enable_lds_shuffle:
        plastic_stage = next(
            (s for s in stages if s.get("product") == "plastic-bar"), None,
        )
        if plastic_stage is not None:
            leg_plastic = float(plastic_stage["rate_per_min"])
            research_prod_lds = _research_prod_for_recipe(
                "casting-low-density-structure", research_levels,
            )
            shuffle = compute_lds_shuffle_stage(
                leg_plastic, data,
                module_quality=module_quality,
                quality_module_tier=quality_module_tier,
                prod_module_tier=3,
                research_prod=research_prod_lds,
            )
            if shuffle is not None:
                normal_in = float(shuffle["normal_plastic_in_per_min"])

                # Re-walk main chain treating plastic-bar as supplied externally.
                stages, raw_demand = walk_recipe_tree(
                    item_key, rate, data, research_levels, assembler_level,
                    fluids, planet_props, planets_fs,
                    extra_raws=frozenset({"plastic-bar"}),
                    assembly_modules=assembly_modules,
                    assembly_module_quality=module_quality,
                    prod_module_tier=prod_module_tier,
                )
                raw_demand.pop("plastic-bar", None)

                # Cap byproduct credits at observed demand (no negative inputs).
                # Demand for byproducts is the rate_per_min on their stages, OR
                # raw_demand if the byproduct shows up as a leaf.
                stage_demand = {s.get("product"): s["rate_per_min"] for s in stages}
                capped_credits: dict[str, float] = {}
                overflow: dict[str, float] = {}
                for byprod, byprod_rate in shuffle["byproduct_legendary"].items():
                    have = float(
                        stage_demand.get(byprod, raw_demand.get(byprod, 0.0))
                    )
                    cap = min(float(byprod_rate), have)
                    capped_credits[byprod] = cap
                    surplus = float(byprod_rate) - cap
                    if surplus > 1e-6:
                        overflow[byprod] = surplus

                if any(v > 0 for v in capped_credits.values()):
                    # Re-walk with credits subtracted from initial demand.
                    stages, raw_demand = walk_recipe_tree(
                        item_key, rate, data, research_levels, assembler_level,
                        fluids, planet_props, planets_fs,
                        extra_raws=frozenset({"plastic-bar"}),
                        byproduct_credits=capped_credits,
                        assembly_modules=assembly_modules,
                        assembly_module_quality=module_quality,
                        prod_module_tier=prod_module_tier,
                    )
                    raw_demand.pop("plastic-bar", None)

                for byprod, surplus in overflow.items():
                    extra_notes.append(
                        f"shuffle byproduct surplus: {surplus:.1f} legendary "
                        f"{byprod}/min unused (no downstream demand)"
                    )

                # Walk the normal-quality plastic-bar leg separately, then route
                # its raws into the normal_input bucket (no quality loop needed).
                n_stages, n_raws = walk_recipe_tree(
                    "plastic-bar", normal_in, data, research_levels, assembler_level,
                    fluids, planet_props, planets_fs,
                    assembly_modules=assembly_modules,
                    assembly_module_quality=module_quality,
                    prod_module_tier=prod_module_tier,
                )
                for st in n_stages:
                    st["normal_quality_chain"] = True
                normal_chain_stages = n_stages
                for raw, amt in n_raws.items():
                    if raw in fluids:
                        normal_fluid_input[raw] = normal_fluid_input.get(raw, 0.0) + amt
                    else:
                        normal_solid_input[raw] = normal_solid_input.get(raw, 0.0) + amt

                shuffle_byproduct_legendary = dict(shuffle["byproduct_legendary"])
                shuffle_byproduct_credited = dict(capped_credits)
                shuffle_byproduct_overflow = dict(overflow)
                shuffle_stages.append({
                    "role": "cross-item-shuffle",
                    "shuffle": "lds",
                    "recipe": "casting-low-density-structure + low-density-structure-recycling",
                    "machine": "foundry+recycler",
                    "machine_count": (
                        float(shuffle["foundry_machines"])
                        + float(shuffle["recycler_machines"])
                    ),
                    "foundry_machines": float(shuffle["foundry_machines"]),
                    "recycler_machines": float(shuffle["recycler_machines"]),
                    "yield_per_normal_plastic_pct": (
                        float(shuffle["yield_per_normal_plastic"]) * 100.0
                    ),
                    "legendary_plastic_per_min": float(shuffle["legendary_plastic_per_min"]),
                    "normal_plastic_in_per_min": normal_in,
                    "byproduct_legendary": dict(shuffle["byproduct_legendary"]),
                    "byproduct_credited": dict(capped_credits),
                    "byproduct_overflow": dict(overflow),
                    "fluid_demand": dict(shuffle["fluid_demand"]),
                })

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

    # Planet-mined solid raws (coal, stone, tungsten-ore, scrap, holmium-ore,
    # uranium-ore): legendary via recycler self-loop (25% retention, 4 quality
    # slots).  We attach one stage per demanded mined raw.  Input is expressed
    # in "normal raws mined per minute" — that's what the user's miner fleet
    # must produce.
    mined_recycle_stages: list[dict] = []
    mined_input: dict[str, float] = {}
    fluid_raws_demand: dict[str, float] = {}
    for raw_key, demand_rate in raw_demand.items():
        if demand_rate <= 0:
            continue
        # Skip asteroid-routed raws (already consumed by chunk_demand).
        if raw_key in RAW_TO_CHUNK:
            continue
        # Fluids: quality-transparent, just record demand (no loop).
        if raw_key in fluids:
            fluid_raws_demand[raw_key] = demand_rate
            continue
        if raw_key in MINED_RAW_PLANETS:
            # Check user has an appropriate planet unlocked.
            if not any(p in planets_fs for p in MINED_RAW_PLANETS[raw_key]):
                needed = MINED_RAW_PLANETS[raw_key]
                raise ValueError(
                    f"ERROR: item '{item_key}' requires mined raw '{raw_key}' on planet(s) "
                    f"{list(needed)} — add --planets {','.join(needed)}"
                )
            v, configs = solve_mined_raw_self_recycle_loop(
                raw_key, data, module_quality, quality_module_tier,
            )
            if v <= 0:
                raise ValueError(
                    f"ERROR: '{raw_key}' has no <raw>-recycling recipe — cannot produce legendary"
                )
            normal_input_per_min = demand_rate / v
            mined_input[raw_key] = normal_input_per_min
            rec_recipe = _recipe_by_key(data, f"{raw_key}-recycling")
            retention = _recipe_result_amount(rec_recipe, raw_key) if rec_recipe else 0.25
            total_crafts_per_min = normal_input_per_min / max(1.0 - retention, 1e-6)
            rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2
            machine_count = total_crafts_per_min * rec_time / (RECYCLER_SPEED * 60.0)
            mined_recycle_stages.append({
                "role": "mined-raw-self-recycle",
                "raw": raw_key,
                "recipe": f"{raw_key}-recycling",
                "machine": "recycler",
                "machine_count": machine_count,
                "yield_pct": v * 100.0,
                "legendary_per_min": demand_rate,
                "normal_mined_per_min": normal_input_per_min,
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
        + sum(s["machine_count"] for s in mined_recycle_stages)
        + sum(s["machine_count"] for s in shuffle_stages)
        + sum(s["machine_count"] for s in normal_chain_stages)
    )

    # Annotate per-stage power and total (V3 power accounting).
    machine_power_w = cli.build_machine_power_w(data)
    all_stages_for_power = (
        stages + crushing_stages + reprocessing_stages
        + mined_recycle_stages + shuffle_stages + normal_chain_stages
    )
    for st in all_stages_for_power:
        st["power_kw"] = _stage_power_kw(st, machine_power_w)
    total_power_mw = sum(s["power_kw"] for s in all_stages_for_power) / 1000.0

    notes: list[str] = list(extra_notes)
    # Detect if we used fluid transparency
    for st in stages:
        if st.get("fluid_inputs"):
            notes.append(
                f"stage {st['recipe']} uses fluid-transparent input ({list(st['fluid_inputs'].keys())})"
            )

    out = {
        "target": {"item": item_key, "rate_per_min": rate, "tier": "legendary"},
        "asteroid_input": asteroid_input,
        "mined_input": mined_input,
        "fluid_input": fluid_raws_demand,
        "normal_solid_input": normal_solid_input,
        "normal_fluid_input": normal_fluid_input,
        "shuffle_byproduct_legendary": shuffle_byproduct_legendary,
        "shuffle_byproduct_credited": shuffle_byproduct_credited,
        "shuffle_byproduct_overflow": shuffle_byproduct_overflow,
        "stages": (
            reprocessing_stages
            + crushing_stages
            + mined_recycle_stages
            + shuffle_stages
            + list(reversed(normal_chain_stages))
            + list(reversed(stages))
        ),
        "total_machine_count": total_machines,
        "total_power_mw": total_power_mw,
        "module_quality": module_quality,
        "assembler_level": assembler_level,
        "research_levels": dict(research_levels),
        "planets": sorted(planets_fs),
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
    if out.get("planets"):
        L.append(f"Unlocked planets: {', '.join(out['planets'])}")
    if out.get("research_levels"):
        L.append(f"Research: {out['research_levels']}")
    L.append("")
    L.append("=== Asteroid Input (normal chunks/min) ===")
    if out["asteroid_input"]:
        for chunk, amt in sorted(out["asteroid_input"].items()):
            L.append(f"  {_humanize(chunk)}: {amt:.2f}")
    else:
        L.append("  (none)")
    if out.get("mined_input"):
        L.append("")
        L.append("=== Mined Raws (normal mined/min, via planet miners) ===")
        for raw, amt in sorted(out["mined_input"].items()):
            L.append(f"  {_humanize(raw)}: {amt:.2f}")
    if out.get("fluid_input"):
        L.append("")
        L.append("=== Fluid Raws (quality-transparent, fluid/min) ===")
        for fluid, amt in sorted(out["fluid_input"].items()):
            L.append(f"  {_humanize(fluid)}: {amt:.2f}")
    if out.get("normal_solid_input"):
        L.append("")
        L.append("=== Normal-Quality Solid Input (e.g. shuffle inputs, /min) ===")
        for raw, amt in sorted(out["normal_solid_input"].items()):
            L.append(f"  {_humanize(raw)}: {amt:.2f}")
    if out.get("normal_fluid_input"):
        L.append("")
        L.append("=== Normal-Quality Fluid Input (/min) ===")
        for raw, amt in sorted(out["normal_fluid_input"].items()):
            L.append(f"  {_humanize(raw)}: {amt:.2f}")
    if out.get("shuffle_byproduct_legendary"):
        L.append("")
        L.append("=== Shuffle Byproducts (legendary/min) ===")
        emitted = out["shuffle_byproduct_legendary"]
        credited = out.get("shuffle_byproduct_credited", {})
        overflow = out.get("shuffle_byproduct_overflow", {})
        for item, amt in sorted(emitted.items()):
            c = credited.get(item, 0.0)
            o = overflow.get(item, 0.0)
            L.append(
                f"  {_humanize(item)}: {amt:.2f} emitted "
                f"(credited {c:.2f}, surplus {o:.2f})"
            )
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
        elif role == "self-recycle-target":
            L.append(
                f"  [self-recycle] {_humanize(st['target'])}: "
                f"{st['crafts_per_min']:.2f} crafts/min -> "
                f"{st['rate_per_min']:.2f}/min legendary "
                f"({st['craft_machines']:.2f} × {_humanize(st['machine'])} + "
                f"{st['recycler_machines']:.2f} recyclers, "
                f"yield {st['yield_pct']:.4f}% per craft)"
            )
        elif role == "cross-item-shuffle":
            byp = ", ".join(
                f"{_humanize(k)}={v:.1f}/min"
                for k, v in st.get("byproduct_legendary", {}).items()
            )
            L.append(
                f"  [shuffle]      {st.get('shuffle','?')}: "
                f"{st['normal_plastic_in_per_min']:.2f} normal plastic-bar in -> "
                f"{st['legendary_plastic_per_min']:.2f} legendary plastic-bar out + "
                f"byproducts [{byp}] "
                f"({st['foundry_machines']:.1f} foundries + "
                f"{st['recycler_machines']:.1f} recyclers, "
                f"yield {st['yield_per_normal_plastic_pct']:.3f}%)"
            )
        elif role == "mined-raw-self-recycle":
            L.append(
                f"  [mined-recycle] {_humanize(st['raw'])}: "
                f"{st['normal_mined_per_min']:.2f} normal mined -> "
                f"{st['legendary_per_min']:.2f} legendary out "
                f"({st['machine_count']:.2f} recyclers, "
                f"yield {st['yield_pct']:.4f}%)"
            )
        else:
            fluids = f", fluids=[{','.join(st['fluid_inputs'])}]" if st.get("fluid_inputs") else ""
            capped = " [PROD-CAPPED]" if st.get("prod_capped") else ""
            tag = " [NORMAL]" if st.get("normal_quality_chain") else ""
            n_prod = int(st.get("prod_modules", 0))
            if n_prod > 0:
                mods = (
                    f", {n_prod}x prod-{st.get('prod_module_tier', 3)}-"
                    f"{st.get('prod_module_quality', 'normal')} "
                    f"(+{st.get('module_prod', 0.0) * 100.0:.0f}%)"
                )
            else:
                mods = ""
            L.append(
                f"  [{role:10s}] {st['recipe']}: "
                f"{st['rate_per_min']:.2f}/min "
                f"({st['machine_count']:.2f} × {_humanize(st['machine'])}){fluids}{mods}{capped}{tag}"
            )
    L.append("")
    L.append(f"Total machines: {out['total_machine_count']:.2f}")
    if "total_power_mw" in out:
        pwr_mw = float(out["total_power_mw"])
        if pwr_mw >= 1000.0:
            L.append(f"Total power:    {pwr_mw / 1000.0:.2f} GW (electric machines only)")
        else:
            L.append(f"Total power:    {pwr_mw:.2f} MW (electric machines only)")
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
    p = argparse.ArgumentParser(description="Legendary production planner (V2)")
    p.add_argument("--item", required=True)
    p.add_argument("--rate", required=True, type=float, help="target legendary items per minute")
    p.add_argument("--module-quality", default="legendary", choices=list(QUALITY_TIERS))
    p.add_argument("--quality-module-tier", default=3, type=int, choices=[1, 2, 3])
    p.add_argument("--assembler-level", default=3, type=int, choices=[2, 3])
    p.add_argument("--research", action="append", default=[],
                   help="research-tech=level, repeatable")
    p.add_argument(
        "--planets", default="",
        help=(
            "comma-separated list of unlocked planets (e.g. "
            "'nauvis,vulcanus,fulgora'). Unlocks planet-local raws (crude-oil, "
            "lava, scrap, bioflux, …). Default: asteroid-only (V1 behaviour)."
        ),
    )
    p.add_argument(
        "--assembly-modules", action="store_true",
        help=(
            "Fill assembly-stage machine slots with prod modules "
            "(matching --module-quality, tier 3). Reduces ingredient demand "
            "and machine counts throughout the chain by 1/(1+prod) per "
            "stage. Inherent +50%% prod (foundry/EM-plant/biochamber) is "
            "always applied — this flag adds the module slots on top."
        ),
    )
    p.add_argument(
        "--prod-module-tier", default=3, type=int, choices=[1, 2, 3],
        help="Tier of prod modules used by --assembly-modules (default 3).",
    )
    p.add_argument(
        "--enable-lds-shuffle", action="store_true",
        help=(
            "Replace the legendary plastic-bar chain with the LDS shuffle "
            "(foundry-cast LDS + recycle for legendary plastic + copper/steel "
            "byproducts). Improves throughput when plastic-bar is in the "
            "production tree, especially with high plastic-bar / LDS / "
            "low-density-structure-recycling productivity research."
        ),
    )
    p.add_argument("--format", default="human", choices=["human", "json"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data = cli.load_data("nauvis")
    research = _parse_research(args.research)
    planets_list = [p.strip() for p in args.planets.split(",") if p.strip()]
    try:
        out = plan(
            args.item, args.rate, data,
            module_quality=args.module_quality,
            research_levels=research,
            assembler_level=args.assembler_level,
            quality_module_tier=args.quality_module_tier,
            planets=planets_list,
            enable_lds_shuffle=args.enable_lds_shuffle,
            assembly_modules=args.assembly_modules,
            prod_module_tier=args.prod_module_tier,
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
