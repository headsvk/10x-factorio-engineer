#!/usr/bin/env python3
"""
Factorio Production Calculator

Usage:
    python cli.py --item <item-id> (--rate <N> | --machines <N>)
                  [--item <item-id2> (--rate <N2> | --machines <N2>) ...]
                  [--assembler 1|2|3]
                  [--furnace stone|steel|electric]
                  [--miner electric|big]
                  [--location PLANET]
                  [--machine-quality QUALITY]
                  [--beacon-quality QUALITY]
                  [--modules MACHINE=COUNT:TYPE:TIER:QUALITY]   # repeatable
                  [--beacon MACHINE=COUNT:TIER:QUALITY]         # repeatable
                  [--recipe ITEM=RECIPE]                        # repeatable
                  [--recipe-machine RECIPE=MACHINE]             # repeatable
                  [--recipe-modules RECIPE=COUNT:TYPE:TIER:QUALITY]  # repeatable
                  [--recipe-beacon RECIPE=COUNT:TIER:QUALITY]   # repeatable
                  [--bus-item ITEM-ID]                          # repeatable
                  [--format json|human]

Outputs clean JSON to stdout (default), or human-readable text with --format human:
  - production_steps: machine type + count per recipe in the dependency tree
  - raw_resources:    mining / pumping rates per minute (no recipe)
  - miners_needed:    drill / pumpjack / offshore-pump counts per raw resource

Solver notes
------------
* All arithmetic uses fractions.Fraction for exact (rational) results.
* Multi-output recipes credit co-products as surplus before running more
  machines, eliminating double-counting.
* Oil processing (petroleum-gas / light-oil / heavy-oil) is solved as a
  3-variable linear system using the selected refinery recipe (AOP by
  default; coal-liquefaction or simple-coal-liquefaction when overridden
  via --recipe heavy-oil=<recipe>):
        net_heavy * ref - hoc_in * hoc                   = D_heavy
        light_yield * ref + hoc_out * hoc - loc_in * loc = D_light
        petgas_yield * ref               + loc_out * loc = D_petgas
  net_heavy = gross heavy yield - self-consumed heavy oil (CL only).
  Negative-variable cases are handled by clamping to zero and re-solving
  the reduced system.
* Productivity and speed module bonuses are applied uniformly per --prod / --speed.

Dataset files (vanilla-2.0.55.json, space-age-2.0.55.json) are vendored in
./assets/  and automatically downloaded from KirkMcDonald's calculator GitHub repo
on first run.
"""

import argparse
import json
import math
import os
import sys
import urllib.request
from collections import defaultdict
from fractions import Fraction

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR   = os.path.dirname(os.path.abspath(__file__))

DATA_FILES = {
    "vanilla":   "vanilla-2.0.55.json",
    "space-age": "space-age-2.0.55.json",
}

DATA_URLS = {
    k: (
        "https://raw.githubusercontent.com/KirkMcDonald/"
        f"kirkmcdonald.github.io/master/data/{v}"
    )
    for k, v in DATA_FILES.items()
}

# Miner / extractor speeds (game constants -- not stored in data files)
MINER_SPEED: dict[str, Fraction] = {
    "electric-mining-drill": Fraction(1, 2),
    "big-mining-drill":      Fraction(5, 2),   # Space Age only
    "pumpjack":              Fraction(1),
}
OFFSHORE_PUMP_RATE  = Fraction(1200)           # fixed 1200 items/min
PUMPJACK_CATEGORIES = frozenset(["basic-fluid"])

# Assembler crafting speeds
ASSEMBLER_SPEED: dict[int, Fraction] = {
    1: Fraction(1, 2),
    2: Fraction(3, 4),
    3: Fraction(5, 4),
}
ASSEMBLER_KEY: dict[int, str] = {
    1: "assembling-machine-1",
    2: "assembling-machine-2",
    3: "assembling-machine-3",
}

# Furnace crafting speeds
FURNACE_SPEED: dict[str, Fraction] = {
    "stone":    Fraction(1),
    "steel":    Fraction(2),
    "electric": Fraction(2),
}
FURNACE_KEY: dict[str, str] = {
    "stone":    "stone-furnace",
    "steel":    "steel-furnace",
    "electric": "electric-furnace",
}

# Fixed-machine categories (vanilla + Space Age).
# Vanilla-only datasets simply never produce Space Age category keys.
FIXED_MACHINE_FOR_CAT: dict[str, tuple[str, Fraction]] = {
    # Vanilla ----------------------------------------------------------------
    "chemistry":                         ("chemical-plant",          Fraction(1)),
    "oil-processing":                    ("oil-refinery",            Fraction(1)),
    "centrifuging":                      ("centrifuge",              Fraction(1)),
    "rocket-building":                   ("rocket-silo",             Fraction(1)),
    # Space Age --------------------------------------------------------------
    "cryogenics":                        ("cryogenic-plant",         Fraction(3, 2)),
    "cryogenics-or-assembling":          ("cryogenic-plant",         Fraction(3, 2)),
    "chemistry-or-cryogenics":           ("cryogenic-plant",         Fraction(3, 2)),
    "organic":                           ("biochamber",              Fraction(3, 2)),
    "organic-or-assembling":             ("biochamber",              Fraction(3, 2)),
    "organic-or-chemistry":              ("biochamber",              Fraction(3, 2)),
    "organic-or-hand-crafting":          ("biochamber",              Fraction(3, 2)),
    "electromagnetics":                  ("electromagnetic-plant",   Fraction(2)),
    "electronics":                       ("electromagnetic-plant",   Fraction(2)),
    "electronics-or-assembling":         ("electromagnetic-plant",   Fraction(2)),
    "electronics-with-fluid":            ("electromagnetic-plant",   Fraction(2)),
    "metallurgy":                        ("foundry",                 Fraction(4)),
    "metallurgy-or-assembling":          ("foundry",                 Fraction(4)),
    "crafting-with-fluid-or-metallurgy": ("foundry",                 Fraction(4)),
    "crushing":                          ("crusher",                 Fraction(1)),
    "pressing":                          ("agricultural-tower",      Fraction(1)),
    "captive-spawner-process":           ("captive-spawner",         Fraction(1)),
}

# Crafting speed by machine key — used by Solver.solve() and resolve_oil() when
# applying --machine CATEGORY=MACHINE overrides.  Every machine that can appear
# as an override target must be listed here; unknown keys are silently ignored.
MACHINE_CRAFTING_SPEED: dict[str, Fraction] = {
    # Assemblers
    "assembling-machine-1": Fraction(1, 2),
    "assembling-machine-2": Fraction(3, 4),
    "assembling-machine-3": Fraction(5, 4),
    # Furnaces
    "stone-furnace":           Fraction(1),
    "steel-furnace":           Fraction(2),
    "electric-furnace":        Fraction(2),
    # Vanilla fixed-machine categories
    "chemical-plant":          Fraction(1),
    "oil-refinery":            Fraction(1),
    "centrifuge":              Fraction(1),
    "rocket-silo":             Fraction(1),
    # Space Age fixed-machine categories
    "cryogenic-plant":         Fraction(3, 2),
    "biochamber":              Fraction(3, 2),
    "electromagnetic-plant":   Fraction(2),
    "foundry":                 Fraction(4),
    "crusher":                 Fraction(1),
    "agricultural-tower":      Fraction(1),
    "captive-spawner":         Fraction(1),
}

SMELTING_CATS   = frozenset(["smelting"])
SKIP_SUBGROUPS  = frozenset(["empty-barrel", "fill-barrel"])
SKIP_CATEGORIES = frozenset(["recycling", "recycling-or-hand-crafting"])

# These three products are solved jointly via a linear system to avoid
# double-counting crude-oil when multiple oil products are needed.
OIL_PRODUCTS = frozenset(["petroleum-gas", "light-oil", "heavy-oil"])

# Hard-coded preferred recipe for items whose order-sort default is either
# un-automatable or produces a circular dependency in the solver.
# Applied as step 3.5 in pick_recipe (after AOP fallback, before order-sort).
# Can always be overridden by an explicit --recipe flag.
RECIPE_DEFAULTS: dict[str, str] = {
    # nutrients-from-fish is order-sorted first but requires raw-fish (not
    # minable) and fish-breeding creates a circular nutrients dependency.
    # nutrients-from-yumako-mash is the cleanest fully-automatable Gleba route.
    "nutrients": "nutrients-from-yumako-mash",
    # steam-condensation sorts before ice-melting (order field: b < c) but
    # steam is never a raw resource — ice-melting is the correct automatable default.
    "water": "ice-melting",
    # ammoniacal-solution-separation sorts first for ice (order a[ammonia] < b-a-c)
    # but ammoniacal-solution is only a raw resource on Aquilo. On space platforms
    # and elsewhere, oxide-asteroid-crushing is the correct automatable source.
    # On Aquilo, ice is mined directly so this default is never reached there.
    "ice": "oxide-asteroid-crushing",
}

