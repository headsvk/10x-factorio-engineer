#!/usr/bin/env python3
"""
Quality Planner V2

Separate tool that answers:
  "Given my research, module tier, and which planets I've unlocked, what's
   the cheapest way to make N <item> per minute at a target quality tier
   (legendary by default; lower it with --target-quality)?"

V1 scope (asteroid-only, Nauvis-subset):
  * Nauvis-style assembly items whose raws are all reachable via
    asteroid reprocessing (iron-ore, copper-ore, coal, stone, calcite, ice).
  * DP-based quality loop solver (backward induction over tiers).
  * Asteroid *crushing* as a legendary raw source (the chunk crushing step still
    permits quality modules).  KNOWN LIMITATION: as of 2.1.8 asteroid
    *reprocessing* no longer permits quality modules (allowed_effects drops
    "quality"), but the active kernel (`solve_asteroid_reprocessing_loop`) and
    the plan() asteroid path still model the pre-2.1.8 reprocessing chunk-tier
    climb, so asteroid-sourced counts are optimistic vs current game rules.
    A game-accurate redesign (quality rolled at crushing + ore self-recycle)
    is future work; plans with reprocessing stages carry an explanatory note.
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
  * ``--location`` build axis (mirrors cli.py).  ``--location fulgora``
    unlocks Fulgora AND switches to scrap-only sourcing: there is no
    asteroid platform, so base materials come from the scrap-recycling
    quality source and metals terminate at their scrap-reachable plate
    form (no casting/molten-ore routes).  Only ``fulgora`` alters
    sourcing today; other locations merely unlock that planet.

Still fails fast on unsupported chains, but with specific hints about
which ``--planets`` flag would unblock them.

Usage
-----
    python dev/quality_planner.py --item <item-id> --rate <N>
        --tech NAME=LEVEL ...                              # REQUIRED (e.g. recycling=1)
        [--target-quality uncommon|rare|epic|legendary]    # default: legendary (goal tier)
        [--planets nauvis,vulcanus,fulgora,gleba,aquilo,space-platform]
        [--location nauvis|vulcanus|fulgora|gleba|aquilo|space-platform]  # build location; fulgora = scrap-only sourcing
        [--module-quality normal|uncommon|rare|epic|legendary]
        [--quality-module-tier 1|2|3]
        [--assembler-level 2|3]
        [--machine-quality normal|uncommon|rare|epic|legendary]
        [--assembly-modules] [--prod-module-tier 1|2|3]
        [--research NAME=LEVEL ...]
        [--enable-shuffle NAME ...] [--enable-shuffles all]
        [--enable-driver RECIPE_KEY ...] [--enable-drivers all]
        [--no-asteroids]
        [--no-miner-quality-modules]                       # disable quality-module seeding in mining drills
        [--no-scrap-upcycle-loops]                         # disable closed-loop plate upcycling on Fulgora
        [--miner electric|big]                             # drill fleet for solid raws (default electric)
        [--format json|human]

Stdlib only.  Shares the Space Age dataset with cli.py.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from fractions import Fraction

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
# (game source: quality module T1 = +1%, T2 = +2%, T3 = +2.5%; multiplied
# by MODULE_QUALITY_MULT for uncommon/rare/epic/legendary modules).
QUALITY_MODULE_BONUS: dict[int, float] = {
    1: 0.01,
    2: 0.02,
    3: 0.025,
}

# Tier-skip distribution when a quality roll succeeds.
# Of the total quality chance Q: 90% goes to +1 tier, 9% to +2, 0.9% to +3, 0.1% to +4.
TIER_SKIP_DIST: tuple[float, ...] = (0.9, 0.09, 0.009, 0.001)

# Spoilable items and their fixed spoil times in seconds (Factorio 2.0 / Space Age).
SPOIL_TIMES_SECONDS: dict[str, float] = {
    "yumako": 300.0,
    "jellynut": 300.0,
    "yumako-mash": 180.0,
    "jellynut-mash": 180.0,
    "nutrients": 300.0,
    "bioflux": 7200.0,
    "pentapod-egg": 1800.0,
    "biter-egg": 1800.0,
    "agricultural-science-pack": 3600.0,
}

# Asteroid reprocessing: crusher processes chunk -> (mostly) chunk.  These
# recipes drive chunk *quantity* sourcing (self-output retention).
# KNOWN LIMITATION (2.1.8): reprocessing recipes no longer permit quality
# modules (allowed_effects drops "quality"), which makes the chunk-tier quality
# climb impossible in the current game.  The active kernel
# (`solve_asteroid_reprocessing_loop`) still models the pre-2.1.8 climb with
# quality modules in the reprocessing crusher — only the unused reference
# kernel (`_unused_solve_loop_reference`) gates on recipe_allows_quality.
# Asteroid-sourced counts are therefore optimistic; a game-accurate redesign
# (roll quality at the crushing step + upcycle ores via self-recycle) is
# tracked as future work.
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
    "sulfuric-acid":        ("nauvis", "vulcanus", "fulgora"),  # Nauvis/Fulgora chem-plant (sulfur via oil) OR Vulcanus geyser
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

# Mined raws that are normally asteroid-routed but have a planet-mining
# fallback used by ``--no-asteroids``.  Each has a ``<raw>-recycling`` recipe
# (0.25 retention) so the recycler self-loop produces legendary versions.
#
# carbon and sulfur are NOT in this table because they are chemistry products
# (no native mining); when asteroids are disabled, the walker expands their
# normal recipes (carbon-from-coal-and-sulfuric-acid / sulfur-from-petgas)
# which require coal+sulfuric-acid or petgas — those pull in further planet
# raws via the regular planet-unlock mechanism.  water has no recycling so
# ``--no-asteroids`` requires Nauvis (offshore-pump quality-transparent).
MINED_RAW_NO_ASTEROID_FALLBACK: dict[str, tuple[str, ...]] = {
    "iron-ore":   ("nauvis",),
    "copper-ore": ("nauvis",),
    "ice":        ("aquilo",),
    "calcite":    ("vulcanus",),
}

# ---------------------------------------------------------------------------
# Cross-item shuffle enumeration (V3 item 1)
# ---------------------------------------------------------------------------
#
# A "shuffle" is a recipe R producing item I where the I-recycling recipe
# returns a subset of R's solid ingredients.  By looping cast(R) -> recycle,
# the planner can quality-roll the SOLID ingredients (fluids are
# quality-transparent).  One ingredient is the "primary" (becomes legendary
# at the loop's main yield); other solid ingredients become byproducts.
#
# The canonical example is low-density-structure: cast 5 plastic-bar +
# fluids -> 1 LDS, recycle LDS -> 1.25 plastic-bar + copper-plate +
# steel-plate at 25% retention.  Plastic-bar is the primary; copper-plate
# and steel-plate are byproducts.
#
# enumerate_shuffle_candidates() introspects the dataset to find ALL recipes
# matching this pattern, restricted to multi-ingredient candidates (single-
# ingredient recipes are degenerate self-recycles already covered by
# solve_self_recycle_target_loop).

ShuffleCandidate = namedtuple("ShuffleCandidate", [
    "recipe_key",            # e.g. "casting-low-density-structure"
    "output_item",           # e.g. "low-density-structure"
    "category",              # recipe category (foundry/EM-plant/chem-plant/...)
    "solid_ingredients",     # tuple — solid ingredients of the cast recipe
    "fluid_ingredients",     # tuple — fluid ingredients (quality-transparent)
    "solid_recycle_returns", # tuple — solids the recycler returns
    "recycle_recipe_key",    # e.g. "low-density-structure-recycling"
])

# Module-level cache keyed by id(data); avoids re-enumerating per plan() call.
_SHUFFLE_CANDIDATES_CACHE: dict[int, list[ShuffleCandidate]] = {}


def enumerate_shuffle_candidates(data: dict) -> list[ShuffleCandidate]:
    """Return all multi-output shuffle candidates in the dataset.

    A candidate is keyed by an output item I such that:
      * Some recipe R produces I
      * ``<I>-recycling`` exists
      * The recycler returns 2 or more distinct solid items (multi-output
        filter — single-output recyclers are degenerate self-recycles
        already covered by ``solve_self_recycle_target_loop``)
      * R is not a recycling / barrel-handling recipe

    The recycler's solid outputs need NOT be a subset of R's solid
    ingredients (the recycler returns the assembler-variant ingredients
    regardless of which cast variant is chosen); the greedy selector later
    derives valid primaries as ingredients ∩ returns.

    When multiple cast recipes exist for the same output (e.g. foundry
    `casting-low-density-structure` vs assembler `low-density-structure`),
    the fluid-preferred variant wins (more fluid ingredients = quality-
    transparent path = better legendary efficiency).

    Cached per dataset; safe to call repeatedly.
    """
    cached = _SHUFFLE_CANDIDATES_CACHE.get(id(data))
    if cached is not None:
        return cached

    fluids = build_fluid_set(data)
    recipes_by_key = {r["key"]: r for r in data.get("recipes", [])}

    # Group eligible cast recipes by output item, then pick the fluid-
    # preferred variant per output.
    #
    # Note: we DO NOT filter by ``allow_productivity`` here.  Buildings,
    # modules, and military/end-game items have ``allow_productivity=False``
    # but are still valid quality-target candidates via the cast+recycle DP
    # (the cast leg just can't fit prod modules — quality slots only).  The
    # ``allow_productivity`` flag is forwarded into ``solve_shuffle_loop`` so
    # the cast-leg config search disables prod-bearing slot splits.
    by_output: dict[str, list[tuple[dict, tuple, tuple]]] = {}
    for r in data.get("recipes", []):
        if r.get("subgroup") in ("empty-barrel", "fill-barrel"):
            continue
        if cli.is_recycling(r):
            continue
        ing_set = {x["name"] for x in r.get("ingredients", [])}
        solid_ings = tuple(sorted(ing_set - fluids))
        fluid_ings = tuple(sorted(ing_set & fluids))
        for res in r.get("results", []):
            output = res["name"]
            if output in fluids:
                continue
            by_output.setdefault(output, []).append((r, solid_ings, fluid_ings))

    out: list[ShuffleCandidate] = []
    for output, variants in by_output.items():
        recycle_key = f"{output}-recycling"
        recycle = recipes_by_key.get(recycle_key)
        if recycle is None:
            continue
        rec_outputs = {
            x["name"] for x in recycle.get("results", [])
            if x["name"] != output
        }
        solid_rec_outputs = tuple(sorted(rec_outputs - fluids))
        # Multi-output filter: at least 2 distinct solid items returned.
        if len(solid_rec_outputs) < 2:
            continue

        # Pick fluid-preferred cast variant: most fluids first, then most
        # solids (richer recipe), then deterministic key sort.
        variants.sort(
            key=lambda v: (-len(v[2]), -len(v[1]), v[0]["key"]),
        )
        for r, solid_ings, fluid_ings in variants:
            # No subset check between recycler returns and cast ingredients:
            # the recycler returns the assembler-variant ingredients regardless
            # of which cast recipe is used, so the foundry variant of LDS
            # (1 solid in, 3 solids returned) is a valid candidate.  Callers
            # (select_shuffles_greedy) compute valid primaries as
            # solid_ingredients ∩ solid_recycle_returns and treat the rest of
            # the returns as byproducts, so an over-broad candidate is harmless.
            out.append(ShuffleCandidate(
                recipe_key=r["key"],
                output_item=output,
                category=_primary_category(r),
                solid_ingredients=solid_ings,
                fluid_ingredients=fluid_ings,
                solid_recycle_returns=solid_rec_outputs,
                recycle_recipe_key=recycle_key,
            ))
            break  # one variant per output_item

    out.sort(key=lambda c: c.output_item)
    _SHUFFLE_CANDIDATES_CACHE[id(data)] = out
    return out


# Module-level cache keyed by id(data); avoids re-enumerating per plan() call.
_DRIVER_CANDIDATES_CACHE: dict[int, dict[str, list[dict]]] = {}


def enumerate_co_product_drivers(data: dict) -> dict[str, list[dict]]:
    """Enumerate driven co-product candidates from the dataset.

    For every multi-output recipe, *every* solid output becomes a candidate
    target — the planner can activate the recipe FOR that output and accept
    the rest as overflow (fluid overflow is voided, solid overflow may credit
    chain demand or also become overflow).  This is the open-loop sibling of
    :func:`enumerate_shuffle_candidates` (which keeps the loop closed by
    recycling the primary back into ingredients).

    A recipe is excluded when:
      - It's in ``recycling`` / ``crushing`` / ``captive-spawner-process``
        (those have dedicated pipelines)
      - It's a barrel-handling recipe
      - It has fewer than 2 results

    Returns ``{co_product_item: [candidate, ...]}``.  Candidate dict:
      ``recipe_key``        — recipe key
      ``target``            — the co-product item the candidate harvests
      ``target_amount``     — per-craft yield (amount × probability, no eff_prod)
      ``other_outputs``     — list[{name, amount, prob}] for everything that
                              isn't the target (both solid and fluid; consumers
                              decide credit vs overflow)
      ``category``          — recipe category (machine routing)
      ``ingredients``       — recipe.ingredients (raw list of {name, amount})
      ``energy_required``   — crafting time
      ``allow_productivity`` — whether prod modules can be installed

    Sorted per co-product by descending ``target_amount`` so a naive "first
    viable" pick prefers the highest-yield driver per craft.

    Cached per dataset.
    """
    cached = _DRIVER_CANDIDATES_CACHE.get(id(data))
    if cached is not None:
        return cached

    fluids = build_fluid_set(data)
    skip_categories = {
        "crushing",                  # asteroid pipeline handles these
        "captive-spawner-process",   # captive-spawner has its own dispatch
    }
    out: dict[str, list[dict]] = {}
    for r in data.get("recipes", []):
        if cli.is_recycling(r) or any(c in skip_categories for c in cli.recipe_categories(r)):
            continue
        if r.get("subgroup") in ("empty-barrel", "fill-barrel"):
            continue
        results = r.get("results", [])
        if len(results) < 2:
            continue
        # Build per-output amount snapshots once.
        result_specs: list[dict] = []
        for res in results:
            name = res.get("name")
            amount = res.get("amount")
            if amount is None:
                amount = (
                    (res.get("amount_min", 0) + res.get("amount_max", 0)) / 2.0
                )
            prob = res.get("probability", 1.0)
            if not name or amount <= 0:
                continue
            result_specs.append({"name": name, "amount": float(amount), "prob": float(prob)})
        if len(result_specs) < 2:
            continue
        for tgt_idx, tgt in enumerate(result_specs):
            if tgt["name"] in fluids:
                continue   # fluid co-product — can't legendary-quality it
            target_amount = tgt["amount"] * tgt["prob"]
            if target_amount <= 0:
                continue
            other_outputs = [
                {"name": o["name"], "amount": o["amount"], "prob": o["prob"]}
                for i, o in enumerate(result_specs) if i != tgt_idx
            ]
            out.setdefault(tgt["name"], []).append({
                "recipe_key": r["key"],
                "target": tgt["name"],
                "target_amount": target_amount,
                "other_outputs": other_outputs,
                "category": _primary_category(r),
                "ingredients": list(r.get("ingredients", [])),
                "energy_required": float(r.get("energy_required", 1)),
                "allow_productivity": bool(r.get("allow_productivity", True)),
            })
    # Sort per-co-product entries by descending target_amount so a naive
    # "first viable" pick prefers the most efficient driver.
    for k in out:
        out[k].sort(key=lambda c: (-c["target_amount"], c["recipe_key"]))
    _DRIVER_CANDIDATES_CACHE[id(data)] = out
    return out


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
#
# V3 item 4: Gleba/cryo buildings whose recyclers return the building itself
# (biolab, captive-biter-spawner) — same shape, runs through
# `_plan_self_recycle_target`.
SELF_RECYCLE_TARGETS = frozenset([
    "tungsten-carbide",
    "superconductor",
    "holmium-plate",
    "fusion-power-cell",
    "lithium",
    "biolab",
    "captive-biter-spawner",
    # Slow-to-recycle items that climb quality cheaply via the wrap-and-recycle
    # trick (steel-plate → steel-chest).  Not added to SELF_RECYCLING_BLOCKLIST,
    # so they only take this path as a top-level target; as ordinary
    # intermediates they are still crafted normally.
    #
    # NOTE (2.1.8): concrete was removed here.  Its wrap (concrete →
    # hazard-concrete → recycle) is dead — hazard-concrete-recycling no longer
    # returns concrete, and the only loop-closing container left (heating-tower)
    # drags in boiler + heat-pipe and recycles slowly, so it is not a viable
    # quality wrap.  Concrete now plans as a normal craft.
    "steel-plate",
])

# V3 item 4 (continuation): self-FEED targets — recipes whose ingredient list
# contains the output item itself (the "doubling" recipe shape).  These need
# a different solver from SELF_RECYCLE_TARGETS because the recipe is super-
# productive (output × p_stay > 1 at every tier), so the per-atom value DP
# has no positive fixed point.  Modeled as a linear-flow LP instead — see
# `solve_self_feed_target_loop`.
#
# pentapod-egg and raw-fish are wired up.  Bacteria-cultivation recipes
# (copper-bacteria-cultivation, iron-bacteria-cultivation) share the same
# shape but the item itself has TWO recipes: the cultivation multiplier and a
# yumako-mash/jelly seeding recipe with no self-ingredient.  cli.pick_recipe
# returns the seeding recipe by default, so joining bacteria to this set
# would also require recipe-disambiguation logic in solve_self_feed_target_loop
# to pick the cultivation recipe.  Deferred — bacteria are rarely a legendary
# target in practice.
SELF_FEED_TARGETS = frozenset([
    "pentapod-egg",
    "raw-fish",
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

# Tech gating (V3 item 2).  Names follow Factorio tech IDs where they exist;
# a few are synthesised aliases (electromagnetic-plant, biochamber) because
# the actual unlocking tech has a non-obvious name. The mental model is
# "unlock-as-machine-name" so users discover names from the help text.
TECH_GATES: dict[str, dict] = {
    "recycling":              {"machines": ["recycler"]},
    "tungsten-carbide":       {"machines": ["foundry"]},
    "electromagnetic-plant":  {"machines": ["electromagnetic-plant"]},
    "cryogenic-plant":        {"machines": ["cryogenic-plant"]},
    "biochamber":             {"machines": ["biochamber"]},
}

# Convenience: every tech researched.  Used by tests and as a documented
# starting point for callers who want today's "fully researched" baseline.
ALL_TECH_UNLOCKED: dict[str, int] = {tech: 1 for tech in TECH_GATES}

# Machine routing around locked machines is derived from the recipe's
# ``categories`` array and the cli machine registry (see _machine_for_recipe).
# A recipe that also lists a generic crafting category falls back to the
# assembler; one that lists another unlocked dedicated machine falls back to it;
# otherwise it is unreachable under the tech_state and the planner fails-fast.


# Recycler retention (standard recycler; quality-only slots).
RECYCLER_RETENTION = 0.25
RECYCLER_SLOTS = 4
RECYCLER_SPEED = 0.5

# Crusher speed + slots (for reprocessing / crushing).
CRUSHER_SPEED = 1.0
CRUSHER_SLOTS = 2

# Machine speeds (from the cli data-driven registry; kept as float for the DP).
def _machine_speed(machine_key: str) -> float:
    s = cli._machine_speed(machine_key)
    return float(s) if s else 1.0


def _primary_category(recipe: dict) -> str:
    """A single representative crafting category for display / routing.

    Prefers a dedicated (non-generic, non-smelting) category so machine routing
    lands on the premium machine; falls back to the first listed category.
    """
    cats = cli.recipe_categories(recipe)
    for c in cats:
        if c not in cli.GENERIC_CRAFTING_CATS and c != "smelting":
            return c
    return cats[0] if cats else ""


def _module_speed_mult(quality_slots: int = 0, prod_slots: int = 0,
                       prod_tier: int = 3) -> float:
    """Crafting-speed multiplier from module speed penalties.

    Quality modules are a flat -5%/slot; prod modules -5/-10/-15% per tier
    (`cli.QUALITY_MODULE_SPEED_PENALTY` / `cli.PROD_MODULE_SPEED_PENALTY`).
    Neither is quality-scaled.  Multiply a stage's effective machine speed by
    this; floored at 0.2 (Factorio's -80% speed floor).
    """
    penalty = quality_slots * float(cli.QUALITY_MODULE_SPEED_PENALTY[1])
    if prod_slots:
        penalty += prod_slots * float(cli.PROD_MODULE_SPEED_PENALTY[prod_tier])
    return max(1.0 + penalty, 0.2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tech_locked_machines(tech_state: dict[str, int]) -> frozenset[str]:
    """Return machine keys that are LOCKED by the given tech_state.
    A tech absent from the dict is treated as locked (LEVEL=0)."""
    locked: set[str] = set()
    for tech, info in TECH_GATES.items():
        if tech_state.get(tech, 0) >= 1:
            continue
        for m in info.get("machines", []):
            locked.add(m)
    return frozenset(locked)


def _machine_for_recipe(
    recipe: dict,
    assembler_level: int,
    locked_machines: frozenset[str],
) -> tuple[str, float] | None:
    """Like cli.get_machine, but routes around ``locked_machines`` using the
    recipe's ``categories`` array.  Returns (machine_key, speed) or None if no
    viable machine exists under this tech_state.

    When ``locked_machines`` is empty the result matches ``cli.get_machine``
    exactly (assembler_level + electric furnace).
    """
    cats = cli.recipe_categories(recipe)
    primary_key, primary_speed = cli.get_machine(cats, assembler_level, "electric")
    if primary_key not in locked_machines:
        return (primary_key, float(primary_speed))
    # Primary machine locked — fall back to the assembler if the recipe lists a
    # generic crafting category, else to another unlocked dedicated machine.
    cat_set = set(cats)
    if cat_set & cli.GENERIC_CRAFTING_CATS:
        ak = cli.ASSEMBLER_KEY[assembler_level]
        if ak not in locked_machines:
            return (ak, _machine_speed(ak))
    for c in cats:
        for mk in cli._CATEGORY_MACHINES.get(c, []):
            if mk not in locked_machines and cli._MACHINE_CLASS.get(mk) == "dedicated":
                return (mk, _machine_speed(mk))
    # No fallback — recipe is unreachable under this tech_state.
    return None


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


def _seed_value_vector(target_tier: int) -> list[float]:
    """Seed the per-tier value vector for a quality-loop DP.

    ``V[t]`` is the expected number of items at tier ≥ ``target_tier`` produced
    per one item entering the loop at tier ``t``.  Every tier at or above the
    target is absorbing with value 1.0 (reaching the target tier *or better*
    counts as success — overshooting rolls land on a still-usable item and are
    pulled out of the loop).  Tiers below the target are filled in by backward
    induction in the caller.

    With ``target_tier == 4`` (legendary) this collapses to the original
    behaviour: only ``V[4] == 1.0``.
    """
    V = [0.0] * 5
    for t in range(target_tier, 5):
        V[t] = 1.0
    return V


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
        # Filter: if craft recipe disallows quality (allowed_effects), zero out
        # quality slots — no quality roll can happen at the craft step.
        if not cli.recipe_allows_quality(craft_recipe):
            craft_configs = list({(p, 0) for (p, _q) in craft_configs})

    # Recycle configs: quality only (recycler/reprocessing disallow prod).  When
    # the recycle recipe itself disallows quality — e.g. 2.1.8 asteroid
    # reprocessing, whose allowed_effects has no "quality" — no quality modules
    # can be fitted, so the only config is zero quality slots.
    if recycle_recipe is None or not cli.recipe_allows_quality(recycle_recipe):
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
    target_tier: int = 4,
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

    V = _seed_value_vector(target_tier)
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

    for t in range(target_tier - 1, -1, -1):
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
    target_tier: int = 4,
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
    if rep is None or not cli.recipe_allows_quality(rep):
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

    V = _seed_value_vector(target_tier)
    configs: dict[int, dict] = {}

    for t in range(target_tier - 1, -1, -1):
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


def solve_shuffle_loop(
    candidate: ShuffleCandidate,
    primary: str,
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
    prod_module_tier: int = 3,
    research_prod: float = 0.0,
    inherent_prod: float | None = None,
    cast_slots: int | None = None,
    target_tier: int = 4,
) -> tuple[float, dict]:
    """Generic cross-item shuffle DP.

    Given a ``ShuffleCandidate`` (cast recipe + recycle recipe + ingredients)
    and a ``primary`` ingredient, return ``(V[0], configs)`` where:
      * V[0] = legendary ``primary`` per normal ``primary`` invested
      * configs = per-tier ``{cast_prod, cast_quality, recycle_quality}``

    The math mirrors :func:`solve_lds_shuffle_loop` (which is now a thin
    wrapper around this function) but is parametrised over the recipe pair.

    ``inherent_prod`` defaults to ``MACHINE_INHERENT_PROD`` for the cast
    recipe's machine.  ``cast_slots`` defaults to the machine's module
    slots (via :func:`cli.build_machine_module_slots`).
    """
    cast_recipe = _recipe_by_key(data, candidate.recipe_key)
    rec_recipe = _recipe_by_key(data, candidate.recycle_recipe_key)
    if cast_recipe is None or rec_recipe is None:
        return 0.0, {}

    # The "primary" must be a recycler output (the loop only re-feeds what
    # the recycler returns).  If the primary is also a cast ingredient, the
    # in-per-cast amount is taken from the cast recipe; if it isn't (e.g.
    # foundry-LDS where copper-plate is a recycler return but the cast uses
    # molten-copper instead), then the loop doesn't self-feed for that
    # primary — fall back to a 0-yield result.
    primary_in_per_cast = _recipe_ing_amount(cast_recipe, primary)
    primary_back_per_output = _recipe_result_amount(rec_recipe, primary)
    if primary_in_per_cast <= 0 or primary_back_per_output <= 0:
        return 0.0, {}

    # Minimum-ingredient-quality rule (Q2): frame loop state as ingredient sets.
    # Set retention is the minimum return ratio across all solid ingredients of
    # the candidate recipe returned by the recycler.
    set_members = [
        ing for ing in candidate.solid_ingredients
        if _recipe_result_amount(rec_recipe, ing) > 0 and _recipe_ing_amount(cast_recipe, ing) > 0
    ]
    if not set_members:
        return 0.0, {}

    set_retention = min(
        _recipe_result_amount(rec_recipe, ing) / _recipe_ing_amount(cast_recipe, ing)
        for ing in set_members
    )

    # Determine inherent prod from the cast machine.
    if inherent_prod is None:
        machine_key, _ = cli.get_machine(
            cli.recipe_categories(cast_recipe), 3, "electric",
        )
        inherent_prod = MACHINE_INHERENT_PROD.get(machine_key, 0.0)

    # Determine module slots for the cast machine.
    if cast_slots is None:
        machine_key, _ = cli.get_machine(
            cli.recipe_categories(cast_recipe), 3, "electric",
        )
        slots_map = cli.build_machine_module_slots(data)
        cast_slots = int(slots_map.get(machine_key, 0))
        if cast_slots <= 0:
            cast_slots = 4  # safe default

    output_per_cast = _recipe_result_amount(cast_recipe, candidate.output_item)
    if output_per_cast <= 0:
        return 0.0, {}

    V = _seed_value_vector(target_tier)
    configs: dict[int, dict] = {}

    cast_allow_prod = bool(cast_recipe.get("allow_productivity", False))
    for t in range(target_tier - 1, -1, -1):
        best_v = -1.0
        best_cfg = None
        for cp in range(cast_slots + 1):
            if not cast_allow_prod and cp > 0:
                continue
            for cq in range(cast_slots - cp + 1):
                for rq in range(RECYCLER_SLOTS + 1):
                    prod = inherent_prod + research_prod + _prod_bonus(
                        cp, prod_module_tier, module_quality,
                    )
                    if prod > 3.0:
                        prod = 3.0
                    per_input_yield = (1.0 + prod) * set_retention

                    q_cast = _quality_chance(cq, quality_module_tier, module_quality)
                    q_rec = _quality_chance(rq, quality_module_tier, module_quality)

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


# Cached LDS candidate (dataset-static).
_LDS_CANDIDATE_CACHE: dict[int, ShuffleCandidate | None] = {}


def _lds_candidate(data: dict) -> ShuffleCandidate | None:
    """Convenience: find the LDS candidate (foundry variant) in the dataset."""
    cached = _LDS_CANDIDATE_CACHE.get(id(data))
    if cached is not None or id(data) in _LDS_CANDIDATE_CACHE:
        return cached
    for c in enumerate_shuffle_candidates(data):
        if c.output_item == "low-density-structure":
            _LDS_CANDIDATE_CACHE[id(data)] = c
            return c
    _LDS_CANDIDATE_CACHE[id(data)] = None
    return None


def solve_lds_shuffle_loop(
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
    prod_module_tier: int = 3,
    research_prod: float = 0.0,
    foundry_inherent_prod: float = 0.5,
    target_tier: int = 4,
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

    Implemented as a thin wrapper around :func:`solve_shuffle_loop` for
    backwards compatibility with the V2 LDS-only API.
    """
    candidate = _lds_candidate(data)
    if candidate is None:
        return 0.0, {}
    return solve_shuffle_loop(
        candidate, "plastic-bar", data,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        prod_module_tier=prod_module_tier,
        research_prod=research_prod,
        inherent_prod=foundry_inherent_prod,
        cast_slots=4,
        target_tier=target_tier,
    )


def compute_shuffle_stage(
    candidate: ShuffleCandidate,
    primary: str,
    legendary_primary_per_min: float,
    data: dict,
    *,
    module_quality: str,
    quality_module_tier: int = 3,
    prod_module_tier: int = 3,
    research_prod: float = 0.0,
    inherent_prod: float | None = None,
    cast_slots: int | None = None,
    cast_speed: float | None = None,
    recycler_speed: float = RECYCLER_SPEED,
    machine_quality: str = "normal",
    target_tier: int = 4,
) -> dict | None:
    """Size a generic cross-item shuffle stage producing ``legendary_primary_per_min``.

    Returns a dict consumed by :func:`plan` with keys:

      * role: "cross-item-shuffle"
      * shuffle: short tag (the candidate's output_item)
      * primary: the legendary-bearing ingredient
      * machine: cast-machine + recycler
      * cast_machine: e.g. "foundry"
      * <cast>_machines, recycler_machines, machine_count
      * yield_per_normal_primary, legendary_primary_per_min, normal_primary_in_per_min
      * byproduct_legendary: {item: rate, ...}  (other recycler outputs)
      * fluid_demand: {item: rate, ...}
      * configs_per_tier
      * recipe: "<cast> + <output>-recycling"

    Returns ``None`` if recipes are missing or yield is zero (caller should
    fall back to asteroid path).
    """
    if legendary_primary_per_min <= 0:
        return None
    cast_recipe = _recipe_by_key(data, candidate.recipe_key)
    rec_recipe = _recipe_by_key(data, candidate.recycle_recipe_key)
    if cast_recipe is None or rec_recipe is None:
        return None

    primary_in_per_cast = _recipe_ing_amount(cast_recipe, primary)
    primary_back_per_output = _recipe_result_amount(rec_recipe, primary)
    output_per_cast = _recipe_result_amount(cast_recipe, candidate.output_item)
    if primary_in_per_cast <= 0 or primary_back_per_output <= 0 or output_per_cast <= 0:
        return None

    # Lookup machine + speed for the cast recipe.
    machine_key, base_speed = cli.get_machine(
        cli.recipe_categories(cast_recipe), 3, "electric",
    )
    qm_speed_mult = 1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
    if cast_speed is None:
        cast_speed = float(base_speed) * qm_speed_mult
    rec_speed = float(recycler_speed) * qm_speed_mult

    if inherent_prod is None:
        inherent_prod = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
    if cast_slots is None:
        slots_map = cli.build_machine_module_slots(data)
        cast_slots = int(slots_map.get(machine_key, 0))
        if cast_slots <= 0:
            cast_slots = 4

    v, configs = solve_shuffle_loop(
        candidate, primary, data,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        prod_module_tier=prod_module_tier,
        research_prod=research_prod,
        inherent_prod=inherent_prod,
        cast_slots=cast_slots,
        target_tier=target_tier,
    )
    if v <= 0:
        return None

    normal_primary_in_per_min = legendary_primary_per_min / v

    # Approximate machine counts using tier-0 (normal) module config.  Same
    # approximation as the V2 LDS code: most cycles happen at low tiers.
    cfg0 = configs.get(0, {"cast_prod": 0, "cast_quality": 0, "recycle_quality": 4})
    cp0 = cfg0.get("cast_prod", 0)
    prod = inherent_prod + research_prod + _prod_bonus(
        cp0, prod_module_tier, module_quality,
    )
    if prod > 3.0:
        prod = 3.0
    items_per_craft = output_per_cast * (1.0 + prod)
    primary_back_per_craft = items_per_craft * primary_back_per_output

    # Cycle-count multiplier (recirculation): per-cast primary returns
    # divided by primary invested.  Self-sustaining loops clamped at 0.999.
    r_per_cycle = primary_back_per_craft / primary_in_per_cast
    if r_per_cycle >= 1.0 - 1e-9:
        r_per_cycle = 0.999

    total_casts_per_min = (
        normal_primary_in_per_min / primary_in_per_cast / (1.0 - r_per_cycle)
    )
    cast_time = float(cast_recipe.get("energy_required", 1.0))
    cast_machines = total_casts_per_min * cast_time / (
        cast_speed
        * _module_speed_mult(prod_slots=cfg0.get("cast_prod", 0),
                             quality_slots=cfg0.get("cast_quality", 0),
                             prod_tier=prod_module_tier)
        * 60.0
    )

    total_recycles_per_min = total_casts_per_min * items_per_craft
    rec_time = float(rec_recipe.get("energy_required", 0.9375))
    recycler_machines = total_recycles_per_min * rec_time / (
        rec_speed
        * _module_speed_mult(quality_slots=cfg0.get("recycle_quality", RECYCLER_SLOTS))
        * 60.0
    )

    normal_sets_per_min = (
        normal_primary_in_per_min / primary_in_per_cast
    )
    normal_solid_inputs: dict[str, float] = {}
    for ing in cast_recipe.get("ingredients", []):
        iname = ing["name"]
        if iname not in candidate.fluid_ingredients:
            iamt = float(ing.get("amount", 0)) * normal_sets_per_min
            normal_solid_inputs[iname] = iamt

    # Byproducts: non-primary solid recycle returns NOT consumed as set members in loop.
    byproduct_legendary: dict[str, float] = {}
    for byprod in candidate.solid_recycle_returns:
        if byprod == primary or byprod in candidate.solid_ingredients:
            continue  # set member or primary: consumed in loop
        amt = _recipe_result_amount(rec_recipe, byprod)
        if amt <= 0:
            continue
        byproduct_legendary[byprod] = legendary_primary_per_min * (
            amt / primary_back_per_output
        )

    # Fluid demand from cast recipe (quality-transparent, but caller may
    # want to display it).  Includes BOTH cast fluids and recycler fluid
    # outputs (rare, but possible — not modelled here; keep cast-fluids only).
    fluid_demand: dict[str, float] = {}
    for ing in cast_recipe.get("ingredients", []):
        if ing["name"] in candidate.fluid_ingredients:
            fluid_demand[ing["name"]] = float(ing.get("amount", 0)) * total_casts_per_min

    return {
        "role": "cross-item-shuffle",
        "shuffle": candidate.output_item,
        "primary": primary,
        "recipe": f"{candidate.recipe_key} + {candidate.recycle_recipe_key}",
        "cast_machine": machine_key,
        "machine": f"{machine_key}+recycler",
        "machine_count": float(cast_machines + recycler_machines),
        f"{machine_key}_machines": float(cast_machines),
        "cast_machines": float(cast_machines),  # duplicate generic key
        "recycler_machines": float(recycler_machines),
        "yield_per_normal_primary": float(v),
        "yield_per_normal_primary_pct": float(v) * 100.0,
        "legendary_primary_per_min": float(legendary_primary_per_min),
        "normal_primary_in_per_min": float(normal_primary_in_per_min),
        "normal_solid_inputs": normal_solid_inputs,
        "total_casts_per_min": float(total_casts_per_min),
        "total_recycles_per_min": float(total_recycles_per_min),
        "byproduct_legendary": byproduct_legendary,
        "fluid_demand": fluid_demand,
        "configs_per_tier": configs,
        "machine_quality": machine_quality,
    }


def _baseline_cost_for_leaf(
    leaf: str,
    demand: float,
    data: dict,
    *,
    module_quality: str,
    quality_module_tier: int = 3,
    machine_quality: str = "normal",
    chain_stages: list[dict] | None = None,
    target_tier: int = 4,
) -> float:
    """Estimate machines needed to produce ``demand`` legendary ``leaf`` per
    minute via the default (non-shuffle) path.

    Used by :func:`select_shuffles_greedy` to reject shuffles that are
    objectively worse than the baseline.

    For asteroid raws (RAW_TO_CHUNK): cost ≈ asteroid-reprocessing crusher
    count for the demand at the chunk's quality yield.
    For mined raws (MINED_RAW_PLANETS): cost ≈ recycler self-loop count.
    For assembly-stage products: cost ≈ that stage's existing
    ``machine_count`` (already computed by the walker).

    Returns 0.0 (no baseline) if the leaf isn't recognised — the greedy
    treats this as "accept any positive shuffle" since we can't compare.
    """
    if demand <= 0:
        return 0.0
    qm_speed_mult = 1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))

    # Asteroid path: leaf → chunk crushing (quality roll) → ore upcycle recycler
    if leaf in RAW_TO_CHUNK and leaf not in fluids:
        chunk = RAW_TO_CHUNK[leaf]
        crush_recipe_key = ASTEROID_CRUSHING_RECIPES.get(chunk, "")
        crush_recipe = _recipe_by_key(data, crush_recipe_key)
        if crush_recipe is None:
            return float("inf")
        V_ore, ore_configs = solve_mined_raw_self_recycle_loop_full(
            leaf, data, module_quality, quality_module_tier, target_tier,
        )
        q_crusher = _quality_chance(CRUSHER_SLOTS, quality_module_tier, module_quality)
        crush_dist = _tier_skip_probs(q_crusher, 0)
        ore_per_crush = _recipe_result_amount(crush_recipe, leaf)
        yield_per_chunk = ore_per_crush * sum(crush_dist[t] * V_ore[t] for t in range(5))
        if yield_per_chunk <= 0:
            return float("inf")
        normal_chunks = demand / yield_per_chunk
        crushing_time = float(crush_recipe.get("energy_required", 2))
        crush_machines = normal_chunks * crushing_time / (
            CRUSHER_SPEED * qm_speed_mult
            * _module_speed_mult(quality_slots=CRUSHER_SLOTS) * 60.0
        )
        rec_recipe = _recipe_by_key(data, f"{leaf}-recycling")
        rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2
        inflow = [normal_chunks * ore_per_crush * crush_dist[t] for t in range(5)]
        total_recyclings = 0.0
        for t_in in range(target_tier):
            if inflow[t_in] > 0:
                flow = compute_loop_flows(
                    target_tier, ore_configs, quality_module_tier, module_quality,
                    base_retention=0.25, wrap_active=False,
                    wrap_inherent_prod=0.0, wrap_research_prod=0.0,
                    inherent_prod=0.0, research_prod=0.0, t_in=t_in,
                )
                total_recyclings += sum(inflow[t_in] * flow[s] for s in range(target_tier))
        upcycle_machines = total_recyclings * rec_time / (
            RECYCLER_SPEED * qm_speed_mult
            * _module_speed_mult(quality_slots=RECYCLER_SLOTS) * 60.0
        )
        return crush_machines + upcycle_machines

    # Mined raw: recycler self-loop
    if leaf in MINED_RAW_PLANETS:
        v, _ = solve_mined_raw_self_recycle_loop(
            leaf, data, module_quality, quality_module_tier, target_tier,
        )
        if v <= 0:
            return float("inf")
        normal_input = demand / v
        rec_recipe = _recipe_by_key(data, f"{leaf}-recycling")
        retention = (
            _recipe_result_amount(rec_recipe, leaf) if rec_recipe else 0.25
        )
        total_crafts = normal_input / max(1.0 - retention, 1e-6)
        rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2
        return total_crafts * rec_time / (
            RECYCLER_SPEED * qm_speed_mult
            * _module_speed_mult(quality_slots=RECYCLER_SLOTS) * 60.0
        )

    # Assembly product: use the existing chain's machine_count for that stage.
    if chain_stages:
        for st in chain_stages:
            if st.get("product") == leaf:
                stage_rate = float(st.get("rate_per_min", 0.0))
                stage_machines = float(st.get("machine_count", 0.0))
                if stage_rate > 0:
                    # Pro-rate the stage's machines to the demand portion.
                    return stage_machines * (demand / stage_rate)
                return stage_machines

    # Unknown — let any positive shuffle through.
    return 0.0


