#!/usr/bin/env python3
"""
Factorio Production Calculator

Usage:
    python cli.py --item <item-id> --rate <N>
                  [--assembler 1|2|3]
                  [--furnace stone|steel|electric]
                  [--miner electric|big]
                  [--dataset vanilla|space-age]
                  [--machine-quality QUALITY]
                  [--beacon-quality QUALITY]
                  [--belt yellow|red|blue|turbo]
                  [--pump QUALITY]
                  [--modules MACHINE=COUNT:TYPE:TIER:QUALITY]   # repeatable
                  [--beacon MACHINE=COUNT:TIER:QUALITY]         # repeatable
                  [--recipe ITEM=RECIPE]                        # repeatable
                  [--recipe-machine RECIPE=MACHINE]             # repeatable
                  [--recipe-modules RECIPE=COUNT:TYPE:TIER:QUALITY]  # repeatable
                  [--recipe-beacon RECIPE=COUNT:TIER:QUALITY]   # repeatable
                  [--recipe-belt RECIPE=BELT]                   # repeatable
                  [--recipe-pump RECIPE=QUALITY]                # repeatable

Auto-loads factorio-prefs.json from the current directory if present.
CLI flags always override prefs.

Outputs clean JSON to stdout:
  - production_steps: machine type + count per recipe in the dependency tree
  - raw_resources:    mining / pumping rates per minute (no recipe)
  - miners_needed:    drill / pumpjack / offshore-pump counts per raw resource
  - belts_for_output: yellow / red / blue (/ turbo) belt counts for target output

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
PREFS_FILE = "factorio-prefs.json"   # auto-loaded from CWD if present

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

# Belt throughput: items / minute per full belt (both lanes combined)
# turbo is Space Age only — validated in parse_args / main.
BELT_THROUGHPUT: dict[str, int] = {
    "yellow": 900,     # transport-belt          15/s
    "red":    1800,    # fast-transport-belt      30/s
    "blue":   2700,    # express-transport-belt   45/s
    "turbo":  3600,    # turbo-transport-belt     60/s
}
BELT_TIERS_VANILLA    = frozenset(["yellow", "red", "blue"])
BELT_TIERS_SPACE_AGE  = frozenset(["yellow", "red", "blue", "turbo"])

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
    "electronics":                       ("electronics-assembly",    Fraction(3)),
    "electronics-or-assembling":         ("electronics-assembly",    Fraction(3)),
    "electronics-with-fluid":            ("electronics-assembly",    Fraction(3)),
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
    "electronics-assembly":    Fraction(3),
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

# Module slots per machine (not stored in dataset -- hardcoded from game data).
# Machines with 0 slots effectively get no productivity bonus regardless of tier.
MACHINE_MODULE_SLOTS: dict[str, int] = {
    # Vanilla ---------------------------------------------------------------
    "assembling-machine-1":  0,
    "assembling-machine-2":  2,
    "assembling-machine-3":  4,
    "stone-furnace":         0,
    "steel-furnace":         0,
    "electric-furnace":      2,
    "chemical-plant":        3,
    "oil-refinery":          3,
    "centrifuge":            2,
    "rocket-silo":           4,
    # Space Age -------------------------------------------------------------
    "cryogenic-plant":       4,
    "biochamber":            4,
    "electromagnetic-plant": 5,
    "electronics-assembly":  5,
    "foundry":               4,
    "crusher":               2,
    "agricultural-tower":    0,
    "captive-spawner":       0,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(dataset: str) -> dict:
    """Return parsed JSON for *dataset*, downloading the file if absent."""
    path = os.path.join(DATA_DIR, DATA_FILES[dataset])
    if not os.path.exists(path):
        url = DATA_URLS[dataset]
        sys.stderr.write(f"Downloading {url} ...\n")
        urllib.request.urlretrieve(url, path)
        sys.stderr.write(f"Saved to {path}\n")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_prefs(path: str | None = None) -> dict:
    """
    Load factorio-prefs.json from the current working directory (or *path*
    if given).  Returns an empty dict if the file doesn't exist.

    Supported keys (all optional):
      dataset, assembler, furnace, miner, machine_quality, beacon_quality, belt, pump
        — become CLI flag defaults; explicit flags still win.
      recipe_overrides  {item-id: recipe-key}
        — merged with --recipe flags; explicit --recipe flags win.
      preferred_belt    "yellow"|"red"|"blue"|"turbo"
        — consumed by Claude (SKILL.md) only; not used by the solver.
    """
    filepath = path or PREFS_FILE
    if not os.path.exists(filepath):
        return {}
    with open(filepath, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def build_raw_set(data: dict) -> frozenset:
    """Return set of item keys that are raw inputs (mined / pumped)."""
    raw: set[str] = set()
    for res in data.get("resources", []):
        for r in res.get("results", []):
            raw.add(r["name"])
    for planet in data.get("planets", []):
        pres = planet.get("resources", {})
        raw.update(pres.get("resource", []))
        raw.update(pres.get("offshore", []))
    return frozenset(raw)


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


def build_fluid_set(data: dict) -> frozenset:
    """Return set of item keys whose type is 'fluid' in the dataset."""
    fluids: set[str] = set()
    for item in data.get("items", []):
        if item.get("type") == "fluid":
            key = item.get("key") or item.get("name", "")
            if key:
                fluids.add(key)
    return frozenset(fluids)


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


def pick_recipe(
    item_key: str,
    recipe_idx: dict,
    overrides: dict | None = None,
) -> dict | None:
    """
    Select canonical recipe for item_key.

    Priority:
      1. Explicit override from --recipe ITEM=RECIPE flag.
      2. Recipe whose key == item_key (exact match).
      3. advanced-oil-processing (legacy fallback for oil products).
      3.5. Entry in RECIPE_DEFAULTS (overrides order-sort for un-automatable defaults).
      4. First candidate after sorting by the game's ``order`` field.

    Sorting by ``order`` before the fallback selects the game-preferred recipe
    (e.g. solid-fuel-from-petroleum-gas over less-efficient variants).
    """
    candidates = recipe_idx.get(item_key, [])
    if not candidates:
        return None

    # 1. Explicit override
    if overrides and item_key in overrides:
        wanted = overrides[item_key]
        for r in candidates:
            if r["key"] == wanted:
                return r
        # Override key not found among candidates -- fall through to defaults

    # Sort by the game's display order so fallback picks the preferred variant
    candidates = sorted(candidates, key=lambda r: r.get("order", ""))

    # 2. Exact key match
    for r in candidates:
        if r["key"] == item_key:
            return r

    # 3. advanced-oil-processing legacy fallback
    for r in candidates:
        if r["key"] == "advanced-oil-processing":
            return r

    # 3.5. Hard-coded preferred recipe (avoids unautomatable order-sort defaults)
    if item_key in RECIPE_DEFAULTS:
        wanted = RECIPE_DEFAULTS[item_key]
        for r in candidates:
            if r["key"] == wanted:
                return r

    # 4. First after order-sort
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
        machine_quality: str = "normal",
        beacon_quality: str = "normal",
        recipe_overrides: dict | None = None,
        recipe_machine_overrides: dict | None = None,
        recipe_module_overrides: dict | None = None,
        recipe_beacon_overrides: dict | None = None,
    ):
        self.recipe_idx      = recipe_idx
        self.raw_set         = raw_set
        self.assembler_level = assembler_level
        self.furnace_type    = furnace_type
        self.module_configs:  dict = module_configs  or {}
        self.beacon_configs:  dict = beacon_configs  or {}
        self.machine_quality: str  = machine_quality
        self.beacon_quality:  str  = beacon_quality
        self.recipe_overrides:         dict = recipe_overrides         or {}
        self.recipe_machine_overrides: dict = recipe_machine_overrides or {}
        self.recipe_module_overrides:  dict = recipe_module_overrides  or {}
        self.recipe_beacon_overrides:  dict = recipe_beacon_overrides  or {}

        self.steps: dict[str, dict]             = {}
        self.raw_resources: dict[str, Fraction] = defaultdict(Fraction)
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
        slots = MACHINE_MODULE_SLOTS.get(machine_key, 0)
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

        # Defer oil products to the linear system
        if item_key in OIL_PRODUCTS:
            self.oil_demands[item_key] += rate
            return

        # Raw resource
        if item_key in self.raw_set:
            self.raw_resources[item_key] += rate
            return

        recipe = pick_recipe(item_key, self.recipe_idx, self.recipe_overrides)

        # No recipe → treat as raw
        if recipe is None:
            self.raw_resources[item_key] += rate
            return

        recipe_key = recipe["key"]

        # Cycle guard
        if recipe_key in _chain:
            self.raw_resources[item_key] += rate
            return

        new_chain = _chain | {recipe_key}

        # Output amount per craft cycle for the requested item
        result_amount = Fraction(1)
        for res in recipe.get("results", []):
            if res["name"] == item_key:
                result_amount = Fraction(str(res.get("amount", 1)))
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

        # Accumulate step (same recipe may arrive from multiple tree paths)
        if recipe_key in self.steps:
            self.steps[recipe_key]["rate_per_min"]  += rate
            self.steps[recipe_key]["machine_count"] += machines_needed
        else:
            self.steps[recipe_key] = {
                "recipe":             recipe_key,
                "machine":            machine_key,
                "machine_count":      machines_needed,
                "rate_per_min":       rate,
                "beacon_speed_bonus": beacon_speed_bonus,
            }

        # Credit co-products as surplus (productivity applies to them too)
        for res in recipe.get("results", []):
            co = res["name"]
            if co == item_key:
                continue
            co_amt = Fraction(str(res.get("amount", 1)))
            if prod_bonus > 0:
                co_amt = co_amt * (Fraction(1) + prod_bonus)
            self.surplus[co] += cycles_per_min * co_amt

        # Recurse into ingredients
        for ing in recipe.get("ingredients", []):
            ing_rate = cycles_per_min * Fraction(str(ing.get("amount", 1)))
            self.solve(ing["name"], ing_rate, new_chain)

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

            if rkey in self.steps:
                self.steps[rkey]["machine_count"] += machines
                self.steps[rkey]["rate_per_min"]  += disp_rate
            else:
                self.steps[rkey] = {
                    "recipe":             rkey,
                    "machine":            machine_key,
                    "machine_count":      machines,
                    "rate_per_min":       disp_rate,
                    "beacon_speed_bonus": 0.0,
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
) -> dict:
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
            result[item] = {
                "machine":            machine,
                "machine_count":      round(float(count), 4),
                "machine_count_ceil": math.ceil(count),
                "rate_per_min":       round(float(rate), 4),
            }
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
            machine   = drill_key
            rate_each = (MINER_SPEED[drill_key] / info["mining_time"]) * info["yield"] * 60
            count = rate / rate_each
            result[item] = {
                "machine":            machine,
                "machine_count":      round(float(count), 4),
                "machine_count_ceil": math.ceil(count),
                "rate_per_min":       round(float(rate), 4),
            }

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
    fluid_set: frozenset | None = None,
) -> dict:
    """
    Assemble the final JSON output dict from solver results and CLI args.

    Belt output is included only when args.belt is set and the item is solid.
    Pump output is included only when args.pump is set and the item is a fluid.
    """
    steps_list = sorted(
        [
            {
                "recipe":             s["recipe"],
                "machine":            s["machine"],
                "machine_count":      _f(s["machine_count"]),
                "machine_count_ceil": math.ceil(s["machine_count"]),
                "rate_per_min":       _f(s["rate_per_min"]),
                "beacon_speed_bonus": round(s["beacon_speed_bonus"], 6),
            }
            for s in solver.steps.values()
        ],
        key=lambda x: -x["rate_per_min"],
    )

    raw_sorted = {
        k: _f(v)
        for k, v in sorted(solver.raw_resources.items(), key=lambda x: -x[1])
    }

    miners = compute_miners(solver.raw_resources, resource_info, args.miner)

    out: dict = {
        "item":            args.item,
        "rate_per_min":    args.rate,
        "dataset":         args.dataset,
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

    out["production_steps"] = steps_list
    out["raw_resources"]    = raw_sorted
    out["miners_needed"]    = miners

    # Belt / pump output (solid vs fluid item distinction)
    is_fluid = fluid_set is not None and args.item in fluid_set
    belt = getattr(args, "belt", None)
    pump = getattr(args, "pump", None)

    if belt and not is_fluid:
        out["belt"]         = belt
        out["belts_needed"] = round(float(Fraction(str(args.rate)) / BELT_THROUGHPUT[belt]), 6)

    if pump and is_fluid:
        out["pump"]         = pump
        out["pumps_needed"] = round(args.rate / PUMP_THROUGHPUT[pump], 8)

    return out


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


def parse_args(prefs: dict | None = None) -> argparse.Namespace:
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
  python cli.py --item rocket-fuel --rate 5 --assembler 3 --dataset space-age
  python cli.py --item tungsten-carbide --rate 60 --dataset space-age --miner big
  python cli.py --item electronic-circuit --rate 60 --belt blue
  python cli.py --item lubricant --rate 60 --pump legendary
  python cli.py --item electronic-circuit --rate 60 \\
      --modules "assembling-machine-3=4:prod:3:normal" \\
      --beacon "assembling-machine-3=4:3:normal" \\
      --machine-quality legendary
""",
    )
    p.add_argument("--item",     required=True,
                   help="Item ID (e.g. electronic-circuit).")
    p.add_argument("--rate",     required=True, type=float,
                   help="Target production rate in items / minute.")
    p.add_argument("--assembler", default=3, type=int, choices=[1, 2, 3],
                   help="Assembling machine level (default: 3).")
    p.add_argument("--furnace",  default="electric",
                   choices=["stone", "steel", "electric"],
                   help="Furnace type (default: electric).")
    p.add_argument("--miner",    default="electric", choices=["electric", "big"],
                   help="Mining drill for solid ores (default: electric).")
    p.add_argument("--dataset",  default="vanilla", choices=["vanilla", "space-age"],
                   help="Game dataset (default: vanilla).")
    p.add_argument("--machine-quality", default="normal",
                   choices=list(QUALITY_NAMES), dest="machine_quality",
                   help="Quality tier of all machines (default: normal).")
    p.add_argument("--beacon-quality", default="normal",
                   choices=list(QUALITY_NAMES), dest="beacon_quality",
                   help="Quality tier of beacons (default: normal).")
    p.add_argument("--belt", default=None,
                   choices=list(BELT_THROUGHPUT.keys()),
                   help="Show belt output for this tier (e.g. blue).")
    p.add_argument("--pump", default=None,
                   choices=list(QUALITY_NAMES),
                   help="Show pump output for this quality (e.g. legendary).")
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
        "--recipe-belt",
        action="append", default=[],
        metavar="RECIPE=BELT",
        dest="recipe_belt",
        help="Per-recipe belt tier override (for display only). Repeatable.",
    )
    p.add_argument(
        "--recipe-pump",
        action="append", default=[],
        metavar="RECIPE=QUALITY",
        dest="recipe_pump",
        help="Per-recipe pump quality override (for display only). Repeatable.",
    )
    if prefs:
        p.set_defaults(**{
            k: v for k, v in prefs.items()
            if k in {"dataset", "assembler", "furnace", "miner",
                     "machine_quality", "beacon_quality", "belt", "pump"}
        })
    return p.parse_args()