# Location-specific recipe overrides. Checked before exact-key-match so that
# location correctness wins over the implicit "recipe key == item key" heuristic.
# Overridden by explicit --recipe flags (step 1 in pick_recipe).
RECIPE_DEFAULTS_BY_LOCATION: dict[str, dict[str, str]] = {
    "space-platform": {
        # The recipe with key=="carbon" (coal+sulfuric-acid) is the standard
        # Nauvis route but coal and sulfuric-acid are unavailable on platforms.
        # carbonic-asteroid-chunk is a platform raw resource; use it directly.
        "carbon": "carbonic-asteroid-crushing",
    },
}

# Productivity module bonus per filled slot, by tier
MODULE_PROD_BONUS: dict[int, Fraction] = {
    0: Fraction(0),
    1: Fraction(4,  100),   # productivity-module:   +4 % each
    2: Fraction(6,  100),   # productivity-module-2: +6 % each
    3: Fraction(10, 100),   # productivity-module-3: +10 % each
}

# Valid quality names (enum)
QUALITY_NAMES: frozenset = frozenset(["normal", "uncommon", "rare", "epic", "legendary"])

# Quality multiplier applied to module bonuses (normal=×1.0 … legendary=×2.5)
MODULE_QUALITY_MULT: dict[str, Fraction] = {
    "normal":    Fraction(1),
    "uncommon":  Fraction(13, 10),   # ×1.3
    "rare":      Fraction(8,  5),    # ×1.6
    "epic":      Fraction(19, 10),   # ×1.9
    "legendary": Fraction(5,  2),    # ×2.5
}

# Additive crafting-speed bonus from machine quality (applied to base speed)
MACHINE_QUALITY_SPEED: dict[str, Fraction] = {
    "normal":    Fraction(0),
    "uncommon":  Fraction(3,  10),   # +30%
    "rare":      Fraction(3,  5),    # +60%
    "epic":      Fraction(9,  10),   # +90%
    "legendary": Fraction(3,  2),    # +150%
}

# Beacon distribution effectivity by quality (affects how strongly modules apply)
BEACON_EFFECTIVITY: dict[str, Fraction] = {
    "normal":    Fraction(3,  2),    # 1.5
    "uncommon":  Fraction(17, 10),   # 1.7
    "rare":      Fraction(19, 10),   # 1.9
    "epic":      Fraction(21, 10),   # 2.1
    "legendary": Fraction(5,  2),    # 2.5
}

# Speed module base bonus per tier per slot (at normal quality)
SPEED_MODULE_BONUS: dict[int, Fraction] = {
    1: Fraction(1, 5),    # +20%
    2: Fraction(3, 10),   # +30%
    3: Fraction(1, 2),    # +50%
}

# Number of module slots in a standard beacon (quality-invariant)
BEACON_SLOTS: int = 2

# Fluid pump throughput by pump quality (fluid / minute)
PUMP_THROUGHPUT: dict[str, int] = {
    "normal":    72_000,
    "uncommon":  93_600,
    "rare":      115_200,
    "epic":      136_800,
    "legendary": 180_000,
}

# Beacon idle power draw by beacon housing quality (kW)
BEACON_POWER_KW: dict[str, int] = {
    "normal":    480,
    "uncommon":  400,
    "rare":      320,
    "epic":      240,
    "legendary": 80,
}

# Tile footprint (longest dimension) used to compute beacon sharing factor
MACHINE_SIZE: dict[str, int] = {
    "assembling-machine-1":  3,
    "assembling-machine-2":  3,
    "assembling-machine-3":  3,
    "electric-furnace":      3,
    "chemical-plant":        3,
    "centrifuge":            3,
    "biochamber":            3,
    "agricultural-tower":    3,
    "electromagnetic-plant": 4,
    "crusher":               3,   # 2×3 footprint; use longest dimension
    "oil-refinery":          5,
    "foundry":               5,
    "cryogenic-plant":       5,
    "captive-spawner":       5,
    "big-mining-drill":      5,
    "electric-mining-drill": 3,
    "rocket-silo":           9,
}

# Energy consumption penalty from speed/prod modules — NOT quality-scaled
MODULE_CONSUMPTION_PENALTY: dict[str, dict[int, Fraction]] = {
    "speed": {1: Fraction(1, 2),  2: Fraction(3, 5),  3: Fraction(7, 10)},
    "prod":  {1: Fraction(2, 5),  2: Fraction(3, 5),  3: Fraction(4, 5)},
}

# Efficiency module reduction per slot — IS quality-scaled via MODULE_QUALITY_MULT
MODULE_EFFICIENCY_REDUCTION: dict[int, Fraction] = {
    1: Fraction(3, 10),
    2: Fraction(2, 5),
    3: Fraction(1, 2),
}




# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(location: str | None = None) -> dict:
    """Return parsed JSON for the appropriate dataset, downloading the file if absent.

    location=None  → vanilla dataset (no planet filtering)
    location=str   → space-age dataset; validates location key against dataset planets
    """
    dataset = "space-age" if location else "vanilla"
    path = os.path.join(DATA_DIR, DATA_FILES[dataset])
    if not os.path.exists(path):
        url = DATA_URLS[dataset]
        sys.stderr.write(f"Downloading {url} ...\n")
        urllib.request.urlretrieve(url, path)
        sys.stderr.write(f"Saved to {path}\n")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if location is not None:
        valid_keys = {p["key"] for p in data.get("planets", [])}
        if location not in valid_keys:
            sys.exit(f"Unknown location '{location}'. Valid: {sorted(valid_keys)}")
    return data


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def build_raw_set(data: dict, location: str | None = None) -> frozenset:
    """Return set of item keys that are raw inputs (mined / pumped).

    location=None  → original behaviour (all planets' resources)
    location=str   → only resources available at that specific planet
    """
    raw: set[str] = set()
    if location is None:
        for res in data.get("resources", []):
            for r in res.get("results", []):
                raw.add(r["name"])
        for planet in data.get("planets", []):
            pres = planet.get("resources", {})
            raw.update(pres.get("resource", []))
            raw.update(pres.get("offshore", []))
    else:
        for planet in data.get("planets", []):
            if planet["key"] == location:
                pres = planet.get("resources", {})
                raw.update(pres.get("resource", []))
                raw.update(pres.get("offshore", []))
                raw.update(pres.get("plants", []))
                break
        # Asteroid collectors are not modeled in the dataset — chunks are the
        # raw inputs for space platforms, gathered externally by collectors.
        if location == "space-platform":
            raw.update({
                "metallic-asteroid-chunk",
                "carbonic-asteroid-chunk",
                "oxide-asteroid-chunk",
                "promethium-asteroid-chunk",
            })
    return frozenset(raw)


def get_planet_props(data: dict, location: str | None) -> dict:
    """Return surface_properties dict for location, or {} if not found/None."""
    if not location:
        return {}
    for p in data.get("planets", []):
        if p["key"] == location:
            return p.get("surface_properties", {})
    return {}


def build_recipe_index(data: dict) -> dict[str, list]:
    """Return {item_key: [recipe_dict, ...]} excluding barrels and recycling."""
    idx: dict[str, list] = defaultdict(list)
    for recipe in data.get("recipes", []):
        if recipe.get("subgroup") in SKIP_SUBGROUPS:
            continue
        if recipe.get("category") in SKIP_CATEGORIES:
            continue
        for result in recipe.get("results", []):
            idx[result["name"]].append(recipe)
    return dict(idx)


def build_resource_info(data: dict) -> dict:
    """
    Return {item_name: {"mining_time": Fraction, "yield": Fraction, "category": str}}
    for every raw resource.  Uses Fraction for exact arithmetic downstream.
    """
    info: dict[str, dict] = {}
    for res in data.get("resources", []):
        results = res.get("results", [])
        if not results:
            continue
        r0 = results[0]
        if "amount" in r0:
            yield_amt = Fraction(str(r0["amount"]))
        else:
            yield_amt = (
                Fraction(str(r0.get("amount_min", 1)))
                + Fraction(str(r0.get("amount_max", 1)))
            ) / 2
        info[r0["name"]] = {
            "mining_time": Fraction(str(res.get("mining_time", 1))),
            "yield":       yield_amt,
            "category":    res.get("category", "solid"),
        }
    for planet in data.get("planets", []):
        for item_name in planet.get("resources", {}).get("offshore", []):
            info.setdefault(item_name, {
                "mining_time": Fraction(1),
                "yield":       Fraction(1),
                "category":    "offshore",
            })
    return info



def build_machine_power_w(data: dict) -> dict[str, int]:
    """
    Return {machine_key: watts} for all **electric** machines in the dataset.
    Burner machines are excluded (missing key → 0 W in callers).

    Scans: crafting_machines, agricultural_tower, rocket_silo, mining_drills.
    The dataset key 'captive-biter-spawner' (burner) is automatically excluded
    because its energy_source type is 'burner'.
    """
    result: dict[str, int] = {}
    sources: list[list] = [
        data.get("crafting_machines", []),
        data.get("agricultural_tower", []),
        data.get("rocket_silo", []),
        data.get("mining_drills", []),
    ]
    for machine_list in sources:
        for m in machine_list:
            if m.get("energy_source", {}).get("type") != "electric":
                continue
            key = m.get("key", "")
            watts = m.get("energy_usage", 0)
            if key and watts:
                result[key] = int(watts)
    return result