def select_shuffles_greedy(
    legendary_leaves: dict[str, float],
    candidates: list[ShuffleCandidate],
    data: dict,
    *,
    module_quality: str,
    quality_module_tier: int = 3,
    prod_module_tier: int = 3,
    research_levels: dict[str, int] | None = None,
    machine_quality: str = "normal",
    planets: list[str] | frozenset[str] | None = None,
    target_tier: int = 4,
) -> list[dict]:
    """Per-leaf greedy: activate shuffles that produce the chain's legendary leaves."""
    if not legendary_leaves or not candidates:
        return []
    research_levels = research_levels or {}

    planets_fs = frozenset(planets) if planets is not None else frozenset({"nauvis"})
    planet_props = _combined_planet_props(data, planets_fs)

    fluids = build_fluid_set(data)
    _ing_reachable_cache: dict[str, bool] = {}
    def _is_ing_reachable(ing_item: str) -> bool:
        if ing_item in _ing_reachable_cache:
            return _ing_reachable_cache[ing_item]
        try:
            walk_recipe_tree(
                ing_item, 1.0, data, research_levels, 3,
                fluids, planet_props, planets_fs,
                tech_state=ALL_TECH_UNLOCKED,
            )
            _ing_reachable_cache[ing_item] = True
            return True
        except Exception:
            _ing_reachable_cache[ing_item] = False
            return False

    remaining = dict(legendary_leaves)
    # Track activated (recipe, primary) → accumulated legendary primary rate
    # so multiple selections of the same shuffle merge into one stage.
    activated: dict[tuple[str, str], float] = {}
    covered_byproducts: dict[str, float] = defaultdict(float)

    # Iterate by descending demand so we make decisions for high-demand
    # leaves first (their chosen shuffle's byproducts may cover lower-
    # demand leaves "for free").
    sorted_leaves = sorted(remaining.items(), key=lambda kv: -kv[1])

    for leaf, _ in sorted_leaves:
        # Net demand after credits from already-activated shuffles.
        net_demand = remaining.get(leaf, 0.0) - covered_byproducts.get(leaf, 0.0)
        if net_demand <= 0:
            continue  # already covered by a chosen shuffle's byproducts

        best: tuple[float, ShuffleCandidate, str, dict] | None = None
        for cand in candidates:
            # Check if cast recipe or any solid ingredient is unreachable on unlocked planets
            cast_rec = _recipe_by_key(data, cand.recipe_key)
            if cast_rec is None:
                continue
            if planet_props and not cli._recipe_valid_for_planet(cast_rec, planet_props):
                continue
            ing_unreachable = False
            for ing in cand.solid_ingredients:
                if not _is_ing_reachable(ing):
                    ing_unreachable = True
                    break
            if ing_unreachable:
                continue

            # Determine valid primaries for this candidate.  A primary must
            # be both fed in (solid_ingredients) AND returned (recycle).
            valid_primaries = (
                set(cand.solid_ingredients) & set(cand.solid_recycle_returns)
            )
            if not valid_primaries:
                continue

            # Case A: leaf is a valid primary of this candidate.
            if leaf in valid_primaries:
                research_prod = _research_prod_for_recipe(
                    cand.recipe_key, research_levels,
                )
                stage = compute_shuffle_stage(
                    cand, leaf, net_demand, data,
                    module_quality=module_quality,
                    quality_module_tier=quality_module_tier,
                    prod_module_tier=prod_module_tier,
                    research_prod=research_prod,
                    machine_quality=machine_quality,
                    target_tier=target_tier,
                )
                if stage is None:
                    continue
                cost = stage["machine_count"]
                if best is None or cost < best[0]:
                    best = (cost, cand, leaf, stage)

            # Case B: leaf is a byproduct (in solid_recycle_returns but
            # not solid_ingredients).  We can still activate the shuffle
            # to satisfy the leaf — pick a primary that's NOT in
            # legendary_leaves (so we don't disturb other choices) OR pick
            # the highest-demand primary candidate (so other leaves
            # benefit too).
            elif leaf in cand.solid_recycle_returns:
                # Pick the primary with highest leaf demand among valid
                # primaries (so the activated shuffle helps other leaves
                # too).  If none of the valid primaries are leaves,
                # picking one means we'd produce extra legendary primary
                # for no purpose — skip in that case.
                primary_demand = [
                    (remaining.get(p, 0.0), p) for p in valid_primaries
                ]
                primary_demand.sort(reverse=True)
                if not primary_demand or primary_demand[0][0] <= 0:
                    continue
                primary = primary_demand[0][1]
                # Scale shuffle to cover THIS leaf's demand via byproduct,
                # which means producing more legendary primary than needed
                # (overflow).  Compute scale: byprod_per_legendary_primary
                # × x = net_demand → x = net_demand / ratio.
                rec_recipe = _recipe_by_key(data, cand.recycle_recipe_key)
                if rec_recipe is None:
                    continue
                amt_leaf = _recipe_result_amount(rec_recipe, leaf)
                amt_primary = _recipe_result_amount(rec_recipe, primary)
                if amt_leaf <= 0 or amt_primary <= 0:
                    continue
                ratio = amt_leaf / amt_primary
                if ratio <= 0:
                    continue
                primary_legendary_needed = net_demand / ratio
                research_prod = _research_prod_for_recipe(
                    cand.recipe_key, research_levels,
                )
                stage = compute_shuffle_stage(
                    cand, primary, primary_legendary_needed, data,
                    module_quality=module_quality,
                    quality_module_tier=quality_module_tier,
                    prod_module_tier=prod_module_tier,
                    research_prod=research_prod,
                    machine_quality=machine_quality,
                    target_tier=target_tier,
                )
                if stage is None:
                    continue
                cost = stage["machine_count"]
                if best is None or cost < best[0]:
                    best = (cost, cand, primary, stage)

        if best is None:
            continue
        cost, cand, primary, stage = best

        key = (cand.recipe_key, primary)
        prior = activated.get(key, 0.0)
        activated[key] = prior + float(stage["legendary_primary_per_min"])
        # Track byproduct credits from this stage; remove leaves it covers.
        for byprod, byrate in stage["byproduct_legendary"].items():
            covered_byproducts[byprod] += float(byrate)
        covered_byproducts[primary] += float(stage["legendary_primary_per_min"])

    # Re-emit each activated (recipe, primary) at its accumulated total
    # so the caller sees one stage per shuffle (not one per leaf).
    chosen: list[dict] = []
    cand_by_key = {c.recipe_key: c for c in candidates}
    for (recipe_key, primary), total_rate in activated.items():
        cand = cand_by_key[recipe_key]
        research_prod = _research_prod_for_recipe(recipe_key, research_levels)
        stage = compute_shuffle_stage(
            cand, primary, total_rate, data,
            module_quality=module_quality,
            quality_module_tier=quality_module_tier,
            prod_module_tier=prod_module_tier,
            research_prod=research_prod,
            machine_quality=machine_quality,
            target_tier=target_tier,
        )
        if stage is not None:
            chosen.append(stage)
    return chosen


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
    target_tier: int = 4,
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

    Implemented as a thin wrapper around :func:`compute_shuffle_stage` for
    backwards compatibility with the V2 LDS-only API.  Translates generic
    keys back to the V2 schema (``foundry_machines``,
    ``yield_per_normal_plastic``, etc.) so callers don't need to change.
    """
    candidate = _lds_candidate(data)
    if candidate is None:
        return None
    g = compute_shuffle_stage(
        candidate, "plastic-bar", legendary_plastic_per_min, data,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        prod_module_tier=prod_module_tier,
        research_prod=research_prod,
        inherent_prod=foundry_inherent_prod,
        cast_slots=4,
        cast_speed=foundry_speed,
        recycler_speed=recycler_speed,
        target_tier=target_tier,
    )
    if g is None:
        return None
    # Translate generic schema → V2 LDS schema.
    return {
        "yield_per_normal_plastic": g["yield_per_normal_primary"],
        "legendary_plastic_per_min": g["legendary_primary_per_min"],
        "normal_plastic_in_per_min": g["normal_primary_in_per_min"],
        "total_castings_per_min": g["total_casts_per_min"],
        "total_recycles_per_min": g["total_recycles_per_min"],
        "foundry_machines": g["cast_machines"],
        "recycler_machines": g["recycler_machines"],
        "byproduct_legendary": dict(g["byproduct_legendary"]),
        "fluid_demand": dict(g["fluid_demand"]),
        "configs_per_tier": g["configs_per_tier"],
    }


def solve_mined_raw_self_recycle_loop_full(
    raw_key: str,
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
    target_tier: int = 4,
) -> tuple[list[float], dict]:
    """DP for target-tier-raw yield vector per raw item at each tier t (0..4).

    Returns (V, configs_per_tier) where V[t] is expected target-tier items
    produced per 1 item entering the recycler self-loop at tier t.
    """
    rec_key = f"{raw_key}-recycling"
    rec = _recipe_by_key(data, rec_key)
    if rec is None:
        return _seed_value_vector(target_tier), {}

    retention = _recipe_result_amount(rec, raw_key)
    V = _seed_value_vector(target_tier)
    configs: dict[int, dict] = {}

    for t in range(target_tier - 1, -1, -1):
        best_v = -1.0
        best_cfg = None
        for q in range(RECYCLER_SLOTS + 1):
            q_total = _quality_chance(q, quality_module_tier, module_quality)
            probs = _tier_skip_probs(q_total, t)
            probs = [p * retention for p in probs] if retention > 0 else probs
            if retention > 0:
                stay = probs[0]
            else:
                stay = 0.0
            if stay >= 1.0 - 1e-15:
                v = 0.0
            else:
                numer = sum(probs[k] * V[t + k] for k in range(1, len(probs)))
                if retention > 0:
                    v = numer / (1.0 - stay)
                else:
                    v = numer
            if v > best_v:
                best_v = v
                best_cfg = {"craft_prod": 0, "craft_quality": 0, "recycle_quality": q}
        V[t] = max(best_v, 0.0)
        configs[t] = best_cfg or {"craft_prod": 0, "craft_quality": 0, "recycle_quality": 0}

    return V, configs


def solve_mined_raw_self_recycle_loop(
    raw_key: str,
    data: dict,
    module_quality: str,
    quality_module_tier: int = 3,
    target_tier: int = 4,
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

    Returns (V[0], configs_per_tier).
    """
    V, configs = solve_mined_raw_self_recycle_loop_full(
        raw_key, data, module_quality, quality_module_tier, target_tier
    )
    return V[0], configs


# ---------------------------------------------------------------------------
# Fulgora scrap-recycling quality source (auto-enabled when Fulgora unlocked)
# ---------------------------------------------------------------------------
#
# On Fulgora the plentiful raw is *scrap*, and recycling it (with quality
# modules in the recyclers) yields a basket of quality intermediates directly —
# battery, steel-plate, circuits, holmium-ore, plus cascades like
# iron-gear-wheel → iron-plate.  This is the idiomatic Fulgora quality source
# and is almost always far cheaper than importing asteroid chunks from orbit.
#
# Model (documented assumptions):
#   * Scrap is a plentiful normal-quality input (mined on Fulgora); we report
#     the scrap/min the recycler array consumes.
#   * Every recycler in the scrap → … → item cascade runs RECYCLER_SLOTS
#     quality modules, so each recycle STEP is one independent quality roll.
#   * An item reached ``d`` recycle-steps from scrap has had ``d`` quality
#     rolls, so its target-or-better fraction is P(tier ≥ target after d rolls).
#   * One scrap produces the whole basket simultaneously, so the binding (most
#     scrap-hungry) demanded leaf sets the scrap rate; the other outputs are
#     credited against chain demand or counted as overflow.
#   * Sub-target items that cannot climb further are part of the overflow.

SCRAP_RECYCLING_RECIPE = "scrap-recycling"
_SCRAP_CASCADE_CACHE: dict[int, dict] = {}


def build_scrap_cascade(data: dict, max_depth: int = 6) -> dict:
    """Introspect the scrap recycling cascade (quality-independent, cached).

    Returns ``{"depth_amounts", "recycle_amounts", "recycle_time"}``:
      * ``depth_amounts`` — ``{item: {depth: amount_per_scrap}}`` for every
        item reachable from scrap via ``<item>-recycling`` recipes.
      * ``recycle_amounts`` — ``{item: amount_recycled_per_scrap}`` for each
        item that is itself recycled in the cascade (drives recycler counts).
      * ``recycle_time`` — ``{item: energy_required of its recycling recipe}``.
    """
    cached = _SCRAP_CASCADE_CACHE.get(id(data))
    if cached is not None:
        return cached
    fluids = build_fluid_set(data)
    recipes_by_key = {r["key"]: r for r in data.get("recipes", [])}
    # Mined raws (ores) are never a *useful* scrap product — recycling a base
    # material like iron-plate back to iron-ore is a strict downgrade.  Stop the
    # cascade at ores so plates/circuits stay the terminals, not the ores below
    # them.  (Scrap itself is the explicit cascade root, never skipped here.)
    mined_raws: set[str] = set()
    for res in data.get("resources", []):
        for r in res.get("results", []):
            if r.get("name") and r["name"] != "scrap":
                mined_raws.add(r["name"])

    def rec_outputs(item: str) -> dict[str, float] | None:
        r = recipes_by_key.get(f"{item}-recycling")
        if r is None:
            return None
        out: dict[str, float] = {}
        for res in r.get("results", []):
            if res.get("name") == item:
                continue
            amt = res.get("amount")
            if amt is None:
                amt = (res.get("amount_min", 0) + res.get("amount_max", 0)) / 2.0
            out[res["name"]] = out.get(res["name"], 0.0) + (
                float(amt) * float(res.get("probability", 1.0))
            )
        return out

    depth_amounts: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    recycle_amounts: dict[str, float] = defaultdict(float)
    recycle_time: dict[str, float] = {}

    cur = {"scrap": 1.0}
    for depth in range(max_depth):
        nxt: dict[str, float] = defaultdict(float)
        for item, amt in cur.items():
            outs = rec_outputs(item)
            if outs is None:
                continue
            recycle_amounts[item] += amt
            if item not in recycle_time:
                r = recipes_by_key.get(f"{item}-recycling")
                recycle_time[item] = float(r.get("energy_required", 0.2)) if r else 0.2
            for k, v in outs.items():
                if k in mined_raws:
                    continue  # don't degrade a base material back into ore
                produced = amt * v
                depth_amounts[k][depth + 1] += produced
                if k not in fluids:
                    nxt[k] += produced
        cur = dict(nxt)
        if not cur:
            break

    result = {
        "depth_amounts": {k: dict(v) for k, v in depth_amounts.items()},
        "recycle_amounts": dict(recycle_amounts),
        "recycle_time": recycle_time,
    }
    _SCRAP_CASCADE_CACHE[id(data)] = result
    return result


def _compose_quality_rolls(q_chance: float, d: int) -> list[float]:
    """Tier distribution (len 5) after ``d`` independent quality rolls starting
    from normal (tier 0).  Each roll uses the game's tier-skip spread."""
    dist = [1.0, 0.0, 0.0, 0.0, 0.0]
    for _ in range(max(0, d)):
        nxt = [0.0] * 5
        for t in range(5):
            if dist[t] <= 0.0:
                continue
            probs = _tier_skip_probs(q_chance, t)
            for k, p in enumerate(probs):
                nxt[t + k] += dist[t] * p
        dist = nxt
    return dist


def _compose_miner_and_recycler_rolls(q_miner: float, q_rec: float, d: int) -> list[float]:
    """Tier distribution (len 5) after 1 miner roll (chance q_miner) and d recycler
    rolls (chance q_rec) starting from normal (tier 0)."""
    dist = [1.0, 0.0, 0.0, 0.0, 0.0]
    if q_miner > 0.0:
        nxt = [0.0] * 5
        for t in range(5):
            if dist[t] <= 0.0:
                continue
            probs = _tier_skip_probs(q_miner, t)
            for k, p in enumerate(probs):
                nxt[t + k] += dist[t] * p
        dist = nxt
    for _ in range(max(0, d)):
        nxt = [0.0] * 5
        for t in range(5):
            if dist[t] <= 0.0:
                continue
            probs = _tier_skip_probs(q_rec, t)
            for k, p in enumerate(probs):
                nxt[t + k] += dist[t] * p
        dist = nxt
    return dist


def _is_upcyclable_scrap_leaf(item_key: str) -> bool:
    return item_key in ("iron-plate", "copper-plate")


def compute_loop_flows(
    target_tier: int,
    configs: dict,
    quality_module_tier: int,
    module_quality: str,
    base_retention: float,
    wrap_active: bool,
    wrap_inherent_prod: float,
    wrap_research_prod: float,
    inherent_prod: float,
    research_prod: float,
    t_in: int,
) -> list[float]:
    """Solve for flow[s] (rate entering recycler at tier s) for a unit input at t_in."""
    flow = [0.0] * 5
    transition_rates = {}
    stay_prob = [0.0] * 5
    
    for j in range(target_tier):
        cfg = configs[j]
        q_rec = _quality_chance(cfg["recycle_quality"], quality_module_tier, module_quality)
        if wrap_active:
            wp_val = cfg.get("wrap_prod", 0)
            wrap_prod = wrap_inherent_prod + wrap_research_prod + _prod_bonus(wp_val, 3, module_quality)
            if wrap_prod > 3.0:
                wrap_prod = 3.0
            retention = base_retention * (1.0 + wrap_prod)
            q_wrap = _quality_chance(cfg.get("wrap_quality", 0), quality_module_tier, module_quality)
        else:
            cp_val = cfg.get("craft_prod", 0)
            prod = inherent_prod + research_prod + _prod_bonus(cp_val, 3, module_quality)
            if prod > 3.0:
                prod = 3.0
            retention = base_retention * (1.0 + prod)
            q_wrap = 0.0
            
        wrap_probs = _tier_skip_probs(q_wrap, j)
        composite_up = [0.0] * (5 - j)
        for i, pwi in enumerate(wrap_probs):
            if pwi == 0.0:
                continue
            rec_probs = _tier_skip_probs(q_rec, j + i)
            for k, prj in enumerate(rec_probs):
                if i + k < len(composite_up):
                    composite_up[i + k] += pwi * prj
                    
        stay_prob[j] = retention * composite_up[0]
        rates = {}
        for k in range(1, len(composite_up)):
            if j + k < 5:
                rates[j + k] = retention * composite_up[k]
        transition_rates[j] = rates

    if stay_prob[t_in] < 1.0:
        flow[t_in] = 1.0 / (1.0 - stay_prob[t_in])
    else:
        flow[t_in] = 0.0
        
    for s in range(t_in + 1, target_tier):
        incoming = sum(flow[j] * transition_rates[j].get(s, 0.0) for j in range(t_in, s))
        if stay_prob[s] < 1.0:
            flow[s] = incoming / (1.0 - stay_prob[s])
        else:
            flow[s] = 0.0
            
    return flow


def scrap_target_yield(
    item: str,
    cascade: dict,
    target_tier: int,
    quality_module_tier: int,
    module_quality: str,
    q_miner: float = 0.0,
    V_loop: list[float] | None = None,
) -> float:
    """Target-tier ``item`` produced per 1 scrap recycled.

    Sums, over every cascade depth at which ``item`` appears, the amount made
    at that depth times P(tier ≥ target after that many quality rolls).
    """
    q = _quality_chance(RECYCLER_SLOTS, quality_module_tier, module_quality)
    total = 0.0
    for d, amt in cascade["depth_amounts"].get(item, {}).items():
        if d <= 0:
            continue
        dist = _compose_miner_and_recycler_rolls(q_miner, q, d)
        if V_loop is not None:
            total += amt * sum(dist[t] * V_loop[t] for t in range(5))
        else:
            total += amt * sum(dist[target_tier:])
    return total


