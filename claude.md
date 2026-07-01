# 10x Factorio Engineer — Claude Context

Kept up-to-date so Claude can understand the full project without needing conversation history.

---

## Project Overview

Two components that work together to act as a Factorio factory co-pilot:

**Component 1 — CLI Calculator** (`10x-factorio-engineer/assets/cli.py`)
Single-file zero-dependency Python CLI. Takes an item + target rate and emits
precise JSON covering machine counts, raw resource rates, miner counts, and belt
requirements. Based on KirkMcDonald's recipe data. Claude calls this for all
production math — it never does the recursive recipe tree in its head.

```
python 10x-factorio-engineer/assets/cli.py --item <item-id> --rate <N> [options]
```

**Component 2 — Claude Skill + Dashboard** (`10x-factorio-engineer/`)
A `SKILL.md` that tells Claude how to behave as a planning assistant: when and
how to call the CLI, how to track the player's factory conversationally, and how
to output a `FACTORY_STATE` for import into the dashboard. The dashboard is a
published `application/vnd.ant.html` artifact — a single vanilla HTML file with
no runtime dependencies. State is encoded as base64 and stored in `window.storage`
(Anthropic server-side, cross-device) with `localStorage` fallback. An in-artifact
chat panel is powered by `window.claude.complete()`. Strategy references
in `10x-factorio-engineer/references/` are loaded on demand per topic.

---

## Maintenance Rules

**These rules apply every time you edit any file in this repo.**

| Trigger | Required follow-up action |
|---------|--------------------------|
| `dev/dashboard.html` is modified | Run `python dev/build_dashboard.py` from the repo root to rebuild `10x-factorio-engineer/assets/dashboard.html`. Never edit the built artifact directly — it is overwritten on every build. To preview: run `python dev/preview.py` (defaults to sample state) **or** `python dev/preview.py --state dev/my-factory.json` to render the user's working factory; then use the Claude Preview MCP tool (server name `dashboard-preview`, config at `.claude/launch.json`) and reload the page after each preview.py rerun — **never** open the file in a browser via `--open` or `subprocess`. If the change is visually observable (new section, restyled chip, new render path), also re-run `python dev/screenshot_tests.py` so the regenerated PNGs in `dev/screenshots/` match the new dashboard. **`screenshot_tests.py` renders the shipped artifact (`assets/dashboard.html`), not the source — so always run `build_dashboard.py` first; the script errors out if the artifact is missing or older than the source.** A clean rebuild that changes zero PNGs confirms minification is faithful (a render bug would show up as a diff). When the new feature requires fixture data the existing scenarios don't cover (e.g. a new `cli_args` field), add or extend the synthetic state factories in `screenshot_tests.py` so at least one screenshot exercises it. |
| `10x-factorio-engineer/assets/cli.py` output shape changes (new fields, renamed keys) | Update the JSON output example and field table in `10x-factorio-engineer/SKILL.md` §2. The JSON example must include every field that appears in real CLI output — run the CLI and copy actual values rather than inventing them. Then check whether the factory-state schema (SKILL.md §3) needs updating — if yes, follow the factory-state rule below. Verify by grepping SKILL.md for each new field name and confirming it appears in both the example block and the field table. |
| `cli.py` (`10x-factorio-engineer/assets/cli.py`) flag added, removed, or changed | This is the general-purpose calculator — NOT the quality planner. 1. Update the module-level docstring at the top of `cli.py` (Usage block). 2. Update the flags table in `10x-factorio-engineer/SKILL.md` §2. If it affects factory-state tracking, also update `10x-factorio-engineer/SKILL.md` §3 schema and follow the factory-state rule below. |
| `10x-factorio-engineer/assets/cli.py` output shape changes (new fields, renamed keys) OR `--format human` output layout changes | Update the sample `--format human` output block in `README.md`. Run the CLI with `--format human` and copy actual output rather than editing manually. |
| Factory state schema changes (SKILL.md §3 fields added/removed/renamed) | 1. Update `10x-factorio-engineer/SKILL.md` §3. 2. Update `dev/dashboard.html` to reflect the new schema. 3. Update `dev/sample/state.json` to match the new schema. 4. Run `python dev/build_dashboard.py` to rebuild the artifact. |
| New `cli.py` flag or solver behaviour added | Add tests to `dev/test_cli.py` covering the new feature. Run `python -m unittest dev.test_cli -v` and fix any failures before finishing. Update the test count in `README.md` and in the Tests section of `CLAUDE.md`. |
| `dev/quality_planner.py` flag added, removed, or changed | **This is the SEPARATE quality/legendary planner — NOT `cli.py`.** Do NOT touch `cli.py`'s docstring, SKILL.md §2, or `README.md` for these changes. 1. Update the module-level docstring Usage block at the top of `dev/quality_planner.py`. 2. Update the CLI surface table in `dev/quality_planner.md` (the living spec / source of truth for this tool). 3. Update the invocation block in `10x-factorio-engineer/SKILL.md` §11. Verify by grepping all three for the flag name. |
| New `dev/quality_planner.py` flag or solver behaviour added | Add tests to `dev/test_quality_planner.py` (NOT `dev/test_cli.py`). Run `python -m unittest dev.test_quality_planner -v` and fix any failures before finishing. Update the test count in `dev/quality_planner.md` (Status + Tests sections) and in the `dev/test_quality_planner.py` row of the Tests section of `CLAUDE.md`. |
| Any `.py` file is created or edited | Run `get_errors` on the file afterwards and fix all Pylance errors before finishing. Prefer `assert x is not None` over `assertIsNotNone(x)` when the result is used afterward — Pylance uses the former as a type-narrowing guard but not the latter. |
| Before making a commit | Review `README.md` and update it to reflect any changes made (test counts, new features, changed behaviour, etc.). |
| Before spawning a subagent to implement CLI or dashboard changes | Include in the subagent prompt: (1) an instruction to read and follow all maintenance rules in `CLAUDE.md` before finishing, and (2) an explicit end-of-task checklist derived from those rules — e.g. "grep SKILL.md for every new JSON field added to cli.py output and confirm each appears in both the example block and the field table in §2". Subagents do not automatically load `CLAUDE.md`. |
| Every 30 days | Run the wiki maintenance workflow (see below) to update the split reference files in `10x-factorio-engineer/references/`. The MediaWiki RecentChanges API only goes back 30 days — running less frequently means changes fall out of the window undetected. |

The goal is that `claude.md` always accurately describes the codebase.

---

## Strategy Reference Maintenance (Every 30 Days)

The split reference files in `10x-factorio-engineer/references/` embed facts crawled from the
Factorio wiki, and `dev/wiki/` holds the full per-page corpus (417 pages, gitignored).
The wiki is actively updated — run this workflow monthly to pick up changes.

### Workflow

**Step 1 — Fetch recently changed pages via MediaWiki API:**
```
https://wiki.factorio.com/api.php?action=query&list=recentchanges&rcnamespace=0&rclimit=500&rcdays=30&rctype=edit|new&format=json
```
This returns all English main-namespace pages edited in the last 30 days. Filter out
translations (`/zh`, `/ru`, `/de`, etc.) and non-article pages (`Special:`, `File:`, etc.).

**Step 2 — Cross-reference against our crawled page list:**
Our 417-page list is in `dev/wiki/urls.json`. Check which recently-changed wiki pages
appear in that list — those are the ones to re-crawl.

Also check which split reference files embed facts from those changed pages — if any of those changed,
update the embedded summaries too (Step 4).

**Step 3 — Re-crawl changed pages using `dev/wiki/crawl.py`:**
```bash
python dev/wiki/crawl.py update [--days 30] [--dry-run]
```
This automates Steps 1–3: queries RecentChanges, cross-references against
`dev/wiki/urls.json`, deletes stale files, and re-crawls via Cloudflare.
Credentials come from env vars `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`.

> **Note:** Do NOT use Cloudflare's `modifiedSince` parameter for this — tested and confirmed
> that the Factorio wiki does not serve `Last-Modified` headers that Cloudflare can use.
> All pages are returned as "completed" regardless of whether they changed. Use the
> MediaWiki RecentChanges API (Step 1) to determine what actually changed.

**Step 4 — Update the relevant split reference file(s) for changed embedded pages:**
Compare newly crawled content against what's embedded in the split reference files in `10x-factorio-engineer/references/`.
Update any facts that changed. Focus on **mechanics, strategic constraints, and planning guidance** — not raw stats or recipe ingredients (the CLI provides those on demand). Prioritise: spoilage timers, planet-specific constraints, combat mechanics, circuit patterns, and infrastructure ratios (solar/nuclear/fusion) that the CLI doesn't model.

**Step 5 — Also check for new high-value pages:**
Filter the full RecentChanges list for pages not yet in `dev/wiki/urls.json` but relevant
to players (new buildings, mechanics, Space Age content). Add them to `dev/wiki/urls.json`
and run `python dev/wiki/crawl.py crawl` to fetch them.