def main() -> None:
    prefs = load_prefs()
    args  = parse_args(prefs)

    # Parse --recipe ITEM=RECIPE (prefs baseline; CLI flags win)
    recipe_overrides: dict[str, str] = dict(prefs.get("recipe_overrides", {}))
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

    recipe_belt_overrides: dict[str, str] = {}
    for raw in args.recipe_belt:
        k, v = _parse_kv(raw, "--recipe-belt")
        recipe_belt_overrides[k] = v

    recipe_pump_overrides: dict[str, str] = {}
    for raw in args.recipe_pump:
        k, v = _parse_kv(raw, "--recipe-pump")
        recipe_pump_overrides[k] = v

    data          = load_data(args.dataset)
    raw_set       = build_raw_set(data)
    recipe_idx    = build_recipe_index(data)
    resource_info = build_resource_info(data)
    fluid_set     = build_fluid_set(data)

    solver = Solver(
        recipe_idx, raw_set,
        args.assembler, args.furnace,
        module_configs=module_configs or None,
        beacon_configs=beacon_configs or None,
        machine_quality=args.machine_quality,
        beacon_quality=args.beacon_quality,
        recipe_overrides=recipe_overrides or None,
        recipe_machine_overrides=recipe_machine_overrides or None,
        recipe_module_overrides=recipe_module_overrides or None,
        recipe_beacon_overrides=recipe_beacon_overrides or None,
    )

    solver.solve(args.item, Fraction(str(args.rate)))
    solver.resolve_oil(data)

    # Attach parsed configs to args so format_output can echo them
    args.module_configs           = module_configs or None
    args.beacon_configs           = beacon_configs or None
    args.recipe_machine_overrides = recipe_machine_overrides or None
    args.recipe_module_overrides  = recipe_module_overrides  or None
    args.recipe_beacon_overrides  = recipe_beacon_overrides  or None
    args.recipe_belt_overrides    = recipe_belt_overrides    or None
    args.recipe_pump_overrides    = recipe_pump_overrides    or None

    print(json.dumps(format_output(
        args, solver, resource_info, fluid_set=fluid_set,
    ), indent=2))


if __name__ == "__main__":
    main()