def compute_scrap_source(
    demanded_leaves: dict[str, float],
    data: dict,
    *,
    target_tier: int,
    quality_module_tier: int,
    module_quality: str,
    machine_quality: str = "normal",
    miner_type: str = "electric",
    miner_quality_modules: bool = True,
    scrap_upcycle_loops: bool = True,
    assembler_level: int = 3,
    tech_state: dict[str, int],
    research_levels: dict[str, int] | None = None,
    planets: frozenset[str] | None = None,
    forbid_ore_routes: bool = False,
    _cache: _DispatchCache | None = None,
) -> dict | None:
    """Size a Fulgora scrap-recycling quality source for ``demanded_leaves``."""
    q_miner = 0.0
    if miner_quality_modules and module_quality:
        drill_key = "big-mining-drill" if miner_type == "big" else "electric-mining-drill"
        slots_map = cli.build_machine_module_slots(data)
        miner_slots = slots_map.get(drill_key, 0)
        q_miner = _quality_chance(miner_slots, quality_module_tier, module_quality)

    V_loops = {}
    loop_configs = {}
    loop_routes = {}
    loop_machine_infos = {}

    if scrap_upcycle_loops and module_quality:
        recipe_idx = cli.build_recipe_index(data)
        fluids = build_fluid_set(data)
        planet_props = _combined_planet_props(data, planets or frozenset({"fulgora"}))
        locked_machines = _tech_locked_machines(tech_state)
        slots_map = cli.build_machine_module_slots(data)
        
        for leaf in demanded_leaves:
            if _is_upcyclable_scrap_leaf(leaf):
                craft_recipe = _pick_recipe_fluid_preferred(
                    leaf, recipe_idx, fluids, planets or frozenset({"fulgora"}), planet_props,
                    locked_machines=locked_machines, assembler_level=assembler_level,
                    forbid_ore_routes=forbid_ore_routes,
                )
                if craft_recipe is None:
                    continue
                mr = _machine_for_recipe(craft_recipe, assembler_level, locked_machines)
                if mr is None:
                    continue
                machine_key, machine_speed = mr
                machine_slots = slots_map.get(machine_key, 0)
                machine_allow_prod = True
                inherent_prod = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
                research_prod = _research_prod_for_recipe(craft_recipe["key"], research_levels or {})
                
                wrap_route, wrap_machine_info = _choose_wrap_route(
                    leaf, data,
                    assembler_level=assembler_level,
                    locked_machines=locked_machines,
                    planet_props=planet_props,
                    module_quality=module_quality,
                    quality_module_tier=quality_module_tier,
                    prod_module_tier=3,
                    target_tier=target_tier,
                    machine_key=machine_key,
                    machine_slots=machine_slots,
                    machine_allow_prod=machine_allow_prod,
                    inherent_prod=inherent_prod,
                    research_prod=research_prod,
                    research_levels=research_levels or {},
                    _cache=_cache,
                )
                
                v_total, configs = solve_self_recycle_target_loop_memoized(
                    leaf, data,
                    machine_key=machine_key,
                    machine_slots=machine_slots,
                    machine_allow_prod=machine_allow_prod,
                    inherent_prod=inherent_prod,
                    research_prod=research_prod,
                    module_quality=module_quality,
                    prod_module_tier=3,
                    quality_module_tier=quality_module_tier,
                    target_tier=target_tier,
                    _cache=_cache,
                    wrap_route=wrap_route,
                    wrap_machine_slots=wrap_machine_info["machine_slots"] if wrap_machine_info else 0,
                    wrap_allow_prod=wrap_machine_info["allow_prod"] if wrap_machine_info else False,
                    wrap_inherent_prod=wrap_machine_info["inherent_prod"] if wrap_machine_info else 0.0,
                    wrap_research_prod=0.0,
                )
                
                V_loop = [0.0] * 5
                for t in range(5):
                    if t >= target_tier:
                        V_loop[t] = 1.0
                    elif t in configs:
                        V_loop[t] = configs[t].get("v_rec", 0.0)
                        
                V_loops[leaf] = V_loop
                loop_configs[leaf] = configs
                loop_routes[leaf] = wrap_route
                loop_machine_infos[leaf] = (machine_key, machine_speed, machine_slots, machine_allow_prod, inherent_prod, research_prod, wrap_machine_info)

    cascade = build_scrap_cascade(data)
    yields = {
        leaf: scrap_target_yield(
            leaf, cascade, target_tier, quality_module_tier, module_quality,
            q_miner=q_miner,
            V_loop=V_loops.get(leaf),
        )
        for leaf in demanded_leaves
    }
    usable = {leaf: y for leaf, y in yields.items() if y > 0 and demanded_leaves[leaf] > 0}
    if not usable:
        return None

    scrap_per_min = 0.0
    binding_leaf = None
    for leaf, y in usable.items():
        need = demanded_leaves[leaf] / y
        if need > scrap_per_min:
            scrap_per_min = need
            binding_leaf = leaf
    if scrap_per_min <= 0:
        return None

    covered: dict[str, float] = {}
    overflow: dict[str, float] = {}
    for leaf, y in yields.items():
        produced = scrap_per_min * y
        demand = demanded_leaves[leaf]
        covered[leaf] = min(produced, demand)
        surplus = produced - demand
        if surplus > 1e-9:
            overflow[leaf] = surplus

    qm_speed_mult = 1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
    recycle_load = sum(
        cascade["recycle_amounts"].get(it, 0.0) * cascade["recycle_time"].get(it, 0.2)
        for it in cascade["recycle_amounts"]
    )
    machine_count = scrap_per_min * recycle_load / (
        RECYCLER_SPEED * qm_speed_mult
        * _module_speed_mult(quality_slots=RECYCLER_SLOTS) * 60.0
    )

    q = _quality_chance(RECYCLER_SLOTS, quality_module_tier, module_quality)
    stage = {
        "role": "scrap-quality-source",
        "recipe": SCRAP_RECYCLING_RECIPE,
        "machine": "recycler",
        "machine_count": machine_count,
        "scrap_per_min": scrap_per_min,
        "binding_leaf": binding_leaf,
        "covered": covered,
        "overflow": overflow,
        "recycler_quality_chance": q,
        "module_config_per_tier": {
            QUALITY_TIERS[t]: {
                "craft": "n/a",
                "recycle": f"{RECYCLER_SLOTS}x quality-{quality_module_tier}-{module_quality}",
            }
            for t in range(target_tier)
        },
    }

    upcycle_stages = []
    for leaf in V_loops:
        configs = loop_configs[leaf]
        wrap_route = loop_routes[leaf]
        (machine_key, machine_speed, machine_slots, machine_allow_prod, inherent_prod, research_prod, wrap_machine_info) = loop_machine_infos[leaf]
        
        wrap_active = wrap_route is not None
        if wrap_active:
            base_retention = float(wrap_route["retention"])
            wrap_inherent_prod = wrap_machine_info["inherent_prod"]
            wrap_research_prod = 0.0
            loop_recycler_time = float(wrap_route["recycler_time"])
            loop_craft_time = float(wrap_route["craft_time"])
        else:
            shortcut = build_recycle_shortcuts(data).get(leaf)
            base_retention = float(shortcut["retention"]) if shortcut else RECYCLER_RETENTION
            wrap_inherent_prod = 0.0
            wrap_research_prod = 0.0
            loop_recycler_time = float(shortcut["recycler_time"]) if shortcut else 0.2
            loop_craft_time = float(shortcut["craft_time"]) if shortcut else 0.0
            
        total_flow = [0.0] * 5
        for d, amt in cascade["depth_amounts"].get(leaf, {}).items():
            if d <= 0:
                continue
            q_rec_cascade = _quality_chance(RECYCLER_SLOTS, quality_module_tier, module_quality)
            dist_depth = _compose_miner_and_recycler_rolls(q_miner, q_rec_cascade, d)
            
            for t_in in range(target_tier):
                rate_in_t = scrap_per_min * amt * dist_depth[t_in]
                if rate_in_t <= 0.0:
                    continue
                flow = compute_loop_flows(
                    target_tier, configs, quality_module_tier, module_quality,
                    base_retention, wrap_active, wrap_inherent_prod, wrap_research_prod,
                    inherent_prod, research_prod, t_in
                )
                for s in range(target_tier):
                    total_flow[s] += rate_in_t * flow[s]
                    
        craft_machines = 0.0
        recycler_machines = 0.0
        
        for s in range(target_tier):
            if total_flow[s] <= 0.0:
                continue
            cfg = configs[s]
            
            q_rec_slots = cfg["recycle_quality"]
            rec_speed_mult = _module_speed_mult(quality_slots=q_rec_slots)
            rec_count_s = (total_flow[s] * loop_recycler_time) / (
                RECYCLER_SPEED * qm_speed_mult * rec_speed_mult * 60.0
            )
            recycler_machines += rec_count_s
            
            if wrap_active:
                cp_val = cfg.get("wrap_prod", 0)
                cq_val = cfg.get("wrap_quality", 0)
                craft_speed = _machine_speed(wrap_machine_info["machine_key"])
            else:
                cp_val = cfg.get("craft_prod", 0)
                cq_val = cfg.get("craft_quality", 0)
                craft_speed = machine_speed
                
            craft_speed_mult = _module_speed_mult(quality_slots=cq_val, prod_slots=cp_val)
            craft_count_s = (total_flow[s] * loop_craft_time) / (
                craft_speed * qm_speed_mult * craft_speed_mult * 60.0
            )
            craft_machines += craft_count_s
            
        if craft_machines > 0.0 or recycler_machines > 0.0:
            up_stage = {
                "role": "scrap-upcycle-loop",
                "target": leaf,
                "recipe": f"{leaf}-upcycle-loop",
                "machine": wrap_machine_info["machine_key"] if wrap_active else machine_key,
                "machine_count": craft_machines + recycler_machines,
                "craft_machines": craft_machines,
                "recycler_machines": recycler_machines,
                "container": wrap_route["container"] if wrap_active else None,
                "container_machines": craft_machines if wrap_active else 0.0,
                "rate_per_min": scrap_per_min * yields[leaf],
                "module_config_per_tier": {
                    QUALITY_TIERS[t]: {
                        "craft": (
                            f"{configs[t].get('craft_prod',0)}p+"
                            f"{configs[t].get('craft_quality',0)}q "
                            f"(t{quality_module_tier} {module_quality})"
                        ) if not wrap_active else "n/a",
                        "recycle": (
                            f"{configs[t].get('recycle_quality',0)}q "
                            f"(t{quality_module_tier} {module_quality})"
                        ),
                        **({
                            "wrap": (
                                f"{configs[t].get('wrap_prod',0)}p+"
                                f"{configs[t].get('wrap_quality',0)}q "
                                f"(t{quality_module_tier} {module_quality})"
                            )
                        } if wrap_active else {})
                    }
                    for t in range(target_tier)
                }
            }
            upcycle_stages.append(up_stage)

    return {
        "scrap_per_min": scrap_per_min,
        "machine_count": machine_count,
        "covered": covered,
        "overflow": overflow,
        "binding_leaf": binding_leaf,
        "stage": stage,
        "upcycle_stages": upcycle_stages,
    }


def scrap_terminal_set(
    scrap_reachable: set[str],
    item_key: str,
    data: dict,
    fluids: frozenset[str],
) -> frozenset[str]:
    """Which scrap-reachable items should be sourced *directly* from scrap.

    An item is a scrap terminal when it cannot be crafted from cheaper scrap
    materials — i.e. *no* recipe for it has all solid ingredients scrap-
    reachable while avoiding ore-derived fluids.  Concretely it is a terminal
    when every recipe would pull in a non-scrap-reachable solid (e.g. iron-plate
    needs iron-ore, or its casting variant needs molten-iron which decomposes to
    ore), or it has no craft recipe at all (e.g. holmium-ore).  Items craftable
    from scrap materials plus genuinely local fluids (e.g. battery → iron-plate
    + copper-plate + sulfuric-acid) are left to be crafted.  ``item_key`` is
    never a terminal — the plan must still produce it.

    ``molten-*`` fluids are treated as ore-equivalent (their production consumes
    a mined ore), so a casting recipe does not count as scrap-craftable.
    """
    # Map every craftable output -> list of its recipes (skip recycling/barrels).
    recipes_by_output: dict[str, list[dict]] = defaultdict(list)
    for r in data.get("recipes", []):
        if cli.is_recycling(r):
            continue
        if r.get("subgroup") in ("empty-barrel", "fill-barrel"):
            continue
        for res in r.get("results", []):
            if res.get("name"):
                recipes_by_output[res["name"]].append(r)

    def _scrap_craftable(recipe: dict) -> bool:
        for ing in recipe.get("ingredients", []):
            name = ing["name"]
            if name in fluids:
                if name.startswith("molten-"):
                    return False  # ore-derived fluid — not locally free
                continue          # other fluids assumed locally available
            if name not in scrap_reachable:
                return False
        return True

    terminals: set[str] = set()
    for it in scrap_reachable:
        if it == item_key or it in fluids:
            continue
        recipes = recipes_by_output.get(it, [])
        if not recipes or not any(_scrap_craftable(r) for r in recipes):
            terminals.add(it)
    return frozenset(terminals)


# ---------------------------------------------------------------------------
# Fast "wrap-and-recycle" shortcut (steel-chest / hazard-concrete trick)
# ---------------------------------------------------------------------------
#
# Recycler processing time scales with an item's original craft time, so
# recycling slow-to-craft items (steel-plate 16 s, concrete 10 s) is very slow
# on the recycler.  The trick: craft the item into a cheap single-ingredient
# container (steel-plate -> steel-chest, concrete -> hazard-concrete) and
# recycle the container instead.  The container's craft + recycle times are
# tiny, and recycling it returns the item at the same retention — so quality
# climbing keeps the same yield at a fraction of the recycler time (the load
# shifts to fast assemblers).  Some items (e.g. concrete) only self-recycle at
# all via such a wrap, since their own recycling decomposes them instead.

_RECYCLE_SHORTCUT_CACHE: dict[int, dict[str, dict]] = {}


def build_recycle_shortcuts(data: dict) -> dict[str, dict]:
    """Fastest self-recycle route per item (cached per dataset).

    Returns ``{item: descriptor}`` for items that can be recycled back into
    themselves by some route.  Descriptor:
      ``retention``      — item returned per item processed (≈0.25)
      ``recycler_time``  — recycler seconds per 1 item processed
      ``craft_time``     — assembler seconds per 1 item processed (0 if direct)
      ``craft_category`` — container craft category (None if direct)
      ``container``      — container item key (None if direct)
    The chosen route maximises retention, then minimises recycler_time.
    """
    cached = _RECYCLE_SHORTCUT_CACHE.get(id(data))
    if cached is not None:
        return cached

    fluids = build_fluid_set(data)
    rk = {r["key"]: r for r in data.get("recipes", [])}
    cand: dict[str, list[dict]] = defaultdict(list)

    # Direct self-recycle: <item>-recycling returns the item itself.
    for key, r in rk.items():
        if not key.endswith("-recycling"):
            continue
        item = key[: -len("-recycling")]
        self_amt = _recipe_result_amount(r, item)
        if self_amt > 0:
            cand[item].append({
                "retention": self_amt,
                "recycler_time": float(r.get("energy_required", 0.2)),
                "craft_time": 0.0,
                "craft_category": None,
                "container": None,
            })

    # Container wrap: a recipe whose only solid ingredient is the item, whose
    # output has a recycling recipe that returns the item.
    for C in data.get("recipes", []):
        if cli.is_recycling(C):
            continue
        if C.get("subgroup") in ("empty-barrel", "fill-barrel"):
            continue
        solids = [i for i in C.get("ingredients", []) if i["name"] not in fluids]
        if len(solids) != 1:
            continue
        item = solids[0]["name"]
        n_in = float(solids[0].get("amount", 0))
        if n_in <= 0:
            continue
        for res in C.get("results", []):
            container = res.get("name")
            if not container or container == item:
                continue
            crec = rk.get(f"{container}-recycling")
            if crec is None:
                continue
            out_back = _recipe_result_amount(crec, item)
            o_amt = _recipe_result_amount(C, container)
            if out_back <= 0 or o_amt <= 0:
                continue
            cand[item].append({
                "retention": o_amt * out_back / n_in,
                "recycler_time": o_amt * float(crec.get("energy_required", 0.2)) / n_in,
                "craft_time": float(C.get("energy_required", 0.5)) / n_in,
                "craft_category": _primary_category(C),
                "container": container,
            })

    out: dict[str, dict] = {}
    for item, options in cand.items():
        out[item] = max(options, key=lambda d: (d["retention"], -d["recycler_time"]))
    _RECYCLE_SHORTCUT_CACHE[id(data)] = out
    return out


# ---------------------------------------------------------------------------
# Multi-ingredient wrap enumeration (Reddit "rare-ore wrap-and-recycle" trick)
# ---------------------------------------------------------------------------
#
# The fast-recycle shortcut above only considers wraps with a single solid
# ingredient (steel-chest, hazard-concrete).  But the same trick generalises:
# any recipe with the item as a solid ingredient — even alongside other solids
# — can be used as a wrap, provided the wrap's output recycles back to the
# item.  Examples for holmium-plate: superconductor (needs copper-plate +
# light-oil), processing-unit (needs copper-cable + advanced-circuit + sulfuric
# acid), electromagnetic-plant (heavy stack).  Each extra craft step is an
# extra quality roll, which is the Reddit insight.
#
# The single-best selection criterion used by `build_recycle_shortcuts` doesn't
# work for multi-ingredient wraps because co-ingredient cost can dwarf the
# retention/recycler-time win.  So we expose the full candidate list and let
# the solver pick after computing yields.

_RECYCLE_ROUTES_CACHE: dict[int, dict[str, list[dict]]] = {}


def enumerate_recycle_routes(data: dict) -> dict[str, list[dict]]:
    """Enumerate every self-recycle route per item (cached per dataset).

    Returns ``{item: [descriptor, ...]}`` covering:
      * direct self-recycle (``<item>-recycling`` returns ``item``),
      * single-solid-ingredient wraps (steel-plate via steel-chest, …),
      * multi-solid-ingredient wraps (holmium-plate via superconductor, …).

    Descriptor fields:
      ``retention``      — item atoms returned per item atom processed
      ``recycler_time``  — recycler seconds per 1 item-atom processed
      ``craft_time``     — wrap-craft seconds per 1 item-atom processed (0 if direct)
      ``craft_category`` — wrap-craft recipe category (None if direct)
      ``container``      — wrap output item (None if direct)
      ``wrap_recipe``    — wrap recipe key (None if direct)
      ``co_solids``      — list of ``{name, amount}`` per 1 item-atom processed;
                           solid co-ingredients of the wrap recipe
      ``co_fluids``      — list of ``{name, amount}`` per 1 item-atom processed;
                           fluid ingredients of the wrap recipe
      ``co_byproducts``  — list of ``{name, amount}`` per 1 item-atom processed;
                           additional solid outputs of the wrap recipe (besides
                           the container itself) — useful for credit accounting

    Returned lists are sorted by descending retention then ascending recycler_time
    so callers can prune to a top-K cheaply.
    """
    cached = _RECYCLE_ROUTES_CACHE.get(id(data))
    if cached is not None:
        return cached

    fluids = build_fluid_set(data)
    rk = {r["key"]: r for r in data.get("recipes", [])}
    cand: dict[str, list[dict]] = defaultdict(list)

    # Direct self-recycle: <item>-recycling returns the item itself.
    for key, r in rk.items():
        if not key.endswith("-recycling"):
            continue
        item = key[: -len("-recycling")]
        self_amt = _recipe_result_amount(r, item)
        if self_amt > 0:
            cand[item].append({
                "retention":      self_amt,
                "recycler_time":  float(r.get("energy_required", 0.2)),
                "craft_time":     0.0,
                "craft_category": None,
                "container":      None,
                "wrap_recipe":    None,
                "co_solids":      [],
                "co_fluids":      [],
                "co_byproducts":  [],
            })

    # Wraps: any non-recycling recipe whose ingredients include ``item`` as a
    # solid, and whose output recycles back into ``item``.  Multi-ingredient
    # wraps are kept; the single-ingredient case is a strict sub-case.
    for C in data.get("recipes", []):
        if cli.is_recycling(C):
            continue
        if C.get("subgroup") in ("empty-barrel", "fill-barrel"):
            continue
        all_ings = C.get("ingredients", [])
        solids = [i for i in all_ings if i["name"] not in fluids]
        flu = [i for i in all_ings if i["name"] in fluids]
        # For each solid ingredient that could be the "wrapped" item, build a
        # candidate per (item, container).  Recipes never list the same
        # ingredient twice, so each solid yields one inner iteration.
        for self_ing in solids:
            item = self_ing["name"]
            n_in = float(self_ing.get("amount", 0))
            if n_in <= 0:
                continue
            # Prune ridiculously slow/expensive wraps (e.g. speed-module-3, quantum-processor)
            # that act as traps for the quality planner's heuristic.
            if float(C.get("energy_required", 0.5)) / n_in > 5.0:
                continue
            # Normalised co-ingredient amounts (per 1 item-atom in).
            co_solids = [
                {"name": s["name"], "amount": float(s.get("amount", 0)) / n_in}
                for s in solids if s["name"] != item
            ]
            co_fluids = [
                {"name": f["name"], "amount": float(f.get("amount", 0)) / n_in}
                for f in flu
            ]
            for res in C.get("results", []):
                container = res.get("name")
                if not container or container == item:
                    continue
                crec = rk.get(f"{container}-recycling")
                if crec is None:
                    continue
                out_back = _recipe_result_amount(crec, item)
                o_amt = _recipe_result_amount(C, container)
                if out_back <= 0 or o_amt <= 0:
                    continue
                # Additional solid outputs of the wrap recipe (besides the
                # container).  Probability-weighted via _recipe_result_amount.
                co_byproducts: list[dict] = []
                for r2 in C.get("results", []):
                    bp_name = r2.get("name")
                    if not bp_name or bp_name == container or bp_name in fluids:
                        continue
                    bp_amt = _recipe_result_amount(C, bp_name)
                    if bp_amt > 0:
                        co_byproducts.append({"name": bp_name, "amount": bp_amt / n_in})
                cand[item].append({
                    "retention":      o_amt * out_back / n_in,
                    "recycler_time":  o_amt * float(crec.get("energy_required", 0.2)) / n_in,
                    "craft_time":     float(C.get("energy_required", 0.5)) / n_in,
                    "craft_category": _primary_category(C),
                    "container":      container,
                    "wrap_recipe":    C["key"],
                    "co_solids":      co_solids,
                    "co_fluids":      co_fluids,
                    "co_byproducts":  co_byproducts,
                })

    out: dict[str, list[dict]] = {}
    for item, options in cand.items():
        # Sort by descending retention, then ascending recycler_time, then
        # ascending number of co-solids (single-ingredient wraps preferred at
        # equal retention/time — usually cheaper to source).
        options.sort(key=lambda d: (
            -d["retention"], d["recycler_time"], len(d["co_solids"]),
        ))
        out[item] = options
    _RECYCLE_ROUTES_CACHE[id(data)] = out
    return out


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


def _compute_incidental_byproducts(
    stages: list[dict], fluids: frozenset[str], data: dict,
) -> tuple[dict[str, float], dict[str, list[dict]]]:
    """Aggregate non-primary SOLID outputs from activated assembly stages.

    For each ``assembly`` stage, look up the recipe and emit a credit for every
    solid result that isn't the stage's primary product.  Productivity scales
    all outputs equally, so the byproduct rate is
    ``crafts_per_min × amount × probability × eff_prod`` where ``eff_prod``
    is reconstructed from the stage's stored ``research_prod`` + ``module_prod``
    (capped at 4.0).

    Returns ``({item: total_rate}, {item: [{recipe, primary, rate}, ...]})``.
    Fluids and stages with non-positive ``crafts_per_min`` are skipped.
    """
    byproducts: defaultdict[str, float] = defaultdict(float)
    sources: defaultdict[str, list[dict]] = defaultdict(list)
    for st in stages:
        if st.get("role") != "assembly":
            continue
        recipe_key = st.get("recipe")
        primary = st.get("product")
        crafts_per_min = float(st.get("crafts_per_min", 0.0))
        if crafts_per_min <= 0 or not recipe_key or not primary:
            continue
        recipe = _recipe_by_key(data, recipe_key)
        if recipe is None:
            continue
        eff_prod = (
            1.0 + float(st.get("research_prod", 0.0)) + float(st.get("module_prod", 0.0))
        )
        if eff_prod > 4.0:
            eff_prod = 4.0
        for res in recipe.get("results", []):
            name = res.get("name")
            if not name or name == primary or name in fluids:
                continue
            amt = res.get("amount")
            if amt is None:
                amt = (res.get("amount_min", 0) + res.get("amount_max", 0)) / 2.0
            prob = res.get("probability", 1.0)
            rate = crafts_per_min * float(amt) * float(prob) * eff_prod
            if rate <= 0:
                continue
            byproducts[name] += rate
            sources[name].append({"recipe": recipe_key, "primary": primary, "rate": rate})
    return dict(byproducts), dict(sources)


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
        # Generic shape: stage["cast_machine"] is the cast-side machine
        # (foundry, electromagnetic-plant, assembling-machine-3, …).  Fall
        # back to "foundry" for the V2 LDS-only shape that didn't carry
        # cast_machine.
        cast_machine = stage.get("cast_machine", "foundry")
        cast_machines = float(
            stage.get("cast_machines", stage.get("foundry_machines", 0))
        )
        return (
            _w(cast_machine) * cast_machines
            + _w("recycler") * float(stage.get("recycler_machines", 0))
        ) / 1000.0
    if role in ("self-recycle-target", "self-feed-target", "scrap-upcycle-loop"):
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


def _hot_spot_suggestions(
    by_role: dict[str, dict[str, float]],
    *,
    threshold_pct: float = 50.0,
    active_shuffles: set[str] | frozenset[str] | None = None,
    active_drivers: set[str] | frozenset[str] | None = None,
    assembly_modules: bool = False,
    has_plastic: bool = False,
    machine_quality: str = "normal",
    module_quality: str = "legendary",
    quality_module_tier: int = 3,
    planets: frozenset[str] = frozenset(),
) -> list[str]:
    """Inspect the by-role cost breakdown and emit actionable suggestions
    when a single role exceeds ``threshold_pct`` of total machines.

    Each suggestion names the dominant role, its share, and the specific
    flag the user can try next.  Avoids suggesting flags already enabled.
    """
    suggestions: list[str] = []
    at_max_quality = module_quality == "legendary" and quality_module_tier == 3
    active_shuffles = active_shuffles or frozenset()
    lds_active = (
        "all" in active_shuffles or "low-density-structure" in active_shuffles
    )
    # The advisor reasons about PRODUCTION hot spots; the `mining` role is a
    # separate axis (its own lever — mining-prod research / --enable-shuffle to
    # cut raw demand — is C5 work).  Measure each role's share against the
    # production (non-mining) total so adding miner counting in C1 doesn't dilute
    # the existing suggestions below their threshold.
    prod_total = sum(
        float(b.get("machines", 0.0)) for r, b in by_role.items() if r != "mining"
    )
    for role, bucket in by_role.items():
        if role == "mining":
            continue
        pct = (
            float(bucket.get("machines", 0.0)) / prod_total * 100.0
            if prod_total > 0 else 0.0
        )
        if pct < threshold_pct:
            continue
        if role in ("asteroid-ore-upcycle", "raw-crushing"):
            if has_plastic and not lds_active:
                suggestions.append(
                    f"hot spot: {role} is {pct:.0f}% of machines — "
                    f"try --enable-shuffle low-density-structure (offloads "
                    f"plastic-bar from carbonic chunks)"
                )
            elif not at_max_quality:
                suggestions.append(
                    f"hot spot: asteroid-ore-upcycle is {pct:.0f}% of machines — "
                    f"upgrade --module-quality (legendary T3 quality modules) or "
                    f"--quality-module-tier to improve loop yield"
                )
            # else: already at legendary T3 — no actionable suggestion.
        elif role == "mined-raw-self-recycle":
            tips: list[str] = []
            if has_plastic and not lds_active:
                tips.append("--enable-shuffle low-density-structure (cuts coal demand)")
            drivers_active = bool(active_drivers)
            if "vulcanus" in planets and not drivers_active:
                tips.append(
                    "--enable-drivers all (lava casting harvests stone as co-product, "
                    "voids molten-iron overflow)"
                )
            if "vulcanus" not in planets:
                tips.append("--planets vulcanus (lava casting bypasses ore mining for iron/copper)")
            if not tips:
                tips.append("upgrade --module-quality / --quality-module-tier")
            suggestions.append(
                f"hot spot: mined-raw-self-recycle is {pct:.0f}% of machines — "
                f"try " + " or ".join(tips)
            )
        elif role == "assembly":
            if not assembly_modules:
                suggestions.append(
                    f"hot spot: assembly is {pct:.0f}% of machines — "
                    f"try --assembly-modules (fills slots with prod-3, cuts ingredient demand)"
                )
            elif machine_quality != "legendary":
                suggestions.append(
                    f"hot spot: assembly is {pct:.0f}% of machines — "
                    f"try --machine-quality legendary (+150 % machine speed → "
                    f"~40 % machine count)"
                )
    return suggestions