### Notes
- The 30-day window is a hard limit of the MediaWiki API — do not skip months
- `render: false` crawls won't follow links between unrelated pages — crawl each target URL directly
- `dev/wiki/findings.md` tracks crawl history (gitignored, local only)
- Cloudflare free tier (Quick Actions `/markdown` endpoint): 1 request/10 s, no daily cap — use `--workers 1`
- `dev/wiki/pages/` is gitignored — regenerate with `python dev/wiki/crawl.py crawl` (~70 min at 1 req/10 s)

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `10x-factorio-engineer/assets/cli.py` | Calculator — entire implementation, stdlib only |
| `10x-factorio-engineer/assets/vanilla-2.0.55.json` | KirkMcDonald dataset — base game |
| `10x-factorio-engineer/assets/space-age-2.0.55.json` | KirkMcDonald dataset — Space Age DLC |
| `10x-factorio-engineer/SKILL.md` | Skill definition — Claude gameplay assistant behaviour |
| `10x-factorio-engineer/references/` | Split strategy reference files (11 topic files): early-game, factory-layouts, trains, megabase, planets, space-platforms, power, combat-defense, logistics-circuits, quality, resources |
| `dev/dashboard.html` | Dashboard source — single vanilla HTML file, no build dependencies |
| `dev/build_dashboard.py` | Build script — minifies `dev/dashboard.html` → `10x-factorio-engineer/assets/dashboard.html` via the `minify-html` library (dev-time dependency: `pip install minify-html`) |
| `dev/preview.py` | Generates `dev/preview.tmp.html` with factory state pre-loaded; defaults to `dev/sample/state.json`; use `--state PATH` for a custom JSON file; use `--no-min` for the unminified source dashboard |
| `10x-factorio-engineer/assets/dashboard.html` | Built artifact — run `python dev/build_dashboard.py` to regenerate; paste into claude.ai as `application/vnd.ant.html` and publish |
| `dev/sample/state.json` | Source JSON for the sample factory state — edit this directly; paste into the dashboard Import dialog to test |
| `dev/my-factory.json` | The user's actual working factory state — primary fixture for previewing real-world layouts. **Gitignored** (personal data). Use `python dev/preview.py --state dev/my-factory.json` to render it. When the user says "my factory" they mean this file. |
| `dev/update_research.py` | Applies a research-level change to a factory state and re-runs only the affected lines (`python dev/update_research.py TECH=LEVEL ... [--state PATH] [--dry-run] [--list]`; default state = `dev/my-factory.json`). Use this instead of hand-editing `research_levels` + manually re-running lines — it reconstructs each line's CLI command from its `cli_args` + shared top-level config, re-solves the affected lines, and rewrites their `cli_result` (LF output). Mining-prod re-runs miner lines; recipe-prod re-runs lines whose steps touch a boosted recipe; lab-only techs (`research-productivity` / `lab-research-speed`) update the field but trigger no re-run. See the **research-level updates** workflow note below. |
| `dev/test_cli.py` | `unittest` suite (278 tests, stdlib only) — dev only |
| `dev/quality_planner.py` | Legendary production planner V1 (MVP) — separate stdlib-only tool; DP quality loop solver for asteroid-reprocessing chains. `--location fulgora` switches to scrap-only sourcing (no asteroid platform; metals terminate at scrap-reachable plates via `forbid_ore_routes`) |
| `dev/test_quality_planner.py` | `unittest` suite (340 tests) for quality_planner |
| `dev/quality_planner.md` | Living spec — current capabilities, architecture, gotchas, and roadmap (consolidates the former v1 / v2 specs) |
| `dev/wiki/crawl.py` | Two subcommands: `crawl` (full crawl, resume-safe) and `update` (monthly maintenance via RecentChanges API); 30 workers, 9 req/sec rate limiter |
| `dev/wiki/urls.json` | Curated list of 417 English gameplay wiki page titles to crawl |
| `dev/wiki/` | Per-page wiki corpus (417 `.md` files); **gitignored** — regenerate with `python dev/wiki/crawl.py crawl` (~15 min) |
| `dev/artifact-api/test.html` | claude.ai runtime API test suite — paste as `application/vnd.ant.html` to verify `window.claude` / `window.storage` / localStorage after platform updates |
| `dev/artifact-api/research.md` | Field research doc for the claude.ai artifact runtime API; compare against test suite output to diagnose breakage |

Dataset files are vendored. Auto-downloaded from KirkMcDonald's GitHub if missing.

### Research-level updates (workflow)

When the user reports finishing a research ("I just hit mining productivity 14",
"scrap recycling productivity 1"), prefer `dev/update_research.py` over editing
`research_levels` and re-running lines by hand:

```bash
python dev/update_research.py mining-productivity=14 scrap-recycling-productivity=1
python dev/update_research.py --list            # current levels + affected lines per tech
python dev/update_research.py steel-productivity=6 --dry-run   # preview, don't write
```

It updates the top-level `research_levels` and re-solves only the affected lines
(mining-prod → miner lines; recipe-prod → lines whose steps touch a boosted
recipe; lab-only techs update the field with no re-run), reconstructing each
line's command from its `cli_args` + shared top-level config and rewriting
`cli_result`. Re-running with an unchanged set reproduces existing results
(faithfulness self-check). This is the script form of the manual workflow in
`10x-factorio-engineer/SKILL.md` §3 ("I just finished mining productivity 5"). After it
writes, regenerate the preview (`python dev/preview.py --state dev/my-factory.json`)
if the user is viewing the dashboard.

---

## Architecture

CLI flags and JSON output shape: see `10x-factorio-engineer/SKILL.md` §2.

### Key functions