def build_machine_module_slots(data: dict) -> dict[str, int]:
    """
    Return {machine_key: module_slot_count} for all machines in the dataset.
    Scans: crafting_machines, agricultural_tower, rocket_silo, mining_drills.
    Machines missing the 'module_slots' key silently default to 0.
    """
    result: dict[str, int] = {}
    sources: list[list] = [
        data.get("crafting_machines", []),
        data.get("agricultural_tower", []),
        data.get("rocket_silo", []),
        data.get("mining_drills", []),
    ]
    for machine_list in sources:
        for m in machine_list:
            key = m.get("key", "")
            if key:
                result[key] = int(m.get("module_slots", 0))
    return result


def _beacon_sharing_factor(machine_key: str) -> int:
    """
    In a standard double-row beacon layout beacons are shared between machines.
    Returns the approximate number of machines each physical beacon is shared
    across, based on machine tile size:
      size ≤ 4 → 4 machines per beacon
      size 5-7 → 2 machines per beacon
      size ≥ 8 → 1 machine per beacon (e.g. rocket-silo)
    """
    size = MACHINE_SIZE.get(machine_key, 3)
    if size <= 4:
        return 4
    if size <= 7:
        return 2
    return 1


def _compute_step_power(
    machine_key: str,
    machine_count: "float | Fraction",
    module_specs: list,
    beacon_spec: "dict | None",
    beacon_quality: str,
    machine_power_w: dict,
) -> tuple[float, float, float]:
    """
    Compute (power_kw, power_kw_ceil, beacon_power_kw) for one production step.

    * power_kw      — exact fractional machine_count × adjusted draw
    * power_kw_ceil — ceiling machine count × adjusted draw
    * beacon_power_kw — physical beacon count × beacon idle draw
    """
    base_w = machine_power_w.get(machine_key, 0)
    if base_w == 0:
        return (0.0, 0.0, 0.0)

    # Build energy_bonus from module specs
    energy_bonus: Fraction = Fraction(0)
    for spec in module_specs:
        count = Fraction(spec["count"])
        mtype = spec["type"]
        tier  = spec["tier"]
        qual  = spec.get("quality", "normal")
        if mtype == "efficiency":
            # Efficiency: subtract; IS quality-scaled
            energy_bonus -= count * MODULE_EFFICIENCY_REDUCTION[tier] * MODULE_QUALITY_MULT[qual]
        elif mtype in MODULE_CONSUMPTION_PENALTY:
            # Speed/prod: add penalty; NOT quality-scaled
            energy_bonus += count * MODULE_CONSUMPTION_PENALTY[mtype][tier]

    # Clamp to −80% floor
    energy_bonus = max(energy_bonus, Fraction(-4, 5))

    factor: Fraction = Fraction(base_w, 1000) * (Fraction(1) + energy_bonus)

    power_kw      = float(machine_count * factor)
    power_kw_ceil = float(math.ceil(machine_count) * factor)

    # Beacon power
    if beacon_spec is None or beacon_spec.get("count", 0) == 0:
        beacon_power_kw = 0.0
    else:
        sharing  = _beacon_sharing_factor(machine_key)
        physical = math.ceil(float(machine_count)) * beacon_spec["count"] / sharing
        beacon_power_kw = physical * BEACON_POWER_KW[beacon_quality]

    return (power_kw, power_kw_ceil, beacon_power_kw)


# ---------------------------------------------------------------------------
# Machine / recipe helpers
# ---------------------------------------------------------------------------

def get_machine(cat: str, assembler_level: int, furnace_type: str) -> tuple[str, Fraction]:
    """Return (machine_key, crafting_speed) for a recipe category."""
    if cat in SMELTING_CATS:
        return FURNACE_KEY[furnace_type], FURNACE_SPEED[furnace_type]
    if cat in FIXED_MACHINE_FOR_CAT:
        return FIXED_MACHINE_FOR_CAT[cat]
    return ASSEMBLER_KEY[assembler_level], ASSEMBLER_SPEED[assembler_level]


def _recipe_valid_for_planet(recipe: dict, planet_props: dict) -> bool:
    """Return True if all recipe surface_conditions are satisfied by planet_props."""
    for cond in recipe.get("surface_conditions", []):
        prop = cond["property"]
        val = planet_props.get(prop, 0)
        if val < cond.get("min", val) or val > cond.get("max", val):
            return False
    return True


def pick_recipe(
    item_key: str,
    recipe_idx: dict,
    overrides: dict | None = None,
    planet_props: dict | None = None,
    location: str | None = None,
) -> dict | None:
    """
    Select canonical recipe for item_key.

    Priority:
      1. Explicit override from --recipe ITEM=RECIPE flag.
      2. Entry in RECIPE_DEFAULTS_BY_LOCATION for the current location.
         (Before exact-key-match so location correctness wins over the implicit
         "recipe key == item key" heuristic.)
      3. Recipe whose key == item_key (exact match).
      4. advanced-oil-processing (legacy fallback for oil products).
      4.5. Entry in RECIPE_DEFAULTS (overrides order-sort for un-automatable defaults).
      5. First candidate after sorting by the game's ``order`` field.

    Sorting by ``order`` before the fallback selects the game-preferred recipe
    (e.g. solid-fuel-from-petroleum-gas over less-efficient variants).
    """
    candidates = recipe_idx.get(item_key, [])
    if not candidates:
        return None

    # 1. Explicit override — bypasses planet filtering
    if overrides and item_key in overrides:
        wanted = overrides[item_key]
        for r in candidates:
            if r["key"] == wanted:
                return r
        # Override key not found among candidates -- fall through to defaults

    # Planet filtering (only when planet_props given, no explicit override matched)
    if planet_props:
        filtered = [r for r in candidates if _recipe_valid_for_planet(r, planet_props)]
        if filtered:
            candidates = filtered
        elif not (overrides and item_key in overrides):
            return None  # all recipes filtered out by planet conditions

    # Sort by the game's display order so fallback picks the preferred variant
    candidates = sorted(candidates, key=lambda r: r.get("order", ""))

    # 2. Location-specific defaults (checked before exact-key-match)
    if location:
        loc_defaults = RECIPE_DEFAULTS_BY_LOCATION.get(location, {})
        if item_key in loc_defaults:
            wanted = loc_defaults[item_key]
            for r in candidates:
                if r["key"] == wanted:
                    return r

    # 3. Exact key match
    for r in candidates:
        if r["key"] == item_key:
            return r

    # 4. advanced-oil-processing legacy fallback
    for r in candidates:
        if r["key"] == "advanced-oil-processing":
            return r

    # 4.5. Hard-coded preferred recipe (avoids unautomatable order-sort defaults)
    if item_key in RECIPE_DEFAULTS:
        wanted = RECIPE_DEFAULTS[item_key]
        for r in candidates:
            if r["key"] == wanted:
                return r

    # 5. First after order-sort
    return candidates[0]


# ---------------------------------------------------------------------------
# Oil linear-system solver
# ---------------------------------------------------------------------------

def _gauss2(A: list, b: list) -> list[Fraction] | None:
    """Solve 2x2 exact linear system Ax=b.  Returns None if singular."""
    det = A[0][0] * A[1][1] - A[0][1] * A[1][0]
    if det == 0:
        return None
    return [
        (b[0] * A[1][1] - b[1] * A[0][1]) / det,
        (A[0][0] * b[1] - A[1][0] * b[0]) / det,
    ]


def _gauss3(A: list, b: list) -> list[Fraction] | None:
    """Solve 3x3 exact linear system Ax=b via Gaussian elimination."""
    n = 3
    M = [[A[i][j] for j in range(n)] + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if M[r][col] != 0), None)
        if pivot is None:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        for row in range(n):
            if row != col and M[row][col] != 0:
                f = M[row][col] / M[col][col]
                for j in range(col, n + 1):
                    M[row][j] -= f * M[col][j]
    return [M[i][n] / M[i][i] for i in range(n)]


def _recipe_yield(recipe: dict, product: str) -> Fraction:
    for r in recipe.get("results", []):
        if r["name"] == product:
            return Fraction(str(r.get("amount", 1)))
    return Fraction(0)


def _recipe_ing(recipe: dict, ingredient: str) -> Fraction:
    for i in recipe.get("ingredients", []):
        if i["name"] == ingredient:
            return Fraction(str(i.get("amount", 1)))
    return Fraction(0)