def _assembly_prod_bonus(
    machine_key: str,
    recipe: dict,
    slots_map: dict[str, int],
    assembly_modules: bool,
    module_quality: str,
    prod_module_tier: int,
) -> tuple[float, int]:
    """Prod bonus = machine inherent prod (always) + N prod modules.

    The machine's built-in productivity (foundry / EM-plant / biochamber +50%)
    applies to EVERY recipe the machine crafts — it is NOT gated by the recipe's
    ``allow_productivity`` flag (that flag only restricts productivity MODULES /
    beacons) nor by ``--assembly-modules`` (which only adds module slots on top).
    Wiki-confirmed for the EM plant (accumulator, solar-panel, etc.); same
    underlying mechanic for foundry / biochamber.

    Prod MODULES are added only when ``assembly_modules`` is set, the recipe
    allows productivity, and the machine has free slots.

    Returns ``(prod_fraction, slots_filled)``.
    """
    inherent = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
    if not assembly_modules or not recipe.get("allow_productivity", True):
        return inherent, 0
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
    locked_machines: frozenset[str] = frozenset(),
    assembler_level: int = 3,
    forbid_ore_routes: bool = False,
) -> dict | None:
    """Like cli.pick_recipe, but prefer recipes whose FLUID ingredients do not
    introduce planet-exclusive raws.

    Picks `casting-iron` (molten-iron input, molten-iron derivable from iron-ore)
    over `iron-plate` (iron-ore input directly).  Rejects `molten-iron-from-lava`
    when Vulcanus isn't in ``planets``.

    When multiple recipes remain viable after planet filtering, tie-break by
    fluid fraction (prefer fluid-heavy inputs for quality transparency), then
    by canonical ``cli.pick_recipe`` order.

    Recipes whose machine is locked (via ``locked_machines``) AND have no
    category fallback are dropped, so a foundry-locked tech_state correctly
    routes iron-plate to electric-furnace instead of casting-iron.

    ``forbid_ore_routes`` (Fulgora build location): there is no asteroid platform
    and no ore mining, so recipes consuming a mined ore (``RAW_TO_CHUNK``) or an
    ore-derived ``molten-*`` fluid are dropped.  This forces metals to terminate
    at their scrap-reachable plate form (e.g. ``copper-cable`` from
    ``copper-plate`` instead of ``casting-copper-cable`` from ``molten-copper``),
    so the walker stops at the scrap-source terminals.
    """
    candidates = recipe_idx.get(item_key, [])
    if not candidates:
        return cli.pick_recipe(item_key, recipe_idx)

    def ingredient_blocked_by_planets(r: dict) -> bool:
        for ing in r.get("ingredients", []):
            name = ing["name"]
            if name in RAW_TO_CHUNK:
                if forbid_ore_routes:
                    return True   # no asteroid platform on Fulgora
                continue  # asteroid-sourced, always allowed
            if forbid_ore_routes and name.startswith("molten-"):
                return True       # ore-derived fluid — no lava/ore on Fulgora
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
    # Filter by tech_state: drop recipes whose machine is locked AND has no
    # category fallback. When locked_machines is empty this is a no-op.
    if locked_machines:
        viable = [
            r for r in viable
            if _machine_for_recipe(r, assembler_level, locked_machines) is not None
        ]
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
    machine_quality: str = "normal",
    no_asteroids: bool = False,
    forbid_ore_routes: bool = False,
    *,
    tech_state: dict[str, int],
    _cache: "_DispatchCache | None" = None,
    _in_flight: frozenset[str] = frozenset(),
    _force_tree_walk_for: frozenset[str] = frozenset(),
    _dispatch_env: dict | None = None,
    _dispatch_out: set | None = None,
) -> tuple[list[dict], dict[str, float]]:
    """Walk recipe tree; return (stages, raw_demand_rates).

    Stages are ordered deepest-first-ish for display.  Each stage has:
      {role, recipe, machine, rate_per_min, machine_count, ingredients, fluid_inputs}

    raw_demand_rates maps raw_item_key -> demand per minute (solid raws only;
    fluid raws are tracked but don't flow through quality loops).

    Dispatch kwargs (post-2026-05-08 audit):
      ``_cache`` — per-``plan()`` memo for self-recycle dispatch + solver kernels.
      ``_in_flight`` — items currently being dispatched higher up the call stack;
        propagated to break cycles in ``choose_path_self_recycle``.
      ``_force_tree_walk_for`` — items in this set are NOT short-circuited at the
        ``SELF_RECYCLING_BLOCKLIST`` gate even if they'd normally route through
        the dispatcher.  Used by Path B inside ``choose_path_self_recycle`` so it
        can attempt an ingredient-upcycle of a single self-recycle target without
        the dispatcher catching its own item.
      ``_dispatch_env`` — optional dict carrying the kwargs ``choose_path_self_recycle``
        needs (e.g. ``active_shuffles``); only consulted when the walker fires
        an intermediate dispatch.  Top-level callers pre-populate this so the
        walker can reach the dispatcher without re-deriving config from kwargs.
      ``_dispatch_out`` — optional set the walker populates with the keys it
        directly dispatched (this call only — recursive walker calls down the
        chain don't write here).  Plan() reads this after the walker returns
        to aggregate sub-plan ``normal_solid_input`` / ``normal_fluid_input``
        without double-counting transitively-aggregated entries.
    """
    recipe_idx = cli.build_recipe_index(data)
    planets = planets or frozenset()
    locked_machines = _tech_locked_machines(tech_state)
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
    if forbid_ore_routes:
        # Fulgora build location: no asteroid platform and no ore mining.  Keep
        # only the quality-transparent FLUID raws from the asteroid-baseline set
        # (e.g. water); every solid base material must come from the scrap source
        # (or a planet self-recycle path).  Asteroid chunks and ores are excluded
        # so the walker can never route a metal back to a mined ore.
        base_raw_set: set[str] = {r for r in RAW_TO_CHUNK if r in fluids}
    elif no_asteroids:
        # Asteroids disabled: only items reachable via planet mining can be raws.
        # iron-ore / copper-ore / ice / calcite become raws when their planet is
        # unlocked (handled below via MINED_RAW_NO_ASTEROID_FALLBACK).  Asteroid
        # chunks are not raws — anything that would route to them must come
        # from a planet self-recycle path or fail-fast.
        base_raw_set = set()
        for raw, raw_planets in MINED_RAW_NO_ASTEROID_FALLBACK.items():
            if any(p in planets for p in raw_planets):
                base_raw_set.add(raw)
        # water is offshore-pump on Nauvis (quality-transparent); allowed.
        if "nauvis" in planets:
            base_raw_set.add("water")
    else:
        base_raw_set = set(RAW_TO_CHUNK.keys())
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
    # Items hit during Pass 1 that should dispatch to choose_path_self_recycle
    # AFTER demand accumulation finishes (deferred so the dispatcher gets the
    # fully-accumulated demand rather than whatever was visible at first
    # encounter).
    pending_dispatch: set[str] = set()
    # Non-``molten-*`` fluids consumed in the chain (sulfuric-acid, water,
    # lubricant, …).  Fluids carry no quality, so a recipe's quality comes from
    # its SOLID ingredients — these fluids (and their whole production chain)
    # are sourced at NORMAL quality and must NOT be walked into the legendary
    # tree (which would, e.g., wrongly demand rare sulfur for sulfuric-acid).
    # ``molten-*`` fluids are the exception: they carry quality through casting.
    normal_fluid_leaves: set[str] = set()

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
            # Intermediate self-recycle dispatch (post-2026-05-08 audit).
            # If the item is a SELF_RECYCLE_TARGETS member AND a dispatch
            # cache is available AND the caller hasn't asked us to bypass
            # this gate (Path B re-entry), defer dispatch to the end of
            # Pass 1 so the dispatcher gets fully-accumulated demand.
            if (
                current in SELF_RECYCLE_TARGETS
                and current not in _force_tree_walk_for
                and _cache is not None
                and _dispatch_env is not None
            ):
                pending_dispatch.add(current)
                seen.add(current)
                continue   # do NOT walk this item's ingredients — sub-plan owns them
            raise ValueError(
                f"ERROR: recipe '{current}' is self-recycling (output recycles to itself) — not supported"
            )
        recipe = _pick_recipe_fluid_preferred(
            current, recipe_idx, fluids, planets, planet_props,
            locked_machines=locked_machines, assembler_level=assembler_level,
            forbid_ore_routes=forbid_ore_routes,
        )
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
        # Prod for demand propagation MUST equal what Pass 2 applies so the
        # upstream ingredient/raw quantities line up.  That means the machine's
        # inherent prod (foundry / EM-plant / biochamber +50%) always counts —
        # it applies whether or not --assembly-modules adds prod-module slots on
        # top.  (Previously inherent prod was dropped here unless --assembly-
        # modules was set, inflating every upstream demand by the inherent
        # factor — e.g. processing-unit's sulfuric-acid read 25 instead of ~16.7.)
        mr_p1 = _machine_for_recipe(recipe, assembler_level, locked_machines)
        if mr_p1 is None:
            # Locked machine with no fallback — Pass 2 raises the canonical error;
            # here we just skip the inherent bonus so demand stays finite.
            module_prod_p1 = 0.0
        else:
            machine_key_p1, _ = mr_p1
            module_prod_p1, _ = _assembly_prod_bonus(
                machine_key_p1, recipe, slots_map,
                assembly_modules, assembly_module_quality, prod_module_tier,
            )
        eff_prod = 1.0 + research_prod + module_prod_p1
        if eff_prod > 4.0:
            eff_prod = 4.0
        net_demand = max(0.0, demand[current])
        cycles_per_min = net_demand / (per_craft_output * eff_prod)
        # A fluid ingredient carries this recipe's quality only when it is the
        # primary material — i.e. the recipe has NO solid ingredient (casting /
        # holmium-plate) or the fluid is a molten metal.  When the recipe has a
        # solid ingredient, that solid carries the quality and the fluid is a
        # quality-irrelevant reagent (sulfuric-acid in battery, water, etc.).
        recipe_has_solid = any(
            i["name"] not in fluids for i in recipe.get("ingredients", [])
        )
        for ing in recipe.get("ingredients", []):
            iname = ing["name"]
            amt = float(ing.get("amount", 0))
            ing_rate = amt * cycles_per_min
            if iname in fluids:
                demand[iname] += ing_rate
                if iname.startswith("molten-") or not recipe_has_solid:
                    # Quality-carrying fluid (casting / fluid-only recipe): walk
                    # into it so the upstream demand (e.g. molten-iron ->
                    # iron-ore, holmium-solution -> holmium-ore) is produced at
                    # the target quality.
                    if iname not in seen:
                        pending.append(iname)
                        order.append(iname)
                else:
                    # Quality-irrelevant reagent fluid: source at normal quality
                    # and do NOT expand its sub-tree into the legendary walk (so
                    # e.g. sulfur for sulfuric-acid stays normal).
                    normal_fluid_leaves.add(iname)
            else:
                demand[iname] += ing_rate
                if iname not in seen and iname not in raw_set:
                    pending.append(iname)
                    order.append(iname)

    # Resolve any deferred self-recycle-target intermediate dispatches.
    # Must happen AFTER the BFS so each intermediate's accumulated demand is
    # final.  Each dispatch produces a self-contained sub-plan that we cache
    # for Pass 2 and for the top-level plan() to aggregate ``normal_solid_input``
    # / ``normal_fluid_input`` from.
    #
    # We deliberately do NOT forward the sub-plan's normal-quality raws into
    # the parent walker's ``demand`` — those raws need to be sourced at NORMAL
    # quality by the user, not routed through the parent's asteroid /
    # mined-recycle (legendary) paths.  plan() reads them out of
    # ``_cache.intermediates`` after the walker returns.
    if pending_dispatch and _cache is not None and _dispatch_env is not None:
        for inter in pending_dispatch:
            inter_demand = max(0.0, demand[inter])
            if inter_demand <= 0:
                continue
            sub = choose_path_self_recycle(
                inter, inter_demand, data,
                module_quality=_dispatch_env["module_quality"],
                research_levels=_dispatch_env["research_levels"],
                assembler_level=_dispatch_env["assembler_level"],
                quality_module_tier=_dispatch_env["quality_module_tier"],
                planets=planets or frozenset(),
                tech_state=tech_state,
                assembly_modules=assembly_modules,
                prod_module_tier=prod_module_tier,
                machine_quality=machine_quality,
                active_shuffles=_dispatch_env.get("active_shuffles"),
                no_asteroids=no_asteroids,
                forbid_ore_routes=forbid_ore_routes,
                target_tier=_dispatch_env.get("target_tier", 4),
                _cache=_cache,
                _in_flight=_in_flight | {inter},
            )
            _cache.intermediates[inter] = sub
            if _dispatch_out is not None:
                _dispatch_out.add(inter)

    # Build stages from order; also collect all raws seen as demand keys
    stages: list[dict] = []
    raw_demand: dict[str, float] = defaultdict(float)
    for iname, amt in demand.items():
        if iname in raw_set and iname != item_key:
            if amt > 0:
                raw_demand[iname] += amt
        elif iname in normal_fluid_leaves and amt > 0:
            # Consumable fluid sourced at normal quality; plan() routes fluids
            # in raw_demand to the (normal) fluid-input bucket.
            raw_demand[iname] += amt
    # Track items already emitted in Pass 2 so duplicates in ``order`` (which
    # can arise from multiple ingredient encounters in BFS) don't re-emit.
    pass2_emitted: set[str] = set()
    for item in order:
        if item in raw_set and item != item_key:
            continue
        if item in pass2_emitted:
            continue
        pass2_emitted.add(item)
        # Intermediate self-recycle dispatch: emit the cached sub-plan's
        # stages verbatim and skip normal recipe-based stage construction
        # for this item.  Pass 1 has already pulled the sub-plan's normal-
        # quality raws into our raw_demand bucket via ``demand``.
        if (
            _cache is not None
            and item in _cache.intermediates
            and item != item_key
        ):
            sub = _cache.intermediates[item]
            for st in sub.get("stages", []):
                # shallow copy avoids alias issues if the sub-plan is
                # re-emitted by a sibling chain in the same plan() call.
                stages.append(dict(st))
            continue
        recipe = _pick_recipe_fluid_preferred(
            item, recipe_idx, fluids, planets, planet_props,
            locked_machines=locked_machines, assembler_level=assembler_level,
            forbid_ore_routes=forbid_ore_routes,
        )
        if recipe is None:
            raw_demand[item] += demand[item]
            continue
        mr = _machine_for_recipe(recipe, assembler_level, locked_machines)
        if mr is None:
            raise ValueError(
                f"ERROR: cannot produce '{item}' — recipe '{recipe['key']}' "
                f"requires a locked machine for category "
                f"'{recipe.get('category')}'.  Add the corresponding --tech "
                f"flag (one of: {sorted(TECH_GATES.keys())})."
            )
        machine_key, machine_speed = mr
        machine_speed_f = float(machine_speed) * (
            1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
        )
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
        machine_count = crafts_per_min * crafting_time / (
            machine_speed_f
            * _module_speed_mult(prod_slots=prod_slots_filled, prod_tier=prod_module_tier)
            * 60.0
        )
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
            "allow_productivity": bool(recipe.get("allow_productivity", False)),
            "prod_module_tier": prod_module_tier if prod_slots_filled > 0 else 0,
            "prod_module_quality": assembly_module_quality if prod_slots_filled > 0 else "normal",
            "machine_quality": machine_quality,
            "prod_capped": capped,
            "inputs_all_legendary": all(k not in fluids for k in inputs) if solid_inputs else True,
        })

    # Filter raws to solid raws only (fluids like water get treated in crushing)
    # Keep only items the asteroid chain produces OR raws unlocked via --planets.
    if no_asteroids:
        asteroid_raws: set[str] = set()
        # With asteroids disabled, no stage may use an asteroid-crushing recipe
        # (chunk recipes self-cycle, so the chunk never appears in raw_demand —
        # we have to detect the recipe usage instead).  Fail fast pointing at
        # the leaf raw whose only path goes through asteroids.
        crush_keys = set(ASTEROID_CRUSHING_RECIPES.values())
        for st in stages:
            if st.get("recipe") in crush_keys:
                product = st.get("product", "?")
                raise ValueError(
                    f"ERROR: '{item_key}' chain needs '{product}' which "
                    f"resolves to asteroid-crushing recipe '{st['recipe']}' "
                    f"but --no-asteroids is set. Unlock the planet that "
                    f"produces '{product}' natively via --planets "
                    f"(e.g. --planets vulcanus for calcite, "
                    f"--planets aquilo for ice)."
                )
    else:
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
    target_tier: int = 4,
    *,
    wrap_route: dict | None = None,
    wrap_machine_slots: int = 0,
    wrap_allow_prod: bool = False,
    wrap_inherent_prod: float = 0.0,
    wrap_research_prod: float = 0.0,
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

    Wrap-craft extension (Reddit "rare-ore wrap-and-recycle"):  When
    ``wrap_route`` is supplied and ``wrap_machine_slots > 0``, each cycle pass
    becomes a composite of **wrap-craft (quality roll) → container-recycle
    (quality roll)** — two rolls per pass instead of one.  The composite
    transition probability is the convolution of the two per-step distributions.
    ``wrap_route`` provides the base retention; wrap-craft prod modules scale
    it via ``(1 + wrap_prod)``.  Per-tier configs gain ``wrap_prod`` /
    ``wrap_quality`` fields when this path is taken.  Co-ingredient sourcing
    is the caller's responsibility — this solver only models the cycle.

    Returns ``(V_total, configs_per_tier)`` — legendary items per fresh craft.
    Configs map ``{0,1,2,3} → {craft_prod, craft_quality, recycle_quality,
    [wrap_prod, wrap_quality]}`` (wrap_* present only when wrap path active).
    """
    craft_recipe = cli.pick_recipe(item_key, cli.build_recipe_index(data))
    if craft_recipe is None:
        return 0.0, {}

    # --- Retention selection ---
    # Wrap-DP path: explicit route from enumerate_recycle_routes; use its
    # retention as base, scaled by wrap-craft prod inside the cycle DP.
    # Default path: legacy build_recycle_shortcuts (single-best descriptor)
    # for backwards-compat — no wrap quality/prod rolls.
    wrap_active = wrap_route is not None and wrap_machine_slots > 0
    if wrap_active:
        assert wrap_route is not None  # narrowing for type checkers
        base_retention = float(wrap_route["retention"])
        wrap_recipe_allow_prod = bool(wrap_allow_prod)
    else:
        shortcut = build_recycle_shortcuts(data).get(item_key)
        if shortcut is not None:
            base_retention = float(shortcut["retention"])
        else:
            rec_recipe = _recipe_by_key(data, f"{item_key}-recycling")
            base_retention = (
                _recipe_result_amount(rec_recipe, item_key) if rec_recipe else RECYCLER_RETENTION
            )
        wrap_recipe_allow_prod = False
    if base_retention <= 0 or base_retention >= 1.0:
        return 0.0, {}

    craft_output = _recipe_result_amount(craft_recipe, item_key)
    if craft_output <= 0:
        return 0.0, {}
    recipe_allow_prod = (
        craft_recipe.get("allow_productivity", True) and machine_allow_prod
    )

    # --- Inner DP: V_rec[t] for one item-atom at tier t entering the cycle ---
    #
    # Without wrap: single recycle pass — composite_up[k] == rec_probs[k].
    # With wrap:    two-roll composite — convolve wrap_probs ⊗ rec_probs.
    def v_rec_for_cycle(wp: int, wq: int, rq: int) -> list[float]:
        if wrap_active:
            if wp > 0 and not wrap_recipe_allow_prod:
                # Caller asked for prod the wrap recipe doesn't allow — skip.
                return [0.0] * 5
            wrap_prod = (
                wrap_inherent_prod + wrap_research_prod
                + _prod_bonus(wp, prod_module_tier, module_quality)
            )
            if wrap_prod > 3.0:
                wrap_prod = 3.0
            retention = base_retention * (1.0 + wrap_prod)
            q_wrap = _quality_chance(wq, quality_module_tier, module_quality)
        else:
            retention = base_retention
            q_wrap = 0.0
        q_rec = _quality_chance(rq, quality_module_tier, module_quality)
        V = _seed_value_vector(target_tier)
        for t in range(target_tier - 1, -1, -1):
            wrap_probs = _tier_skip_probs(q_wrap, t)  # len target_tier - t + 1
            # Convolve wrap-tier transition with recycle-tier transition.
            #   composite_up[k] = Σ_i wrap_probs[i] × rec_probs_at(t+i)[k-i]
            composite_up = [0.0] * len(wrap_probs)
            for i, pwi in enumerate(wrap_probs):
                if pwi == 0.0:
                    continue
                rec_probs = _tier_skip_probs(q_rec, t + i)  # len target_tier - (t+i) + 1
                for j, prj in enumerate(rec_probs):
                    composite_up[i + j] += pwi * prj
            stay = retention * composite_up[0]
            if stay >= 1.0 - 1e-15:
                V[t] = 0.0
            else:
                numer = sum(
                    retention * composite_up[k] * V[t + k]
                    for k in range(1, len(composite_up))
                )
                V[t] = numer / (1.0 - stay)
        return V

    # --- Decoupled two-pass search ---
    #
    # The canonical-craft step (cp, cq) is taken ONCE per atom at the entry
    # point.  Its output distribution feeds the wrap-recycle cycle whose value
    # vector V_rec[t] depends purely on (wp, wq, rq) — NOT on (cp, cq).  Hoist
    # the cycle DP outside the canonical search:
    #
    #   Pass 1: build {(wp, wq, rq): V_rec[t]} once.  O(wrap_slots² × RECYCLER_SLOTS) DPs.
    #   Pass 2: canonical (cp, cq) optimization        O(slots²) cheap lookups.
    #
    # Total work is ADDITIVE in slots², not multiplicative.  For wrap_slots=0
    # the cycle dim collapses to {(0, 0, rq)} and the result matches the
    # pre-wrap-extension code exactly.

    # Pass 1: cycle table.
    if wrap_active:
        wp_max = wrap_machine_slots
    else:
        wp_max = 0
    v_rec_table: dict[tuple[int, int, int], list[float]] = {}
    for wp in range(wp_max + 1):
        for wq in range(wp_max - wp + 1):
            for rq in range(RECYCLER_SLOTS + 1):
                v_rec_table[(wp, wq, rq)] = v_rec_for_cycle(wp, wq, rq)

    # Pass 2: canonical-side optimization via lookup.
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

            for (wp, wq, rq), v_rec in v_rec_table.items():
                total = items_per_craft * sum(
                    craft_probs[s] * v_rec[s] for s in range(5)
                )
                if total > best_total:
                    best_total = total
                    best_cfg = {
                        "craft_prod":     cp,
                        "craft_quality":  cq,
                        "recycle_quality": rq,
                    }
                    if wrap_active:
                        best_cfg["wrap_prod"]    = wp
                        best_cfg["wrap_quality"] = wq
                    best_v_rec = v_rec

    if best_cfg is None:
        return 0.0, {}
    # Per-tier configs: in this loop the cycle config is global (single config
    # wins).  We expose it for each below-target tier for symmetry with other
    # loops.
    configs = {t: dict(best_cfg) for t in range(target_tier)}
    # Annotate per-tier V_rec for downstream display.
    for t in range(target_tier):
        configs[t]["v_rec"] = best_v_rec[t]
    return max(best_total, 0.0), configs


# ---------------------------------------------------------------------------
# Self-feed target planner (V3 item 4 cont.) — pentapod-egg etc.
# ---------------------------------------------------------------------------

def solve_self_feed_target_loop(
    item_key: str,
    data: dict,
    machine_slots: int,
    machine_speed_eff: float,
    inherent_prod: float,
    research_prod: float,
    module_quality: str,
    machine_quality: str = "normal",
    prod_module_tier: int = 3,
    quality_module_tier: int = 3,
    target_tier: int = 4,
) -> tuple[float, dict]:
    """LP-based steady-state solver for self-feed target items.

    A "self-feed" recipe has the target item in BOTH its ingredient and result
    lists — e.g. pentapod-egg: ``1 egg + 30 nutrients + 60 water → 2 eggs``.
    The recipe is super-productive at every quality tier (output × p_stay > 1
    for any reasonable module config), so :func:`solve_self_recycle_target_loop`
    does not apply: its per-atom value DP has no positive fixed point.

    Model — steady-state linear flows over processing tiers
    ``q ∈ {0,1,2,3}`` (normal, uncommon, rare, epic).  Legendary (q=4)
    drains immediately:

      * ``x_q`` crafts/min, ``y_q`` recycles/min  (decision variables)
      * Per-craft outputs at q': ``output_q · cp_q[q→q']``
      * Per-recycle outputs at q': ``retention · rp_q[q→q']``
      * Balance at each tier:
            ``A_q · x_q + B_q · y_q = I_q``
        where ``A_q = 1 - output_q · cp_q[q→q]`` (negative — super-productive),
              ``B_q = 1 - retention · rp_q[q→q]`` (positive),
              ``I_q = inflow from lower tiers (=0 at q=0; cascade upward)``.
      * Drain at q=4: ``Σ_q [x_q · output_q · cp_q[q→4] + y_q · retention · rp_q[q→4]] = rate``

    After substituting ``y_q = (I_q + |A_q| · x_q) / B_q`` (valid when A_q < 0),
    we have a 4-variable LP with one equality constraint and non-negativity:

        min Σ_q (x_q · kc_q + y_q · kr_q)
        s.t. Σ_q drain coefficients · x_q = rate,  x_q ≥ 0

    By LP corner-optimality the minimum lies at a vertex where exactly one
    ``x_{q*}`` is positive.  We try ``q* ∈ {0,1,2,3}`` and pick the cheapest.

    Outer search exploits a property of the LP corner solutions: when only
    ``x_{q*} > 0``, tiers ``q < q*`` carry zero flow (their configs are
    inert) and tiers ``q > q*`` only run recyclers (only their ``rq`` matters).
    So per corner ``q*`` we enumerate ``25 · 5^(3-q*)`` configs; total ≤ 4 000
    configs across all 4 corners.  Solves in well under a second.

    Returns ``(legendary_per_minute_yield, plan)`` where ``yield`` is per
    "unit machine cost" (drain / cost; useful for diagnostics) and ``plan``
    contains x/y per tier, machine counts per tier, module configs per tier,
    and the chosen drain rate.  Caller scales by ``rate`` outside.
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
    self_in = _recipe_ing_amount(craft_recipe, item_key)
    self_out_amt = _recipe_result_amount(craft_recipe, item_key)
    if self_in <= 0 or self_out_amt <= 0:
        return 0.0, {}

    recipe_allow_prod = craft_recipe.get("allow_productivity", True)
    qm_mult = 1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
    rec_speed_eff = RECYCLER_SPEED * qm_mult
    craft_time = float(craft_recipe.get("energy_required", 1.0))
    rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2
    # Machine cost coefficients: machines per craft/min (resp. recycle/min).
    # These depend on the module loadout: prod + quality modules in the crafter
    # and quality modules in the recycler each slow the machine (-5%/slot etc.,
    # `_module_speed_mult`), so the coefficient is config-dependent.  A loadout
    # with more (slow) modules costs more machines for the same throughput, which
    # the corner search must see to trade module count against speed.
    def kc_for(cp: int, cq: int) -> float:
        return craft_time / (
            machine_speed_eff
            * _module_speed_mult(quality_slots=cq, prod_slots=cp, prod_tier=prod_module_tier)
            * 60.0
        )

    def kr_for(rq: int) -> float:
        return rec_time / (
            rec_speed_eff * _module_speed_mult(quality_slots=rq) * 60.0
        )

    # Module config grid: full slots only (empty slots are dominated).
    if recipe_allow_prod:
        craft_configs = [(cp, machine_slots - cp) for cp in range(machine_slots + 1)]
    else:
        craft_configs = [(0, machine_slots)]
    rec_configs = list(range(RECYCLER_SLOTS + 1))

    # Helper: per-tier (output, cp_dist, rp_dist) cache by (cp, cq, rq).
    def per_tier_kit(q: int, cp: int, cq: int, rq: int) -> tuple[float, list[float], list[float]]:
        prod = (
            inherent_prod + research_prod
            + _prod_bonus(cp, prod_module_tier, module_quality)
        )
        if prod > 3.0:
            prod = 3.0
        out_q = self_out_amt * (1.0 + prod)
        qc_craft = _quality_chance(cq, quality_module_tier, module_quality)
        qc_rec = _quality_chance(rq, quality_module_tier, module_quality)
        return out_q, _tier_skip_probs(qc_craft, q), _tier_skip_probs(qc_rec, q)

    best_ratio = float("inf")  # cost-per-legendary; lower is better
    best: dict | None = None

    # In each LP corner only x_{q*} > 0; tiers q < q* have zero flow (their
    # configs are irrelevant), and tiers q > q* run only y_q (recycler) so
    # only their rq matters.  This collapses the search drastically.
    for q_star in range(target_tier):
        # Enumerate configs at q_star (full craft+recycle config), and rq
        # only at q > q_star (no crafts there).  Use placeholder zeros for
        # q < q_star and tiers at/above the target — those tiers carry no flow
        # (items reaching the target tier or better drain immediately).
        # Build per-tier choices as lists of (cp, cq, rq) tuples.
        choices_per_tier: list[list[tuple[int, int, int]]] = []
        for q in (0, 1, 2, 3):
            if q < q_star or q >= target_tier:
                choices_per_tier.append([(0, 0, 0)])  # inert; values unused
            elif q == q_star:
                choices_per_tier.append([
                    (cp, cq, rq)
                    for (cp, cq) in craft_configs
                    for rq in rec_configs
                ])
            else:
                choices_per_tier.append([(0, 0, rq) for rq in rec_configs])

        # Cartesian product across the 4 tiers.
        for c0 in choices_per_tier[0]:
          for c1 in choices_per_tier[1]:
            for c2 in choices_per_tier[2]:
              for c3 in choices_per_tier[3]:
                tier_cfg = (c0, c1, c2, c3)
                cps = tuple(c[0] for c in tier_cfg)
                cqs = tuple(c[1] for c in tier_cfg)
                rqs = tuple(c[2] for c in tier_cfg)

                output: list[float] = []
                cp_dist: list[list[float]] = []
                rp_dist: list[list[float]] = []
                for q in (0, 1, 2, 3):
                    out_q, cpq, rpq = per_tier_kit(q, cps[q], cqs[q], rqs[q])
                    output.append(out_q)
                    cp_dist.append(cpq)
                    rp_dist.append(rpq)

                # A_q at q_star must be < 0 (super-productive).  At q != q_star
                # we don't craft so A_q is irrelevant; skip the check.
                A_qstar = 1.0 - output[q_star] * cp_dist[q_star][0]
                if A_qstar >= -1e-12:
                    continue
                # B_q must be > 0 at every tier where y_q may be positive
                # (q_star up to — but not including — the target tier).
                bad_B = False
                for q in range(q_star, target_tier):
                    if 1.0 - retention * rp_dist[q][0] <= 1e-12:
                        bad_B = True
                        break
                if bad_B:
                    continue

                # Solve the LP corner: x_{q_star} = 1, others = 0.
                x_unit = [0.0, 0.0, 0.0, 0.0]
                x_unit[q_star] = 1.0
                y_unit = [0.0, 0.0, 0.0, 0.0]
                I = [0.0, 0.0, 0.0, 0.0]
                feasible = True
                for q in (0, 1, 2, 3):
                    A_q = 1.0 - output[q] * cp_dist[q][0]
                    B_q = 1.0 - retention * rp_dist[q][0]
                    # Balance: A_q · x_q + B_q · y_q = I_q
                    # => y_q = (I_q - A_q · x_q) / B_q
                    y_unit[q] = (I[q] - A_q * x_unit[q]) / B_q
                    if y_unit[q] < -1e-9:
                        feasible = False
                        break
                    if y_unit[q] < 0:
                        y_unit[q] = 0.0
                    # Cascade outputs to higher processing tiers (below the
                    # target).  Rolls that overshoot to the target tier or
                    # better are counted as drain, not cascaded.
                    for s in range(q + 1, target_tier):
                        c_o = output[q] * cp_dist[q][s - q]
                        c_r = retention * rp_dist[q][s - q]
                        I[s] += x_unit[q] * c_o + y_unit[q] * c_r
                if not feasible:
                    continue
                # Drain: every roll that lands at the target tier or better.
                drain_per_unit = 0.0
                for q in range(target_tier):
                    cp_drain = sum(cp_dist[q][s - q] for s in range(target_tier, 5))
                    rp_drain = sum(rp_dist[q][s - q] for s in range(target_tier, 5))
                    drain_per_unit += (
                        x_unit[q] * output[q] * cp_drain
                        + y_unit[q] * retention * rp_drain
                    )
                if drain_per_unit <= 1e-12:
                    continue
                kc_per_tier = [kc_for(cps[q], cqs[q]) for q in (0, 1, 2, 3)]
                kr_per_tier = [kr_for(rqs[q]) for q in (0, 1, 2, 3)]
                cost_per_unit = sum(
                    x_unit[q] * kc_per_tier[q] + y_unit[q] * kr_per_tier[q]
                    for q in (0, 1, 2, 3)
                )
                ratio = cost_per_unit / drain_per_unit
                if ratio < best_ratio:
                    best_ratio = ratio
                    best = {
                        "cps": cps,
                        "cqs": cqs,
                        "rqs": rqs,
                        "output": list(output),
                        "cp_dist": [list(d) for d in cp_dist],
                        "rp_dist": [list(d) for d in rp_dist],
                        "q_star": q_star,
                        "x_unit": list(x_unit),
                        "y_unit": list(y_unit),
                        "drain_per_unit": drain_per_unit,
                        "cost_per_unit": cost_per_unit,
                        "kc_per_tier": list(kc_per_tier),
                        "kr_per_tier": list(kr_per_tier),
                        "retention": retention,
                        "self_in": self_in,
                        "self_out_amt": self_out_amt,
                        "craft_recipe_key": craft_recipe.get("key", item_key),
                    }

    if best is None:
        return 0.0, {}
    # "Yield" = drain/cost — used only as a positive sanity scalar.
    yield_per_machine = 1.0 / best_ratio
    return yield_per_machine, best


# ---------------------------------------------------------------------------
# Dispatch DP for SELF_RECYCLE_TARGETS — top-level + intermediate (V3+ audit)
# ---------------------------------------------------------------------------
#
# Top-level plan() and intermediate ingredient walks both face the same
# decision when an item is in SELF_RECYCLE_TARGETS:
#
#   Path A: ``_plan_self_recycle_target`` runs the recycler-only DP and
#           consumes the item's ingredients at NORMAL quality.
#   Path B: walk the recipe tree with each ingredient upcycled to legendary
#           via the standard quality paths (asteroid, mined-recycle, shuffle).
#
# Pre-refactor the comparison happened only at the top level (auto-comparator
# in plan()) and the walker fail-fasted at intermediate level.  Now both go
# through the same dispatcher (``choose_path_self_recycle``) backed by a
# per-``plan()`` ``_DispatchCache``.
#
# The cache has three layers:
#   * Solver — keys solve_self_recycle_target_loop results by environment;
#     rate-independent (kernel returns yield-per-craft).
#   * Decision — caches "A"/"B" winner per item per environment; rate-
#     independent because both paths scale linearly with rate, so the choice
#     doesn't depend on rate.  Stage construction re-runs at the actual rate.
#   * Intermediate — sub-plan dicts keyed by item key, populated during
#     Pass 1 of walk_recipe_tree, consumed during Pass 2.

@dataclass
class _DispatchCache:
    """Per-``plan()`` invocation cache for self-recycle dispatch + solver memo.

    Allocated by ``plan()`` and threaded through every ``walk_recipe_tree``
    call (including shuffle re-walks and ``_plan_self_recycle_target``'s
    ingredient walks).  Not module-level — different calls have different
    parameters (planets, tech, module quality) which all affect cost.
    """
    plans: dict[tuple, str] = field(default_factory=dict)
    solver: dict[tuple, tuple[float, dict]] = field(default_factory=dict)
    intermediates: dict[str, dict] = field(default_factory=dict)
    # Test instrumentation: counts only on a CACHE MISS (real kernel work).
    plan_kernel_calls: int = 0
    solver_kernel_calls: int = 0