| Function | Role |
|----------|------|
| `load_data(location)` | Load JSON; `location=None` → vanilla, location string → space-age; auto-download if missing |
| `build_raw_set(data, location)` | Raw input items (mined/pumped); `location=None` → all planets, location string → specific planet only. Resolves resource entity keys → result item names (e.g. `sulfuric-acid-geyser` → `sulfuric-acid`), maps plant entity names via `PLANT_HARVESTS` (e.g. `yumako-tree` → `yumako`), and adds `PLANET_EXTRA_RAWS` (e.g. `spoilage` on Gleba) |
| `get_planet_props(data, location)` | Return `surface_properties` dict for the given planet, or `{}` if not found/None |
| `_recipe_valid_for_planet(recipe, planet_props)` | Return True if all recipe surface_conditions are satisfied |
| `build_recipe_index(data)` | `{item_key: [recipe, ...]}`, skips recycling + barrel subgroups |
| `build_resource_info(data)` | `{item: {mining_time, yield, category}}` using `Fraction` |
| `build_machine_power_w(data)` | `{machine_key: watts}` for electric machines only (burners excluded); scans `crafting_machines`, `agricultural_tower`, `rocket_silo`, `mining_drills` |
| `build_machine_prod_bonus(data)` | `{machine_key: Fraction}` built-in productivity from the dataset's `prod_bonus` (foundry/EM-plant/biochamber = 1/2, else 0). Applied in `_compute_module_effects` to **every** recipe regardless of `allow_productivity` (that flag only gates modules/beacons) |
| `_beacon_sharing_factor(machine_key)` | Returns how many machines share each physical beacon (4 for ≤4-tile machines, 2 for 5–7-tile, 1 for ≥8-tile) |
| `Solver._beacon_quality_penalty(beacon_spec)` | Quality-chance penalty from SPEED modules in the beacon, scaled by the same transmission as `_compute_beacon_speed` (`effectivity × sqrt(count)`). Subtracted from `quality_chance_from_specs` at each step ("haste makes waste" applies through beacons too). Rounded `Fraction`; 0 when no speed modules |
| `_compute_step_power(...)` | Returns `(power_kw, power_kw_ceil, beacon_power_kw)` for a production step using module/beacon config |
| `compute_location_unlocks(location)` | Return the `frozenset` of planet-locked advanced machines unlocked at `location` (e.g. Vulcanus → `{foundry}`). `None` for `location=None` (legacy "all unlocked"). |
| `get_machine(cat, assembler_level, furnace_type, location_unlocks=None)` | Maps recipe category → `(machine_key, speed)`. When `location_unlocks` is given, planet-locked machines that aren't in the set are routed to the basic alternative via `CATEGORY_LOCATION_FALLBACK`. |
| `pick_recipe(item_key, recipe_idx, overrides, planet_props)` | Picks canonical recipe; filters by planet surface_conditions when planet_props given (see selection logic below) |
| `_gauss2 / _gauss3` | Exact `Fraction` Gaussian elimination (2×2 and 3×3) |
| `solve_oil_system(...)` | Joint linear solve for refinery recipe (AOP / CL / simple-CL) + cracking |
| `Solver.solve(item_key, rate)` | Recursive tree walk; defers oil products |
| `Solver.resolve_oil(data)` | Injects oil linear-system results into steps/raw_resources |
| `compute_miners(...)` | Per-resource miner/pump counts |
| `format_output(...)` | Assembles final JSON dict |
| `_lp_minimize(c, A_ge, b_ge)` | Exact-rational two-phase simplex (Bland's rule); `min cᵀx s.t. Ax ≥ b, x ≥ 0`; returns `(status, x)` with status `optimal`/`infeasible`/`unbounded`. Used by the Fulgora LP |
| `build_recycling_index(data)` | `{output_item: [recycling_recipe, ...]}` — recycling recipes only (excluded from `build_recipe_index`); read only by the Fulgora LP |
| `solve_fulgora(solver, data, targets)` | Fulgora recycling-graph LP entry point; builds the activity set, solves, populates `solver.steps`/`raw_resources`/`surplus`; see "Fulgora Recycling LP" below |
| `_fulgora_activity_coeffs(solver, recipe)` | Per-craft LP coefficients (machine, machine_coef, io with module/quality/prod effects) for one activity. Under `--quality-pickout`, scales each activity's outputs by the normal-tier fraction and returns `q_chance`/`pickout`/`gross_outputs` for post-solve quality accounting |
| `quality_chance_from_specs(specs, slots)` | Net per-craft quality-upgrade chance from `specs` (slot-scaled like `_compute_module_effects`, clamped 0..1). Quality modules ADD chance; speed modules SUBTRACT it (`SPEED_MODULE_QUALITY_PENALTY`, "haste makes waste" — a tier-T speed module cancels a tier-T quality module at equal housing quality); both scale with module quality |
| `quality_tier_probs(q_total, max_index)` | Length-5 per-tier probability vector for a normal-tier craft; mass above `max_index` (highest unlocked tier) folds onto it |

### `Solver` class state

- `steps`: `{recipe_key: {recipe, machine, machine_count, rate_per_min, beacon_speed_bonus}}` — accumulated across all tree paths; `machine_count` is `float` when beacons active, `Fraction` otherwise
- `raw_resources`: `{item: Fraction}` — total demanded rate for true raws (ores, crude-oil, water); excludes bus items
- `bus_inputs`: `{item: Fraction}` — demanded rate for items sourced from the bus (`--bus-item`); separate from `raw_resources`
- `surplus`: `{item: Fraction}` — co-product credits not yet consumed
- `oil_demands`: `{item: Fraction}` — deferred petroleum-gas/light-oil/heavy-oil demands
- `module_configs`: `{machine_key: [ModuleSpec]}` — global module config per machine (`--modules`)
- `beacon_configs`: `{machine_key: BeaconSpec}` — global beacon config per machine (`--beacon`)
- `recipe_machine_overrides`: `{recipe_key: machine_key}` — per-recipe machine override (`--recipe-machine`)
- `recipe_module_overrides`: `{recipe_key: [ModuleSpec]}` — per-recipe module override (`--recipe-modules`)
- `recipe_beacon_overrides`: `{recipe_key: BeaconSpec}` — per-recipe beacon override (`--recipe-beacon`)
- `bus_items`: `frozenset[str]` — item IDs treated as bus inputs; stops recursion (`--bus-item`)
- `planet_props`: `dict` — surface_properties for the target location; empty dict means no planet filtering
- `location`: `str | None` — location string (for error messages); `None` for vanilla
- `machine_quality`: `str` — quality tier applied to all machines (speed bonus via `MACHINE_QUALITY_SPEED`)
- `beacon_quality`: `str` — quality tier of beacon housings (effectivity via `BEACON_EFFECTIVITY`)
- `max_quality`: `str` / `max_quality_index`: `int` — highest UNLOCKED quality tier (`--max-quality`, default `legendary`); cascade mass above it folds onto it
- `quality_pickout`: `bool` — when set, any step with quality modules has its >normal output siphoned off; the step is scaled up so the normal-tier yield meets demand (`effective_result_normal = effective_result × (1 − q_chance)`), extracted items accumulate in `quality_yield` (`--quality-pickout`)
- `quality_yield`: `{item: {tier_name: Fraction}}` — higher-quality items extracted by pickout, aggregated across steps; surfaced as top-level `quality_yield`. Each step also caches `_quality_chance`/`_pickout` so `format_output` can render the per-step `quality_output` split

**`ModuleSpec`** (named tuple or dict): `{count: int, type: str, tier: int, quality: str}`
**`BeaconSpec`** (named tuple or dict): `{count: int, tier: int, quality: str}`

---

## Arithmetic

All numeric values use `fractions.Fraction` internally. Only converted to `float` in `format_output()`. This eliminates floating-point accumulation errors.

**Exception:** beacon speed bonus uses `math.sqrt(count)` which is irrational, so `machine_count` becomes `float` for any recipe whose machine has a beacon config. Runs with no beacons remain fully `Fraction`.

### New constant tables

```python
# Quality enum (valid values for all quality flags)
QUALITY_NAMES = frozenset(["normal", "uncommon", "rare", "epic", "legendary"])

# Ordered tiers (index == tier number) for the quality-output cascade.
QUALITY_TIERS = ("normal", "uncommon", "rare", "epic", "legendary")
QUALITY_INDEX = {q: i for i, q in enumerate(QUALITY_TIERS)}

# Base per-slot quality CHANCE at normal module quality (T1 +1%, T2 +2%,
# T3 +2.5%); scaled by MODULE_QUALITY_MULT like every other positive stat.
QUALITY_MODULE_BONUS: dict[int, Fraction] = {
    1: Fraction(1, 100), 2: Fraction(3, 200), 3: Fraction(1, 40),
}

# Quality PENALTY per speed-module slot (Space Age "haste makes waste"): same
# magnitude as the quality bonus of the same tier, so a tier-T speed module
# cancels a tier-T quality module at equal housing quality. Quality-scaled like
# the bonus. Subtracted in quality_chance_from_specs.
SPEED_MODULE_QUALITY_PENALTY: dict[int, Fraction] = {
    1: Fraction(1, 100), 2: Fraction(3, 200), 3: Fraction(1, 40),
}

# When a quality roll succeeds: +1..+4 tiers split 90/9/0.9/0.1. Mass above the
# highest UNLOCKED tier (--max-quality) folds back onto it.
QUALITY_TIER_SKIP_DIST = (Fraction(9,10), Fraction(9,100), Fraction(9,1000), Fraction(1,1000))

# Multiplier applied to positive module stats at each quality tier
MODULE_QUALITY_MULT: dict[str, Fraction] = {
    "normal":    Fraction(1),
    "uncommon":  Fraction(13, 10),   # ×1.3
    "rare":      Fraction(8,  5),    # ×1.6
    "epic":      Fraction(19, 10),   # ×1.9
    "legendary": Fraction(5,  2),    # ×2.5
}

# Additive crafting-speed bonus from machine quality
MACHINE_QUALITY_SPEED: dict[str, Fraction] = {
    "normal":    Fraction(0),
    "uncommon":  Fraction(3, 10),    # +30%
    "rare":      Fraction(3, 5),     # +60%
    "epic":      Fraction(9, 10),    # +90%
    "legendary": Fraction(3, 2),     # +150%
}

# Beacon distribution effectivity by beacon housing quality
# Range 1.5–2.5; verified against FactorioLab
BEACON_EFFECTIVITY: dict[str, Fraction] = {
    "normal":    Fraction(3,  2),    # 1.5
    "uncommon":  Fraction(17, 10),   # 1.7
    "rare":      Fraction(19, 10),   # 1.9
    "epic":      Fraction(21, 10),   # 2.1
    "legendary": Fraction(5,  2),    # 2.5
}

# Base speed bonus per speed-module tier at normal quality
SPEED_MODULE_BONUS: dict[int, Fraction] = {
    1: Fraction(1, 5),    # +20%
    2: Fraction(3, 10),   # +30%
    3: Fraction(1, 2),    # +50%
}

# Speed PENALTY per prod-module tier (NOT quality-scaled; flat per slot)
PROD_MODULE_SPEED_PENALTY: dict[int, Fraction] = {
    1: Fraction(-1, 20),   # −5%
    2: Fraction(-1, 10),   # −10%
    3: Fraction(-3, 20),   # −15%
}

# Base productivity bonus per prod-module tier at normal quality (same as MODULE_PROD_BONUS)
# combined with MODULE_QUALITY_MULT for effective bonus

BEACON_SLOTS = 2   # standard beacon has 2 module slots; supply range = 3 tiles (quality-invariant)

# Pump throughput by pump quality (fluid/min per pump)
PUMP_THROUGHPUT: dict[str, int] = {
    "normal":    72_000,
    "uncommon":  93_600,
    "rare":      115_200,
    "epic":      136_800,
    "legendary": 180_000,
}
```

### Beacon speed formula

```
beacon_speed(recipe) =
    BEACON_EFFECTIVITY[beacon_quality]
    × sqrt(count)
    × BEACON_SLOTS
    × SPEED_MODULE_BONUS[tier] × MODULE_QUALITY_MULT[module_quality]
```

Speed modules in a beacon also transmit a QUALITY penalty (same `effectivity ×
sqrt(count)` scaling), so the net per-step quality chance is
`quality_chance_from_specs(machine_specs) − _beacon_quality_penalty(beacon)`,
clamped at 0. Enough speed beacons drive quality output to 0.

Effective machine speed:
```
effective_speed = base_speed
                × (1 + MACHINE_QUALITY_SPEED[machine_quality])
                × (1 + beacon_speed(recipe))
```

Effective prod bonus (from machine modules):
```
prod_bonus = sum(
    count_i × MODULE_PROD_BONUS[tier_i] × MODULE_QUALITY_MULT[quality_i]
    for each prod module spec in this recipe's module config
)
```

Recipe module config lookup order (first match wins):
1. `recipe_module_overrides[recipe_key]` — per-recipe override (`--recipe-modules`)
2. `module_configs[machine_key]` — global per-machine default (`--modules`)
3. No modules (zero bonus)

Same lookup order applies to beacon config (`recipe_beacon_overrides` → `beacon_configs` → no beacons).

---

## Planet Machine Unlocks

Each `--location` defines which planet-locked advanced machines (foundry,
biochamber, electromagnetic-plant, cryogenic-plant) are available. Without
`--location`, all are considered unlocked (legacy behaviour).

### `PLANET_MACHINE_UNLOCKS`

| Location | Unlocked advanced machines |
|----------|----------------------------|
| `nauvis` | (none) |
| `vulcanus` | `foundry` |
| `gleba` | `biochamber` |
| `fulgora` | `electromagnetic-plant` |
| `aquilo` | all four (final-tier planet) |
| `space-platform` | (none — conservative default; everything must be shipped) |

### `CATEGORY_LOCATION_FALLBACK`

When the primary machine for a recipe category is locked at the current
location, `get_machine` routes to the basic alternative:

| Category | Premium machine | Nauvis fallback |
|----------|-----------------|-----------------|
| `chemistry-or-cryogenics` | cryogenic-plant | chemical-plant |
| `organic-or-chemistry` | biochamber | chemical-plant |
| `organic-or-assembling`, `organic-or-hand-crafting` | biochamber | assembler-N |
| `electronics`, `electronics-or-assembling`, `electronics-with-fluid` | EM-plant | assembler-N |
| `metallurgy-or-assembling`, `crafting-with-fluid-or-metallurgy` | foundry | assembler-N |
| `cryogenics-or-assembling` | cryogenic-plant | assembler-N |
| `pressing` | foundry | assembler-N |

### `HARD_CATEGORY_REQUIRES`

Categories with no fallback — recipes are filtered out by `pick_recipe` if the
required machine isn't unlocked:

| Category | Required machine |
|----------|------------------|
| `organic` | biochamber |
| `metallurgy` | foundry |
| `electromagnetics` | electromagnetic-plant |
| `cryogenics` | cryogenic-plant |

Explicit `--recipe` and `--recipe-machine` overrides bypass both filters (user opt-in).

---

## Recipe Selection Logic (`pick_recipe`)

Priority (in `pick_recipe`):
1. Explicit `--recipe ITEM=RECIPE` override passed in from CLI — bypasses planet filtering entirely.
2. Planet filtering: when `planet_props` given, remove candidates whose `surface_conditions` are not satisfied. If all candidates are filtered out, return `None`.
2.5. Machine-unlock filtering: when `location_unlocks` given, drop candidates whose hard category (`organic`, `metallurgy`, `electromagnetics`, `cryogenics`) requires a planet-locked machine not in the set. "X-or-Y" categories are not filtered here — `get_machine` routes them to the basic alternative.
3. Recipe whose `key == item_key` (exact match).
4. `advanced-oil-processing` (legacy fallback for oil products).
4.5. Entry in `RECIPE_DEFAULTS_BY_LOCATION[location]` — location-specific preferred recipe (wins over exact-key-match heuristic and order-sort).
5. Entry in `RECIPE_DEFAULTS` (hard-coded preferred recipes that override the order-sort default when the order-sort winner is un-automatable or causes circular dependencies in the solver).
6. First candidate after sorting all candidates by the game's `order` field.

Step 5's sort ensures the game-preferred variant is chosen when no exact match exists (e.g. `solid-fuel-from-petroleum-gas` over the less-efficient heavy-oil and petroleum-gas variants).

### `RECIPE_DEFAULTS_BY_LOCATION`

A module-level dict mapping `location → {item_key → recipe_key}` for items where the order-sort default is wrong for a specific planet:

| Location | Item | Default recipe | Reason |
|----------|------|---------------|--------|
| `space-platform` | `carbon` | `carbonic-asteroid-crushing` | Coal+sulfuric-acid route is unavailable on platforms; carbonic asteroid chunks are a platform raw resource |
| `vulcanus` | `molten-copper` | `molten-copper-from-lava` | Order-sort picks ore-based recipe; lava is Vulcanus's primary smelting resource |
| `vulcanus` | `molten-iron` | `molten-iron-from-lava` | Same — lava is always preferred over importing iron ore on Vulcanus |
| `vulcanus` | `water` | `steam-condensation` | RECIPE_DEFAULTS sends water to ice-melting but Vulcanus has no ice; steam comes from acid-neutralisation (Vulcanus-only, pressure=4000) |
| `gleba` | `plastic-bar` | `bioplastic` | Exact-key-match picks petroleum route which crashes (no crude oil on Gleba); bioplastic is the correct bio-substitute |
| `gleba` | `sulfur` | `biosulfur` | Same — petroleum sulfur route crashes on Gleba |
| `gleba` | `lubricant` | `biolubricant` | Same — heavy-oil lubricant route crashes on Gleba |
| `aquilo` | `ice` | `ammoniacal-solution-separation` | RECIPE_DEFAULTS sends ice to oxide-asteroid-crushing; on Aquilo ammoniacal-solution is a raw offshore resource and is the correct source |

### `RECIPE_DEFAULTS`

A module-level dict that maps `item_key → recipe_key` for items where the order-sort default is wrong:

| Item | Default recipe | Reason |
|------|---------------|--------|
| `nutrients` | `nutrients-from-yumako-mash` | `nutrients-from-fish` sorts first but is un-automatable (raw-fish not minable) and causes a circular dependency via `fish-breeding → nutrients` |
| `water` | `ice-melting` | `steam-condensation` sorts first (order `b < c`) but steam is never a raw resource — ice-melting is the correct automatable default |
| `ice` | `oxide-asteroid-crushing` | `ammoniacal-solution-separation` sorts first but ammoniacal-solution is only raw on Aquilo; asteroid crushing is the correct default elsewhere |

### Why this matters

- **Vanilla**: `solid-fuel` has 3 recipes. Sorting by `order` picks `solid-fuel-from-petroleum-gas` (order `b[fluid-chemistry]-c[...]`), which is the game's canonical display order. Use `--recipe solid-fuel=solid-fuel-from-light-oil` to override.
- **Space Age**: 37 items have multiple recipes. Common cases: casting upgrades in foundry for plates/cable/gears/pipe, alternative processes for `rocket-fuel`, `nutrients`, etc.

---

## Fulgora Recycling LP

Fulgora has no ore mining — its only raw is `scrap`, and `scrap-recycling` is a
single 1→12 probabilistic recipe (gears 20%, … holmium-ore 1%, stone 4%). Base
materials come from recycling those outputs further down (e.g.
`iron-gear-wheel → recycle → iron-plate → smelt → steel-plate`). This fixed-ratio
multi-output cascade can't be expressed by the recursive tree walk, so
`--location fulgora` routes `main()` to **`solve_fulgora`**, which models it as a
linear program. The recursive solver and all other locations are untouched.

**Trigger**: `fulgora_mode = args.location == "fulgora"` in `main()` skips the
recursive solve / oil resolve / `--step-machines` floor and calls
`solve_fulgora(solver, data, targets)`. `--step-machines` errors out (the LP
sizes all machines jointly); `--use-ceil` and Phase B/C are skipped.

**Activity set** (`solve_fulgora`):
1. **`recycle_reachable`** — items obtainable through *pure recycling* cascades
   from `{scrap, heavy-oil}`. Recycling activities are gated on "ingredient ∈
   recycle_reachable" so the LP can only shred natural scrap-byproducts, never
   craft-a-building-to-shred-it (which would explode the activity set — iron-plate
   alone has 40+ recycling producers). Fixed `FULGORA_WRAP_ROUTES` wrap items
   (steel-chest, hazard-concrete) are whitelisted into this set so their fast
   `<wrap>-recycling` recipes become LP candidates.
2. **Forward-availability closure** — crafting recipes (all Fulgora-valid
   non-recycling recipes, planet + machine-unlock filtered; NOT collapsed to one
   canonical per item, so oil cracking → plastic etc. are reachable) added when
   all inputs are available; recycling recipes added when input ∈ recycle_reachable.
3. **Backward reachability** from targets trims to activities that produce a
   needed item, keeping the LP small (~40 vars for a science chain).

**LP**: variables `x_r` = crafts/min per activity; one `≥` row per consumed/target
item (`Σ (out−in)·x ≥ demand`, demand = target rate else 0, raws are free inputs);
objective = minimise total machines (`Σ machine_coef_r · x_r`,
`machine_coef = energy/(60·eff_speed)`). Solved by `_lp_minimize` (exact-rational
simplex). Per-activity coefficients come from `_fulgora_activity_coeffs`, which
reuses the solver's module/quality/prod/beacon math (recycling recipes run on the
`recycler`, speed 1/2, 4 slots; beacons fold in as a rounded Fraction).