def solve_oil_system(
    D_heavy: Fraction,
    D_light: Fraction,
    D_petgas: Fraction,
    refinery: dict,
    hoc: dict | None,
    loc: dict | None,
) -> dict[str, dict]:
    """
    Compute cycle rates (per minute) for the refinery recipe, heavy-oil-cracking,
    and light-oil-cracking to satisfy downstream demands D_heavy, D_light, D_petgas.

    ``refinery`` may be any oil-processing recipe: advanced-oil-processing,
    basic-oil-processing, coal-liquefaction (self-consuming heavy oil), or
    simple-coal-liquefaction.  Self-consumption is handled by using the *net*
    heavy-oil output (gross minus the heavy-oil ingredient, if any).

    Returns {recipe_key: {"cycles_per_min": Fraction, "recipe": dict}}.
    """
    ref_H_gross = _recipe_yield(refinery, "heavy-oil")
    ref_H_in    = _recipe_ing(refinery,   "heavy-oil")  # self-consumption (CL only)
    ref_H = ref_H_gross - ref_H_in   # net heavy oil per cycle
    ref_L = _recipe_yield(refinery, "light-oil")
    ref_P = _recipe_yield(refinery, "petroleum-gas")

    hoc_in  = _recipe_ing(hoc,  "heavy-oil")   if hoc else Fraction(0)
    hoc_out = _recipe_yield(hoc, "light-oil")   if hoc else Fraction(0)
    loc_in  = _recipe_ing(loc,  "light-oil")    if loc else Fraction(0)
    loc_out = _recipe_yield(loc, "petroleum-gas") if loc else Fraction(0)

    # With no cracking available, just run enough refinery cycles for biggest demand
    if not hoc or not loc:
        demands = []
        if ref_H: demands.append(D_heavy  / ref_H)
        if ref_L: demands.append(D_light  / ref_L)
        if ref_P: demands.append(D_petgas / ref_P)
        r = max(demands) if demands else Fraction(0)
        return {refinery["key"]: {"cycles_per_min": r, "recipe": refinery}}

    # Full 3-variable system:
    #  ref_H * r - hoc_in * h                 = D_heavy
    #  ref_L * r + hoc_out * h - loc_in * l   = D_light
    #  ref_P * r               + loc_out * l  = D_petgas
    A = [
        [ref_H,  -hoc_in,   Fraction(0)],
        [ref_L,   hoc_out,  -loc_in    ],
        [ref_P,   Fraction(0), loc_out ],
    ]
    b = [D_heavy, D_light, D_petgas]

    sol = _gauss3(A, b)
    r, h, l = sol if sol else [Fraction(0)] * 3

    # Heavy cracking negative -> excess heavy oil, don't crack it
    if h < 0:
        h = Fraction(0)
        r_floor = D_heavy / ref_H if ref_H else Fraction(0)
        s2 = _gauss2([[ref_L, -loc_in], [ref_P, loc_out]], [D_light, D_petgas])
        if s2 and s2[0] >= r_floor and s2[1] >= 0:
            r, l = s2
        else:
            r = max(r_floor, D_petgas / ref_P if ref_P else Fraction(0))
            l = Fraction(0)

    # Light cracking negative -> surplus gas, don't crack light oil
    if l < 0:
        l = Fraction(0)
        s2 = _gauss2([[ref_H, -hoc_in], [ref_L, hoc_out]], [D_heavy, D_light])
        if s2 and s2[0] >= 0 and s2[1] >= 0 and ref_P * s2[0] >= D_petgas:
            r, h = s2
        else:
            h = Fraction(0)
            demands = []
            if ref_H: demands.append(D_heavy  / ref_H)
            if ref_P: demands.append(D_petgas / ref_P)
            r = max(demands) if demands else Fraction(0)

    out: dict[str, dict] = {}
    if r > 0:
        out[refinery["key"]] = {"cycles_per_min": r, "recipe": refinery}
    if h > 0 and hoc:
        out[hoc["key"]] = {"cycles_per_min": h, "recipe": hoc}
    if l > 0 and loc:
        out[loc["key"]] = {"cycles_per_min": l, "recipe": loc}
    return out


# ---------------------------------------------------------------------------
# Recursive solver
# ---------------------------------------------------------------------------