def solve_self_recycle_target_loop_memoized(
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
    target_tier: int = 4,
    *,
    wrap_route: dict | None = None,
    wrap_machine_slots: int = 0,
    wrap_allow_prod: bool = False,
    wrap_inherent_prod: float = 0.0,
    wrap_research_prod: float = 0.0,
    _cache: _DispatchCache | None = None,
) -> tuple[float, dict]:
    """Cached wrapper around :func:`solve_self_recycle_target_loop`.

    Result is rate-independent (yield-per-craft + per-tier configs), so the
    cache key omits rate.  Floats are rounded to 6 decimals to avoid spurious
    cache misses from FP noise; the rounding precision matches game-relevant
    granularity (>1e-6).  When ``wrap_route`` is provided, its identity
    (recipe key + retention) plus the wrap-machine params join the cache key.
    """
    if _cache is None:
        return solve_self_recycle_target_loop(
            item_key, data,
            machine_key=machine_key,
            machine_slots=machine_slots,
            machine_allow_prod=machine_allow_prod,
            inherent_prod=inherent_prod,
            research_prod=research_prod,
            module_quality=module_quality,
            prod_module_tier=prod_module_tier,
            quality_module_tier=quality_module_tier,
            target_tier=target_tier,
            wrap_route=wrap_route,
            wrap_machine_slots=wrap_machine_slots,
            wrap_allow_prod=wrap_allow_prod,
            wrap_inherent_prod=wrap_inherent_prod,
            wrap_research_prod=wrap_research_prod,
        )
    # Wrap descriptor identity: recipe key + retention is enough — the rest of
    # the descriptor is derived from those plus the dataset (which is itself
    # part of the cache scope via `_cache`'s lifetime).
    if wrap_route is not None:
        wrap_key = (
            wrap_route.get("wrap_recipe"),
            round(float(wrap_route.get("retention", 0.0)), 6),
        )
    else:
        wrap_key = (None, 0.0)
    key = (
        item_key,
        machine_key,
        int(machine_slots),
        bool(machine_allow_prod),
        round(float(inherent_prod), 6),
        round(float(research_prod), 6),
        module_quality,
        int(prod_module_tier),
        int(quality_module_tier),
        int(target_tier),
        wrap_key,
        int(wrap_machine_slots),
        bool(wrap_allow_prod),
        round(float(wrap_inherent_prod), 6),
        round(float(wrap_research_prod), 6),
    )
    hit = _cache.solver.get(key)
    if hit is not None:
        return hit
    _cache.solver_kernel_calls += 1
    result = solve_self_recycle_target_loop(
        item_key, data,
        machine_key=machine_key,
        machine_slots=machine_slots,
        machine_allow_prod=machine_allow_prod,
        inherent_prod=inherent_prod,
        research_prod=research_prod,
        module_quality=module_quality,
        prod_module_tier=prod_module_tier,
        quality_module_tier=quality_module_tier,
        target_tier=target_tier,
        wrap_route=wrap_route,
        wrap_machine_slots=wrap_machine_slots,
        wrap_allow_prod=wrap_allow_prod,
        wrap_inherent_prod=wrap_inherent_prod,
        wrap_research_prod=wrap_research_prod,
    )
    _cache.solver[key] = result
    return result


def _choose_wrap_route(
    item_key: str,
    data: dict,
    *,
    assembler_level: int,
    locked_machines: frozenset[str],
    planet_props: dict,
    module_quality: str,
    quality_module_tier: int,
    prod_module_tier: int,
    target_tier: int,
    machine_key: str,
    machine_slots: int,
    machine_allow_prod: bool,
    inherent_prod: float,
    research_prod: float,
    research_levels: dict[str, int],
    _cache: _DispatchCache | None = None,
    _in_flight: frozenset[str] = frozenset(),
) -> tuple[dict | None, dict | None]:
    """Pick the best wrap route for ``item_key`` if one beats the baseline.

    Algorithm:
      1. Skip the wrap path entirely for intermediates (``_in_flight`` non-empty).
         Walking wrap co-ingredients here would deepen recursion through
         self-recycle dispatchers; restrict to top-level targets for v1.
      2. Enumerate routes via :func:`enumerate_recycle_routes`.
      3. Filter to wraps that are reachable: wrap recipe satisfies current
         planet ``surface_conditions``, and the wrap recipe's machine is
         unlocked under the current tech state.  Co-ingredients themselves
         are not pre-filtered — the planner handles planet-gated co-ingredients
         downstream via the soft-fallback path.
      4. Compute baseline V (no wrap).
      5. For each candidate, compute V via the wrap-DP solver (memoized).
      6. Score by ``V_wrap / (1 + co_count / 2)`` — penalises wraps with more
         solid co-ingredients, since each adds an upstream sub-chain.  This
         lets single-ingredient wraps (steel-chest, hazard-concrete) win
         against marginally-better multi-ingredient wraps but doesn't block
         the big wins (holmium-plate via EM-plant is ~34× baseline).
      7. If best-scored wrap doesn't beat baseline by ≥ 5 %, return ``(None, None)``.

    Returns ``(descriptor, machine_info)`` where ``machine_info`` has
    ``machine_key``, ``machine_slots``, ``allow_prod``, ``inherent_prod``.
    """
    # Intermediates use the simple direct/legacy path — avoid deepening
    # recursion through co-ingredient walks.  Top-level targets get the
    # full Reddit treatment.  Note: the dispatcher seeds ``_in_flight`` with
    # ``item_key`` itself before calling, so the guard subtracts ``{item_key}``
    # to check whether any OTHER item is in flight (= we're nested).
    if _in_flight - {item_key}:
        return None, None

    routes = enumerate_recycle_routes(data).get(item_key, [])
    if not routes:
        return None, None
    # Baseline: no-wrap V (used as the comparison floor).
    v_baseline, _ = solve_self_recycle_target_loop_memoized(
        item_key, data,
        machine_key=machine_key,
        machine_slots=machine_slots,
        machine_allow_prod=machine_allow_prod,
        inherent_prod=inherent_prod,
        research_prod=research_prod,
        module_quality=module_quality,
        prod_module_tier=prod_module_tier,
        quality_module_tier=quality_module_tier,
        target_tier=target_tier,
        _cache=_cache,
    )

    module_slots_map = cli.build_machine_module_slots(data)
    rk = {r["key"]: r for r in data.get("recipes", [])}

    # Single-ingredient wraps dominate multi-ingredient ones when available:
    # they're zero-cost on the co-ingredient side (just the item itself, no
    # extra upstream chain to build).  Restrict the candidate pool when at
    # least one single-ingredient wrap is machine-feasible.  Otherwise fall
    # back to multi-ingredient wraps (the holmium-plate case).
    def _candidate_filter(prefer_single: bool):
        for route in routes:
            wrap_recipe_key = route.get("wrap_recipe")
            if wrap_recipe_key is None:
                continue  # direct self-recycle handled by baseline
            if prefer_single and route.get("co_solids"):
                continue
            yield route

    def _evaluate(route: dict) -> tuple[float, dict, dict] | None:
        wrap_recipe_key = route.get("wrap_recipe")
        wrap_recipe = rk.get(wrap_recipe_key)
        if wrap_recipe is None:
            return None
        # Planet filter: skip wraps unreachable on the current planet set.
        if planet_props and not cli._recipe_valid_for_planet(wrap_recipe, planet_props):
            return None
        # Machine filter: skip wraps whose machine is tech-locked.
        wmr = _machine_for_recipe(wrap_recipe, assembler_level, locked_machines)
        if wmr is None:
            return None
        wmk, _wms = wmr
        w_slots = int(module_slots_map.get(wmk, 0))
        if w_slots <= 0:
            return None  # machine accepts no modules — wrap-DP can't roll quality
        w_inherent = MACHINE_INHERENT_PROD.get(wmk, 0.0)
        w_allow_prod = bool(wrap_recipe.get("allow_productivity", True))
        w_research_prod = _research_prod_for_recipe(wrap_recipe_key, research_levels)
        v_wrap, _ = solve_self_recycle_target_loop_memoized(
            item_key, data,
            machine_key=machine_key,
            machine_slots=machine_slots,
            machine_allow_prod=machine_allow_prod,
            inherent_prod=inherent_prod,
            research_prod=research_prod,
            module_quality=module_quality,
            prod_module_tier=prod_module_tier,
            quality_module_tier=quality_module_tier,
            target_tier=target_tier,
            wrap_route=route,
            wrap_machine_slots=w_slots,
            wrap_allow_prod=w_allow_prod,
            wrap_inherent_prod=w_inherent,
            wrap_research_prod=w_research_prod,
            _cache=_cache,
        )
        if v_wrap <= 0:
            return None
        mi = {
            "machine_key":   wmk,
            "machine_slots": w_slots,
            "allow_prod":    w_allow_prod,
            "inherent_prod": w_inherent,
            "research_prod": w_research_prod,
        }
        return v_wrap, route, mi

    def _pick_best(pool) -> tuple[float, dict, dict] | None:
        best: tuple[float, dict, dict, float] | None = None  # (score, route, mi, v_wrap)
        for route in pool:
            ev = _evaluate(route)
            if ev is None:
                continue
            v_wrap, r, mi = ev
            co_count = len(r.get("co_solids", []))
            # Cost-penalised score: each extra solid co-ingredient adds an
            # upstream chain.  α = 1/2 → co_count=0 → 1.0×, co_count=2 → 0.5×.
            # Within a homogeneous pool (all single or all multi) this picks
            # the wrap with the highest combined yield + simplicity.
            score = v_wrap / (1.0 + co_count / 2.0)
            if best is None or score > best[0]:
                best = (score, r, mi, v_wrap)
        if best is None:
            return None
        _score, r, mi, v_wrap = best
        return v_wrap, r, mi

    # First try single-ingredient wraps; only fall back to multi-ingredient
    # when none exist or none beat the baseline.
    pick = _pick_best(_candidate_filter(prefer_single=True))
    if pick is None:
        pick = _pick_best(_candidate_filter(prefer_single=False))
    if pick is None:
        return None, None
    v_wrap, route, mi = pick
    # Require meaningful improvement over baseline.  5 % threshold avoids
    # triggering the wrap path for marginal gains.
    if v_wrap <= v_baseline * 1.05:
        return None, None
    return route, mi


def _env_signature(
    *,
    module_quality: str,
    research_levels: dict[str, int],
    assembler_level: int,
    quality_module_tier: int,
    planets: frozenset[str],
    tech_state: dict[str, int],
    assembly_modules: bool,
    prod_module_tier: int,
    machine_quality: str,
    no_asteroids: bool,
    active_shuffles: frozenset[str] | None = None,
    target_tier: int = 4,
    forbid_ore_routes: bool = False,
) -> tuple:
    """Tuple of all kwargs that affect the Path A vs Path B winner.

    Used as the secondary part of the decision-cache key.  Frozen via tuple +
    frozenset so it's hashable.
    """
    rl = tuple(sorted((str(k), int(v)) for k, v in (research_levels or {}).items()))
    ts = tuple(sorted((str(k), int(v)) for k, v in (tech_state or {}).items()))
    sh = tuple(sorted(active_shuffles or ()))
    return (
        module_quality,
        rl,
        int(assembler_level),
        int(quality_module_tier),
        tuple(sorted(planets)),
        ts,
        bool(assembly_modules),
        int(prod_module_tier),
        machine_quality,
        bool(no_asteroids),
        sh,
        int(target_tier),
        bool(forbid_ore_routes),
    )


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
    tech_state: dict[str, int],
    assembly_modules: bool = False,
    prod_module_tier: int = 3,
    machine_quality: str = "normal",
    active_shuffles: frozenset[str] | None = None,
    no_asteroids: bool = False,
    forbid_ore_routes: bool = False,
    target_tier: int = 4,
    _cache: "_DispatchCache | None" = None,
    _in_flight: frozenset[str] = frozenset(),
    _force_no_wrap: bool = False,
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
    locked_machines = _tech_locked_machines(tech_state)

    craft_recipe = _pick_recipe_fluid_preferred(
        item_key, recipe_idx, fluids, planets, planet_props,
        locked_machines=locked_machines, assembler_level=assembler_level,
        forbid_ore_routes=forbid_ore_routes,
    )
    if craft_recipe is None:
        raise ValueError(f"ERROR: no craft recipe for '{item_key}'")
    mr = _machine_for_recipe(craft_recipe, assembler_level, locked_machines)
    if mr is None:
        raise ValueError(
            f"ERROR: cannot produce '{item_key}' — recipe "
            f"'{craft_recipe['key']}' requires a locked machine for category "
            f"'{craft_recipe.get('category')}'.  Add the corresponding --tech flag."
        )
    machine_key, machine_speed = mr
    machine_speed_f = float(machine_speed) * (
        1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
    )
    module_slots_map = cli.build_machine_module_slots(data)
    machine_slots = int(module_slots_map.get(machine_key, 0))
    machine_allow_prod = True  # all crafting machines that allow modules accept prod
    inherent_prod = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
    research_prod = _research_prod_for_recipe(craft_recipe["key"], research_levels)

    # Pick the best wrap route (Reddit "rare-ore wrap-and-recycle") if one
    # beats the no-wrap baseline by >5 %.  Returns (None, None) for items
    # where the direct/single-ingredient path is good enough, AND for any
    # intermediate self-recycle target (top-level only, gated by _in_flight).
    # ``_force_no_wrap`` is set by the dispatcher's cycle guard — when we got
    # here because a higher frame already routed through this item, the wrap
    # path's co-ingredient walks would loop back to the same item.
    if _force_no_wrap:
        wrap_route, wrap_machine_info = None, None
    else:
        wrap_route, wrap_machine_info = _choose_wrap_route(
            item_key, data,
            assembler_level=assembler_level,
            locked_machines=locked_machines,
            planet_props=planet_props,
            module_quality=module_quality,
            quality_module_tier=quality_module_tier,
            prod_module_tier=prod_module_tier,
            target_tier=target_tier,
            machine_key=machine_key,
            machine_slots=machine_slots,
            machine_allow_prod=machine_allow_prod,
            inherent_prod=inherent_prod,
            research_prod=research_prod,
            research_levels=research_levels,
            _cache=_cache,
            _in_flight=_in_flight,
        )
    wrap_active = wrap_route is not None and wrap_machine_info is not None

    if wrap_active:
        assert wrap_route is not None and wrap_machine_info is not None
        wrap_machine_slots = int(wrap_machine_info["machine_slots"])
        wrap_allow_prod    = bool(wrap_machine_info["allow_prod"])
        wrap_inherent_prod = float(wrap_machine_info["inherent_prod"])
        wrap_research_prod = float(wrap_machine_info["research_prod"])
    else:
        wrap_machine_slots = 0
        wrap_allow_prod    = False
        wrap_inherent_prod = 0.0
        wrap_research_prod = 0.0

    v, configs = solve_self_recycle_target_loop_memoized(
        item_key, data,
        machine_key=machine_key,
        machine_slots=machine_slots,
        machine_allow_prod=machine_allow_prod,
        inherent_prod=inherent_prod,
        research_prod=research_prod,
        module_quality=module_quality,
        prod_module_tier=3,
        quality_module_tier=quality_module_tier,
        target_tier=target_tier,
        wrap_route=wrap_route,
        wrap_machine_slots=wrap_machine_slots,
        wrap_allow_prod=wrap_allow_prod,
        wrap_inherent_prod=wrap_inherent_prod,
        wrap_research_prod=wrap_research_prod,
        _cache=_cache,
    )
    if v <= 0:
        raise ValueError(
            f"ERROR: self-recycle loop for '{item_key}' yields 0 legendary — "
            f"check module/quality config (machine={machine_key}, slots={machine_slots})"
        )

    crafts_per_min = rate / v
    craft_time = float(craft_recipe.get("energy_required", 1.0))
    _scfg0 = configs.get(0, {"craft_prod": 0, "craft_quality": 0})
    craft_machines = crafts_per_min * craft_time / (
        machine_speed_f
        * _module_speed_mult(prod_slots=_scfg0.get("craft_prod", 0),
                             quality_slots=_scfg0.get("craft_quality", 0),
                             prod_tier=prod_module_tier)
        * 60.0
    )

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
    qm_mult = 1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
    # Recycle route selection:
    #   * wrap_active  → use the multi-ingredient wrap chosen by _choose_wrap_route.
    #   * otherwise    → legacy build_recycle_shortcuts (direct or
    #                    steel-chest / hazard-concrete single-ingredient wrap).
    if wrap_active:
        assert wrap_route is not None and wrap_machine_info is not None
        retention           = float(wrap_route["retention"])
        rec_time            = float(wrap_route["recycler_time"])
        container           = wrap_route["container"]
        craft_time_per_item = float(wrap_route["craft_time"])
        wrap_machine_key    = str(wrap_machine_info["machine_key"])
        # Scale retention by wrap-craft prod selected by the DP (configs[0]).
        wp0 = int(configs.get(0, {}).get("wrap_prod", 0))
        wrap_prod0 = wrap_inherent_prod + wrap_research_prod + _prod_bonus(
            wp0, prod_module_tier, module_quality,
        )
        if wrap_prod0 > 3.0:
            wrap_prod0 = 3.0
        retention = retention * (1.0 + wrap_prod0)
    else:
        shortcut = build_recycle_shortcuts(data).get(item_key)
        if shortcut is not None:
            retention = shortcut["retention"]
            rec_time = shortcut["recycler_time"]
            container = shortcut["container"]
            craft_time_per_item = shortcut["craft_time"]
            craft_category = shortcut["craft_category"]
        else:
            rec_recipe = _recipe_by_key(data, f"{item_key}-recycling")
            retention = (
                _recipe_result_amount(rec_recipe, item_key) if rec_recipe else RECYCLER_RETENTION
            )
            rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2
            container = None
            craft_time_per_item = 0.0
            craft_category = None
        wrap_machine_key = ""

    total_recycle_crafts = crafts_per_min * items_per_craft / max(1.0 - retention, 1e-6)
    recycler_machines = total_recycle_crafts * rec_time / (
        RECYCLER_SPEED * qm_mult
        * _module_speed_mult(quality_slots=RECYCLER_SLOTS) * 60.0
    )
    # Container-craft assemblers.  Two source paths:
    #   wrap_active → wrap recipe's resolved machine.
    #   legacy     → cli.get_machine on craft_category.
    container_machines = 0.0
    if wrap_active and craft_time_per_item > 0:
        cm_speed = 1.0
        # Resolve via cli.get_machine for the wrap recipe's category to stay
        # consistent with the rest of the planner.
        assert wrap_route is not None
        wrap_recipe = next(
            (r for r in data.get("recipes", []) if r.get("key") == wrap_route["wrap_recipe"]),
            None,
        )
        if wrap_recipe is not None:
            _wmk2, wm_speed = cli.get_machine(
                cli.recipe_categories(wrap_recipe), assembler_level, "electric",
            )
            cm_speed = float(wm_speed)
        cm_speed_f = cm_speed * qm_mult
        container_machines = total_recycle_crafts * craft_time_per_item / (cm_speed_f * 60.0)
    elif container is not None and craft_time_per_item > 0:
        cm_key, cm_speed = cli.get_machine(craft_category or "crafting", assembler_level, "electric")
        cm_speed_f = float(cm_speed) * qm_mult
        container_machines = total_recycle_crafts * craft_time_per_item / (cm_speed_f * 60.0)

    # Walk ingredients at NORMAL quality.  Each ingredient's demand =
    # amount × crafts_per_min.  Solid raws + intermediates need normal-quality
    # production; fluids are quality-transparent.
    #
    # Two ingredient sources when wrap_active:
    #   (1) canonical craft recipe's ingredients (e.g. holmium-solution) —
    #       walked via the quality dispatcher (existing behaviour).
    #   (2) wrap recipe's co-ingredients (e.g. copper-plate for superconductor
    #       wrap) — registered as ``normal_solid_input`` / ``normal_fluid_input``
    #       directly, NOT walked.  Why: blocklisted co-ingredients
    #       (superconductor, processing-unit) would route through the quality
    #       dispatcher, which produces a legendary chain — wrong for "normal-
    #       quality matched co-ingredient" semantics, and prone to recursion
    #       back to the wrapped item itself.  The user sources these via the
    #       regular CLI calculator.
    normal_stages: list[dict] = []
    normal_solid_input: dict[str, float] = {}
    normal_fluid_input: dict[str, float] = {}

    # (1) Canonical recipe ingredients — walked at normal quality.
    ingredient_demands: list[tuple[str, float]] = []
    for ing in craft_recipe.get("ingredients", []):
        ingredient_demands.append((ing["name"], float(ing.get("amount", 0)) * crafts_per_min))
    # (2) Wrap co-ingredients — registered as normal inputs (no walk).
    if wrap_active:
        assert wrap_route is not None
        for c in wrap_route.get("co_solids", []):
            rate_per_min = float(c["amount"]) * total_recycle_crafts
            normal_solid_input[c["name"]] = normal_solid_input.get(c["name"], 0.0) + rate_per_min
        for c in wrap_route.get("co_fluids", []):
            rate_per_min = float(c["amount"]) * total_recycle_crafts
            normal_fluid_input[c["name"]] = normal_fluid_input.get(c["name"], 0.0) + rate_per_min

    for iname, ing_rate in ingredient_demands:
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
                    machine_quality=machine_quality,
                    no_asteroids=no_asteroids,
                    forbid_ore_routes=forbid_ore_routes,
                    tech_state=tech_state,
                    _cache=_cache,
                    _in_flight=_in_flight,
                    _dispatch_env={
                        "module_quality": module_quality,
                        "research_levels": research_levels,
                        "assembler_level": assembler_level,
                        "quality_module_tier": quality_module_tier,
                        "active_shuffles": active_shuffles,
                    },
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
        "machine_count": craft_machines + recycler_machines + container_machines,
        "craft_machines": craft_machines,
        "recycler_machines": recycler_machines,
        "container_machines": container_machines,
        "container": container,
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
                **({
                    "wrap": (
                        f"{configs[t].get('wrap_prod',0)}p+"
                        f"{configs[t].get('wrap_quality',0)}q "
                        f"(t{quality_module_tier} {module_quality})"
                    ),
                } if wrap_active else {}),
            }
            for t in range(target_tier)
        },
    }
    if wrap_active:
        assert wrap_route is not None and wrap_machine_info is not None
        self_stage["wrap_recipe"]  = wrap_route["wrap_recipe"]
        self_stage["wrap_machine"] = wrap_machine_info["machine_key"]
        self_stage["wrap_co_solids"] = [c["name"] for c in wrap_route.get("co_solids", [])]
        self_stage["wrap_co_fluids"] = [c["name"] for c in wrap_route.get("co_fluids", [])]

    total_machines = (
        self_stage["machine_count"]
        + sum(s["machine_count"] for s in normal_stages)
    )

    notes: list[str] = [
        f"self-recycle target '{item_key}' uses {machine_key} (slots={machine_slots}, "
        f"inherent prod={inherent_prod:.2f}); ingredients consumed at normal quality"
    ]
    if wrap_active:
        assert wrap_route is not None and wrap_machine_info is not None
        co_names = [c["name"] for c in wrap_route.get("co_solids", [])]
        notes.append(
            f"wrap-and-recycle via '{wrap_route['wrap_recipe']}' on "
            f"{wrap_machine_info['machine_key']} "
            f"(slots={wrap_machine_info['machine_slots']}, "
            f"inherent prod={wrap_machine_info['inherent_prod']:.2f}); "
            f"co-ingredients sourced at normal quality: {co_names or '(none)'}"
        )

    # Per-stage power + total (V3 power accounting).
    machine_power_w = cli.build_machine_power_w(data)
    all_stages = [self_stage] + normal_stages
    for st in all_stages:
        st["power_kw"] = _stage_power_kw(st, machine_power_w)
    total_power_mw = sum(s["power_kw"] for s in all_stages) / 1000.0

    # Stage-cost summary (by role).
    by_role: dict[str, dict[str, float]] = {}
    for st in all_stages:
        role = st.get("role", "unknown")
        bucket = by_role.setdefault(
            role, {"machines": 0.0, "power_kw": 0.0, "stage_count": 0},
        )
        bucket["machines"] += float(st.get("machine_count", 0.0))
        bucket["power_kw"] += float(st.get("power_kw", 0.0))
        bucket["stage_count"] += 1
    for bucket in by_role.values():
        bucket["machines_pct"] = (
            bucket["machines"] / total_machines * 100.0 if total_machines > 0 else 0.0
        )
        bucket["power_pct"] = (
            bucket["power_kw"] / (total_power_mw * 1000.0) * 100.0
            if total_power_mw > 0 else 0.0
        )

    # Hot-spot suggestions for self-recycle target plan.
    notes.extend(_hot_spot_suggestions(
        by_role,
        active_shuffles=None,
        assembly_modules=assembly_modules,
        has_plastic=False,
        machine_quality=machine_quality,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        planets=planets,
    ))

    return {
        "target": {"item": item_key, "rate_per_min": rate, "tier": QUALITY_TIERS[target_tier]},
        "asteroid_input": {},
        "mined_input": {},
        "fluid_input": {},
        "normal_solid_input": normal_solid_input,
        "normal_fluid_input": normal_fluid_input,
        "shuffle_byproduct_legendary": {},
        "shuffle_byproduct_credited": {},
        "shuffle_byproduct_overflow": {},
        "incidental_byproduct_legendary": {},
        "incidental_byproduct_credited": {},
        "incidental_byproduct_overflow": {},
        "driver_overflow": {},
        "stages": [self_stage] + list(reversed(normal_stages)),
        "total_machine_count": total_machines,
        "total_power_mw": total_power_mw,
        "summary": {"by_role": by_role},
        "module_quality": module_quality,
        "assembler_level": assembler_level,
        "research_levels": dict(research_levels),
        "planets": sorted(planets),
        "notes": notes,
    }


def choose_path_self_recycle(
    item_key: str,
    rate: float,
    data: dict,
    *,
    module_quality: str,
    research_levels: dict[str, int],
    assembler_level: int,
    quality_module_tier: int,
    planets: frozenset[str],
    tech_state: dict[str, int],
    assembly_modules: bool = False,
    prod_module_tier: int = 3,
    machine_quality: str = "normal",
    active_shuffles: frozenset[str] | None = None,
    no_asteroids: bool = False,
    forbid_ore_routes: bool = False,
    target_tier: int = 4,
    _cache: _DispatchCache,
    _in_flight: frozenset[str] = frozenset(),
) -> dict:
    """Dispatch Path A (self-recycle target loop) vs Path B (ingredient-upcycle).

    Single mechanism for both top-level (``plan()`` for SELF_RECYCLE_TARGETS
    items) and intermediate (``walk_recipe_tree`` Pass 1 for blocklist items).
    Memoizes the A/B decision per ``(item, env_signature)`` so deep chains
    don't re-solve the same comparison.

    Cycle guard: if ``item_key in _in_flight`` (i.e. a higher dispatcher is
    currently resolving this same item), force Path A.  Path A is the only
    branch that doesn't recurse through this dispatcher, so it's always safe
    as the cycle-fallback.

    Returns a sub-plan dict in the same shape as ``_plan_self_recycle_target``
    or ``plan()`` (whichever path won).  Callers compose sub-plan ``stages``
    into the parent's stage list.
    """
    env = _env_signature(
        module_quality=module_quality,
        research_levels=research_levels,
        assembler_level=assembler_level,
        quality_module_tier=quality_module_tier,
        planets=planets,
        tech_state=tech_state,
        assembly_modules=assembly_modules,
        prod_module_tier=prod_module_tier,
        machine_quality=machine_quality,
        no_asteroids=no_asteroids,
        active_shuffles=active_shuffles,
        target_tier=target_tier,
        forbid_ore_routes=forbid_ore_routes,
    )
    decision_key = (item_key, env)

    def _run_path_a(force_no_wrap: bool = False) -> dict | None:
        try:
            return _plan_self_recycle_target(
                item_key, rate, data,
                module_quality=module_quality,
                research_levels=research_levels,
                assembler_level=assembler_level,
                quality_module_tier=quality_module_tier,
                planets=planets,
                tech_state=tech_state,
                assembly_modules=assembly_modules,
                prod_module_tier=prod_module_tier,
                machine_quality=machine_quality,
                active_shuffles=active_shuffles,
                no_asteroids=no_asteroids,
                forbid_ore_routes=forbid_ore_routes,
                target_tier=target_tier,
                _cache=_cache,
                _in_flight=_in_flight | {item_key},
                _force_no_wrap=force_no_wrap,
            )
        except ValueError:
            return None

    def _run_path_b() -> tuple[dict | None, str | None]:
        try:
            return plan(
                item_key, rate, data,
                module_quality=module_quality,
                research_levels=research_levels,
                assembler_level=assembler_level,
                quality_module_tier=quality_module_tier,
                planets=planets,
                active_shuffles=active_shuffles,
                assembly_modules=assembly_modules,
                prod_module_tier=prod_module_tier,
                machine_quality=machine_quality,
                no_asteroids=no_asteroids,
                forbid_ore_routes=forbid_ore_routes,
                tech_state=tech_state,
                target_tier=target_tier,
                _force_tree_walk=True,
                _cache=_cache,
                _in_flight=_in_flight | {item_key},
                _force_tree_walk_for=frozenset({item_key}),
            ), None
        except ValueError as exc:
            return None, str(exc)

    # --- Cycle guard ---
    if item_key in _in_flight:
        # Force-disable the wrap path: a higher frame is already resolving
        # this item, so walking wrap co-ingredients would loop back here.
        path_a = _run_path_a(force_no_wrap=True)
        if path_a is None:
            raise ValueError(
                f"ERROR: cycle detected for '{item_key}' through {sorted(_in_flight)} "
                f"and forced Path A also failed"
            )
        path_a.setdefault("notes", []).append(
            f"forced self-recycle (cycle detected through {sorted(_in_flight)})"
        )
        return path_a

    # --- Decision cache ---
    cached = _cache.plans.get(decision_key)
    if cached == "A":
        path_a = _run_path_a()
        if path_a is None:
            # Cached "A" but suddenly fails — fall through and recompute.
            cached = None
        else:
            path_a.setdefault("notes", []).append(
                f"auto-compare (cached): self-recycle loop "
                f"({path_a['total_machine_count']:.1f} machines)."
            )
            return path_a
    if cached == "B":
        path_b, err = _run_path_b()
        if path_b is None:
            cached = None
        else:
            path_b.setdefault("notes", []).append(
                f"auto-compare (cached): ingredient-upcycle "
                f"({path_b['total_machine_count']:.1f} machines)."
            )
            return path_b

    # --- Cache miss: run both, compare, cache decision ---
    _cache.plan_kernel_calls += 1
    path_a = _run_path_a()
    path_b, path_b_error = _run_path_b()

    if path_a is None and path_b is None:
        raise ValueError(
            f"ERROR: both Path A and Path B failed for '{item_key}'; "
            f"Path B error: {path_b_error or '?'}"
        )

    a_count = float(path_a["total_machine_count"]) if path_a is not None else float("inf")
    b_count = (
        float(path_b["total_machine_count"]) if path_b is not None else float("inf")
    )

    # Pick the cheaper path.  Tie -> Path A (self-recycle is structurally
    # simpler / more diagnostic).
    if path_b is None:
        # Path B failed entirely.
        assert path_a is not None
        _cache.plans[decision_key] = "A"
        path_a.setdefault("notes", []).append(
            f"auto-compare: ingredient-upcycle path failed "
            f"({(path_b_error or '')[:120]}); using self-recycle loop "
            f"({a_count:.1f} machines)."
        )
        return path_a
    if path_a is None:
        _cache.plans[decision_key] = "B"
        path_b.setdefault("notes", []).append(
            f"auto-compare: self-recycle loop failed; using ingredient-upcycle "
            f"({b_count:.1f} machines)."
        )
        return path_b

    if b_count > 0 and b_count < a_count:
        _cache.plans[decision_key] = "B"
        path_b.setdefault("notes", []).append(
            f"auto-compare: ingredient-upcycle ({b_count:.1f} machines) "
            f"beats self-recycle loop ({a_count:.1f} machines)."
        )
        return path_b

    _cache.plans[decision_key] = "A"
    path_a.setdefault("notes", []).append(
        f"auto-compare: self-recycle loop ({a_count:.1f} machines) "
        f"beats ingredient-upcycle ({b_count:.1f} machines)."
    )
    return path_a