**Output**: steps populate `solver.steps` in the same shape the recursive solver
emits (so `format_output` is reused); `scrap` (+ `heavy-oil`) → `raw_resources`;
net overflow → `solver.surplus` → **`co_products`** (the uranium-238 field).
Infeasible demand → `SystemExit` suggesting `--bus-item`. The human format gains a
"Co-Products (surplus)" section.

**Step ordering**: because the recycling graph is a multi-output DAG with one
dominant source, `format_output` orders Fulgora `production_steps` as a strict
sources-last bill of materials (target first; `scrap-recycling` last; every step
below ALL of its consumers) via a longest-path level sort gated on
`args.location == "fulgora"`. Every other location keeps the recursive tree's
DFS pre-order.

**Quality pick-out on Fulgora**: `--quality-pickout` works in the LP too.
`_fulgora_activity_coeffs` scales each activity's output coefficients by the
normal-tier fraction `(1 − q_chance)` (so the LP runs more crafts to meet demand)
and returns `q_chance`/`pickout`/`gross_outputs`. After the solve, every output of
a pick-out activity contributes `x_r · gross · tier_probs[s>0]` to `quality_yield`
(recycling activities are multi-output, so co-products roll quality too). The step
caches `_quality_chance`/`_pickout` so the shared `format_output` renders its
per-step `quality_output` split, identical to the recursive path.

---

## Quality-Module Output (`--max-quality`, `--quality-pickout`)

`cli.py` models the quality tier of crafted output. Quality modules give a
per-craft upgrade chance `q_chance` (`quality_chance_from_specs`: T1 +1% / T2 +2%
/ T3 +2.5% per slot, ×`MODULE_QUALITY_MULT`, slot-scaled, clamped). Speed modules
SUBTRACT quality at the same per-tier magnitude (`SPEED_MODULE_QUALITY_PENALTY`,
"haste makes waste") — both in the same machine AND transmitted from a beacon
(`Solver._beacon_quality_penalty`, scaled by `effectivity × sqrt(count)`), so
speed + quality cancel tier-for-tier and enough speed beacons drive quality to 0.
A normal-tier
craft lands at tier `s` with probability `quality_tier_probs(q, max_index)` — the
90/9/0.9/0.1 cascade with mass above `--max-quality` (highest UNLOCKED tier) folded
onto the cap.

- **Reporting (default).** Whenever a step carries quality modules, `format_output`
  attaches a per-step `quality_output = {primary_item: {tier: rate}}` — the tier
  composition of the flowing output. Nominal flow is unchanged (the higher-quality
  items are informational; downstream still receives the full nominal amount). Only
  the existing speed penalty applies. (Output-quality was previously NOT modelled —
  the old comment "quality rolls are not modelled here" is gone.)
- **Pick-out (`--quality-pickout`).** For each step with quality modules, only the
  `(1 − q_chance)` normal fraction stays in the chain. `solve()` divides the cycle
  count by `normal_frac` (`effective_result_normal`), so machine counts and input
  feed scale up to keep the normal-tier yield at demand; co-products credit only
  their normal fraction to `surplus`. The extracted higher-quality items accumulate
  in `solver.quality_yield` → top-level **`quality_yield`** `{item: {tier: rate}}`.
  `rate_for_machines` applies the same `(1 − q_chance)` factor so `--machines`/
  `--step-machines` reference runs stay consistent; `_primary_amount` is stored as
  the normal-tier per-cycle amount so the `--step-machines` floor pass works.
  `100% q_chance` (no normal output) raises `ValueError`.

Top-level echoes: `quality_pickout: true` (when set), `max_quality` (when pickout
or any extraction occurred). Human format adds a "Quality pick-out: ON" header
line, a `~ quality <item>: …` line per step, and a "Picked-Out Quality Items"
section. Works on every location including the Fulgora LP (see above).

---

## Oil Processing

`petroleum-gas`, `light-oil`, `heavy-oil` are in `OIL_PRODUCTS` and handled specially:

1. During `Solver.solve()`, demands for these are **deferred** into `oil_demands{}` (not recursed into immediately).
2. After the whole tree is walked, `Solver.resolve_oil()` calls `solve_oil_system()` once to solve the refinery + HOC + LOC jointly.
3. This prevents double-counting crude-oil when multiple oil products are needed by different sub-trees.

**Refinery recipe selection** (in `resolve_oil()`):
1. If any oil product has a `--recipe` override pointing to an `oil-processing` recipe (e.g. `coal-liquefaction`, `simple-coal-liquefaction`), use it.
2. Otherwise default to `advanced-oil-processing` (or `basic-oil-processing`).

The linear system (where `ref_H` is the **net** heavy-oil yield = gross output − self-consumed input, handling coal-liquefaction's 25-heavy-oil self-feed):
```
ref_H * r - hoc_in * h                  = D_heavy
ref_L * r + hoc_out * h - loc_in * l    = D_light
ref_P * r               + loc_out * l   = D_petgas
```
Negative-variable cases (surplus of one oil fraction) are handled by clamping to zero and re-solving the reduced system.

**Coal liquefaction** (`--recipe heavy-oil=coal-liquefaction`):
- Inputs: coal 10 + heavy-oil 25 (self-consumed, excluded from raw demands) + steam 50
- Net outputs per cycle: heavy-oil 65, light-oil 20, petroleum-gas 10
- `ref_H = 90 − 25 = 65` — the solver handles the circular self-feed transparently
- coal and steam become raw resources; crude-oil is absent

**Simple coal liquefaction** (`--recipe heavy-oil=simple-coal-liquefaction`, Space Age Vulcanus):
- Inputs: coal 10 + calcite 2 + sulfuric-acid 25 (no self-consuming heavy oil)
- Output: heavy-oil 50 only; cracking handles light-oil / petgas demand

---

## Machine Category Mappings

**Vanilla:**
- `smelting` → furnace (stone/steel/electric per `--furnace`)
- `chemistry` → chemical-plant (speed 1)
- `oil-processing` → oil-refinery (speed 1)
- `centrifuging` → centrifuge (speed 1)
- `rocket-building` → rocket-silo (speed 1)
- everything else → assembling-machine-N per `--assembler`

**Space Age additions:**
- `cryogenics*` → cryogenic-plant (speed 3/2)
- `organic*` → biochamber (speed 3/2)
- `electromagnetics` → electromagnetic-plant (speed 2)
- `electronics*`, `electronics-or-assembling`, `electronics-with-fluid` → electromagnetic-plant (speed 2)
- `metallurgy*`, `crafting-with-fluid-or-metallurgy` → foundry (speed 4)
- `crushing` → crusher (speed 1)
- `pressing` → foundry (speed 4)
- `captive-spawner-process` → captive-spawner (speed 1)

---

## Miner Logic

| Resource category | Machine | Output metric |
|-------------------|---------|---------------|
| `offshore` | `offshore-pump` | `machine_count` (fixed 72 000/min each — 1200/sec) |
| `basic-fluid` (crude-oil, heavy-oil springs) | `pumpjack` | `required_yield_pct` |
| everything else (solid ores) | `electric-mining-drill` or `big-mining-drill` | `machine_count` |

**Pumpjack yield formula:**
```
rate_at_100pct = (pumpjack_speed / mining_time) * yield * 60
required_pct   = demanded_rate / rate_at_100pct * 100
```
This matches FactorioLab's display. Players divide this across their pumpjack fields.

---

## Using the CLI

Before invoking `cli.py` for any calculation, read `10x-factorio-engineer/SKILL.md` §2 for the full flags reference and output shape. CLAUDE.md only has the bare invocation pattern — SKILL.md §2 is the authoritative flags table.

---

## Tests

```bash
python -m unittest dev.test_cli -v
```

`dev/test_cli.py` contains 278 tests covering:

| Class | What's tested |
|-------|---------------|
| `TestPickRecipe` | Exact key match, order-sort fallback, override priority, unknown override fall-through |
| `TestElectronicCircuit` | Raw resource rates (iron-ore=60, copper-ore=90 at 60/min) |
| `TestOilChainNoDoubleCounting` | crude-oil ≈ 487.18 for processing-unit at 10/min; AOP counted once; no oil products in raw_resources |
| `TestPumpjackYield` | `required_yield_pct` ≈ 81.2% for crude-oil; water → offshore-pump |
| `TestRecipeOverride` | `--recipe` override flag; default solid-fuel = petroleum-gas variant; override surfaced in JSON output |
| `TestSpaceAgeMachineRouting` | superconductor routes to electromagnetic-plant + foundry + cryogenic-plant |
| `TestBigMiningDrill` | 4 big drills for tungsten-ore at 60/min; electric drill for vanilla iron |
| `TestMachineCategoryVanilla` | assembler-3 default; electric/stone furnace; chemical-plant; oil-refinery |
| `TestModuleConfig` | `--modules MACHINE=...` reduces machine count (prod); speed modules reduce count; mixed prod+speed; zero-slot machine ignores prod/speed; module quality multiplier scales bonus; per-recipe override via `--recipe-modules`; quality modules impose a flat −5%/module speed penalty (raises machine_count, not quality-scaled; output quality not modelled) |
| `TestFractionArithmetic` | All `raw_resources` and `machine_count` values remain `Fraction` in beacon-free runs |
| `TestCoalLiquefaction` | `coal-liquefaction` via `--recipe heavy-oil=coal-liquefaction`; net heavy-oil math (65/cycle); coal+steam in raw; AOP not used; cracking engaged for petgas demand |
| `TestSimpleCoalLiquefaction` | `simple-coal-liquefaction` (Space Age); coal+calcite+sulfuric-acid in raw; no crude-oil; cracking for petgas |
| `TestGlebaMachineRouting` | `organic` → biochamber (no assembler); `pressing` → foundry (count=1/16 for transport-belt); `captive-spawner-process` → captive-spawner with zero inputs |
| `TestNutrientsRecipes` | Default picks `nutrients-from-yumako-mash` via `RECIPE_DEFAULTS` (not fish); no circular dependency; fish route still available via `--recipe` override; bioflux override full biochamber chain |
| `TestBeaconConfig` | `--beacon MACHINE=BEACON_COUNT:MOD_COUNT:TYPE:TIER:QUALITY` computes speed via sqrt formula; `beacon_speed_bonus` in step output; `machine_count` becomes float; beacon quality effectivity (1.5/1.7/1.9/2.1/2.5); per-recipe override via `--recipe-beacon` |
| `TestMachineQuality` | `--machine-quality` applies `MACHINE_QUALITY_SPEED` bonus; legendary assembler-3 faster than normal; reduces machine count |
| `TestMachineOverride` | `--recipe-machine RECIPE=MACHINE` per-recipe redirect; unknown machine falls through; surfaces in JSON output; independence from category override |
| `TestBusItem` | `--bus-item` stops recursion at item; demand goes to `bus_inputs` (not `raw_resources`); rates correct; `bus_inputs` dict in JSON output; absent when unused; `miners_needed` empty for bus-only lines |
| `TestMachinesFlag` | `rate_for_machines` round-trips integer/fractional machine counts; Fraction return type without beacons; prod-module and beacon round-trips; raises on raw resource; assembler level respected |
| `TestStepMachines` | Pre-2026-05-10 scale-derivation tests (still relevant for the constraints-only path): uranium-processing=8 yields 8 centrifuges; multiple constraints use min-scale binding when no `--rate`; top-level recipe constraint equivalent to `--machines`; recipe-not-in-chain detection; beacon float path. |
| `TestStepMachinesFloor` | Post-solve floor pass via `cli._apply_step_machines_floor`: floor < natural is a no-op (echo only); floor > natural bumps `machine_count` to N and sets `excess_output_per_min > 0`; extra demand cascades to `raw_resources`; multiple independent floors each emit their own buffer; recipe not in chain → `SystemExit` listing available; oil-recipe (e.g. `advanced-oil-processing`) rejected with explanatory error; beacon (float) path works; surplus credited from over-sized step is drained by downstream consumers via subsequent `solver.solve`. |
| `TestStepMachinesEnd2End` | Subprocess-driven CLI tests for the unified Phase A/B/C/D flow: floor-only emits `excess_output_per_min` + top-level `co_products`; high `--rate` with low `--step-machines` triggers `chain_throttled: true` and reduces `rate_per_min`; constraints-only path derives top-level rate (uranium-processing=8); multiple-floor constraints-only run picks binding via min-scale and bumps non-binding to declared N with buffer; `--use-ceil` is no longer rejected with `--step-machines`; combined with `--machines` works (flying-robot-frame=1 + battery=3 floor); `step_machines` echoed in JSON. |
| `TestPowerConsumption` | Electric machines have `power_kw > 0`; burner machines give 0; efficiency modules reduce power (quality-scaled); speed/prod penalty not quality-scaled; efficiency floor at −80%; beacon sharing (3×3 = ÷4, 5×5 = ÷2); `total_power_mw` in output; miner `power_kw` present; miner efficiency reduces power (quality-scaled, −80% floor); miner `beacon_power_kw` emitted and included in `total_power_mw` |
| `TestProbabilisticOutputs` | `uranium-processing` U-238 output reflects 0.993 probability; U-235 reflects 0.007 probability; `rate_for_machines` returns correct probability-weighted rates for both isotopes; ratio U-235/U-238 machine count ≈ 141× |
| `TestMultiTarget` | Two-item solve merges shared sub-recipes; `targets` array replaces top-level `item`/`rate_per_min`; raw_resources and bus_inputs accumulate across all targets; belt/pump fields absent in multi-target output |
| `TestStepInputs` | `inputs` dict present on every production step; ingredient consumption rates correct; reduced by productivity modules; bus items appear in step inputs; oil steps have crude-oil input; multi-target inputs accumulate |
| `TestStepConfig` | `machine_quality` always present per step; `module_specs` present only when modules configured (global or per-recipe override); `beacon_spec`+`beacon_quality` present only when beacon configured; per-recipe override wins over global |
| `TestHumanReadableOutput` | `format_human_readable()` returns non-JSON text; header contains item+rate; sections present (Production Steps, Raw Resources, Miners Needed, Power); machine names in steps; module/beacon config in header and detail lines; machine quality in step label; pumpjack shows yield%; bus inputs section when bus items present |
| `TestLocationFilter` | `--location` raw_set filtering (vulcanus has tungsten-ore+sulfuric-acid, not iron-ore; gleba has yumako+jellynut+spoilage as raw; space-platform is empty); planet surface_conditions filtering; explicit `--recipe` override bypasses planet filter; `location` field in JSON output; Vulcanus water→steam-condensation+acid-neutralisation; Gleba plastic/sulfur/lubricant→bio-substitutes; Aquilo ice→ammoniacal-solution-separation |
| `TestPlanetMachineUnlocks` | `compute_location_unlocks` per-planet table (nauvis empty, vulcanus={foundry}, gleba={biochamber}, fulgora={EM-plant}, aquilo=all four); `get_machine` legacy behaviour (no unlocks) keeps premium machines; Nauvis falls back to chemical-plant for `chemistry-or-cryogenics` / `organic-or-chemistry`, assembler for `electronics*` / `metallurgy-or-assembling` / `pressing` / `cryogenics-or-assembling`; Vulcanus keeps foundry only (cryo/biochamber/EM cats fall back); Aquilo keeps all four; end-to-end regression: Nauvis LDS routes plastic-bar + oil cracking to chemical-plant, electronic-circuit to assembler-3; Fulgora EC uses EM-plant; Vulcanus tungsten-plate stays on foundry; Aquilo plastic-bar uses cryogenic-plant; `pick_recipe` filters out `metallurgy` recipes (casting-iron) on Nauvis; `--recipe-machine` override bypasses unlock filtering. |
| `TestResearchProductivity` | `--research NAME=LEVEL` flag / `research_levels` dict; mining-productivity multiplies drill rate_each (uncapped, skips `offshore-pump`); recipe-prod techs boost all recipes in their `PRODUCTIVITY_RESEARCH` list (steel/plastic-bar/casting paths, asteroid-crushing family, bioplastic on Gleba); additive stacking with module prod; +300 % cap clamps crafting recipes and sets `research_prod_capped`; unknown research names ignored; research prod applies even when the recipe's `allow_productivity` is False (recipe-targeted tech ≠ module — verified on `scrap-recycling`, whose `scrap-recycling-productivity` boost is +30 % at L3 despite `allow_productivity=False`, and saturates at the +300 % cap at L50); `research_levels` + `research_prod_capped` + per-step `prod_capped` echoed in JSON output |
| `TestUseCeil` | `--use-ceil` two-pass re-solve: single-step bus-only line gives integer `machine_count`; two-step chain tops out at integer with intermediate correctly sized; binding-is-intermediate case leaves rate unchanged; already-integer counts produce no rescaling; `use_ceil: true` echoed in JSON output |
| `TestMachineInherentProd` | `build_machine_prod_bonus` returns 1/2 for foundry/EM-plant/biochamber and 0 for assembler/furnace; `_compute_module_effects` returns the machine built-in prod even when `allow_prod=False` (modules gated, inherent not) and 0 for non-inherent machines; EM-plant electronic-circuit machine count is 2/3 of the no-inherent baseline |
| `TestSimplexLP` | Direct unit tests for `_lp_minimize`: basic optimum with exact `Fraction` output; picks the cheaper variable; `infeasible` when an item has no producer (all-zero row, b>0); `unbounded` detection; fractional optimum (2.5 each on a symmetric cover) |
| `TestFulgoraRecyclingLP` | End-to-end `--location fulgora` LP via subprocess: `scrap` is the only solid raw and no asteroid-crushing steps; binding-constraint throughput (battery 60/min → 1500 scrap on `recycler`); `scrap-recycling-productivity` reduces scrap demand in the LP (+10 %/level → 1500/1.1 at L1, 1500/1.2 at L2); by-products surface in `co_products`; holmium-ore/stone resolve with no `--bus-item` (EM-science 90/min → 9800 scrap); cascade uses `iron-gear-wheel-recycling` not asteroids; speed modules flow into LP coefficients and reduce machine counts; `--step-machines` rejected on fulgora; `FULGORA_WRAP_ROUTES` entries are valid single-ingredient wrap recipes with existing `<wrap>-recycling`; production_steps are emitted as a strict sources-last bill of materials (target first, `scrap-recycling` last; every step below ALL its consumers) — `format_output` uses a longest-path level sort for `--location fulgora` (recursive/tree locations keep the DFS pre-order) |
| `TestQualityChanceHelpers` | Unit tests for `quality_chance_from_specs` (T2=2%/slot base, tier+quality scaling, prod modules ignored, **speed modules subtract — a tier-T speed module cancels a tier-T quality module at equal housing quality (incl. legendary); partial penalty nets correctly; clamps to 0 with no quality modules**, slot-scaling caps at machine slots, clamp to 1.0, zero when no slots) and `quality_tier_probs` (legendary-cap 90/9/0.9/0.1 split sums to 1; rare-cap folds +2/+3/+4 mass onto rare; normal-only cap folds everything back to normal) |
| `TestQualityPickout` | End-to-end `--quality-pickout` via subprocess: recursive path scales the quality step up so normal output == demand and extracts uncommon/rare/epic (capped at `--max-quality`, no legendary key); aggregated `quality_yield` matches the per-step `quality_output` >normal split; pick-out raises machine count vs the reporting-only run; reporting-only (no flag) leaves machine count at nominal and emits no `quality_yield` (informational split sums to the flowing rate); pick-out flag with no quality modules extracts nothing; Fulgora LP pick-out (accumulator 5×quality-2 → normal 50/min + rare-capped extraction); `--max-quality rare` suppresses epic/legendary even with legendary T3 modules; human format renders the three quality sections; **speed modules in a beacon reduce the step's quality (`test_beacon_speed_modules_reduce_quality`: a speed beacon lowers `quality_yield`, enough beacons cancel it to `{}`)** |

### `dev/test_quality_planner.py` (340 tests)

Covers the V1+V2 legendary planner in `dev/quality_planner.py`, plus the V3-partial LDS-shuffle wiring:

| Class | What's tested |
|-------|---------------|
| `TestDPKernel` | `_quality_chance` (zero-modules, T3 legendary, linear stacking, clamping at 100%); `_tier_skip_probs` (90/9/0.9/0.1 distribution, sum=1, caps at legendary); `_prod_bonus` scaling |
| `TestDPKernelYields` | Wiki-style yield numbers for iron-plate electric-furnace self-loop (within expected 0.05–5% band); legendary modules beat normal by >2x; +300% prod cap saturates at high research levels |
| `TestAsteroidReprocessing` | Reprocessing recipe aggregate retention = 0.8; legendary yield positive and < 1.0; all three chunk types give identical yields; higher module quality / tier give higher yields; unknown chunk returns zero |
| `TestFluidTransparency` | `casting-iron` picked over `iron-plate` on Nauvis; `casting-copper-cable` picked over `copper-cable`; `molten-iron` picks ore variant (not lava) on Nauvis due to planet-exclusive filter; fluid set correctness |
| `TestAssemblyPropagation` | Electronic-circuit end-stage flagged `inputs_all_legendary=True`; iron-gear-wheel chain includes reprocessing + crushing + foundry casting |
| `TestResearchProd` | Research lookup for asteroid-productivity; no research returns 0; unknown techs ignored; asteroid research reduces required raw chunk input |
| `TestFailFast` | Tungsten-plate → Vulcanus error; holmium-plate → self-recycling blocklist; superconductor → self-recycling; tungsten-carbide → blocklist; plastic-bar / processing-unit / artillery-shell → oil-chain error |
| `TestEndToEnd` | Electronic-circuit @ 60/min full chain; iron-plate and copper-plate simple chains; JSON serialisable output; human format smoke test; rate doubles → asteroid input doubles |
| `TestHelpers` | `_recipe_result_amount` with probability; `_recipe_ing_amount`; `build_fluid_set` contents; `_humanize` mapping |
| `TestParseResearch` | `--research NAME=LEVEL` parsing round-trip; empty list |
| `TestPlanetsFlag` (V2) | `--planets` flag; nauvis unlocks plastic-bar; vulcanus unlocks tungsten-plate; multi-planet artillery-shell; fluid raws marked transparent |
| `TestMinedRawSelfRecycle` (V2) | coal/stone/tungsten-ore/holmium-ore positive yield; legendary modules beat normal; self-recycle yield strictly worse than asteroid reprocessing |
| `TestLDSShuffle` (V2) | per-input yield positive; research improves; +300% prod cap; LDS shuffle beats asteroid reprocessing with high plastic-bar research |
| `TestOtherPlanetUnlocks` (V2) | fulgora unlocks scrap/holmium-ore (electrolyte chain); mined-recycle stage shape |
| `TestLDSShuffleWiring` (V3) | `--enable-shuffle low-density-structure` (formerly `--enable-lds-shuffle`) flag default off; flag on emits cross-item-shuffle stage with positive yield; coal moves from `mined_input` to `normal_solid_input`; high LDS-prod research reduces total machines vs no research; byproduct credit reduces upstream raw demand (verified directly via walker on solar-panel + copper-plate credit); byproduct overflow flagged in notes; total machines includes shuffle cast+recycler; human format renders shuffle/byproducts/normal-input sections |
| `TestShuffleEnumeration` (V3) | `enumerate_shuffle_candidates` returns exactly 16 candidates (multi-solid-recycle-output filter); single-output recyclers (iron-stick, copper-cable, iron-gear-wheel) excluded; LDS picked with foundry variant `casting-low-density-structure` over assembler variant; meta picks present (LDS, advanced-circuit, electronic-circuit, engine-unit, battery, processing-unit); cached per `id(data)`; recycling-category recipes excluded |
| `TestShuffleSolver` (V3) | `solve_shuffle_loop(LDS, plastic-bar)` matches legacy `solve_lds_shuffle_loop` to ±1e-12; positive yields for advanced-circuit / engine-unit primaries; `compute_shuffle_stage` produces positive `machine_count` / `cast_machines` / `recycler_machines`; byproduct_legendary contains copper-plate + steel-plate for LDS; inherent prod auto-resolves to 0.5 for foundry recipes |
| `TestShuffleSelection` (V3) | Greedy picks LDS shuffle for plastic-bar leaf when only LDS enabled; no shuffle activated when no overlap with chain (iron-plate-only); byproducts satisfy other leaves (single LDS activation covers plastic + small copper); empty candidates returns empty; disjoint leaves (uranium-235) emit no errors |
| `TestEnableShufflesAll` (V3) | `--enable-shuffles all` sentinel activates every applicable shuffle subject to the cost gate. Cost gate (compare with baseline plan): if shuffle plan total > no-shuffle total, fall back to baseline + emit explanatory note. Explicit `--enable-shuffle NAME` bypasses the cost gate (user opt-in). iron-plate chain activates zero shuffles (no overlap); unknown shuffle name errors with "unknown shuffle" message; combines cleanly with `--assembly-modules` |
| `TestSelfRecycleTarget` (V3 item 3) | Self-recycling targets work: `holmium-plate` (foundry, 4 slots, +50% inherent prod), `tungsten-carbide` (assembler-3, 4 slots), `superconductor` (EM plant, 5 slots, +50% inherent prod); ingredients consumed at NORMAL quality (tungsten-ore appears in `normal_solid_input`); legendary modules >2× normal-modules yield; rate doubles → total machines double linearly; per-tier module config exposed; human format renders `[self-recycle]` line; `solve_self_recycle_target_loop` returns 0 for unknown items |
| `TestAssemblyModules` (V3 item 5) | `--assembly-modules` flag default off (stages have prod_modules=0, but `module_prod` still carries the machine inherent +50%); flag on cuts total machines >5× and asteroid input >5× on processing-unit chain (fluid-cast foundry/EM-plant/cryogenic with 4–8 prod-3-legendary modules + inherent +50%); `_assembly_prod_bonus` helper returns the machine inherent prod even when `allow_productivity=False` (only prod modules are gated) and even when `--assembly-modules` is off; non-inherent machines (assembler) return 0; +300% cap engages at high research; human format shows `Nx prod-3-legendary (+X%)`, or `inherent +X% prod` when only the built-in bonus applies |
| `TestGlebaPartial` (V3 item 4 partial) | Gleba bio-targets work: `bioflux` (yumako + jellynut both in mined_input), `plastic-bar` routes to bioplastic when only Gleba unlocked (no coal), `sulfur` to biosulfur, `lubricant` to biolubricant, `nutrients`; assembly-modules cuts biochamber chain >3×; `solve_mined_raw_self_recycle_loop("yumako")` positive but tiny (~coal yield); without --planets gleba, bioflux fails-fast with "yumako" / "gleba" / "no recipe" in error. **Spoilage timing NOT modelled.** |
| `TestStagePower` (V3 power accounting) | Every stage has `power_kw`; output has `total_power_mw`; assembly stage power = `machine_power × machine_count / 1000`; compound stages split correctly (self-recycle: craft-machine power × craft_machines + recycler power × recycler_machines; cross-item-shuffle: foundry × foundry_machines + recycler × recycler_machines); biochamber stages report 0 kW (burner-fuelled); assembly-modules cut total_power_mw >5×; human format shows `Total power:` line. |
| `TestMachineQuality` (V3 small) | `--machine-quality` applies `cli.MACHINE_QUALITY_SPEED` (+0/+30/+60/+90/+150% for normal/uncommon/rare/epic/legendary) to every machine speed (assembly + crusher + recycler). Default `normal`. Legendary cuts machine count by 1/2.5 ≈ 0.4×; total monotonically decreases across the quality ladder. Self-recycle-target stages scale `craft_machines` and `recycler_machines` by the multiplier; asteroid-reprocessing crusher count likewise. Each assembly stage is tagged with `machine_quality`. |
| `TestHotSpotAdvisor` (V3 small) | `_hot_spot_suggestions()` helper inspects `summary.by_role` and emits an actionable note when a single role exceeds 50 % of total machines. Maps role → suggestion: `asteroid-reprocessing` + plastic → `--enable-lds-shuffle`; `asteroid-reprocessing` + non-max-quality → upgrade quality; `mined-raw-self-recycle` → `--enable-lds-shuffle` (if plastic) or `--planets vulcanus` (if locked); `assembly` → `--assembly-modules` (or `--machine-quality legendary` if modules already on). Suppresses the suggestion when at legendary T3 and nothing actionable. End-to-end: processing-unit @ Nauvis emits a coal-recycle hot-spot pointing at LDS shuffle; default iron-plate emits no suggestion. |
| `TestStageSummary` (V3 small) | `summary.by_role` aggregates `machine_count` + `power_kw` + `stage_count` per stage role with `machines_pct` and `power_pct` percentages. Sums match `total_machine_count` / `total_power_mw`. Percentages sum to 100. Self-recycle-target plan path also emits the summary. Default asteroid plans show both `asteroid-reprocessing` and `assembly` roles. Human format renders a "Cost Breakdown by Stage Role" table sorted by descending machine count. |
| `TestNoAsteroids` (V3 small) | `--no-asteroids` flag (default off): skips the asteroid-reprocessing path entirely. iron-ore / copper-ore / ice / calcite are sourced via the recycler self-loop on an unlocked planet (`MINED_RAW_NO_ASTEROID_FALLBACK`: nauvis for iron/copper, aquilo for ice, vulcanus for calcite). Default behaviour preserved (asteroid_input populated). With Nauvis-only, iron-plate/copper-plate fail-fast with calcite-needs-vulcanus message naming the recipe (`advanced-oxide-asteroid-crushing`) and pointing to `--planets vulcanus`. With nauvis+vulcanus, copper-plate routes via molten-copper-from-lava (calcite as mined-recycle, lava as fluid raw). processing-unit + assembly-modules + nauvis,vulcanus plans cleanly with `asteroid_input` empty and `mined_input` containing calcite. |
| `TestTechGating` (V3 item 2) | `--tech NAME=LEVEL` flag with strict default-locked semantics. Bare CLI invocation (no `--tech`) → `tech_state={}` → fail-fast on the recycler check. Library `plan(...)` requires `tech_state` as a kwarg; `qp.ALL_TECH_UNLOCKED` is the constant for "fully researched". Verifies: recycler-locked → ValueError mentioning "recycler"; foundry-locked (`tungsten-carbide=0`) iron-plate falls back to electric-furnace via `CATEGORY_FALLBACK`; EM-plant-locked electronic-circuit falls back to assembling-machine-3; same fallback drops the +50% inherent prod (machine count rises); `_machine_for_recipe` returns None for category=`cryogenics` when cryo locked (no fallback); `_parse_tech_state` rejects unknown names with sorted valid list (machine techs only — quality-module tiers are no longer `--tech` gated); `ALL_TECH_UNLOCKED` covers every TECH_GATES key with value=1; partial lock (`recycling=1` + `tungsten-carbide=1`) on iron-plate matches the all-unlocked baseline since iron-plate doesn't need the others. |
| `TestGlebaTargets` (V3 item 4) | Gleba/cryo buildings + auto-compare cost gate. `biolab` and `captive-biter-spawner` added to `SELF_RECYCLE_TARGETS`. `enumerate_shuffle_candidates` no longer filters by `allow_productivity=True` → 195 candidates (was 16); buildings, modules (T1/2/3 prod/speed/quality/efficiency), military (`tank`, `spidertron`, turrets, ammo, armor), end-game power (`nuclear-reactor`, `fusion-reactor`), and logistics (`roboport`, `logistic-robot`) all qualify. Single-output items (`firearm-magazine`, `stone-wall`) still excluded. Auto-comparator runs both Path A (self-recycle target loop) and Path B (ingredient-upcycle) for SELF_RECYCLE_TARGETS items, picks lower `total_machine_count`. Verified outcomes: tungsten-carbide → Path B (480 vs 1106), holmium-plate → Path B, biolab → Path B, captive-biter-spawner plans (path-dependent post-2026-05-08-audit since intermediate dispatch now unblocks Path B for many cases). Non-self-recycle targets (iron-plate, electronic-circuit) get no auto-compare note. Shuffle DP correctly skips prod-bearing slots when recipe has `allow_productivity=False` (verified via biochamber). |
| `TestSelfRecycleIntermediate` (post-2026-05-08 audit) | Items in `SELF_RECYCLING_BLOCKLIST` hit as intermediates now dispatch via `choose_path_self_recycle` instead of fail-fasting. Verifies 14 previously-failing endgame targets now plan: `electromagnetic-plant`, `foundry`, `mech-armor`, `fusion-reactor`, `quality-module-3`, `metallurgic-/electromagnetic-/cryogenic-science-pack`. Verifies normal-quality inputs propagate (e.g. `holmium-solution` in `normal_fluid_input`). Verifies `summary.by_role` includes `self-recycle-target`. Verifies linear scaling under rate doubling. Verifies Pass 2 dedupes `order` entries so no duplicate `self-recycle-target` stages emit. |
| `TestDispatchMemoization` (post-2026-05-08 audit) | `_DispatchCache` memoizes solver kernel calls and Path A/B decisions. Solver kernel called once per unique `(item, machine, slots, allow_prod, inherent, research_prod, module_quality, prod_tier, quality_tier)` key; decision cached and re-used per `(item, env_signature)`. Per-`plan()` cache isolation (no cross-call leak). Cycle detection via pre-populated `_in_flight` forces Path A with explanatory note `forced self-recycle (cycle detected through ...)`. Solver cache keyed by env (epic-quality variant gets a fresh kernel call). |
| `TestSelfFeedTarget` (V3 item 4 cont.) | Pentapod-egg as a self-FEED target: recipe `1 egg + 30 nutrients + 60 water → 2 eggs` has ingredient = output, so `solve_self_recycle_target_loop` doesn't apply. `solve_self_feed_target_loop` solves a 4-tier linear-flow LP (q∈{0,1,2,3} processing, q=4 drain) where each LP corner has exactly one `x_q* > 0`; cheapest of 4 corners wins. `_plan_self_feed_target` dispatcher walks non-self ingredients (nutrients, water) at normal quality via `walk_recipe_tree`, skips the self-ingredient, and emits a `self-feed-target` stage with `craft_machines + recycler_machines + per_tier_flows + module_config_per_tier`. Auto-comparator deliberately skipped (Path B = same problem). Verified: pentapod-egg @ Gleba 60/min produces single self-feed stage (~15 machines @ q*=3), planet gating fails-fast without `--planets gleba` mentioning "gleba", rate doubles → machines double, water flows into `normal_fluid_input` and yumako/jellynut into `normal_solid_input`, self-ingredient absent from input buckets, all 4 processing tiers exposed in `module_config_per_tier`, exactly one tier hosts crafts in LP corner solution, `[self-feed]` tag in human format, solver returns (0, {}) for unknown items / non-self-feed recipes (iron-plate). |
| `TestEnumerateRecycleRoutes` (Reddit wrap-and-recycle) | `enumerate_recycle_routes` returns ALL self-recycle candidates per item including multi-solid-ingredient wraps (which `build_recycle_shortcuts` deliberately filters out). Each descriptor exposes `retention`, `recycler_time`, `craft_time`, `craft_category`, `container`, `wrap_recipe`, `co_solids`, `co_fluids`, `co_byproducts`. Verifies: dict keyed by item; cached by `id(data)`; direct self-recycle entry present (e.g. for holmium-plate); single-ingredient wraps preserved (e.g. steel-chest for steel-plate); multi-ingredient wraps surface for holmium-plate (electromagnetic-plant, supercapacitor, …); co-ingredient amounts normalised per 1 item-atom in; routes sorted by `(-retention, recycler_time)`; recycling recipes never leak in as wraps; `build_recycle_shortcuts` byte-identical (purely additive). |
| `TestWrapDP` (Reddit wrap-and-recycle) | `solve_self_recycle_target_loop` gains optional wrap-craft `(wp, wq)` dimensions via `wrap_route` + `wrap_machine_slots` kwargs. Cycle DP composes wrap-craft quality roll with container-recycle quality roll (2 rolls per pass instead of 1). Wrap-craft prod scales retention by `(1 + wrap_prod)`. Verifies: default call (no wrap) is byte-identical to pre-extension behaviour; supplying a wrap route + slots strictly improves yield; `wrap_machine_slots=0` skips wrap path even when route is provided; `wrap_allow_prod=False` forces `wp=0` in best config; search-space remains additive (20 holmium calls @ 5 slots in <1s); per-tier configs gain `wrap_prod`/`wrap_quality` fields when active. End-to-end `plan('holmium-plate')` activates the wrap path, drops total machines from ~666 (baseline) to <500 (`supercapacitor` wrap via EM-plant); co-ingredients (superconductor, electronic-circuit, battery) appear in `normal_solid_input`; emits `wrap-and-recycle via …` note; linear scaling under rate doubling holds. `_choose_wrap_route` two-tier selection: single-ingredient wraps (`co_solids=[]`) take priority — e.g. steel-plate stays on steel-chest, concrete on hazard-concrete — so the cleanup never switches their wrap recipe even though they now get the second quality roll.  Falls back to multi-ingredient wraps only when no single-ingredient option exists (the holmium-plate case).  Returns `(None, None)` when called with non-self items in `_in_flight` (cycle-prevention) but runs when only self is in flight (genuine top-level). |
| `TestModuleConfigSurface` | Quality-loop stages surface their quality-module config. `scrap-quality-source` stage carries `module_config_per_tier` (every recycler slot = `4x quality-N-Q`); `format_human` renders a `modules:` sub-line for scrap / asteroid-reprocessing / mined-raw stages (these previously showed no modules, only assembly prod). `_module_config_summary` collapses uniform per-tier configs to one string, lists per-tier when they differ, and handles empty / `0x` (no modules). |
| `TestModuleSpeedPenalty` | `_module_speed_mult`: quality modules −5%/slot (×0.8 at 4), prod modules −5/−10/−15% per tier, combined penalties, floored at 0.2 (−80% speed floor). Verifies the penalty is wired into the loop stages — neutralising it lowers the asteroid-crusher-dominated iron-plate plan by ~×1.11 — **and into the self-feed LP** (`test_wired_into_self_feed_lp`: pentapod-egg machine count drops when the penalty is neutralised; the crafter's prod+quality slots and recycler's quality slots are applied per config). |
| `TestLocationFulgora` | `--location fulgora` scrap-only sourcing. Verifies: quality-module-2/-3 @ rare produce **zero** `asteroid_input` and no `asteroid-reprocessing`/`raw-crushing` stages (scrap is the sole base source, `scrap-quality-source` role present); metals route from scrap (copper-plate in `scrap_overflow`, empty `mined_input`); `_pick_recipe_fluid_preferred(..., forbid_ore_routes=True)` returns plain `copper-cable` (not `casting-copper-cable`); `--location fulgora` implies the Fulgora unlock without explicit `--planets`; an unsourceable solid (`tungsten-plate` → tungsten-ore) fails fast naming `vulcanus`. **Fluid sub-chains (Fulgora): the acid chain for processing-unit is delegated to `cli.py` — a `fluid-chain` stage produces `sulfuric-acid` (on `chemical-plant`, tagged `fluid_target`); `fluid_input` lists the true pumped raw `heavy-oil` (not `sulfuric-acid`); `fluid_chain_scrap_draw` (ice/iron-plate) is scrap-reachable and credited against scrap overflow, not added to scrap input; fluid-chain machines fold into `total_machine_count` + `summary.by_role`; off Fulgora fluids stay quality-transparent raws with no fluid-chain stage.** |
| `TestPlannerMiners` (C1, fulgora-realism-plan) | `--miner electric\|big` sizes a drill fleet for the plan's solid raws (scrap + planet-mined ores) via `cli.compute_miners`. Verifies: scrap emits a `mining` stage (`big-mining-drill`, `machine_count>0`); big vs electric differ 1:5 by base mining speed; `--research mining-productivity=20` cuts the count to 1/3; miners fold into `total_machine_count` (Option A: `total == sum(stages)`), `total_power_mw`, and a `mining` bucket in `summary.by_role`; `format_human` renders `[mining]`; a mined raw on the main `plan()` body (iron-ore via `--no-asteroids`, foundry locked) also counts; asteroid-only plans get **no** miners (chunks caught in space); default `miner_type` is electric. Hot-spot advisor measures thresholds against production (non-mining) machines so the addition doesn't dilute existing suggestions. |

---

## Dataset Schema (KirkMcDonald format)

Top-level keys: `items[]`, `recipes[]`, `resources[]`, `planets[]`

**Recipe fields:**
- `key` — unique string ID (matches item name for simple recipes)
- `category` — determines machine type
- `energy_required` — crafting time in seconds
- `ingredients[]` — `{name, amount}`
- `results[]` — `{name, amount}` (multi-output for oil/co-products)
- `allow_productivity` — bool
- `subgroup` — used to filter out barrel recipes
- `order` — game's display sort string (useful for recipe selection)

**Resource fields:**
- `key` / `results[{name, amount}]` — what the resource produces
- `mining_time` — drill mining time
- `category` — `"basic-fluid"` for pumpjack, `"offshore"` for offshore pump, else solid

---

## Excluded Recipes

- `subgroup` in `["empty-barrel", "fill-barrel"]` — barrel packing/unpacking
- `category` in `["recycling", "recycling-or-hand-crafting"]` — Space Age recycler output recipes

---

## Dependencies

Stdlib only — no `pip install` required: `argparse`, `json`, `math`, `os`, `sys`, `urllib.request`, `collections`, `fractions`.

---

## Component 2: Claude Skill

### Purpose

`10x-factorio-engineer/SKILL.md` is a system-prompt document that turns Claude into an active
Factorio gameplay assistant. It defines three responsibilities:

1. **Precise calculations** — always call `python 10x-factorio-engineer/assets/cli.py`, never compute
   production chains mentally.
2. **Conversational factory tracking** — parse freeform player updates ("just
   placed 12 electric furnaces on copper"), maintain a structured factory-state
   JSON in context, detect bottlenecks, and suggest next steps.
3. **Strategy guidance** — load the relevant file from `10x-factorio-engineer/references/` on demand
   (see SKILL.md §10 routing table) to answer questions about layouts, trains, megabases,
   Space Age planets, power, combat, and more.

### Factory State JSON Schema

See `10x-factorio-engineer/SKILL.md` §3 for the canonical factory-state schema Claude tracks in every gameplay session.

### Dashboard (`dev/dashboard.html` → `10x-factorio-engineer/assets/dashboard.html`)

A single self-contained vanilla HTML file — no React, no framework, no
external dependencies beyond the browser at runtime. State is encoded as base64
(minified JSON → UTF-8 bytes → `btoa`) for compact storage and portability.

**Build:** `python dev/build_dashboard.py` — minifies HTML/CSS/JS (strips all
comments, collapses whitespace) via the `minify-html` library and writes
`10x-factorio-engineer/assets/dashboard.html` (~24% smaller than source). Use
`--open` to open the result in a browser immediately. `minify-html` is a
**dev-time build dependency** (`python -m pip install minify-html`); the produced
artifact remains dependency-free in the browser.

**Header:** compact one-line brand label (`10x Factorio Engineer`) left, badges
right (`[Space Age]` when applicable + current `[N SPM]`). Global config badges
were dropped — per-line configs make them misleading. Save name plus an
"updated Xh ago" relative timestamp (from `state.updated_at`, stamped on every
save) form a subtle subtitle.

**Features:** see `10x-factorio-engineer/SKILL.md` §5 for section-by-section description.

**Import/Export:** Export produces a base64 string (copy button). Import
accepts base64 or plain JSON (backward-compatible). Storage uses the same
encoding in both `window.storage` and `localStorage`.

**ID humanisation:** `humanizeText()` converts kebab-case IDs to friendly
names everywhere — machine column, miners section, bottleneck/next-step text.
Known machines use a handcrafted map (`assembling-machine-3` → `Assembler 3`);
everything else falls back to title-cased label conversion.