class Solver:
    """
    Walk the recipe dependency tree accumulating production steps.

    Design decisions
    ----------------
    * All numeric state is Fraction unless beacons are active (sqrt introduces
      irrational numbers, forcing machine_count to float for affected recipes).
    * Oil products are deferred: their demands accumulate in oil_demands and
      are resolved in a single linear-system pass via resolve_oil().
    * Co-products of multi-output recipes are credited to surplus[], consumed
      before starting additional machines.  This eliminates double-counting of
      crude-oil (and any other shared byproducts).
    * Module configs ({machine_key: [mspec, ...]}) and beacon configs
      ({machine_key: bspec}) are per-machine defaults, overridable per-recipe.
    * Machine quality adds an additive speed bonus to base crafting speed.
    * Beacon speed uses Factorio 2.0 diminishing-returns formula:
        effectivity × sqrt(count) × BEACON_SLOTS × module_bonus_per_slot
    """

    def __init__(
        self,
        recipe_idx: dict,
        raw_set: frozenset,
        assembler_level: int,
        furnace_type: str,
        module_configs: dict | None = None,
        beacon_configs: dict | None = None,
        machine_module_slots: dict | None = None,
        machine_quality: str = "normal",
        beacon_quality: str = "normal",
        recipe_overrides: dict | None = None,
        recipe_machine_overrides: dict | None = None,
        recipe_module_overrides: dict | None = None,
        recipe_beacon_overrides: dict | None = None,
        bus_items: frozenset | None = None,
        planet_props: dict | None = None,
        location: str | None = None,
    ):
        self.recipe_idx      = recipe_idx
        self.raw_set         = raw_set
        self.assembler_level = assembler_level
        self.furnace_type    = furnace_type
        self.module_configs:        dict = module_configs        or {}
        self.beacon_configs:        dict = beacon_configs        or {}
        self.machine_module_slots:  dict = machine_module_slots  or {}
        self.machine_quality: str  = machine_quality
        self.beacon_quality:  str  = beacon_quality
        self.recipe_overrides:         dict = recipe_overrides         or {}
        self.recipe_machine_overrides: dict = recipe_machine_overrides or {}
        self.recipe_module_overrides:  dict = recipe_module_overrides  or {}
        self.recipe_beacon_overrides:  dict = recipe_beacon_overrides  or {}
        self.bus_items: frozenset = frozenset(bus_items) if bus_items else frozenset()
        self.planet_props: dict = planet_props or {}
        self.location: str | None = location

        self.steps: dict[str, dict]             = {}
        self.raw_resources: dict[str, Fraction] = defaultdict(Fraction)
        self.bus_inputs: dict[str, Fraction]    = defaultdict(Fraction)
        self.surplus: dict[str, Fraction]       = defaultdict(Fraction)
        self.oil_demands: dict[str, Fraction]   = defaultdict(Fraction)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_modules(self, recipe_key: str, machine_key: str) -> list:
        """Return module specs list (recipe override > machine global > [])."""
        if recipe_key in self.recipe_module_overrides:
            return self.recipe_module_overrides[recipe_key]
        if machine_key in self.module_configs:
            return self.module_configs[machine_key]
        return []

    def _get_beacon(self, recipe_key: str, machine_key: str) -> dict | None:
        """Return beacon spec (recipe override > machine global > None)."""
        if recipe_key in self.recipe_beacon_overrides:
            return self.recipe_beacon_overrides[recipe_key]
        if machine_key in self.beacon_configs:
            return self.beacon_configs[machine_key]
        return None

    def _compute_module_effects(
        self, specs: list, machine_key: str, allow_prod: bool
    ) -> tuple:
        """
        Compute (prod_bonus: Fraction, speed_bonus: Fraction) from module specs.
        Total slot count is capped to the machine's available slots.
        Efficiency modules are tracked for output purposes but have no speed/prod effect.
        """
        if not specs:
            return Fraction(0), Fraction(0)
        slots = self.machine_module_slots.get(machine_key, 0)
        if slots == 0:
            return Fraction(0), Fraction(0)
        total_requested = sum(s["count"] for s in specs)
        if total_requested == 0:
            return Fraction(0), Fraction(0)
        scale = Fraction(min(slots, total_requested), total_requested)
        prod_bonus  = Fraction(0)
        speed_bonus = Fraction(0)
        for spec in specs:
            eff_count = Fraction(spec["count"]) * scale
            qual_mult = MODULE_QUALITY_MULT[spec["quality"]]
            if spec["type"] == "prod" and allow_prod:
                prod_bonus  += eff_count * MODULE_PROD_BONUS[spec["tier"]] * qual_mult
            elif spec["type"] == "speed":
                speed_bonus += eff_count * SPEED_MODULE_BONUS[spec["tier"]] * qual_mult
            # efficiency: no effect on production count
        return prod_bonus, speed_bonus

    def _compute_beacon_speed(self, beacon_spec: dict | None) -> float:
        """
        Compute beacon speed bonus using Factorio 2.0 diminishing-returns formula:
          effectivity × sqrt(count) × BEACON_SLOTS × module_bonus_per_slot
        Returns 0.0 when no beacon or count == 0.
        """
        if not beacon_spec or beacon_spec.get("count", 0) == 0:
            return 0.0
        effectivity  = BEACON_EFFECTIVITY[self.beacon_quality]
        module_bonus = (
            SPEED_MODULE_BONUS[beacon_spec["tier"]]
            * MODULE_QUALITY_MULT[beacon_spec["quality"]]
        )
        return (
            float(effectivity)
            * math.sqrt(beacon_spec["count"])
            * BEACON_SLOTS
            * float(module_bonus)
        )

    def rate_for_machines(self, item_key: str, machines: float) -> Fraction:
        """
        Return the items/min output rate that ``machines`` machines produce for
        item_key, honouring all configured module, beacon, machine-quality, and
        recipe-machine overrides.  Mirrors the inverse of the machine_count
        formula in solve(), so solve(item, rate_for_machines(item, N)) gives
        back exactly N machines for the top-level step.
        """
        recipe = pick_recipe(item_key, self.recipe_idx, self.recipe_overrides, self.planet_props or None, self.location)
        if recipe is None:
            raise ValueError(f"No recipe found for item '{item_key}'")

        recipe_key = recipe["key"]

        result_amount = Fraction(1)
        for res in recipe.get("results", []):
            if res["name"] == item_key:
                prob = Fraction(str(res.get("probability", 1)))
                result_amount = Fraction(str(res.get("amount", 1))) * prob
                break

        energy_req = Fraction(str(recipe.get("energy_required", "0.5")))
        cat        = recipe.get("category", "crafting")

        machine_key, base_speed = self._resolve_machine(recipe_key, cat)

        quality_mult    = Fraction(1) + MACHINE_QUALITY_SPEED[self.machine_quality]
        effective_speed = base_speed * quality_mult

        allow_prod = recipe.get("allow_productivity", False)
        specs      = self._get_modules(recipe_key, machine_key)
        prod_bonus, speed_mod_bonus = self._compute_module_effects(specs, machine_key, allow_prod)
        effective_speed = effective_speed * (Fraction(1) + speed_mod_bonus)

        effective_result = result_amount * (Fraction(1) + prod_bonus)

        beacon_spec        = self._get_beacon(recipe_key, machine_key)
        beacon_speed_bonus = self._compute_beacon_speed(beacon_spec)

        machines_frac = Fraction(str(machines))
        if beacon_speed_bonus:
            eff_total = float(effective_speed) * (1.0 + beacon_speed_bonus)
            rate_f    = float(machines_frac) * eff_total * float(effective_result) * 60.0 / float(energy_req)
            return Fraction(str(round(rate_f, 8)))
        return machines_frac * effective_speed * effective_result * 60 / energy_req

    def _resolve_machine(self, recipe_key: str, cat: str) -> tuple:
        """
        Return (machine_key, base_speed) respecting recipe-level machine overrides.
        Priority: recipe_machine_overrides > category default.
        """
        if recipe_key in self.recipe_machine_overrides:
            ovr = self.recipe_machine_overrides[recipe_key]
            if ovr in MACHINE_CRAFTING_SPEED:
                return ovr, MACHINE_CRAFTING_SPEED[ovr]
        return get_machine(cat, self.assembler_level, self.furnace_type)

    # ------------------------------------------------------------------
    # Core solver
    # ------------------------------------------------------------------

    def solve(self, item_key: str, rate: Fraction, _chain: frozenset = frozenset()) -> None:
        """Recursively satisfy *rate* items/min of *item_key*."""

        # Consume from surplus first
        if self.surplus[item_key] >= rate:
            self.surplus[item_key] -= rate
            return
        rate -= self.surplus[item_key]
        self.surplus[item_key] = Fraction(0)

        # Bus item — provided externally on the bus, not mined or crafted
        if item_key in self.bus_items:
            self.bus_inputs[item_key] += rate
            return

        # Defer oil products to the linear system
        if item_key in OIL_PRODUCTS:
            self.oil_demands[item_key] += rate
            return

        # Raw resource
        if item_key in self.raw_set:
            self.raw_resources[item_key] += rate
            return

        recipe = pick_recipe(item_key, self.recipe_idx, self.recipe_overrides, self.planet_props or None, self.location)

        # No recipe → treat as raw (or raise if planet-restricted)
        if recipe is None:
            if self.planet_props and item_key not in self.raw_set:
                raise ValueError(
                    f"'{item_key}' cannot be produced at location '{self.location}'. "
                    f"Use --bus-item {item_key} to import it."
                )
            self.raw_resources[item_key] += rate
            return

        recipe_key = recipe["key"]

        # Cycle guard
        if recipe_key in _chain:
            self.raw_resources[item_key] += rate
            return

        new_chain = _chain | {recipe_key}

        # Output amount per craft cycle for the requested item
        # (probability-weighted: effective_amount = amount × probability)
        result_amount = Fraction(1)
        for res in recipe.get("results", []):
            if res["name"] == item_key:
                prob = Fraction(str(res.get("probability", 1)))
                result_amount = Fraction(str(res.get("amount", 1))) * prob
                break

        energy_req = Fraction(str(recipe.get("energy_required", "0.5")))
        cat        = recipe.get("category", "crafting")

        machine_key, base_speed = self._resolve_machine(recipe_key, cat)

        # Machine quality: additive speed bonus applied to base speed
        quality_mult    = Fraction(1) + MACHINE_QUALITY_SPEED[self.machine_quality]
        effective_speed = base_speed * quality_mult

        # Module effects
        allow_prod = recipe.get("allow_productivity", False)
        specs      = self._get_modules(recipe_key, machine_key)
        prod_bonus, speed_mod_bonus = self._compute_module_effects(specs, machine_key, allow_prod)
        effective_speed = effective_speed * (Fraction(1) + speed_mod_bonus)

        # Effective output per cycle (productivity bonus)
        effective_result = result_amount * (Fraction(1) + prod_bonus)
        cycles_per_min   = rate / effective_result

        # Beacon speed bonus (may introduce float — sqrt is irrational)
        beacon_spec        = self._get_beacon(recipe_key, machine_key)
        beacon_speed_bonus = self._compute_beacon_speed(beacon_spec)

        if beacon_speed_bonus:
            eff_speed_total = float(effective_speed) * (1.0 + beacon_speed_bonus)
            machines_needed = float(cycles_per_min * energy_req) / (60.0 * eff_speed_total)
        else:
            machines_needed = (cycles_per_min * energy_req) / (60 * effective_speed)

        # Credit co-products as surplus BEFORE recursing into ingredients so that
        # self-recycling co-products (e.g. asteroid chunks returned by crushing)
        # are available to offset the ingredient demand in the same step.
        for res in recipe.get("results", []):
            co = res["name"]
            if co == item_key:
                continue
            prob   = Fraction(str(res.get("probability", 1)))
            co_amt = Fraction(str(res.get("amount", 1))) * prob
            if prod_bonus > 0:
                co_amt = co_amt * (Fraction(1) + prod_bonus)
            self.surplus[co] += cycles_per_min * co_amt

        # Accumulate step (same recipe may arrive from multiple tree paths)
        if recipe_key in self.steps:
            self.steps[recipe_key]["rate_per_min"]  += rate
            self.steps[recipe_key]["machine_count"] += machines_needed
            inputs = self.steps[recipe_key]["inputs"]
            for ing in recipe.get("ingredients", []):
                ing_rate = cycles_per_min * Fraction(str(ing.get("amount", 1)))
                inputs[ing["name"]] = inputs.get(ing["name"], Fraction(0)) + ing_rate
                self.solve(ing["name"], ing_rate, new_chain)
        else:
            step_inputs: dict[str, Fraction] = {}
            for ing in recipe.get("ingredients", []):
                ing_rate = cycles_per_min * Fraction(str(ing.get("amount", 1)))
                step_inputs[ing["name"]] = ing_rate
                self.solve(ing["name"], ing_rate, new_chain)
            self.steps[recipe_key] = {
                "recipe":             recipe_key,
                "output_item":        item_key,
                "machine":            machine_key,
                "machine_count":      machines_needed,
                "rate_per_min":       rate,
                "beacon_speed_bonus": beacon_speed_bonus,
                "inputs":             step_inputs,
            }

    def resolve_oil(self, data: dict) -> None:
        """
        Consume accumulated oil_demands via the refinery + cracking linear system
        and inject the results into self.steps and self.raw_resources.

        The refinery recipe is selected as follows:
          1. If any oil product has a --recipe override pointing to an
             oil-processing recipe (e.g. coal-liquefaction), use that.
          2. Otherwise use advanced-oil-processing (or basic-oil-processing).
        """
        D_heavy  = self.oil_demands.get("heavy-oil",     Fraction(0))
        D_light  = self.oil_demands.get("light-oil",     Fraction(0))
        D_petgas = self.oil_demands.get("petroleum-gas", Fraction(0))

        if D_heavy == D_light == D_petgas == Fraction(0):
            return

        def find(key: str) -> dict | None:
            for r in data.get("recipes", []):
                if r.get("key") == key:
                    return r
            return None

        # 1. User-specified refinery recipe override (e.g. coal-liquefaction)
        refinery = None
        for oil_item in OIL_PRODUCTS:
            override_key = self.recipe_overrides.get(oil_item)
            if override_key:
                candidate = find(override_key)
                if candidate and candidate.get("category") == "oil-processing":
                    refinery = candidate
                    break

        # 2. Default: AOP or BOP
        if refinery is None:
            refinery = find("advanced-oil-processing") or find("basic-oil-processing")

        if refinery is None:
            for item, d in self.oil_demands.items():
                if d > 0:
                    self.raw_resources[item] += d
            return

        hoc = find("heavy-oil-cracking")
        loc = find("light-oil-cracking")

        oil_rates = solve_oil_system(D_heavy, D_light, D_petgas, refinery, hoc, loc)

        for rkey, info in oil_rates.items():
            rcp    = info["recipe"]
            cycles = info["cycles_per_min"]
            cat    = rcp.get("category", "oil-processing")
            machine_key, base_speed = self._resolve_machine(rkey, cat)
            quality_mult = Fraction(1) + MACHINE_QUALITY_SPEED[self.machine_quality]
            eff_speed    = base_speed * quality_mult
            energy_req   = Fraction(str(rcp.get("energy_required", 5)))
            machines     = (cycles * energy_req) / (60 * eff_speed)

            # Representative display rate: largest oil-product output for AOP,
            # primary output for cracking recipes
            oil_outputs = [
                cycles * _recipe_yield(rcp, p)
                for p in OIL_PRODUCTS
                if _recipe_yield(rcp, p) > 0
            ]
            disp_rate = max(oil_outputs) if oil_outputs else cycles

            oil_inputs: dict[str, Fraction] = {}
            for ing in rcp.get("ingredients", []):
                ing_name = ing["name"]
                oil_inputs[ing_name] = (
                    oil_inputs.get(ing_name, Fraction(0))
                    + cycles * Fraction(str(ing.get("amount", 1)))
                )

            if rkey in self.steps:
                self.steps[rkey]["machine_count"] += machines
                self.steps[rkey]["rate_per_min"]  += disp_rate
                step_inp = self.steps[rkey]["inputs"]
                for k, v in oil_inputs.items():
                    step_inp[k] = step_inp.get(k, Fraction(0)) + v
            else:
                self.steps[rkey] = {
                    "recipe":             rkey,
                    "machine":            machine_key,
                    "machine_count":      machines,
                    "rate_per_min":       disp_rate,
                    "beacon_speed_bonus": 0.0,
                    "inputs":             oil_inputs,
                }

            # Push oil-recipe ingredients into raw resources
            for ing in rcp.get("ingredients", []):
                ing_name = ing["name"]
                ing_rate = cycles * Fraction(str(ing.get("amount", 1)))
                if ing_name in self.raw_set:
                    self.raw_resources[ing_name] += ing_rate
                elif ing_name not in OIL_PRODUCTS:
                    # e.g. coal for coal-liquefaction
                    self.solve(ing_name, ing_rate)