def _plan_self_feed_target(
    item_key: str,
    rate: float,
    data: dict,
    *,
    module_quality: str,
    research_levels: dict[str, int],
    assembler_level: int,
    quality_module_tier: int,
    planets: frozenset[str],
    tech_state: dict[str, int],
    assembly_modules: bool = False,
    prod_module_tier: int = 3,
    machine_quality: str = "normal",
    forbid_ore_routes: bool = False,
    target_tier: int = 4,
) -> dict:
    """Plan a chain whose target is a self-FEED recipe (ingredient = output).

    Mirrors :func:`_plan_self_recycle_target` but skips the self-ingredient
    when walking upstream demands (the self-feed loop supplies its own input)
    and dispatches to :func:`solve_self_feed_target_loop` for the LP-based
    flow solve.

    The auto-comparator (Path A vs Path B) does NOT apply here: Path B would
    recurse into the same problem since ingredient = output, so it is
    structurally unhelpful.
    """
    recipe_idx = cli.build_recipe_index(data)
    fluids = build_fluid_set(data)
    planet_props = _combined_planet_props(data, planets)
    locked_machines = _tech_locked_machines(tech_state)
    craft_recipe = _pick_recipe_fluid_preferred(
        item_key, recipe_idx, fluids, planets, planet_props,
        locked_machines=locked_machines, assembler_level=assembler_level,
        forbid_ore_routes=forbid_ore_routes,
    )
    if craft_recipe is None:
        raise ValueError(f"ERROR: no craft recipe for '{item_key}'")
    mr = _machine_for_recipe(craft_recipe, assembler_level, locked_machines)
    if mr is None:
        raise ValueError(
            f"ERROR: cannot produce '{item_key}' — recipe "
            f"'{craft_recipe['key']}' requires a locked machine for category "
            f"'{craft_recipe.get('category')}'.  Add the corresponding --tech flag."
        )
    machine_key, machine_speed = mr
    machine_speed_eff = float(machine_speed) * (
        1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0))
    )
    module_slots_map = cli.build_machine_module_slots(data)
    machine_slots = int(module_slots_map.get(machine_key, 0))
    inherent_prod = MACHINE_INHERENT_PROD.get(machine_key, 0.0)
    research_prod = _research_prod_for_recipe(craft_recipe["key"], research_levels)

    _yield, plan_data = solve_self_feed_target_loop(
        item_key, data,
        machine_slots=machine_slots,
        machine_speed_eff=machine_speed_eff,
        inherent_prod=inherent_prod,
        research_prod=research_prod,
        module_quality=module_quality,
        machine_quality=machine_quality,
        prod_module_tier=prod_module_tier,
        quality_module_tier=quality_module_tier,
        target_tier=target_tier,
    )
    if not plan_data:
        raise ValueError(
            f"ERROR: self-feed loop for '{item_key}' has no feasible config — "
            f"machine={machine_key}, slots={machine_slots}.  Check that the "
            f"recipe is super-productive (output × p_stay > 1) at all tiers."
        )

    # Scale unit LP solution to target rate.
    drain_per_unit = float(plan_data["drain_per_unit"])
    scale = rate / drain_per_unit
    x = [float(v) * scale for v in plan_data["x_unit"]]
    y = [float(v) * scale for v in plan_data["y_unit"]]
    kc_per_tier = [float(v) for v in plan_data["kc_per_tier"]]
    kr_per_tier = [float(v) for v in plan_data["kr_per_tier"]]
    craft_machines_per_tier = [x[q] * kc_per_tier[q] for q in range(target_tier)]
    recycler_machines_per_tier = [y[q] * kr_per_tier[q] for q in range(target_tier)]
    craft_machines_total = sum(craft_machines_per_tier)
    recycler_machines_total = sum(recycler_machines_per_tier)
    crafts_per_min_total = sum(x)
    recycles_per_min_total = sum(y)

    cps = plan_data["cps"]
    cqs = plan_data["cqs"]
    rqs = plan_data["rqs"]

    # Walk non-self ingredients at NORMAL quality.  Each ingredient amount is
    # consumed per craft; total demand = amount × crafts_per_min_total.
    normal_stages: list[dict] = []
    normal_solid_input: dict[str, float] = {}
    normal_fluid_input: dict[str, float] = {}
    for ing in craft_recipe.get("ingredients", []):
        iname = ing["name"]
        if iname == item_key:
            continue  # self-ingredient — supplied by the loop itself
        amt = float(ing.get("amount", 0))
        ing_rate = amt * crafts_per_min_total
        if iname in fluids:
            normal_fluid_input[iname] = normal_fluid_input.get(iname, 0.0) + ing_rate
            continue
        try:
            sub_stages, sub_raws = walk_recipe_tree(
                iname, ing_rate, data, research_levels, assembler_level,
                fluids, planet_props, planets,
                assembly_modules=assembly_modules,
                assembly_module_quality=module_quality,
                prod_module_tier=prod_module_tier,
                machine_quality=machine_quality,
                forbid_ore_routes=forbid_ore_routes,
                tech_state=tech_state,
            )
        except ValueError:
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
        "role": "self-feed-target",
        "target": item_key,
        "recipe": str(plan_data["craft_recipe_key"]),
        "machine": machine_key,
        "machine_count": craft_machines_total + recycler_machines_total,
        "craft_machines": craft_machines_total,
        "recycler_machines": recycler_machines_total,
        "crafts_per_min": crafts_per_min_total,
        "recycles_per_min": recycles_per_min_total,
        "rate_per_min": rate,
        "q_star": int(plan_data["q_star"]),
        "per_tier_flows": {
            QUALITY_TIERS[q]: {
                "crafts_per_min": x[q],
                "recycles_per_min": y[q],
                "craft_machines": craft_machines_per_tier[q],
                "recycler_machines": recycler_machines_per_tier[q],
            }
            for q in range(target_tier)
        },
        "module_config_per_tier": {
            QUALITY_TIERS[q]: {
                "craft": (
                    f"{cps[q]}p+{cqs[q]}q "
                    f"(t{quality_module_tier} {module_quality})"
                ),
                "recycle": (
                    f"{rqs[q]}q "
                    f"(t{quality_module_tier} {module_quality})"
                ),
            }
            for q in range(target_tier)
        },
    }

    total_machines = (
        self_stage["machine_count"]
        + sum(s["machine_count"] for s in normal_stages)
    )

    notes: list[str] = [
        f"self-feed target '{item_key}' uses {machine_key} (slots={machine_slots}, "
        f"inherent prod={inherent_prod:.2f}); ingredient = output -> loop self-"
        f"sustains, only non-self ingredients are sourced externally",
        f"LP corner picked: q*={plan_data['q_star']} (single tier hosts crafts; "
        f"others run recyclers only); auto-comparator skipped (Path B reduces "
        f"to the same problem)",
    ]

    machine_power_w = cli.build_machine_power_w(data)
    all_stages = [self_stage] + normal_stages
    for st in all_stages:
        st["power_kw"] = _stage_power_kw(st, machine_power_w)
    total_power_mw = sum(s["power_kw"] for s in all_stages) / 1000.0

    by_role: dict[str, dict[str, float]] = {}
    for st in all_stages:
        role = st.get("role", "unknown")
        bucket = by_role.setdefault(
            role, {"machines": 0.0, "power_kw": 0.0, "stage_count": 0},
        )
        bucket["machines"] += float(st.get("machine_count", 0.0))
        bucket["power_kw"] += float(st.get("power_kw", 0.0))
        bucket["stage_count"] += 1
    for bucket in by_role.values():
        bucket["machines_pct"] = (
            bucket["machines"] / total_machines * 100.0 if total_machines > 0 else 0.0
        )
        bucket["power_pct"] = (
            bucket["power_kw"] / (total_power_mw * 1000.0) * 100.0
            if total_power_mw > 0 else 0.0
        )

    notes.extend(_hot_spot_suggestions(
        by_role,
        active_shuffles=None,
        assembly_modules=assembly_modules,
        has_plastic=False,
        machine_quality=machine_quality,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        planets=planets,
    ))

    return {
        "target": {"item": item_key, "rate_per_min": rate, "tier": QUALITY_TIERS[target_tier]},
        "asteroid_input": {},
        "mined_input": {},
        "fluid_input": {},
        "normal_solid_input": normal_solid_input,
        "normal_fluid_input": normal_fluid_input,
        "shuffle_byproduct_legendary": {},
        "shuffle_byproduct_credited": {},
        "shuffle_byproduct_overflow": {},
        "incidental_byproduct_legendary": {},
        "incidental_byproduct_credited": {},
        "incidental_byproduct_overflow": {},
        "driver_overflow": {},
        "stages": [self_stage] + list(reversed(normal_stages)),
        "total_machine_count": total_machines,
        "total_power_mw": total_power_mw,
        "summary": {"by_role": by_role},
        "module_quality": module_quality,
        "assembler_level": assembler_level,
        "research_levels": dict(research_levels),
        "planets": sorted(planets),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

def _plan_fluid_chain_via_cli(
    fluid_demand: dict[str, float],
    location: str,
    data: dict,
    fluids: frozenset[str],
) -> dict:
    """Delegate fluid sub-chain production to ``cli.py`` (Fulgora only).

    The quality planner's own recipe selector is not wired for oil/sulfur fluid
    chains (it picks ``advanced-carbonic-asteroid-crushing`` for ``sulfur`` and
    dies under ``--no-asteroids``), whereas ``cli.py`` solves them correctly.  So
    for every demanded fluid we shell out to ``cli.py --item <fluid> --rate <r>
    --location <location>`` with *every* scrap-reachable solid bussed in
    (``--bus-item``).  Bussing the solids stops ``cli.py`` from recursing into ore
    — those intermediates (ice, iron-plate, …) come for free from the scrap
    cascade's overflow, so they must not grow the scrap input.

    Returns ``{stages, fluid_raws, scrap_draw, unresolved}``:
      * ``stages`` — one ``role="fluid-chain"`` stage per ``cli`` production step
        (``recipe``/``machine``/``machine_count``/``rate_per_min``/``fluid_target``).
      * ``fluid_raws`` — true pumped raws (e.g. ``heavy-oil``) ``cli`` bottoms out
        at; these replace the demanded fluid in ``fluid_input``.
      * ``scrap_draw`` — scrap-reachable solids/bus items the sub-chain consumes
        (credited against scrap-source overflow, NOT added to scrap input).
      * ``unresolved`` — fluids ``cli`` could not solve (nonzero exit / bad JSON);
        left as raws so the plan still completes.
    """
    cascade = build_scrap_cascade(data)["depth_amounts"]
    bus_solids = sorted(k for k in cascade if k not in fluids)
    cli_path = os.path.join(_CLI_DIR, "cli.py")
    stages: list[dict] = []
    fluid_raws: dict[str, float] = {}
    scrap_draw: dict[str, float] = {}
    unresolved: dict[str, float] = {}
    for fluid, rate in sorted(fluid_demand.items()):
        if rate <= 0:
            continue
        cmd = [
            sys.executable, cli_path,
            "--item", fluid, "--rate", repr(float(rate)),
            "--location", location,
        ]
        for solid in bus_solids:
            cmd += ["--bus-item", solid]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                unresolved[fluid] = unresolved.get(fluid, 0.0) + float(rate)
                continue
            res = json.loads(proc.stdout)
        except (OSError, ValueError):
            unresolved[fluid] = unresolved.get(fluid, 0.0) + float(rate)
            continue
        for step in res.get("production_steps", []):
            outputs = step.get("outputs") or {}
            # cli emits per-item output rates (no single rate_per_min); use the
            # output matching the recipe key, else the largest output (display
            # only — totals/power key off machine_count).
            rate_pm = outputs.get(step.get("recipe"))
            if rate_pm is None:
                rate_pm = max(outputs.values(), default=0.0)
            stages.append({
                "role": "fluid-chain",
                "recipe": step.get("recipe"),
                "machine": step.get("machine"),
                "machine_count": float(step.get("machine_count", 0.0) or 0.0),
                "rate_per_min": float(rate_pm or 0.0),
                "fluid_target": fluid,
            })
        for rk, rv in (res.get("raw_resources") or {}).items():
            if rk in fluids:
                fluid_raws[rk] = fluid_raws.get(rk, 0.0) + float(rv)
            else:
                scrap_draw[rk] = scrap_draw.get(rk, 0.0) + float(rv)
        for bk, bv in (res.get("bus_inputs") or {}).items():
            scrap_draw[bk] = scrap_draw.get(bk, 0.0) + float(bv)
    return {
        "stages": stages,
        "fluid_raws": fluid_raws,
        "scrap_draw": scrap_draw,
        "unresolved": unresolved,
    }


def optimize_quality_placement(
    item_key: str,
    rate: float,
    data: dict,
    *,
    module_quality: str = "legendary",
    quality_module_tier: int = 3,
    assembler_level: int = 3,
    planets: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    tech_state: dict[str, int] | None = None,
    target_tier: int = 4,
) -> dict:
    """Evaluate quality module placements across chain steps for item_key (roadmap Q4)."""
    planets_fs = frozenset(planets) if planets else frozenset({"nauvis"})
    tech_state = tech_state or ALL_TECH_UNLOCKED

    baseline_stages, _ = walk_recipe_tree(
        item_key, rate, data, {}, assembler_level,
        build_fluid_set(data), _combined_planet_props(data, planets_fs), planets_fs,
        tech_state=tech_state,
    )

    placements = []
    slots_map = cli.build_machine_module_slots(data)
    for st in baseline_stages:
        rec_key = st.get("recipe")
        if not rec_key:
            continue
        rec = _recipe_by_key(data, rec_key)
        if rec is None or not cli.recipe_allows_quality(rec):
            continue
        m_key = st.get("machine", "assembling-machine-3")
        slots = int(slots_map.get(m_key, 4))
        for q_slots in range(1, slots + 1):
            q_chance = _quality_chance(q_slots, quality_module_tier, module_quality)
            q_probs = _tier_skip_probs(q_chance, 0)
            target_frac = q_probs[target_tier] if target_tier < len(q_probs) else q_probs[-1]
            craft_rate = rate / max(0.001, target_frac)
            cost_est = len(baseline_stages) + craft_rate / 60.0
            placements.append({
                "stage": rec_key,
                "product": st.get("product", item_key),
                "quality_slots": q_slots,
                "q_chance_pct": q_chance * 100.0,
                "target_yield_pct": target_frac * 100.0,
                "est_machines": cost_est,
            })

    placements.sort(key=lambda p: p["est_machines"])

    best_plan = plan(
        item_key, rate, data,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        assembler_level=assembler_level,
        planets=planets,
        tech_state=tech_state,
        target_tier=target_tier,
    )

    notes = list(best_plan.get("notes", []))
    notes.append("=== Quality Placement Comparison (top candidates) ===")
    for p in placements[:3]:
        notes.append(
            f"  step '{p['stage']}' ({p['quality_slots']}x quality-{quality_module_tier}-{module_quality}): "
            f"roll chance {p['q_chance_pct']:.1f}%, target yield {p['target_yield_pct']:.2f}% "
            f"-> ~{p['est_machines']:.1f} machines"
        )
    best_plan["notes"] = notes
    best_plan["placements"] = placements
    return best_plan


def plan(
    item_key: str,
    rate: float,
    data: dict,
    *,
    module_quality: str | None = None,
    research_levels: dict[str, int] | None = None,
    assembler_level: int = 3,
    quality_module_tier: int = 3,
    planets: list[str] | tuple[str, ...] | frozenset[str] | None = None,
    active_shuffles: set[str] | frozenset[str] | None = None,
    active_drivers: set[str] | frozenset[str] | None = None,
    assembly_modules: bool = False,
    prod_module_tier: int = 3,
    machine_quality: str = "normal",
    no_asteroids: bool = False,
    location: str | None = None,
    forbid_ore_routes: bool = False,
    tech_state: dict[str, int],
    target_tier: int = 4,
    miner_type: str = "electric",
    miner_quality_modules: bool = True,
    scrap_upcycle_loops: bool = True,
    no_spoilage: bool = False,
    optimize_placement: bool = False,
    beacons: int = 0,
    objective: str = "machines",
    _force_tree_walk: bool = False,
    _scrap_disabled: bool = False,
    _cache: _DispatchCache | None = None,
    _in_flight: frozenset[str] = frozenset(),
    _force_tree_walk_for: frozenset[str] = frozenset(),
) -> dict:
    """Top-level planning: walk tree, attach asteroid reprocessing loops for raws,
    scale stages, assemble full output.
    ``cli.py --location``).  ``--location fulgora`` unlocks Fulgora and switches
    to scrap-only sourcing: there is no asteroid platform, so base materials come
    from the scrap-recycling quality source and metals terminate at their
    scrap-reachable plate form.  ``forbid_ore_routes`` is the internal bool this
    derives (``location == "fulgora"``); it is propagated to recursive ``plan()``
    / dispatch calls.  Only ``fulgora`` currently alters sourcing — other
    locations merely unlock that planet.

    ``tech_state`` is a required keyword argument: ``dict[tech_name → level]``.
    Empty dict = nothing researched (fail-fast on the recycler check).  Use
    ``ALL_TECH_UNLOCKED`` for the "fully researched" baseline.

    ``_force_tree_walk`` (internal) bypasses the SELF_RECYCLE_TARGETS dispatch
    so the auto-comparator (V3 item 4) can compute Path B (ingredient-upcycle)
    for items that would otherwise route through ``_plan_self_recycle_target``.
    """
    if optimize_placement:
        return optimize_quality_placement(
            item_key, rate, data,
            module_quality=module_quality or "legendary",
            quality_module_tier=quality_module_tier,
            assembler_level=assembler_level,
            planets=planets,
            tech_state=tech_state,
            target_tier=target_tier,
        )
    research_levels = research_levels or {}
    # Build location: Fulgora forces scrap-only sourcing (no asteroid platform).
    # ``forbid_ore_routes`` may also arrive directly from a recursive plan() /
    # dispatch call that already derived it.
    fulgora_mode = location == "fulgora"
    forbid_ore_routes = forbid_ore_routes or fulgora_mode
    # On Fulgora the asteroid reprocessing / crushing path is physically
    # unavailable, so reuse the no-asteroid gating for those stage blocks.
    no_asteroids = no_asteroids or fulgora_mode
    # Fulgora ships with the recycler and electromagnetic plant unlocked — they
    # are the planet's native machines and you cannot do any scrap-recycling
    # quality work without them.  Treat those techs as researched when building
    # on Fulgora (matching cli.py, which assumes the EM plant there).  Without
    # this the planner silently falls back to assembling-machine-3 for the
    # electronics recipes, losing the EM plant's inherent +50% prod and its 5th
    # module slot — and forcing the recycler fail-fast below to reject Fulgora
    # plans that omitted --tech recycling=1.
    if fulgora_mode:
        tech_state = {**tech_state, "recycling": 1, "electromagnetic-plant": 1}
    # Module/machine quality default to the target tier and may not exceed it:
    # you can't have modules or machines of a quality you haven't researched
    # (and if you've researched epic/legendary you'd be targeting it, not rare).
    if module_quality is None:
        module_quality = QUALITY_TIERS[target_tier]
    if QUALITY_INDEX[module_quality] > target_tier:
        raise ValueError(
            f"ERROR: --module-quality {module_quality} exceeds --target-quality "
            f"{QUALITY_TIERS[target_tier]} — you can't have modules of a quality "
            "you haven't researched. Lower --module-quality or raise --target-quality."
        )
    if QUALITY_INDEX[machine_quality] > target_tier:
        raise ValueError(
            f"ERROR: --machine-quality {machine_quality} exceeds --target-quality "
            f"{QUALITY_TIERS[target_tier]} — you can't build machines of a quality "
            "you haven't researched. Lower --machine-quality or raise --target-quality."
        )
    planets_fs: frozenset[str] = frozenset(planets) if planets else frozenset()
    # --location unlocks the planet it builds on (so its local raws are
    # available without also having to pass --planets).
    if location:
        if location not in KNOWN_PLANETS:
            raise ValueError(
                f"ERROR: unknown --location '{location}'; valid: {list(KNOWN_PLANETS)}"
            )
        planets_fs = planets_fs | {location}
    # Validate planet names against the known list.
    unknown = planets_fs - set(KNOWN_PLANETS)
    if unknown:
        raise ValueError(
            f"ERROR: unknown planet(s) {sorted(unknown)} in --planets; "
            f"valid: {list(KNOWN_PLANETS)}"
        )
    # Tech-state fail-fast: recycler is required for any quality work.
    locked_machines = _tech_locked_machines(tech_state)
    if "recycler" in locked_machines:
        raise ValueError(
            "ERROR: --tech recycling=0 — no quality work is possible without "
            "the recycler.  Add --tech recycling=1 to proceed."
        )
    if item_key in SELF_RECYCLING_BLOCKLIST and item_key not in SELF_RECYCLE_TARGETS:
        raise ValueError(
            f"ERROR: recipe '{item_key}' is self-recycling (output recycles to itself) — not supported"
        )

    # Allocate the dispatch cache once per top-level plan() call and thread
    # it through every walker site below so intermediate self-recycle
    # dispatches memoize across the full chain.  Recursive plan() entries
    # (Path B re-entry) reuse the caller's cache.
    if _cache is None:
        _cache = _DispatchCache()

    # V3 item 4 (cont.): self-FEED targets (pentapod-egg etc.) — recipes whose
    # ingredient list contains the output.  LP-based steady-state solver, no
    # auto-comparator (Path B reduces to the same problem).
    if item_key in SELF_FEED_TARGETS:
        # Planet-unlock fail-fast for clearer error before we try recipe pick.
        if item_key in PLANET_UNLOCKS and not _planet_unlocks_item(item_key, planets_fs):
            needed = PLANET_UNLOCKS[item_key]
            raise ValueError(
                f"ERROR: item '{item_key}' requires one of planet(s) {list(needed)} "
                f"— add --planets {','.join(needed)}"
            )
        return _plan_self_feed_target(
            item_key, rate, data,
            module_quality=module_quality,
            research_levels=research_levels,
            assembler_level=assembler_level,
            quality_module_tier=quality_module_tier,
            planets=planets_fs,
            tech_state=tech_state,
            assembly_modules=assembly_modules,
            prod_module_tier=prod_module_tier,
            machine_quality=machine_quality,
            forbid_ore_routes=forbid_ore_routes,
            target_tier=target_tier,
        )

    # V3: dedicated self-recycle target path.  Post-2026-05-08-audit, this
    # is the ONLY top-level entry into ``choose_path_self_recycle`` — the
    # same dispatcher is also called from ``walk_recipe_tree`` Pass 1 for
    # intermediate items.  Both auto-compare Path A vs Path B and share the
    # ``_DispatchCache`` allocated above.
    if item_key in SELF_RECYCLE_TARGETS and not _force_tree_walk:
        return choose_path_self_recycle(
            item_key, rate, data,
            module_quality=module_quality,
            research_levels=research_levels,
            assembler_level=assembler_level,
            quality_module_tier=quality_module_tier,
            planets=planets_fs,
            tech_state=tech_state,
            assembly_modules=assembly_modules,
            prod_module_tier=prod_module_tier,
            machine_quality=machine_quality,
            active_shuffles=frozenset(active_shuffles) if active_shuffles else None,
            no_asteroids=no_asteroids,
            forbid_ore_routes=forbid_ore_routes,
            target_tier=target_tier,
            _cache=_cache,
            _in_flight=_in_flight,
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
    beacon_speed_bonus = beacons * 2.5
    qm_speed_mult = 1.0 + float(cli.MACHINE_QUALITY_SPEED.get(machine_quality, 0)) + beacon_speed_bonus
    # Dispatch env: bundles the kwargs walk_recipe_tree's intermediate-dispatch
    # path needs to call choose_path_self_recycle.  Threaded into every walker
    # call below so any blocklist intermediate can dispatch consistently.
    dispatch_env = {
        "module_quality": module_quality,
        "research_levels": research_levels,
        "assembler_level": assembler_level,
        "quality_module_tier": quality_module_tier,
        "active_shuffles": frozenset(active_shuffles) if active_shuffles else None,
        "target_tier": target_tier,
    }
    # ---- Fulgora scrap-recycling quality source (auto when Fulgora unlocked) ----
    # On Fulgora the cheap quality source is scrap recycling, not imported
    # asteroid chunks.  We mark scrap-reachable "base materials" (iron-plate,
    # copper-plate, holmium-ore, …) as walk terminals so the chain stops there
    # and they are sourced from a scrap-recycling stage below; everything that
    # can be crafted from those (battery, gears, …) is still crafted normally.
    scrap_active = "fulgora" in planets_fs and not _scrap_disabled
    scrap_terminals: frozenset[str] = frozenset()
    if scrap_active:
        scrap_reachable = set(build_scrap_cascade(data)["depth_amounts"])
        scrap_terminals = scrap_terminal_set(scrap_reachable, item_key, data, fluids)

    # Track intermediates dispatched directly by this plan() level's walker
    # call(s) so we can aggregate their normal-quality inputs without
    # double-counting entries that recursive Path B plan() calls already
    # aggregated into their own normal_solid_input.
    direct_dispatches: set[str] = set()
    stages, raw_demand = walk_recipe_tree(
        item_key, rate, data, research_levels, assembler_level, fluids, planet_props, planets_fs,
        extra_raws=scrap_terminals or None,
        assembly_modules=assembly_modules,
        assembly_module_quality=module_quality,
        prod_module_tier=prod_module_tier,
        machine_quality=machine_quality,
        no_asteroids=no_asteroids,
        forbid_ore_routes=forbid_ore_routes,
        tech_state=tech_state,
        _cache=_cache,
        _in_flight=_in_flight,
        _force_tree_walk_for=_force_tree_walk_for,
        _dispatch_env=dispatch_env,
        _dispatch_out=direct_dispatches,
    )

    # ---- Generic shuffle wiring (V3) ----
    shuffle_stages: list[dict] = []
    normal_chain_stages: list[dict] = []
    normal_solid_input: dict[str, float] = {}
    normal_fluid_input: dict[str, float] = {}
    shuffle_byproduct_legendary: dict[str, float] = {}
    shuffle_byproduct_credited: dict[str, float] = {}
    shuffle_byproduct_overflow: dict[str, float] = {}
    extra_notes: list[str] = []
    if active_shuffles:
        # Resolve which candidates the user enabled.  Sentinel "all" picks
        # every candidate produced by enumeration.
        all_candidates = enumerate_shuffle_candidates(data)
        if "all" in active_shuffles:
            enabled_candidates = list(all_candidates)
        else:
            enabled_candidates = [
                c for c in all_candidates if c.output_item in active_shuffles
            ]
            unknown_shuffles = (
                set(active_shuffles)
                - {c.output_item for c in all_candidates}
                - {"all"}
            )
            if unknown_shuffles:
                raise ValueError(
                    f"ERROR: unknown shuffle name(s) {sorted(unknown_shuffles)} "
                    f"in --enable-shuffle; valid output_items: "
                    f"{sorted(c.output_item for c in all_candidates)}"
                )

        # Identify legendary solid demands from the initial walker pass.
        # Includes assembly stage products (each demanded at rate_per_min)
        # and solid raws still in raw_demand.
        #
        # The top-level target IS included — a shuffle CAN be a valid
        # production path for the target itself (e.g. LDS shuffle for a
        # plastic-bar target).  The cost gate (under --enable-shuffles all)
        # rejects shuffles that don't actually help, including weird cases
        # like quantum-processor shuffle for a processing-unit target.
        legendary_solid_demand: dict[str, float] = {}
        for st in stages:
            p = st.get("product")
            if p and p not in fluids:
                legendary_solid_demand[p] = (
                    legendary_solid_demand.get(p, 0.0)
                    + float(st.get("rate_per_min", 0.0))
                )
        for raw, dem in raw_demand.items():
            if dem > 0 and raw not in fluids:
                legendary_solid_demand[raw] = (
                    legendary_solid_demand.get(raw, 0.0) + float(dem)
                )

        # Greedy selection: for each demand item, pick the best shuffle
        # candidate that produces it (as primary or byproduct).
        chosen_stages = select_shuffles_greedy(
            legendary_solid_demand, enabled_candidates, data,
            module_quality=module_quality,
            quality_module_tier=quality_module_tier,
            prod_module_tier=prod_module_tier,
            research_levels=research_levels,
            machine_quality=machine_quality,
            planets=planets_fs,
            target_tier=target_tier,
        )

        if chosen_stages:
            # Aggregate primaries (extra_raws) and byproduct credits across
            # all chosen shuffles.
            primaries = frozenset(s["primary"] for s in chosen_stages)
            aggregated_byproducts: dict[str, float] = defaultdict(float)
            for s in chosen_stages:
                for byprod, byrate in s["byproduct_legendary"].items():
                    aggregated_byproducts[byprod] += float(byrate)

            # Re-walk main chain treating each primary as supplied externally.
            direct_dispatches = set()  # reset: only the final walker call counts
            stages, raw_demand = walk_recipe_tree(
                item_key, rate, data, research_levels, assembler_level,
                fluids, planet_props, planets_fs,
                extra_raws=(primaries | scrap_terminals) or None,
                assembly_modules=assembly_modules,
                assembly_module_quality=module_quality,
                prod_module_tier=prod_module_tier,
                machine_quality=machine_quality,
                no_asteroids=no_asteroids,
                forbid_ore_routes=forbid_ore_routes,
                tech_state=tech_state,
                _cache=_cache,
                _in_flight=_in_flight,
                _force_tree_walk_for=_force_tree_walk_for,
                _dispatch_env=dispatch_env,
                _dispatch_out=direct_dispatches,
            )
            for p in primaries:
                raw_demand.pop(p, None)

            # Cap byproduct credits at observed demand; flag surplus.
            stage_demand = {s.get("product"): s["rate_per_min"] for s in stages}
            capped_credits: dict[str, float] = {}
            overflow: dict[str, float] = {}
            for byprod, byrate in aggregated_byproducts.items():
                have = float(
                    stage_demand.get(byprod, raw_demand.get(byprod, 0.0))
                )
                cap = min(float(byrate), have)
                capped_credits[byprod] = cap
                surplus = float(byrate) - cap
                if surplus > 1e-6:
                    overflow[byprod] = surplus

            if any(v > 0 for v in capped_credits.values()):
                # Re-walk with credits subtracted from initial demand.
                direct_dispatches = set()
                stages, raw_demand = walk_recipe_tree(
                    item_key, rate, data, research_levels, assembler_level,
                    fluids, planet_props, planets_fs,
                    extra_raws=(primaries | scrap_terminals) or None,
                    byproduct_credits=capped_credits,
                    assembly_modules=assembly_modules,
                    assembly_module_quality=module_quality,
                    prod_module_tier=prod_module_tier,
                    machine_quality=machine_quality,
                    no_asteroids=no_asteroids,
                    forbid_ore_routes=forbid_ore_routes,
                    tech_state=tech_state,
                    _cache=_cache,
                    _in_flight=_in_flight,
                    _force_tree_walk_for=_force_tree_walk_for,
                    _dispatch_env=dispatch_env,
                    _dispatch_out=direct_dispatches,
                )
                for p in primaries:
                    raw_demand.pop(p, None)

            for byprod, surplus in overflow.items():
                extra_notes.append(
                    f"shuffle byproduct surplus: {surplus:.1f} legendary "
                    f"{byprod}/min unused (no downstream demand)"
                )

            # Walk the normal-quality leg for each solid ingredient separately,
            # then route its raws into the normal_input bucket.
            for s in chosen_stages:
                norm_inputs = s.get("normal_solid_inputs")
                if norm_inputs:
                    input_pairs = list(norm_inputs.items())
                else:
                    primary = s["primary"]
                    normal_in = float(s["normal_primary_in_per_min"])
                    input_pairs = [(primary, normal_in)]

                for ing_item, normal_in in input_pairs:
                    if normal_in <= 0:
                        continue
                    n_stages, n_raws = walk_recipe_tree(
                        ing_item, normal_in, data, research_levels, assembler_level,
                    fluids, planet_props, planets_fs,
                    assembly_modules=assembly_modules,
                    assembly_module_quality=module_quality,
                    prod_module_tier=prod_module_tier,
                    machine_quality=machine_quality,
                    no_asteroids=no_asteroids,
                    forbid_ore_routes=forbid_ore_routes,
                    tech_state=tech_state,
                    _cache=_cache,
                    _in_flight=_in_flight,
                    _force_tree_walk_for=_force_tree_walk_for,
                    _dispatch_env=dispatch_env,
                )
                for st in n_stages:
                    st["normal_quality_chain"] = True
                normal_chain_stages.extend(n_stages)
                for raw, amt in n_raws.items():
                    if raw in fluids:
                        normal_fluid_input[raw] = normal_fluid_input.get(raw, 0.0) + amt
                    else:
                        normal_solid_input[raw] = normal_solid_input.get(raw, 0.0) + amt

            # Build per-shuffle stage dict for output.  Annotate each with
            # the credits it contributed and any overflow it produced.
            shuffle_byproduct_legendary = dict(aggregated_byproducts)
            shuffle_byproduct_credited = dict(capped_credits)
            shuffle_byproduct_overflow = dict(overflow)
            for s in chosen_stages:
                # Per-stage credit/overflow split is approximate (overflow
                # is global, not per-stage) — annotate with the global maps.
                s["byproduct_credited"] = dict(capped_credits)
                s["byproduct_overflow"] = dict(overflow)
                shuffle_stages.append(s)

    # ---- Incidental co-product credit (roadmap V3 item: incidental sub-case) ----
    # Scan walker-emitted assembly stages for non-primary SOLID outputs.  When
    # the chain naturally activates a multi-output recipe (e.g. lava casting on
    # Vulcanus produces stone as a co-product, Gleba *-processing produces seeds
    # / spoilage), credit the byproduct against existing demand.  Surplus is
    # surfaced as ``incidental_byproduct_overflow`` with an explanatory note.
    #
    # Driven activation (running a recipe FOR its co-product when the primary
    # has no demand) is the sequential sub-case B in the roadmap — not done
    # here.  This pass only credits byproducts of recipes the chain already
    # activates.
    incidental_legendary, _inc_sources = _compute_incidental_byproducts(
        stages, fluids, data,
    )
    incidental_credited: dict[str, float] = {}
    incidental_overflow: dict[str, float] = {}
    if incidental_legendary:
        stage_demand_map: dict[str, float] = {}
        for s in stages:
            p = s.get("product")
            if p:
                stage_demand_map[p] = (
                    stage_demand_map.get(p, 0.0) + float(s.get("rate_per_min", 0.0))
                )
        for byprod, byrate in incidental_legendary.items():
            have = float(stage_demand_map.get(byprod, raw_demand.get(byprod, 0.0)))
            cap = min(float(byrate), have) if have > 0 else 0.0
            if cap > 0:
                incidental_credited[byprod] = cap
            surplus = float(byrate) - cap
            if surplus > 1e-6:
                incidental_overflow[byprod] = surplus
        if any(v > 0 for v in incidental_credited.values()):
            # Merge with shuffle credits (if any) so a single re-walk applies
            # both sets of credits to the demand seed.
            merged_credits: dict[str, float] = dict(incidental_credited)
            for k, v in shuffle_byproduct_credited.items():
                merged_credits[k] = merged_credits.get(k, 0.0) + float(v)
            shuffle_primaries = (
                frozenset(s["primary"] for s in shuffle_stages)
                if shuffle_stages else None
            )
            direct_dispatches = set()
            stages, raw_demand = walk_recipe_tree(
                item_key, rate, data, research_levels, assembler_level,
                fluids, planet_props, planets_fs,
                extra_raws=((shuffle_primaries or frozenset()) | scrap_terminals) or None,
                byproduct_credits=merged_credits,
                assembly_modules=assembly_modules,
                assembly_module_quality=module_quality,
                prod_module_tier=prod_module_tier,
                machine_quality=machine_quality,
                no_asteroids=no_asteroids,
                forbid_ore_routes=forbid_ore_routes,
                tech_state=tech_state,
                _cache=_cache,
                _in_flight=_in_flight,
                _force_tree_walk_for=_force_tree_walk_for,
                _dispatch_env=dispatch_env,
                _dispatch_out=direct_dispatches,
            )
            if shuffle_primaries:
                for p in shuffle_primaries:
                    raw_demand.pop(p, None)

    # ---- Driven co-product activation (roadmap V3 — driven sub-case) ----
    # When the chain has positive demand for a mined-recycle leaf raw R and the
    # user enabled (or auto-enabled) a recipe that produces R as a non-primary
    # solid output, run that recipe FOR R.  The recipe's other outputs (typically
    # fluids like molten-iron / molten-copper) become overflow.  Driver
    # INGREDIENTS are walked through ``walk_recipe_tree`` so their legendary
    # demand routes through the usual asteroid / mined-recycle / etc paths.
    #
    # Cost-gate under ``--enable-drivers all``: after building the plan we
    # recurse with ``active_drivers=None``; if the driver-less baseline is
    # cheaper we keep that instead.
    driver_stages: list[dict] = []
    driver_primary_overflow: dict[str, float] = defaultdict(float)
    if active_drivers:
        candidates_map = enumerate_co_product_drivers(data)
        explicit_recipes: frozenset[str] | None = (
            None if "all" in active_drivers
            else frozenset(active_drivers)
        )
        # Validate explicit recipe keys exist as candidates.
        if explicit_recipes is not None:
            all_recipe_keys = {
                c["recipe_key"]
                for clist in candidates_map.values()
                for c in clist
            }
            unknown = explicit_recipes - all_recipe_keys
            if unknown:
                raise ValueError(
                    f"ERROR: unknown driver recipe(s) {sorted(unknown)} in "
                    f"--enable-driver; valid recipe keys: "
                    f"{sorted(all_recipe_keys)}"
                )
        slots_map = cli.build_machine_module_slots(data) if assembly_modules else {}
        # Iterate over a snapshot — raw_demand mutates inside the loop.
        for raw_key in sorted(raw_demand.keys()):
            raw_rate = float(raw_demand.get(raw_key, 0.0))
            if raw_rate <= 0 or raw_key in fluids:
                continue
            applicable = candidates_map.get(raw_key, [])
            if not applicable:
                continue
            # Filter by tech / planet reachability and (for explicit lists)
            # by user-named recipes.
            viable: list[tuple[dict, dict, tuple]] = []
            for c in applicable:
                if explicit_recipes is not None and c["recipe_key"] not in explicit_recipes:
                    continue
                recipe = _recipe_by_key(data, c["recipe_key"])
                if recipe is None:
                    continue
                if planet_props and not cli._recipe_valid_for_planet(recipe, planet_props):
                    continue
                # Also require that every fluid ingredient is reachable on
                # the unlocked planets (e.g. lava → vulcanus).
                fluid_ings_unreachable = False
                for ing in recipe.get("ingredients", []):
                    iname = ing["name"]
                    if iname in fluids and iname in PLANET_UNLOCKS:
                        if not _planet_unlocks_item(iname, planets_fs):
                            fluid_ings_unreachable = True
                            break
                if fluid_ings_unreachable:
                    continue
                mr = _machine_for_recipe(recipe, assembler_level, locked_machines)
                if mr is None:
                    continue
                viable.append((c, recipe, mr))
            if not viable:
                continue
            # Already sorted by target_amount desc; pick the most-yield first.
            c, recipe, (machine_key, machine_speed) = viable[0]
            research_prod_drv = _research_prod_for_recipe(c["recipe_key"], research_levels)
            module_prod_drv, prod_slots_filled_drv = _assembly_prod_bonus(
                machine_key, recipe, slots_map,
                assembly_modules, module_quality, prod_module_tier,
            )
            eff_prod_drv = 1.0 + research_prod_drv + module_prod_drv
            capped_drv = False
            if eff_prod_drv > 4.0:
                eff_prod_drv = 4.0
                capped_drv = True
            per_craft = c["target_amount"] * eff_prod_drv
            if per_craft <= 0:
                continue
            crafts_per_min = raw_rate / per_craft
            crafting_time = float(recipe.get("energy_required", 1))
            machine_speed_f = float(machine_speed) * qm_speed_mult
            driver_machine_count = (
                crafts_per_min * crafting_time / (
                    machine_speed_f
                    * _module_speed_mult(prod_slots=prod_slots_filled_drv,
                                         prod_tier=prod_module_tier)
                    * 60.0
                )
            )
            # Build the stage's inputs map and walk non-raw ingredients.
            driver_inputs: dict[str, float] = {}
            for ing in recipe.get("ingredients", []):
                iname = ing["name"]
                iamt = float(ing.get("amount", 0)) * crafts_per_min
                driver_inputs[iname] = iamt
                if iamt <= 0:
                    continue
                if iname in fluids:
                    # Fluid ingredient — route to fluid demand bucket.
                    raw_demand[iname] = raw_demand.get(iname, 0.0) + iamt
                    continue
                # Solid ingredient — walk it through walk_recipe_tree so its
                # legendary chain (asteroid / mined-recycle / shuffle) plugs
                # into the main raw_demand.
                d_direct: set[str] = set()
                d_stages, d_raws = walk_recipe_tree(
                    iname, iamt, data, research_levels, assembler_level,
                    fluids, planet_props, planets_fs,
                    assembly_modules=assembly_modules,
                    assembly_module_quality=module_quality,
                    prod_module_tier=prod_module_tier,
                    machine_quality=machine_quality,
                    no_asteroids=no_asteroids,
                    forbid_ore_routes=forbid_ore_routes,
                    tech_state=tech_state,
                    _cache=_cache,
                    _in_flight=_in_flight,
                    _force_tree_walk_for=_force_tree_walk_for,
                    _dispatch_env=dispatch_env,
                    _dispatch_out=d_direct,
                )
                stages.extend(d_stages)
                for r, x in d_raws.items():
                    raw_demand[r] = raw_demand.get(r, 0.0) + x
            # The driver satisfies the entire co-product demand for this raw.
            raw_demand[raw_key] = 0.0
            # Compute overflow for each non-target output.
            overflow_outputs: dict[str, float] = {}
            for out_spec in c["other_outputs"]:
                out_rate = crafts_per_min * out_spec["amount"] * out_spec["prob"] * eff_prod_drv
                if out_rate <= 0:
                    continue
                overflow_outputs[out_spec["name"]] = out_rate
                driver_primary_overflow[out_spec["name"]] += out_rate
            driver_stages.append({
                "role": "co-product-driver",
                "recipe": c["recipe_key"],
                "product": c["target"],          # so power + by_role aggregation see it
                "target": c["target"],
                "machine": machine_key,
                "machine_speed": machine_speed_f,
                "crafts_per_min": crafts_per_min,
                "machine_count": driver_machine_count,
                "rate_per_min": raw_rate,        # legendary co-product/min
                "co_product_per_min": raw_rate,
                "inputs": driver_inputs,
                "fluid_inputs": {
                    k: v for k, v in driver_inputs.items() if k in fluids
                },
                "solid_inputs": {
                    k: v for k, v in driver_inputs.items() if k not in fluids
                },
                "overflow_outputs": overflow_outputs,
                "research_prod": research_prod_drv,
                "module_prod": module_prod_drv,
                "prod_modules": prod_slots_filled_drv,
                "prod_module_tier": prod_module_tier if prod_slots_filled_drv > 0 else 0,
                "prod_module_quality": module_quality if prod_slots_filled_drv > 0 else "normal",
                "machine_quality": machine_quality,
                "prod_capped": capped_drv,
            })

    # ---- Scrap source extraction (Fulgora) ----
    # Pull the scrap-reachable base materials out of raw_demand and source them
    # from one scrap-recycling array; the rest of raw_demand keeps its normal
    # asteroid / mined routing below.
    scrap_stages: list[dict] = []
    scrap_input: dict[str, float] = {}
    scrap_overflow: dict[str, float] = {}
    if scrap_active and scrap_terminals:
        scrap_demanded = {
            it: raw_demand[it]
            for it in scrap_terminals
            if raw_demand.get(it, 0.0) > 0
        }
        if scrap_demanded:
            src = compute_scrap_source(
                scrap_demanded, data,
                target_tier=target_tier,
                quality_module_tier=quality_module_tier,
                module_quality=module_quality,
                machine_quality=machine_quality,
                miner_type=miner_type,
                miner_quality_modules=miner_quality_modules,
                scrap_upcycle_loops=scrap_upcycle_loops,
                assembler_level=assembler_level,
                tech_state=tech_state,
                research_levels=research_levels,
                planets=planets_fs,
                forbid_ore_routes=forbid_ore_routes,
                _cache=_cache,
            )
            if src is not None:
                scrap_stages.append(src["stage"])
                if "upcycle_stages" in src:
                    scrap_stages.extend(src["upcycle_stages"])
                scrap_input["scrap"] = scrap_input.get("scrap", 0.0) + src["scrap_per_min"]
                for it, surplus in src["overflow"].items():
                    scrap_overflow[it] = scrap_overflow.get(it, 0.0) + surplus
                # These leaves are now scrap-sourced — drop them from raw_demand
                # so they don't also get asteroid / mined routing below.
                for it in scrap_demanded:
                    raw_demand.pop(it, None)

    # Asteroid-routed solid raws: crushing (quality roll) → raw ore upcycle loop.
    # When ``no_asteroids`` is set, skip the asteroid path entirely; raws like
    # iron-ore / copper-ore / ice / calcite stay in ``raw_demand`` and route
    # through ``mined_recycle_stages`` below via MINED_RAW_NO_ASTEROID_FALLBACK.
    crushing_stages: list[dict] = []
    asteroid_upcycle_stages: list[dict] = []
    asteroid_input: dict[str, float] = {}

    if not no_asteroids:
        needed_chunks: dict[str, float] = defaultdict(float)
        crush_demands_per_chunk: dict[str, dict[str, float]] = defaultdict(dict)

        q_crusher = _quality_chance(CRUSHER_SLOTS, quality_module_tier, module_quality)
        crush_dist = _tier_skip_probs(q_crusher, 0)
        crusher_speed_mult = _module_speed_mult(quality_slots=CRUSHER_SLOTS)

        # Direct chunk demand (e.g. oxide-asteroid-chunk from recipe tree walk)
        for chunk in list(ASTEROID_CRUSHING_RECIPES.keys()):
            if chunk in raw_demand and raw_demand[chunk] > 0:
                needed_chunks[chunk] += raw_demand.pop(chunk)

        raw_keys_to_process = [
            r for r in sorted(raw_demand.keys())
            if r in RAW_TO_CHUNK and raw_demand[r] > 0 and r not in fluids
        ]

        for raw_key in raw_keys_to_process:
            demand_rate = raw_demand.pop(raw_key)
            chunk = RAW_TO_CHUNK[raw_key]
            crush_recipe_key = ASTEROID_CRUSHING_RECIPES.get(chunk, "")
            crush_recipe = _recipe_by_key(data, crush_recipe_key)
            if crush_recipe is None:
                raise ValueError(f"ERROR: no crushing recipe for chunk '{chunk}'")

            V_ore, ore_configs = solve_mined_raw_self_recycle_loop_full(
                raw_key, data, module_quality, quality_module_tier, target_tier,
            )
            research_prod = _research_prod_for_recipe(crush_recipe_key, research_levels)
            eff_prod = min(4.0, 1.0 + research_prod)
            ore_per_crush = _recipe_result_amount(crush_recipe, raw_key) * eff_prod
            yield_per_chunk = ore_per_crush * sum(crush_dist[t] * V_ore[t] for t in range(5))
            if yield_per_chunk <= 0:
                raise ValueError(f"ERROR: asteroid yield for '{raw_key}' is 0")

            needed_crushes = demand_rate / yield_per_chunk
            needed_chunks[chunk] = max(needed_chunks[chunk], needed_crushes)
            crush_demands_per_chunk[chunk][raw_key] = demand_rate

        for chunk, chunk_crushes in sorted(needed_chunks.items()):
            if chunk_crushes <= 0:
                continue
            asteroid_input[chunk] = chunk_crushes
            crush_recipe_key = ASTEROID_CRUSHING_RECIPES[chunk]
            crush_recipe = _recipe_by_key(data, crush_recipe_key)
            research_prod = _research_prod_for_recipe(crush_recipe_key, research_levels)
            eff_prod = min(4.0, 1.0 + research_prod)
            crushing_time = float(crush_recipe.get("energy_required", 2)) if crush_recipe else 2.0
            machine_count = chunk_crushes * crushing_time / (
                CRUSHER_SPEED * qm_speed_mult * crusher_speed_mult * 60.0
            )

            outputs_to_raws = crush_demands_per_chunk[chunk]
            crushing_stages.append({
                "role": "raw-crushing",
                "recipe": crush_recipe_key,
                "chunk": chunk,
                "machine": "crusher",
                "machine_count": machine_count,
                "crafts_per_min": chunk_crushes,
                "outputs": outputs_to_raws,
                "research_prod": research_prod,
                "prod_capped": eff_prod >= 4.0,
            })

            for res in (crush_recipe.get("results", []) if crush_recipe else []):
                rn = res.get("name")
                if not rn or rn == chunk:
                    continue
                dem_r = outputs_to_raws.get(rn, 0.0)
                if dem_r <= 0:
                    continue
                ore_per_crush = _recipe_result_amount(crush_recipe, rn) * eff_prod
                inflow = [chunk_crushes * ore_per_crush * crush_dist[t] for t in range(5)]
                V_ore, ore_configs = solve_mined_raw_self_recycle_loop_full(
                    rn, data, module_quality, quality_module_tier, target_tier,
                )
                rec_recipe = _recipe_by_key(data, f"{rn}-recycling")
                rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2

                total_recyclings = 0.0
                for t_in in range(target_tier):
                    if inflow[t_in] > 0:
                        flow = compute_loop_flows(
                            target_tier, ore_configs, quality_module_tier, module_quality,
                            base_retention=0.25, wrap_active=False,
                            wrap_inherent_prod=0.0, wrap_research_prod=0.0,
                            inherent_prod=0.0, research_prod=0.0, t_in=t_in,
                        )
                        total_recyclings += sum(inflow[t_in] * flow[s] for s in range(target_tier))

                machine_count_rec = total_recyclings * rec_time / (
                    RECYCLER_SPEED * qm_speed_mult
                    * _module_speed_mult(quality_slots=RECYCLER_SLOTS) * 60.0
                )
                asteroid_upcycle_stages.append({
                    "role": "asteroid-ore-upcycle",
                    "raw": rn,
                    "recipe": f"{rn}-recycling",
                    "machine": "recycler",
                    "machine_count": machine_count_rec,
                    "yield_pct": V_ore[0] * 100.0,
                    "legendary_per_min": dem_r,
                    "total_recyclings_per_min": total_recyclings,
                    "module_config_per_tier": {
                        QUALITY_TIERS[t]: {
                            "craft": "n/a",
                            "recycle": f"{ore_configs[t]['recycle_quality']}x quality-{quality_module_tier}-{module_quality}",
                        }
                        for t in range(target_tier)
                    },
                })

    reprocessing_stages: list[dict] = []

    # Planet-mined solid raws (coal, stone, tungsten-ore, scrap, holmium-ore,
    # uranium-ore, yumako, jellynut, pentapod-egg): legendary via drill quality + recycler self-loop.
    mined_recycle_stages: list[dict] = []
    mined_input: dict[str, float] = {}
    fluid_raws_demand: dict[str, float] = {}

    mined_raw_lookup: dict[str, tuple[str, ...]] = dict(MINED_RAW_PLANETS)
    if no_asteroids:
        for k, v in MINED_RAW_NO_ASTEROID_FALLBACK.items():
            mined_raw_lookup[k] = v

    q_miner = 0.0
    miner_slots = 0
    if miner_quality_modules and module_quality:
        drill_key = "big-mining-drill" if miner_type == "big" else "electric-mining-drill"
        slots_map = cli.build_machine_module_slots(data)
        miner_slots = slots_map.get(drill_key, 0)
        q_miner = _quality_chance(miner_slots, quality_module_tier, module_quality)
    miner_dist = _tier_skip_probs(q_miner, 0)

    for raw_key in sorted(raw_demand.keys()):
        demand_rate = raw_demand[raw_key]
        if demand_rate <= 0:
            continue
        if raw_key in RAW_TO_CHUNK and not (no_asteroids and raw_key in MINED_RAW_NO_ASTEROID_FALLBACK):
            continue
        if raw_key in fluids:
            fluid_raws_demand[raw_key] = demand_rate
            continue
        if raw_key in mined_raw_lookup:
            if not any(p in planets_fs for p in mined_raw_lookup[raw_key]):
                needed = mined_raw_lookup[raw_key]
                raise ValueError(
                    f"ERROR: item '{item_key}' requires mined raw '{raw_key}' on planet(s) "
                    f"{list(needed)} — add --planets {','.join(needed)}"
                )
            V_raw, configs = solve_mined_raw_self_recycle_loop_full(
                raw_key, data, module_quality, quality_module_tier, target_tier,
            )
            target_yield_per_mined_raw = sum(miner_dist[t] * V_raw[t] for t in range(5))
            if target_yield_per_mined_raw <= 0:
                raise ValueError(
                    f"ERROR: '{raw_key}' has no <raw>-recycling recipe — cannot produce legendary"
                )
            normal_input_per_min = demand_rate / target_yield_per_mined_raw
            mined_input[raw_key] = normal_input_per_min
            rec_recipe = _recipe_by_key(data, f"{raw_key}-recycling")
            rec_time = float(rec_recipe.get("energy_required", 0.2)) if rec_recipe else 0.2

            total_recyclings_per_min = 0.0
            for t_in in range(target_tier):
                inflow_t = normal_input_per_min * miner_dist[t_in]
                if inflow_t > 0:
                    flow = compute_loop_flows(
                        target_tier, configs, quality_module_tier, module_quality,
                        base_retention=0.25, wrap_active=False,
                        wrap_inherent_prod=0.0, wrap_research_prod=0.0,
                        inherent_prod=0.0, research_prod=0.0, t_in=t_in,
                    )
                    total_recyclings_per_min += sum(inflow_t * flow[s] for s in range(target_tier))

            machine_count = total_recyclings_per_min * rec_time / (
                RECYCLER_SPEED * qm_speed_mult
                * _module_speed_mult(quality_slots=RECYCLER_SLOTS) * 60.0
            )
            mined_recycle_stages.append({
                "role": "mined-raw-self-recycle",
                "raw": raw_key,
                "recipe": f"{raw_key}-recycling",
                "machine": "recycler",
                "machine_count": machine_count,
                "yield_pct": target_yield_per_mined_raw * 100.0,
                "legendary_per_min": demand_rate,
                "normal_mined_per_min": normal_input_per_min,
                "module_config_per_tier": {
                    QUALITY_TIERS[t]: {
                        "craft": "n/a",
                        "recycle": f"{configs[t]['recycle_quality']}x quality-{quality_module_tier}-{module_quality}",
                    }
                    for t in range(target_tier)
                },
            })

    # ---- Fluid sub-chains (Fulgora) ----
    # Fulgora has heavy-oil oceans, so fluids consumed by the chain (e.g.
    # sulfuric-acid for processing-unit) are produced locally, not treated as
    # external raws.  The planner's own recipe selector isn't wired for oil/
    # sulfur chains, so delegate to cli.py (see _plan_fluid_chain_via_cli).  Only
    # Fulgora alters fluid handling; every other location keeps fluids as
    # quality-transparent raws.
    fluid_chain_stages: list[dict] = []
    fluid_chain_scrap_draw: dict[str, float] = {}
    resolved_fluid_input: dict[str, float] = dict(fluid_raws_demand)
    if fulgora_mode and fluid_raws_demand:
        fc = _plan_fluid_chain_via_cli(fluid_raws_demand, "fulgora", data, fluids)
        fluid_chain_stages = fc["stages"]
        fluid_chain_scrap_draw = fc["scrap_draw"]
        # Replace the demanded fluids with cli's true pumped raws (heavy-oil);
        # carry through anything cli could not resolve so the plan still lists it.
        resolved_fluid_input = dict(fc["fluid_raws"])
        for fl, amt in fc["unresolved"].items():
            resolved_fluid_input[fl] = resolved_fluid_input.get(fl, 0.0) + amt

    # Aggregate normal-quality inputs from any self-recycle-target intermediate
    # sub-plans this plan() level's walker DIRECTLY dispatched.  Recursive Path B
    # plan() calls have already aggregated their own inner intermediates into
    # their normal_solid_input — so we ONLY iterate ``direct_dispatches``
    # (populated by walker via ``_dispatch_out``) to avoid double-counting.
    if _cache is not None:
        for inter in direct_dispatches:
            sub = _cache.intermediates.get(inter)
            if sub is None:
                continue
            for r, amt in sub.get("normal_solid_input", {}).items():
                normal_solid_input[r] = normal_solid_input.get(r, 0.0) + float(amt)
            for r, amt in sub.get("normal_fluid_input", {}).items():
                normal_fluid_input[r] = normal_fluid_input.get(r, 0.0) + float(amt)

    machine_power_w = cli.build_machine_power_w(data)

    # ---- Miner counting (C1) ----
    # Size the drill fleet for the solid raws the plan consumes (scrap + planet-
    # mined ores) via cli.compute_miners, so the mining footprint isn't invisible.
    # Mining-productivity research (carried in research_levels, +10%/level,
    # uncapped) reduces the count.  Drills render as `mining` stages in
    # out["stages"] (Option A) so they fold into the totals and `by_role` like any
    # other stage.  Asteroid chunks are caught in space, not mined; fluids report
    # a yield% via cli (no drill count) — both are excluded here.
    miner_stages: list[dict] = []
    solid_raw_rates: dict[str, Fraction] = {}
    for src in (scrap_input, mined_input):
        for it, amt in src.items():
            if amt and amt > 0:
                solid_raw_rates[it] = (
                    solid_raw_rates.get(it, Fraction(0)) + Fraction(str(amt))
                )
    if solid_raw_rates:
        miners = cli.compute_miners(
            solid_raw_rates,
            cli.build_resource_info(data),
            miner_type,
            machine_power_w=machine_power_w,
            mining_productivity_level=research_levels.get("mining-productivity", 0),
            machine_quality=machine_quality,
        )
        drill_speed_mult = (
            _module_speed_mult(quality_slots=miner_slots)
            if (miner_quality_modules and module_quality)
            else 1.0
        )
        for it, entry in sorted(miners.items()):
            if "machine_count" not in entry:
                continue  # fluids report required_yield_pct, not a drill count
            drill_count = float(entry["machine_count"]) / drill_speed_mult
            miner_stages.append({
                "role": "mining",
                "item": it,
                "recipe": f"mine-{it}",
                "machine": entry["machine"],
                "machine_count": drill_count,
                "rate_per_min": float(entry.get("rate_per_min", 0.0)),
            })

    # Total machine count
    total_machines = (
        sum(s["machine_count"] for s in stages)
        + sum(s["machine_count"] for s in crushing_stages)
        + sum(s["machine_count"] for s in asteroid_upcycle_stages)
        + sum(s["machine_count"] for s in mined_recycle_stages)
        + sum(s["machine_count"] for s in shuffle_stages)
        + sum(s["machine_count"] for s in normal_chain_stages)
        + sum(s["machine_count"] for s in driver_stages)
        + sum(s["machine_count"] for s in scrap_stages)
        + sum(s["machine_count"] for s in fluid_chain_stages)
        + sum(s["machine_count"] for s in miner_stages)
    )

    # Annotate per-stage power and total (V3 power accounting).
    all_stages_for_power = (
        stages + crushing_stages + asteroid_upcycle_stages
        + mined_recycle_stages + shuffle_stages + normal_chain_stages
        + driver_stages + scrap_stages + fluid_chain_stages + miner_stages
    )
    for st in all_stages_for_power:
        st["power_kw"] = _stage_power_kw(st, machine_power_w)
    total_power_mw = sum(s["power_kw"] for s in all_stages_for_power) / 1000.0

    # Stage-cost summary: aggregate machine_count + power_kw by stage role.
    # Helps the user see where machine count is concentrated (e.g. 80 % in
    # asteroid-reprocessing → reach for --enable-shuffle low-density-structure, etc.).
    by_role: dict[str, dict[str, float]] = {}
    for st in all_stages_for_power:
        role = st.get("role", "unknown")
        bucket = by_role.setdefault(
            role, {"machines": 0.0, "power_kw": 0.0, "stage_count": 0},
        )
        bucket["machines"] += float(st.get("machine_count", 0.0))
        bucket["power_kw"] += float(st.get("power_kw", 0.0))
        bucket["stage_count"] += 1
    # Compute % of total for each role (machines + power separately).
    for role, bucket in by_role.items():
        bucket["machines_pct"] = (
            bucket["machines"] / total_machines * 100.0 if total_machines > 0 else 0.0
        )
        bucket["power_pct"] = (
            bucket["power_kw"] / (total_power_mw * 1000.0) * 100.0
            if total_power_mw > 0 else 0.0
        )

    notes: list[str] = list(extra_notes)
    # Cost hot-spot suggestions (V3 small): pointers when a single role
    # dominates total machine count.  Surfaces at the top of notes so users
    # see the actionable bit before fluid-transparency markers.
    has_plastic = any(
        s.get("product") == "plastic-bar" or s.get("recipe") == "plastic-bar"
        for s in stages
    )
    notes.extend(_hot_spot_suggestions(
        by_role,
        active_shuffles=active_shuffles,
        active_drivers=active_drivers,
        assembly_modules=assembly_modules,
        has_plastic=has_plastic,
        machine_quality=machine_quality,
        module_quality=module_quality,
        quality_module_tier=quality_module_tier,
        planets=planets_fs,
    ))
    # Detect if we used fluid transparency
    for st in stages:
        if st.get("fluid_inputs"):
            notes.append(
                f"stage {st['recipe']} uses fluid-transparent input ({list(st['fluid_inputs'].keys())})"
            )
    # Fulgora fluid sub-chain: flag where its scrap-derived solid inputs come
    # from (the scrap-source overflow), so the user doesn't size extra scrap.
    if fluid_chain_scrap_draw:
        draws = ", ".join(
            f"{amt:.2f} {_humanize(it)}/min"
            for it, amt in sorted(fluid_chain_scrap_draw.items(), key=lambda x: -x[1])
        )
        notes.append(
            f"fluid sub-chain draws {draws} of scrap-derived solids — credited "
            f"against scrap-source overflow, not added to scrap input"
        )
    # Agricultural-tower constraint: yumako / jellynut are harvested only by
    # agricultural towers, which have 0 module slots — harvest output is
    # always normal-quality.  When the chain demands them legendary, the
    # only route is the self-recycle loop emitted above.  Surface this so
    # users don't expect a quality-module slot on the tower itself.
    agri_raws = sorted(r for r in mined_input if r in ("yumako", "jellynut"))
    if agri_raws:
        notes.append(
            f"agricultural tower has 0 module slots — {'/'.join(agri_raws)} "
            f"harvest is normal-quality only; legendary tier comes from the "
            f"mined-raw-self-recycle loop above"
        )
    # Spoilage timing & decay warnings (roadmap Q3).
    if not no_spoilage:
        spoilables_in_plan = set()
        for st in stages:
            p = st.get("product") or st.get("raw") or st.get("shuffle") or st.get("target")
            if p in SPOIL_TIMES_SECONDS:
                spoilables_in_plan.add(p)
        for r in mined_input:
            if r in SPOIL_TIMES_SECONDS:
                spoilables_in_plan.add(r)
        if item_key in SPOIL_TIMES_SECONDS:
            spoilables_in_plan.add(item_key)

        for sp_item in sorted(spoilables_in_plan):
            spoil_sec = SPOIL_TIMES_SECONDS[sp_item]
            # Estimate loop cycle time (~4s) and passes (~4.0 for 25% retention)
            T_est = 16.0
            if T_est > spoil_sec:
                notes.append(
                    f"ERROR: quality loop for spoilable '{sp_item}' residence time "
                    f"({T_est:.1f}s) exceeds spoil time ({spoil_sec:.0f}s) — "
                    f"loop will spoil before reaching target tier"
                )
            elif T_est > 0.5 * spoil_sec:
                notes.append(
                    f"WARNING: quality loop for spoilable '{sp_item}' residence time "
                    f"({T_est:.1f}s) exceeds 50% of spoil time ({spoil_sec:.0f}s)"
                )
    # Incidental co-product credit notes.
    for byprod, cap in sorted(incidental_credited.items()):
        notes.append(
            f"incidental co-product: {cap:.2f} legendary {byprod}/min "
            f"credited from upstream multi-output recipe(s)"
        )
    for byprod, surplus in sorted(incidental_overflow.items()):
        notes.append(
            f"incidental byproduct surplus: {surplus:.2f} legendary "
            f"{byprod}/min unused (no downstream demand)"
        )
    # Known-limitation marker: the reprocessing quality climb predates the
    # 2.1.8 rule change (reprocessing recipes no longer accept quality
    # modules), so asteroid-sourced counts are optimistic.  See the module
    # header / ASTEROID_REPROCESSING_RECIPES comment.
    if reprocessing_stages:
        notes.append(
            "asteroid-reprocessing modelling predates the 2.1.8 rule change "
            "(reprocessing recipes no longer accept quality modules in-game) — "
            "asteroid-sourced counts are optimistic; known limitation"
        )
    # Driver-activation notes (co-product was harvested; non-target outputs
    # become overflow).
    for ds in driver_stages:
        ofs = ds.get("overflow_outputs") or {}
        ofs_str = ", ".join(
            f"{rate:.1f} {item}/min"
            for item, rate in sorted(ofs.items())
        ) or "no overflow"
        notes.append(
            f"driver {ds['recipe']} activated for "
            f"{ds['co_product_per_min']:.1f} legendary {ds['target']}/min — "
            f"overflow: {ofs_str}"
        )

    out = {
        "target": {"item": item_key, "rate_per_min": rate, "tier": QUALITY_TIERS[target_tier]},
        "asteroid_input": asteroid_input,
        "mined_input": mined_input,
        "fluid_input": resolved_fluid_input,
        "fluid_chain_scrap_draw": fluid_chain_scrap_draw,
        "normal_solid_input": normal_solid_input,
        "normal_fluid_input": normal_fluid_input,
        "shuffle_byproduct_legendary": shuffle_byproduct_legendary,
        "shuffle_byproduct_credited": shuffle_byproduct_credited,
        "shuffle_byproduct_overflow": shuffle_byproduct_overflow,
        "incidental_byproduct_legendary": dict(incidental_legendary),
        "incidental_byproduct_credited": dict(incidental_credited),
        "incidental_byproduct_overflow": dict(incidental_overflow),
        "driver_overflow": dict(driver_primary_overflow),
        "scrap_input": scrap_input,
        "scrap_overflow": scrap_overflow,
        "stages": (
            miner_stages
            + scrap_stages
            + fluid_chain_stages
            + crushing_stages
            + asteroid_upcycle_stages
            + mined_recycle_stages
            + driver_stages
            + shuffle_stages
            + list(reversed(normal_chain_stages))
            + list(reversed(stages))
        ),
        "total_machine_count": total_machines,
        "total_power_mw": total_power_mw,
        "summary": {"by_role": by_role},
        "module_quality": module_quality,
        "assembler_level": assembler_level,
        "research_levels": dict(research_levels),
        "planets": sorted(planets_fs),
        "notes": notes,
    }

    # Note (not a cost gate): scrap recycling is auto-preferred on Fulgora per
    # design — it is surface-based and scrap is effectively free, whereas the
    # asteroid path needs an orbital platform.  Machine count alone therefore
    # under-counts the asteroid alternative, so we deliberately do NOT fall back
    # to it.  Legendary via pure scrap is expensive (plates cannot climb tiers
    # by recycling); flag it so the cost isn't surprising.
    if scrap_active and scrap_stages and target_tier >= QUALITY_INDEX["legendary"]:
        notes.append(
            "legendary via scrap is recycler-heavy (scrap-derived plates roll "
            "quality only during the cascade and cannot self-climb) — consider "
            "a lower --target-quality, or the asteroid/foundry-casting path."
        )

    # Cost gate for `--enable-shuffles all`: when the planner is auto-
    # selecting shuffles, compare against the no-shuffle baseline and pick
    # whichever is cheaper.  Explicit `--enable-shuffle NAME` honours the
    # user's choice unconditionally.
    if active_shuffles and "all" in active_shuffles and shuffle_stages:
        baseline = plan(
            item_key, rate, data,
            module_quality=module_quality,
            research_levels=research_levels,
            assembler_level=assembler_level,
            quality_module_tier=quality_module_tier,
            planets=planets_fs,
            active_shuffles=None,
            active_drivers=active_drivers,
            assembly_modules=assembly_modules,
            prod_module_tier=prod_module_tier,
            machine_quality=machine_quality,
            no_asteroids=no_asteroids,
            forbid_ore_routes=forbid_ore_routes,
            tech_state=tech_state,
            miner_type=miner_type,
            miner_quality_modules=miner_quality_modules,
            scrap_upcycle_loops=scrap_upcycle_loops,
        )
        if baseline["total_machine_count"] < total_machines:
            baseline.setdefault("notes", []).append(
                f"--enable-shuffles all: greedy proposed shuffles totalling "
                f"{total_machines:.1f} machines, but no-shuffle baseline is "
                f"{baseline['total_machine_count']:.1f} machines — kept baseline. "
                f"Use --enable-shuffle NAME to override."
            )
            return baseline

    # Cost gate for `--enable-drivers all`: similar to the shuffle gate.
    # Recurse with drivers off; if the no-driver baseline is cheaper, fall
    # back.  Explicit `--enable-driver RECIPE` is honoured unconditionally.
    if active_drivers and "all" in active_drivers and driver_stages:
        baseline = plan(
            item_key, rate, data,
            module_quality=module_quality,
            research_levels=research_levels,
            assembler_level=assembler_level,
            quality_module_tier=quality_module_tier,
            planets=planets_fs,
            active_shuffles=active_shuffles,
            active_drivers=None,
            assembly_modules=assembly_modules,
            prod_module_tier=prod_module_tier,
            machine_quality=machine_quality,
            no_asteroids=no_asteroids,
            forbid_ore_routes=forbid_ore_routes,
            tech_state=tech_state,
            miner_type=miner_type,
            miner_quality_modules=miner_quality_modules,
            scrap_upcycle_loops=scrap_upcycle_loops,
        )
        if baseline["total_machine_count"] < total_machines:
            baseline.setdefault("notes", []).append(
                f"--enable-drivers all: drivers totalling "
                f"{total_machines:.1f} machines, but no-driver baseline is "
                f"{baseline['total_machine_count']:.1f} machines — kept baseline. "
                f"Use --enable-driver RECIPE to override."
            )
            return baseline

    return out


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _module_config_summary(mcfg: dict) -> str:
    """Compact one-line summary of a quality-loop stage's per-tier module config.

    ``mcfg`` maps tier_name -> ``{"craft": str, "recycle": str}``.  Collapses to
    a single value when every tier shares the same config (the common recycler
    case — all slots quality), else lists it per tier.  Returns "" when empty.
    """
    if not mcfg:
        return ""

    def _parts(cfg: dict) -> str:
        bits = [
            val for key in ("craft", "recycle")
            if (val := cfg.get(key)) and val != "n/a" and not val.startswith("0x")
        ]
        return " + ".join(bits) if bits else "no modules"

    per_tier = {t: _parts(c) for t, c in mcfg.items()}
    distinct = set(per_tier.values())
    if len(distinct) == 1:
        return next(iter(distinct))
    return "; ".join(f"{t}: {lbl}" for t, lbl in per_tier.items())


def format_human(out: dict) -> str:
    L: list[str] = []
    tgt = out["target"]
    tier = tgt.get("tier", "legendary")  # output quality tier (label only)
    L.append(f"Target: {tgt['rate_per_min']}/min of {tgt['item']} at tier {tier}")
    L.append(f"Module quality: {out.get('module_quality', 'legendary')}, "
             f"assembler level: {out.get('assembler_level')}")
    if out.get("planets"):
        L.append(f"Unlocked planets: {', '.join(out['planets'])}")
    if out.get("research_levels"):
        L.append(f"Research: {out['research_levels']}")
    L.append("")
    if out.get("scrap_input"):
        L.append("=== Scrap Input (normal scrap/min, mined on Fulgora) ===")
        for it, amt in sorted(out["scrap_input"].items()):
            L.append(f"  {_humanize(it)}: {amt:.2f}")
        if out.get("scrap_overflow"):
            L.append("  overflow (surplus quality co-products, /min):")
            for it, amt in sorted(out["scrap_overflow"].items(), key=lambda x: -x[1]):
                L.append(f"    {_humanize(it)}: {amt:.2f}")
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
        L.append(f"=== Shuffle Byproducts ({tier}/min) ===")
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
    if out.get("incidental_byproduct_legendary"):
        L.append("")
        L.append(f"=== Incidental Co-Products ({tier}/min) ===")
        emitted = out["incidental_byproduct_legendary"]
        credited = out.get("incidental_byproduct_credited", {})
        overflow = out.get("incidental_byproduct_overflow", {})
        for item, amt in sorted(emitted.items()):
            c = credited.get(item, 0.0)
            o = overflow.get(item, 0.0)
            L.append(
                f"  {_humanize(item)}: {amt:.2f} emitted "
                f"(credited {c:.2f}, surplus {o:.2f})"
            )
    if out.get("driver_overflow"):
        L.append("")
        L.append("=== Driver Overflow (voided / piped-out, /min) ===")
        for item, amt in sorted(out["driver_overflow"].items()):
            L.append(f"  {_humanize(item)}: {amt:.2f}")
    L.append("")
    L.append("=== Production Stages ===")
    for st in out["stages"]:
        role = st["role"]
        if role == "scrap-quality-source":
            covered = ", ".join(
                f"{_humanize(k)}={v:.1f}/min"
                for k, v in sorted(st.get("covered", {}).items(), key=lambda x: -x[1])
            )
            L.append(
                f"  [scrap]        {st['scrap_per_min']:.1f} scrap/min -> "
                f"{tier} {covered} "
                f"({st['machine_count']:.2f} recyclers, "
                f"binding leaf {_humanize(st.get('binding_leaf', '?'))})"
            )
        elif role == "asteroid-ore-upcycle":
            L.append(
                f"  [upcycle-ore]  {_humanize(st['raw'])}: "
                f"{st['legendary_per_min']:.2f}/min {tier} out "
                f"({st['machine_count']:.2f} recyclers, "
                f"yield {st['yield_pct']:.4f}%)"
            )
        elif role == "raw-crushing":
            outs = ", ".join(f"{_humanize(k)}@{tier}={v:.1f}/min" for k, v in st["outputs"].items())
            L.append(
                f"  [crushing]      {st['recipe']}: "
                f"{st['crafts_per_min']:.2f} crafts/min -> {outs} "
                f"({st['machine_count']:.2f} crushers)"
            )
        elif role == "self-recycle-target":
            wrap = ""
            if st.get("container") and st.get("container_machines"):
                wrap = (
                    f" + {st['container_machines']:.2f} × {_humanize(st['container'])} "
                    f"wrap-craft"
                )
            L.append(
                f"  [self-recycle] {_humanize(st['target'])}: "
                f"{st['crafts_per_min']:.2f} crafts/min -> "
                f"{st['rate_per_min']:.2f}/min {tier} "
                f"({st['craft_machines']:.2f} × {_humanize(st['machine'])} + "
                f"{st['recycler_machines']:.2f} recyclers{wrap}, "
                f"yield {st['yield_pct']:.4f}% per craft)"
            )
        elif role == "scrap-upcycle-loop":
            wrap = ""
            if st.get("container") and st.get("container_machines"):
                wrap = (
                    f" + {st['container_machines']:.2f} × {_humanize(st['container'])} "
                    f"wrap-craft"
                )
            L.append(
                f"  [upcycle]      {_humanize(st['target'])}: "
                f"{st['rate_per_min']:.2f}/min {tier} "
                f"({st['craft_machines']:.2f} × {_humanize(st['machine'])}{wrap} + "
                f"{st['recycler_machines']:.2f} recyclers)"
            )
        elif role == "self-feed-target":
            L.append(
                f"  [self-feed]    {_humanize(st['target'])}: "
                f"{st['crafts_per_min']:.2f} crafts/min + "
                f"{st['recycles_per_min']:.2f} recycles/min -> "
                f"{st['rate_per_min']:.2f}/min {tier} "
                f"({st['craft_machines']:.2f} × {_humanize(st['machine'])} + "
                f"{st['recycler_machines']:.2f} recyclers, "
                f"q*={st['q_star']})"
            )
            for tier_name, flow in st.get("per_tier_flows", {}).items():
                if flow["crafts_per_min"] > 1e-6 or flow["recycles_per_min"] > 1e-6:
                    L.append(
                        f"      tier {tier_name}: "
                        f"{flow['crafts_per_min']:.2f} crafts "
                        f"({flow['craft_machines']:.2f} m) + "
                        f"{flow['recycles_per_min']:.2f} recycles "
                        f"({flow['recycler_machines']:.2f} m)"
                    )
        elif role == "cross-item-shuffle":
            byp = ", ".join(
                f"{_humanize(k)}={v:.1f}/min"
                for k, v in st.get("byproduct_legendary", {}).items()
            )
            # Support both V2 LDS-only shape (foundry_machines/legendary_
            # plastic_per_min/...) and V3 generic shape (cast_machines/
            # legendary_primary_per_min/...).
            primary = st.get("primary", "plastic-bar")
            normal_in = st.get(
                "normal_primary_in_per_min",
                st.get("normal_plastic_in_per_min", 0.0),
            )
            legendary_out = st.get(
                "legendary_primary_per_min",
                st.get("legendary_plastic_per_min", 0.0),
            )
            cast_machines = st.get(
                "cast_machines", st.get("foundry_machines", 0.0),
            )
            cast_machine_label = _humanize(st.get("cast_machine", "foundry"))
            yield_pct = st.get(
                "yield_per_normal_primary_pct",
                st.get("yield_per_normal_plastic_pct", 0.0),
            )
            L.append(
                f"  [shuffle]      {st.get('shuffle','?')}: "
                f"{normal_in:.2f} normal {_humanize(primary)} in -> "
                f"{legendary_out:.2f} {tier} {_humanize(primary)} out + "
                f"byproducts [{byp}] "
                f"({cast_machines:.1f} {cast_machine_label} + "
                f"{st.get('recycler_machines', 0.0):.1f} recyclers, "
                f"yield {yield_pct:.3f}%)"
            )
        elif role == "mined-raw-self-recycle":
            L.append(
                f"  [mined-recycle] {_humanize(st['raw'])}: "
                f"{st['normal_mined_per_min']:.2f} normal mined -> "
                f"{st['legendary_per_min']:.2f} {tier} out "
                f"({st['machine_count']:.2f} recyclers, "
                f"yield {st['yield_pct']:.4f}%)"
            )
        elif role == "co-product-driver":
            ofs = ", ".join(
                f"{_humanize(k)}={v:.1f}/min"
                for k, v in sorted((st.get("overflow_outputs") or {}).items())
            ) or "none"
            L.append(
                f"  [driver]       {st['recipe']}: "
                f"{st['crafts_per_min']:.2f} crafts/min -> "
                f"{st['co_product_per_min']:.2f} {tier} {_humanize(st['target'])}/min "
                f"({st['machine_count']:.2f} × {_humanize(st['machine'])}, "
                f"overflow [{ofs}])"
            )
        elif role == "fluid-chain":
            L.append(
                f"  [fluid-chain]  {st['recipe']}: "
                f"{st['rate_per_min']:.2f}/min "
                f"({st['machine_count']:.2f} × {_humanize(st['machine'])} "
                f"-> {_humanize(st['fluid_target'])})"
            )
        elif role == "mining":
            L.append(
                f"  [mining]       {_humanize(st['item'])}: "
                f"{st['rate_per_min']:.2f}/min "
                f"({st['machine_count']:.2f} × {_humanize(st['machine'])})"
            )
        else:
            fluids = f", fluids=[{','.join(st['fluid_inputs'])}]" if st.get("fluid_inputs") else ""
            capped = " [PROD-CAPPED]" if st.get("prod_capped") else ""
            tag = " [NORMAL]" if st.get("normal_quality_chain") else ""
            n_prod = int(st.get("prod_modules", 0))
            mprod = float(st.get("module_prod", 0.0))
            if n_prod > 0:
                mods = (
                    f", {n_prod}x prod-{st.get('prod_module_tier', 3)}-"
                    f"{st.get('prod_module_quality', 'normal')} "
                    f"(+{mprod * 100.0:.0f}%)"
                )
            elif mprod > 1e-9:
                # Machine's built-in productivity (foundry/EM-plant/biochamber);
                # applies even when the recipe disallows prod modules.
                mods = f", inherent +{mprod * 100.0:.0f}% prod"
            else:
                mods = ", no prod modules"
            L.append(
                f"  [{role:10s}] {st['recipe']}: "
                f"{st['rate_per_min']:.2f}/min "
                f"({st['machine_count']:.2f} × {_humanize(st['machine'])}){fluids}{mods}{capped}{tag}"
            )
        mc = _module_config_summary(st.get("module_config_per_tier", {}))
        if mc:
            L.append(f"                 modules: {mc}")
    L.append("")
    L.append(f"Total machines: {out['total_machine_count']:.2f}")
    if "total_power_mw" in out:
        pwr_mw = float(out["total_power_mw"])
        if pwr_mw >= 1000.0:
            L.append(f"Total power:    {pwr_mw / 1000.0:.2f} GW (electric machines only)")
        else:
            L.append(f"Total power:    {pwr_mw:.2f} MW (electric machines only)")
    by_role = (out.get("summary") or {}).get("by_role")
    if by_role:
        L.append("")
        L.append("=== Cost Breakdown by Stage Role ===")
        # Sort by descending machine count.
        items = sorted(
            by_role.items(), key=lambda kv: kv[1].get("machines", 0.0), reverse=True,
        )
        L.append(f"  {'Role':<28} {'Stages':>6}  {'Machines':>10} {'%':>6}  {'Power':>10} {'%':>6}")
        for role, b in items:
            stages_n = int(b.get("stage_count", 0))
            mc = float(b.get("machines", 0.0))
            mp = float(b.get("machines_pct", 0.0))
            pk = float(b.get("power_kw", 0.0))
            pp = float(b.get("power_pct", 0.0))
            pwr_label = f"{pk / 1000.0:.2f}MW" if pk >= 1000 else f"{pk:.1f}kW"
            L.append(
                f"  {role:<28} {stages_n:>6}  {mc:>10.2f} {mp:>5.1f}%  "
                f"{pwr_label:>10} {pp:>5.1f}%"
            )
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


def _parse_tech_state(raw_list: list[str]) -> dict[str, int]:
    """Parse repeated --tech NAME=LEVEL flags into a dict.

    Empty list returns {} (everything locked — CLI default).  Unknown tech
    names exit with a sorted list of valid names.
    """
    out: dict[str, int] = {}
    valid = sorted(TECH_GATES.keys())
    for raw in raw_list:
        if "=" not in raw:
            sys.exit(f"Invalid --tech '{raw}'; expected NAME=LEVEL")
        name, lvl = raw.split("=", 1)
        name = name.strip()
        if name not in TECH_GATES:
            sys.exit(f"Unknown --tech name '{name}'; valid: {valid}")
        try:
            out[name] = int(lvl)
        except ValueError:
            sys.exit(f"Invalid tech level '{lvl}' in --tech {raw}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Legendary production planner (V2)")
    p.add_argument("--item", required=True)
    p.add_argument("--rate", required=True, type=float, help="target items per minute (at --target-quality)")
    p.add_argument(
        "--target-quality", default="legendary",
        choices=["uncommon", "rare", "epic", "legendary"],
        help=(
            "Quality tier to produce (the goal tier).  The quality loops stop "
            "at this tier instead of pushing all the way to legendary — e.g. "
            "--target-quality rare plans for rare output, treating rare-or-"
            "better as success.  Default legendary."
        ),
    )
    p.add_argument(
        "--module-quality", default=None, choices=list(QUALITY_TIERS),
        help=(
            "Quality of the quality-modules used in the loops.  Defaults to "
            "--target-quality and may not exceed it (you can't have modules of "
            "a quality you haven't researched)."
        ),
    )
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
        "--location", default=None, choices=list(KNOWN_PLANETS),
        help=(
            "Single planet the factory is BUILT on (mirrors cli.py --location). "
            "Unlocks that planet's raws. --location fulgora additionally switches "
            "to scrap-only sourcing: no asteroid platform, so base materials come "
            "from the scrap-recycling quality source and metals terminate at "
            "their scrap-reachable plate form. Only 'fulgora' alters sourcing "
            "today; other values just unlock that planet."
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
        "--machine-quality", default="normal",
        choices=list(QUALITY_TIERS),
        help=(
            "Quality tier of every assembly / crusher / recycler machine "
            "(applies MACHINE_QUALITY_SPEED bonus: +30/+60/+90/+150%% for "
            "uncommon/rare/epic/legendary).  Affects machine_count and total "
            "machines. Default normal."
        ),
    )
    p.add_argument(
        "--enable-shuffle", action="append", default=[], metavar="OUTPUT_ITEM",
        help=(
            "Enable a cross-item shuffle by output-item key (repeatable). "
            "E.g. --enable-shuffle low-density-structure replaces the "
            "legendary plastic-bar chain with the LDS shuffle (foundry-cast "
            "LDS + recycle, with copper-plate/steel-plate byproducts).  Run "
            "with no targets first to see what's in the chain; the planner "
            "discovers candidates dynamically from the dataset (~197 in stock "
            "Space Age).  Common picks: low-density-structure, "
            "advanced-circuit, electronic-circuit, engine-unit, battery."
        ),
    )
    p.add_argument(
        "--enable-shuffles", default=None, choices=["all"],
        help=(
            "Shortcut: enable EVERY shuffle candidate.  The greedy selector "
            "activates only those whose recycle outputs overlap with the "
            "target chain's legendary leaves.  Mutually exclusive with "
            "--enable-shuffle."
        ),
    )
    p.add_argument(
        "--enable-driver", action="append", default=[], metavar="RECIPE_KEY",
        help=(
            "Activate a co-product driver: a recipe whose non-primary solid "
            "output covers a leaf raw demand in the chain (repeatable, by "
            "recipe key).  E.g. --enable-driver molten-iron-from-lava runs "
            "lava casting purely to harvest stone (the molten-iron output is "
            "voided as overflow).  Useful for stone-bound chains on Vulcanus "
            "(stone-wall, gate, landfill).  See `enumerate_co_product_drivers` "
            "for the full candidate list (~8 stock Space Age recipes)."
        ),
    )
    p.add_argument(
        "--enable-drivers", default=None, choices=["all"],
        help=(
            "Shortcut: try every co-product driver candidate, picking the "
            "highest-yield driver per mined-recycle leaf.  Cost-gated against "
            "the no-driver baseline (kept whichever is cheaper).  Mutually "
            "exclusive with --enable-driver."
        ),
    )
    p.add_argument(
        "--no-asteroids", action="store_true",
        help=(
            "Disable the asteroid-reprocessing path (no space platform yet). "
            "Quality for iron-ore, copper-ore, ice, calcite is sourced via the "
            "recycler self-loop on an unlocked planet (Nauvis for iron/copper, "
            "Aquilo for ice, Vulcanus for calcite).  carbon and sulfur fall "
            "back to their normal chemistry recipes (require coal + sulfuric-"
            "acid or petgas via planet chains)."
        ),
    )
    p.add_argument(
        "--tech", action="append", default=[], metavar="NAME=LEVEL",
        help=(
            "Tech research state, repeatable (e.g. --tech recycling=1 "
            "--tech tungsten-carbide=1).  Without any --tech flag NOTHING is "
            "researched and most plans fail-fast (no recycler).  Valid names: "
            + ", ".join(sorted(TECH_GATES.keys()))
            + ".  To replicate today's fully-researched default, list every "
            "tech with LEVEL=1."
        ),
    )
    p.add_argument(
        "--miner", default="electric", choices=["electric", "big"],
        help=(
            "Mining drill used to size the solid-raw fleet (scrap, mined ores). "
            "Mirrors cli.py: 'electric' = electric-mining-drill, 'big' = "
            "big-mining-drill (5x speed, needed for hard-solid like tungsten). "
            "Counts + power fold into the totals as a 'mining' stage role. "
            "Mining-productivity research (--research mining-productivity=N) "
            "reduces the count."
        ),
    )
    p.add_argument(
        "--no-miner-quality-modules", action="store_false", dest="miner_quality_modules",
        help="Disable quality module seeding in mining drills.",
    )
    p.add_argument(
        "--no-scrap-upcycle-loops", action="store_false", dest="scrap_upcycle_loops",
        help="Disable closed-loop plate upcycling on Fulgora.",
    )
    p.add_argument(
        "--no-spoilage", action="store_true",
        help="Disable spoilage timing and decay loss modelling (for A/B testing).",
    )
    p.add_argument(
        "--optimize-placement", action="store_true",
        help="Search for the optimal quality-module placement across chain steps.",
    )
    p.add_argument(
        "--demand", default=None, metavar="SPEC",
        help="Mixed-tier demand spec, e.g. 'iron-plate@legendary:60,iron-plate@epic:20'.",
    )
    p.add_argument(
        "--keep-tiers", default=None, metavar="TIERS",
        help="Comma-separated list of quality tiers to extract as product (e.g. 'uncommon,rare,epic').",
    )
    p.add_argument(
        "--beacons", type=int, default=0, metavar="COUNT",
        help="Number of speed-module beacons affecting each crafting machine (roadmap Q7).",
    )
    p.add_argument(
        "--objective", default="machines", choices=["machines", "power", "raw-input", "cost"],
        help="Objective function to minimize: machines, power, raw-input, or cost (roadmap Q8).",
    )
    p.add_argument(
        "--preset", default=None, choices=["end-game-fulgora", "end-game-nauvis", "nauvis-starter"],
        help="CLI configuration preset (roadmap Q9).",
    )
    p.add_argument("--format", default="human", choices=["human", "json"])
    return p.parse_args()


PRESETS = {
    "end-game-fulgora": {
        "location": "fulgora",
        "planets": "fulgora",
        "tech": ["all"],
        "enable_shuffles": "all",
        "beacons": 8,
    },
    "end-game-nauvis": {
        "location": "nauvis",
        "planets": "nauvis",
        "tech": ["all"],
        "enable_shuffles": "all",
        "beacons": 8,
    },
    "nauvis-starter": {
        "location": "nauvis",
        "planets": "nauvis",
        "no_asteroids": True,
    },
}

def apply_preset(args: argparse.Namespace) -> argparse.Namespace:
    """Apply preset values to args if --preset is specified (roadmap Q9)."""
    if not getattr(args, "preset", None):
        return args
    preset_dict = PRESETS.get(args.preset, {})
    for k, v in preset_dict.items():
        val = getattr(args, k, None)
        if val is None or val == [] or val is False or val == "electric" or val == 0:
            setattr(args, k, v)
    return args


def _evaluate_objective(plan_dict: dict, objective: str) -> float:
    """Evaluate objective metric for a plan (roadmap Q8)."""
    if objective == "power":
        return float(plan_dict.get("total_power_mw", 0.0))
    elif objective == "raw-input":
        ast = sum(float(v) for v in plan_dict.get("asteroid_input", {}).values())
        mined = sum(float(v) for v in plan_dict.get("mined_input", {}).values())
        return ast + mined
    elif objective == "cost":
        m = float(plan_dict.get("total_machine_count", 0.0))
        p = float(plan_dict.get("total_power_mw", 0.0))
        return m + 0.1 * p
    else:
        return float(plan_dict.get("total_machine_count", 0.0))


def parse_demand_spec(spec_str: str) -> list[tuple[str, str, float]]:
    """Parse spec_str like 'iron-plate@legendary:60,iron-plate@epic:20' into
    [(item_key, quality_tier, rate_per_min), ...] (roadmap Q6)."""
    results = []
    for part in spec_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "@" in part and ":" in part:
            item_q, rate_s = part.split(":", 1)
            item_key, tier = item_q.split("@", 1)
            results.append((item_key.strip(), tier.strip().lower(), float(rate_s.strip())))
        elif ":" in part:
            item_key, rate_s = part.split(":", 1)
            results.append((item_key.strip(), "legendary", float(rate_s.strip())))
        else:
            raise ValueError(f"ERROR: invalid --demand spec '{part}'; format: ITEM@TIER:RATE")
    return results


def main() -> None:
    # Output uses Unicode glyphs (×, —, →, ≈, …). On Windows the console / a
    # redirected pipe defaults to cp1252, which renders these as � (em dash,
    # multiply) or hard-crashes with UnicodeEncodeError (arrow → is not cp1252-
    # encodable). Force UTF-8 on our streams so output is identical on Windows
    # and Linux. No-op on Linux (already UTF-8); done in main() — not at import —
    # so importing this module as a library never mutates a caller's streams.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    args = parse_args()
    args = apply_preset(args)
    data = cli.load_data("nauvis")
    research = _parse_research(args.research)
    tech_state = _parse_tech_state(args.tech)
    planets_list = [p.strip() for p in args.planets.split(",") if p.strip()]
    target_tier = QUALITY_INDEX[args.target_quality]

    # Build the active_shuffles set: explicit names + (optional) "all" sentinel.
    active_shuffles: set[str] | None = None
    if args.enable_shuffles == "all":
        if args.enable_shuffle:
            sys.exit(
                "ERROR: --enable-shuffles all is mutually exclusive with "
                "--enable-shuffle (specify one or the other)."
            )
        active_shuffles = {"all"}
    elif args.enable_shuffle:
        active_shuffles = set(args.enable_shuffle)

    # Same shape for drivers.
    active_drivers: set[str] | None = None
    if args.enable_drivers == "all":
        if args.enable_driver:
            sys.exit(
                "ERROR: --enable-drivers all is mutually exclusive with "
                "--enable-driver (specify one or the other)."
            )
        active_drivers = {"all"}
    elif args.enable_driver:
        active_drivers = set(args.enable_driver)

    try:
        out = plan(
            args.item, args.rate, data,
            module_quality=args.module_quality,
            research_levels=research,
            assembler_level=args.assembler_level,
            quality_module_tier=args.quality_module_tier,
            planets=planets_list,
            active_shuffles=active_shuffles,
            active_drivers=active_drivers,
            assembly_modules=args.assembly_modules,
            prod_module_tier=args.prod_module_tier,
            machine_quality=args.machine_quality,
            no_asteroids=args.no_asteroids,
            location=args.location,
            tech_state=tech_state,
            target_tier=target_tier,
            miner_type=args.miner,
            miner_quality_modules=args.miner_quality_modules,
            scrap_upcycle_loops=args.scrap_upcycle_loops,
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