# ---------------------------------------------------------------------------
# Miner computation
# ---------------------------------------------------------------------------

def compute_miners(
    raw_resources: dict[str, Fraction],
    resource_info: dict,
    miner_type: str,
    machine_power_w: dict | None = None,
    module_configs: dict | None = None,
    machine_module_slots: dict | None = None,
    beacon_configs: dict | None = None,
    beacon_quality: str = "normal",
) -> dict:
    if machine_power_w is None:
        machine_power_w = {}
    drill_key = "big-mining-drill" if miner_type == "big" else "electric-mining-drill"
    result: dict[str, dict] = {}

    for item, rate in raw_resources.items():
        info = resource_info.get(item)
        if info is None:
            continue

        cat = info["category"]
        if cat == "offshore":
            machine   = "offshore-pump"
            rate_each = OFFSHORE_PUMP_RATE
            count = rate / rate_each
            entry: dict = {
                "machine":            machine,
                "machine_count":      round(float(count), 4),
                "machine_count_ceil": math.ceil(count),
                "rate_per_min":       round(float(rate), 4),
            }
            base_w = machine_power_w.get(machine, 0)
            if base_w:
                entry["power_kw"] = round(float(count * Fraction(base_w, 1000)), 4)
            result[item] = entry
        elif cat in PUMPJACK_CATEGORIES:
            # FactorioLab-style: report total required field yield % rather than
            # machine count, since pumpjack throughput depends on field depletion.
            # rate_at_100pct = rate one pumpjack produces at 100% field yield.
            rate_at_100pct = (MINER_SPEED["pumpjack"] / info["mining_time"]) * info["yield"] * 60
            required_pct   = rate / rate_at_100pct * 100
            result[item] = {
                "machine":            "pumpjack",
                "required_yield_pct": round(float(required_pct), 2),
                "rate_per_min":       round(float(rate), 4),
            }
        else:
            machine = drill_key

            # Module bonuses (miners allow productivity)
            module_specs = (module_configs or {}).get(drill_key, [])
            slots = (machine_module_slots or {}).get(drill_key, 0)
            speed_bonus  = Fraction(0)
            prod_bonus   = Fraction(0)
            energy_bonus = Fraction(0)
            if module_specs and slots > 0:
                total_requested = sum(s["count"] for s in module_specs)
                if total_requested > 0:
                    scale = Fraction(min(slots, total_requested), total_requested)
                    for spec in module_specs:
                        eff_count = Fraction(spec["count"]) * scale
                        qual_mult = MODULE_QUALITY_MULT[spec["quality"]]
                        if spec["type"] == "prod":
                            prod_bonus   += eff_count * MODULE_PROD_BONUS[spec["tier"]] * qual_mult
                            energy_bonus += eff_count * MODULE_CONSUMPTION_PENALTY["prod"][spec["tier"]]
                        elif spec["type"] == "speed":
                            speed_bonus  += eff_count * SPEED_MODULE_BONUS[spec["tier"]] * qual_mult
                            energy_bonus += eff_count * MODULE_CONSUMPTION_PENALTY["speed"][spec["tier"]]
                        elif spec["type"] == "efficiency":
                            energy_bonus -= eff_count * MODULE_EFFICIENCY_REDUCTION[spec["tier"]] * qual_mult
            energy_bonus = max(energy_bonus, Fraction(-4, 5))

            # Beacon speed bonus (same diminishing-returns formula as crafting machines)
            beacon_spec = (beacon_configs or {}).get(drill_key)
            beacon_speed_bonus = 0.0
            if beacon_spec and beacon_spec.get("count", 0) > 0:
                effectivity  = BEACON_EFFECTIVITY[beacon_quality]
                module_bonus = (
                    SPEED_MODULE_BONUS[beacon_spec["tier"]]
                    * MODULE_QUALITY_MULT[beacon_spec["quality"]]
                )
                beacon_speed_bonus = (
                    float(effectivity)
                    * math.sqrt(beacon_spec["count"])
                    * BEACON_SLOTS
                    * float(module_bonus)
                )

            base_speed    = MINER_SPEED[drill_key] * (Fraction(1) + speed_bonus)
            eff_speed     = float(base_speed) * (1.0 + beacon_speed_bonus)
            rate_each     = (Fraction(str(round(eff_speed, 12))) / info["mining_time"]) * info["yield"] * (Fraction(1) + prod_bonus) * 60
            count = rate / rate_each
            entry = {
                "machine":            machine,
                "machine_count":      round(float(count), 4),
                "machine_count_ceil": math.ceil(count),
                "rate_per_min":       round(float(rate), 4),
            }
            if module_specs:
                entry["module_specs"] = module_specs
            base_w = machine_power_w.get(machine, 0)
            if base_w:
                power_factor = Fraction(1) + energy_bonus
                entry["power_kw"] = round(float(count * Fraction(base_w, 1000) * power_factor), 4)
            if beacon_spec and beacon_spec.get("count", 0) > 0:
                sharing  = _beacon_sharing_factor(machine)
                physical = math.ceil(float(count)) * beacon_spec["count"] / sharing
                entry["beacon_power_kw"] = round(physical * BEACON_POWER_KW[beacon_quality], 4)
            result[item] = entry

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _f(x: Fraction, places: int = 4) -> float:
    return round(float(x), places)


def format_output(
    args: argparse.Namespace,
    solver: "Solver",
    resource_info: dict,
    machine_power_w: dict | None = None,
) -> dict:
    """
    Assemble the final JSON output dict from solver results and CLI args.

    Single-target output: top-level item + rate_per_min fields.
    Multi-target output: top-level targets array instead.
    Power fields are included when machine_power_w is provided.
    """
    if machine_power_w is None:
        machine_power_w = {}

    steps_list_raw = []
    for s in solver.steps.values():
        recipe_key  = s["recipe"]
        machine_key = s["machine"]
        machine_count = s["machine_count"]

        # Look up module / beacon config for this step (same priority as solver)
        module_specs = solver._get_modules(recipe_key, machine_key)
        beacon_spec  = solver._get_beacon(recipe_key, machine_key)

        pwr, pwr_ceil, bpwr = _compute_step_power(
            machine_key, machine_count, module_specs,
            beacon_spec, solver.beacon_quality, machine_power_w,
        )

        step_out: dict = {
            "recipe":             recipe_key,
            "output_item":        s.get("output_item", recipe_key),
            "machine":            machine_key,
            "machine_count":      _f(machine_count),
            "machine_count_ceil": math.ceil(machine_count),
            "rate_per_min":       _f(s["rate_per_min"]),
            "inputs": {
                k: _f(v)
                for k, v in sorted(s["inputs"].items(), key=lambda x: -x[1])
            },
            "machine_quality":    solver.machine_quality,
            "beacon_speed_bonus": round(s["beacon_speed_bonus"], 6),
            "power_kw":           round(pwr,      4),
            "power_kw_ceil":      round(pwr_ceil, 4),
            "beacon_power_kw":    round(bpwr,     4),
        }
        if module_specs:
            step_out["module_specs"] = module_specs
        if beacon_spec is not None:
            step_out["beacon_spec"]    = beacon_spec
            step_out["beacon_quality"] = solver.beacon_quality
        steps_list_raw.append(step_out)

    steps_list = sorted(steps_list_raw, key=lambda x: -x["rate_per_min"])

    raw_sorted = {
        k: _f(v)
        for k, v in sorted(solver.raw_resources.items(), key=lambda x: -x[1])
    }

    miners = compute_miners(
        solver.raw_resources, resource_info, args.miner,
        machine_power_w=machine_power_w,
        module_configs=solver.module_configs or None,
        machine_module_slots=solver.machine_module_slots or None,
        beacon_configs=solver.beacon_configs or None,
        beacon_quality=solver.beacon_quality,
    )

    is_multi = len(args.items) > 1
    if is_multi:
        out: dict = {
            "targets": [
                {"item": itm, "rate_per_min": rate}
                for itm, rate in zip(args.items, args.rates)
            ],
            "location":        getattr(args, "location", None),
            "assembler":       args.assembler,
            "furnace":         args.furnace,
            "miner":           args.miner,
            "machine_quality": args.machine_quality,
            "beacon_quality":  args.beacon_quality,
        }
    else:
        out = {
            "item":            args.item,
            "rate_per_min":    args.rate,
            "location":        getattr(args, "location", None),
            "assembler":       args.assembler,
            "furnace":         args.furnace,
            "miner":           args.miner,
            "machine_quality": args.machine_quality,
            "beacon_quality":  args.beacon_quality,
        }

    # Echo non-empty configs
    if getattr(args, "module_configs", None):
        out["module_configs"] = args.module_configs
    if getattr(args, "beacon_configs", None):
        out["beacon_configs"] = args.beacon_configs

    if solver.recipe_overrides:
        out["recipe_overrides"] = solver.recipe_overrides

    # Per-recipe overrides from args
    if getattr(args, "recipe_machine_overrides", None):
        out["recipe_machine_overrides"] = args.recipe_machine_overrides
    if getattr(args, "recipe_module_overrides", None):
        out["recipe_module_overrides"] = args.recipe_module_overrides
    if getattr(args, "recipe_beacon_overrides", None):
        out["recipe_beacon_overrides"] = args.recipe_beacon_overrides

    # Accumulate total power (MW)
    total_step_pwr      = sum(s["power_kw"] + s["beacon_power_kw"] for s in steps_list)
    total_step_pwr_ceil = sum(s["power_kw_ceil"] + s["beacon_power_kw"] for s in steps_list)
    miner_pwr = sum(
        v.get("power_kw", 0) + v.get("beacon_power_kw", 0)
        for v in miners.values()
        if isinstance(v, dict)
    )

    out["production_steps"]    = steps_list
    out["raw_resources"]       = raw_sorted
    out["miners_needed"]       = miners
    out["total_power_mw"]      = round((total_step_pwr + miner_pwr) / 1000, 4)
    out["total_power_mw_ceil"] = round((total_step_pwr_ceil + miner_pwr) / 1000, 4)

    if solver.bus_inputs:
        out["bus_inputs"] = {
            k: _f(v)
            for k, v in sorted(solver.bus_inputs.items(), key=lambda x: -x[1])
        }

    return out


def format_human_readable(out: dict) -> str:
    """Render the output dict from format_output() as human-readable text."""
    lines: list[str] = []

    # --- Header ---
    if "targets" in out:
        targets_str = ", ".join(
            f"{t['item']}@{t['rate_per_min']}/min" for t in out["targets"]
        )
        lines.append(f"=== Targets: {targets_str} ===")
    else:
        lines.append(f"=== {out['item']} @ {out['rate_per_min']}/min ===")

    location_val = out.get("location")
    location_str = location_val if location_val is not None else "vanilla"
    config_parts = [
        f"Location: {location_str}",
        f"Assembler: {out['assembler']}",
        f"Furnace: {out['furnace']}",
        f"Miner: {out['miner']}",
    ]
    lines.append("  |  ".join(config_parts))

    mq = out.get("machine_quality", "normal")
    bq = out.get("beacon_quality", "normal")
    if mq != "normal" or bq != "normal":
        lines.append(f"Machine quality: {mq}  |  Beacon quality: {bq}")

    if out.get("module_configs"):
        for machine, specs in out["module_configs"].items():
            spec_strs = []
            for s in specs:
                spec_strs.append(f"{s['count']}x {s['type']}-{s['tier']}-{s['quality']}")
            lines.append(f"Modules:  {machine} = {', '.join(spec_strs)}")

    if out.get("beacon_configs"):
        for machine, spec in out["beacon_configs"].items():
            lines.append(
                f"Beacons:  {machine} = {spec['count']}x tier-{spec['tier']}-{spec['quality']}"
            )

    # --- Production Steps ---
    lines.append("")
    lines.append("Production Steps")
    lines.append("----------------")
    for step in out.get("production_steps", []):
        recipe       = step["recipe"]
        output_item  = step.get("output_item", recipe)
        machine      = step["machine"]
        machine_q    = step.get("machine_quality", "normal")
        mc           = step["machine_count"]
        mc_ceil      = step["machine_count_ceil"]
        rate         = step["rate_per_min"]
        machine_label = f"{machine_q} {machine}" if machine_q != "normal" else machine
        recipe_label  = f"{recipe} → {output_item}" if output_item != recipe else recipe
        lines.append(f"{recipe_label:<30}  {rate}/min    {mc} -> {mc_ceil} {machine_label}")

        # optional modules / beacons / speed / power detail line
        detail_parts: list[str] = []
        if step.get("module_specs"):
            mod_strs = []
            for s in step["module_specs"]:
                mod_strs.append(f"{s['count']}x {s['type']}-{s['tier']}-{s['quality']}")
            detail_parts.append(f"modules: {', '.join(mod_strs)}")
        if step.get("beacon_spec") is not None:
            bs = step["beacon_spec"]
            detail_parts.append(f"beacons: {bs['count']}x tier-{bs['tier']}-{bs['quality']}")
        if step.get("beacon_speed_bonus", 0):
            detail_parts.append(f"speed bonus: +{round(step['beacon_speed_bonus'], 4)}")
        if detail_parts:
            lines.append(f"  {('  |  ').join(detail_parts)}")

        pwr      = step.get("power_kw", 0)
        pwr_ceil = step.get("power_kw_ceil", 0)
        bpwr     = step.get("beacon_power_kw", 0)
        if pwr or bpwr:
            pwr_str = f"power: {pwr} kW  ({pwr_ceil} kW ceil)"
            if bpwr:
                pwr_str += f"  +  {bpwr} kW beacons"
            lines.append(f"  {pwr_str}")

        for inp_item, inp_rate in step.get("inputs", {}).items():
            lines.append(f"  <- {inp_item:<28}  {inp_rate}/min")
        lines.append("")

    # --- Raw Resources ---
    lines.append("Raw Resources")
    lines.append("-------------")
    for item, rate in out.get("raw_resources", {}).items():
        lines.append(f"  {item:<30}  {rate}/min")

    # --- Miners ---
    miners = out.get("miners_needed", {})
    if miners:
        lines.append("")
        lines.append("Miners Needed")
        lines.append("-------------")
        for item, info in miners.items():
            if not isinstance(info, dict):
                continue
            machine = info.get("machine", "")
            if "required_yield_pct" in info:
                lines.append(f"  {item:<30}  requires {info['required_yield_pct']}% field yield  ({machine})")
            else:
                mc  = info.get("machine_count", 0)
                mcc = info.get("machine_count_ceil", 0)
                lines.append(f"  {item:<30}  {mc} {machine} ({mcc} ceil)")

    # --- Bus Inputs ---
    if out.get("bus_inputs"):
        lines.append("")
        lines.append("Bus Inputs (from bus, not mined)")
        lines.append("---------------------------------")
        for item, rate in out["bus_inputs"].items():
            lines.append(f"  {item:<30}  {rate}/min")

    # --- Power ---
    lines.append("")
    lines.append("Power")
    lines.append("-----")
    lines.append(f"  Total: {out.get('total_power_mw', 0)} MW  ({out.get('total_power_mw_ceil', 0)} MW with ceil counts)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_kv(raw: str, flag: str) -> tuple[str, str]:
    """Parse 'KEY=VALUE' and exit with an error message on bad format."""
    if "=" not in raw:
        sys.exit(f"{flag} requires KEY=VALUE format, got: {raw!r}")
    k, v = raw.split("=", 1)
    return k.strip(), v.strip()


def _parse_module_spec(raw_value: str, flag: str) -> dict:
    """Parse 'COUNT:TYPE:TIER:QUALITY' into a module spec dict."""
    parts = raw_value.split(":")
    if len(parts) < 4:
        sys.exit(f"{flag} value must be COUNT:TYPE:TIER:QUALITY, got: {raw_value!r}")
    try:
        count = int(parts[0])
        tier  = int(parts[2])
    except ValueError:
        sys.exit(f"{flag} COUNT and TIER must be integers, got: {raw_value!r}")
    return {"count": count, "type": parts[1], "tier": tier, "quality": parts[3]}


def _parse_beacon_spec(raw_value: str, flag: str) -> dict:
    """Parse 'COUNT:TIER:QUALITY' into a beacon spec dict."""
    parts = raw_value.split(":")
    if len(parts) < 3:
        sys.exit(f"{flag} value must be COUNT:TIER:QUALITY, got: {raw_value!r}")
    try:
        count = int(parts[0])
        tier  = int(parts[1])
    except ValueError:
        sys.exit(f"{flag} COUNT and TIER must be integers, got: {raw_value!r}")
    return {"count": count, "tier": tier, "quality": parts[2]}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Factorio production calculator -- outputs JSON with machine counts, "
            "raw resource rates, miner counts, and belt/pump counts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --item electronic-circuit --rate 60
  python cli.py --item processing-unit --rate 10 --assembler 3 --furnace electric
  python cli.py --item rocket-fuel --rate 5 --assembler 3 --location nauvis
  python cli.py --item tungsten-carbide --rate 60 --location vulcanus --miner big
  python cli.py --item electronic-circuit --rate 60 --belt blue
  python cli.py --item lubricant --rate 60 --pump legendary
  python cli.py --item electronic-circuit --rate 60 \\
      --modules "assembling-machine-3=4:prod:3:normal" \\
      --beacon "assembling-machine-3=4:3:normal" \\
      --machine-quality legendary
""",
    )
    p.add_argument("--item",
                   action="append", dest="items", default=[],
                   help="Item ID (e.g. electronic-circuit). Repeatable for multi-target.")
    p.add_argument("--rate",
                   action="append", dest="rates", default=[], type=float,
                   help="Target production rate in items / minute. Repeatable; pairs with --item by position.")
    p.add_argument("--machines",
                   action="append", dest="machines_list", default=[], type=float,
                   help=(
                       "Number of machines for the target item (fractional ok). Repeatable; "
                       "pairs with --item by position. Use --rate or --machines, not both."
                   ))
    p.add_argument("--assembler", default=3, type=int, choices=[1, 2, 3],
                   help="Assembling machine level (default: 3).")
    p.add_argument("--furnace",  default="electric",
                   choices=["stone", "steel", "electric"],
                   help="Furnace type (default: electric).")
    p.add_argument("--miner",    default="electric", choices=["electric", "big"],
                   help="Mining drill for solid ores (default: electric).")
    p.add_argument(
        "--location", default=None,
        metavar="PLANET",
        dest="location",
        help=(
            "Target location (space-age planet or space-platform). "
            "Omit for vanilla. Valid: nauvis, vulcanus, fulgora, gleba, aquilo, space-platform. "
            "Automatically selects the Space Age dataset."
        ),
    )
    p.add_argument("--machine-quality", default="normal",
                   choices=list(QUALITY_NAMES), dest="machine_quality",
                   help="Quality tier of all machines (default: normal).")
    p.add_argument("--beacon-quality", default="normal",
                   choices=list(QUALITY_NAMES), dest="beacon_quality",
                   help="Quality tier of beacons (default: normal).")
    p.add_argument(
        "--modules",
        action="append", default=[],
        metavar="MACHINE=COUNT:TYPE:TIER:QUALITY",
        help=(
            "Fill machine slots with modules. Repeatable; multiple specs for "
            "the same machine are stacked (mixed modules). "
            "E.g. --modules 'assembling-machine-3=4:prod:3:normal'"
        ),
    )
    p.add_argument(
        "--beacon",
        action="append", default=[],
        metavar="MACHINE=COUNT:TIER:QUALITY",
        help=(
            "Beacon count and module quality per machine. Repeatable. "
            "E.g. --beacon 'assembling-machine-3=4:3:normal'"
        ),
    )
    p.add_argument(
        "--recipe",
        action="append", default=[],
        metavar="ITEM=RECIPE",
        help=(
            "Override recipe for ITEM. Repeatable. "
            "E.g. --recipe solid-fuel=solid-fuel-from-light-oil"
        ),
    )
    p.add_argument(
        "--recipe-machine",
        action="append", default=[],
        metavar="RECIPE=MACHINE",
        dest="recipe_machine",
        help="Override machine for a specific recipe key. Repeatable.",
    )
    p.add_argument(
        "--recipe-modules",
        action="append", default=[],
        metavar="RECIPE=COUNT:TYPE:TIER:QUALITY",
        dest="recipe_modules",
        help="Per-recipe module override. Repeatable; stack for mixed modules.",
    )
    p.add_argument(
        "--recipe-beacon",
        action="append", default=[],
        metavar="RECIPE=COUNT:TIER:QUALITY",
        dest="recipe_beacon",
        help="Per-recipe beacon override. Repeatable.",
    )
    p.add_argument(
        "--bus-item",
        action="append", default=[],
        metavar="ITEM-ID",
        dest="bus_item",
        help=(
            "Treat item as a bus input (raw resource). Stops recursion at this "
            "item — machines and sub-recipes are not calculated for it. Repeatable. "
            "E.g. --bus-item iron-plate --bus-item copper-plate"
        ),
    )
    p.add_argument(
        "--format", default="json", choices=["json", "human"],
        dest="output_format",
        help="Output format: json (default) or human-readable text.",
    )
    args = p.parse_args()
    if not args.items:
        p.error("At least one --item must be provided.")
    has_rate     = len(args.rates) > 0
    has_machines = len(args.machines_list) > 0
    if has_rate and has_machines:
        p.error("Cannot mix --rate and --machines; use one mode across all targets.")
    if not has_rate and not has_machines:
        p.error("Exactly one of --rate or --machines must be provided.")
    n = len(args.items)
    if has_rate and len(args.rates) != n:
        p.error(
            f"Got {n} --item(s) but {len(args.rates)} --rate(s); "
            "each --item needs a matching --rate."
        )
    if has_machines and len(args.machines_list) != n:
        p.error(
            f"Got {n} --item(s) but {len(args.machines_list)} --machines value(s); "
            "each --item needs a matching --machines."
        )
    # Backwards-compat aliases used by single-target paths
    args.item = args.items[0]
    args.rate = args.rates[0] if has_rate else None
    return args


def main() -> None:
    args  = parse_args()

    # Parse --recipe ITEM=RECIPE
    recipe_overrides: dict[str, str] = {}
    for raw in args.recipe:
        k, v = _parse_kv(raw, "--recipe")
        recipe_overrides[k] = v

    # Parse --modules MACHINE=COUNT:TYPE:TIER:QUALITY
    module_configs: dict[str, list] = {}
    for raw in args.modules:
        k, v = _parse_kv(raw, "--modules")
        module_configs.setdefault(k, []).append(_parse_module_spec(v, "--modules"))

    # Parse --beacon MACHINE=COUNT:TIER:QUALITY
    beacon_configs: dict[str, dict] = {}
    for raw in args.beacon:
        k, v = _parse_kv(raw, "--beacon")
        beacon_configs[k] = _parse_beacon_spec(v, "--beacon")

    # Parse per-recipe overrides
    recipe_machine_overrides: dict[str, str] = {}
    for raw in args.recipe_machine:
        k, v = _parse_kv(raw, "--recipe-machine")
        recipe_machine_overrides[k] = v

    recipe_module_overrides: dict[str, list] = {}
    for raw in args.recipe_modules:
        k, v = _parse_kv(raw, "--recipe-modules")
        recipe_module_overrides.setdefault(k, []).append(_parse_module_spec(v, "--recipe-modules"))

    recipe_beacon_overrides: dict[str, dict] = {}
    for raw in args.recipe_beacon:
        k, v = _parse_kv(raw, "--recipe-beacon")
        recipe_beacon_overrides[k] = _parse_beacon_spec(v, "--recipe-beacon")

    bus_items: frozenset = frozenset(args.bus_item)

    data            = load_data(args.location)
    raw_set         = build_raw_set(data, args.location)
    planet_props    = get_planet_props(data, args.location)
    recipe_idx      = build_recipe_index(data)
    resource_info   = build_resource_info(data)
    machine_power_w      = build_machine_power_w(data)
    machine_module_slots = build_machine_module_slots(data)

    solver = Solver(
        recipe_idx, raw_set,
        args.assembler, args.furnace,
        module_configs=module_configs or None,
        beacon_configs=beacon_configs or None,
        machine_module_slots=machine_module_slots,
        machine_quality=args.machine_quality,
        beacon_quality=args.beacon_quality,
        recipe_overrides=recipe_overrides or None,
        recipe_machine_overrides=recipe_machine_overrides or None,
        recipe_module_overrides=recipe_module_overrides or None,
        recipe_beacon_overrides=recipe_beacon_overrides or None,
        bus_items=bus_items or None,
        planet_props=planet_props or None,
        location=args.location,
    )

    targets: list[tuple[str, Fraction]] = []
    has_machines = len(args.machines_list) > 0
    for i, item in enumerate(args.items):
        if has_machines:
            rate = solver.rate_for_machines(item, args.machines_list[i])
        else:
            rate = Fraction(str(args.rates[i]))
        targets.append((item, rate))

    for item, rate in targets:
        solver.solve(item, rate)
    solver.resolve_oil(data)

    if len(targets) == 1:
        args.rate = float(targets[0][1])
    else:
        args.rates = [float(r) for (_, r) in targets]

    # Attach parsed configs to args so format_output can echo them
    args.module_configs           = module_configs or None
    args.beacon_configs           = beacon_configs or None
    args.recipe_machine_overrides = recipe_machine_overrides or None
    args.recipe_module_overrides  = recipe_module_overrides  or None
    args.recipe_beacon_overrides  = recipe_beacon_overrides  or None

    result = format_output(args, solver, resource_info, machine_power_w=machine_power_w)
    if args.output_format == "human":
        print(format_human_readable(result))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
