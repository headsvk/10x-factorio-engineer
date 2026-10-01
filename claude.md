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
| Twice monthly (1st + 15th) | The `factorio-wiki-maintenance` scheduled routine runs the wiki maintenance workflow (see below) to update the split reference files in `10x-factorio-engineer/references/`. Nothing to do by hand unless it reports a blocker — but if the last `wiki update complete` line in `dev/wiki/findings.md` is more than ~20 days old, the routine isn't firing; investigate rather than waiting. |

The goal is that `claude.md` always accurately describes the codebase.

---

## Strategy Reference Maintenance (Twice Monthly)

Driven by the `factorio-wiki-maintenance` scheduled routine (1st + 15th, 09:00 local;
prompt at `~/.claude/scheduled-tasks/factorio-wiki-maintenance/SKILL.md`). The routine
executes the workflow in `.claude/skills/wiki-maintenance/SKILL.md`, which is the source
of truth for the crawl / triage / reference-refresh steps and the RecentChanges window.
Nothing to do by hand unless it reports a blocker.

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `10x-factorio-engineer/assets/cli.py` | Calculator — entire implementation, stdlib only |
| `10x-factorio-engineer/assets/vanilla-2.1.9.json` | KirkMcDonald dataset — base game |
| `10x-factorio-engineer/assets/space-age-2.1.9.json` | KirkMcDonald dataset — Space Age DLC |
| `10x-factorio-engineer/SKILL.md` | Skill definition — Claude gameplay assistant behaviour |
| `10x-factorio-engineer/references/` | Split strategy reference files (11 topic files): early-game, factory-layouts, trains, megabase, planets, space-platforms, power, combat-defense, logistics-circuits, quality, resources |
| `dev/dashboard.html` | Dashboard source — single vanilla HTML file, no build dependencies |
| `dev/build_dashboard.py` | Build script — minifies `dev/dashboard.html` → `10x-factorio-engineer/assets/dashboard.html` via the `minify-html` library (dev-time dependency: `pip install minify-html`) |
| `dev/preview.py` | Generates `dev/preview.tmp.html` with factory state pre-loaded; defaults to `dev/sample/state.json`; use `--state PATH` for a custom JSON file; use `--no-min` for the unminified source dashboard |
| `10x-factorio-engineer/assets/dashboard.html` | Built artifact — run `python dev/build_dashboard.py` to regenerate; paste into claude.ai as `application/vnd.ant.html` and publish |
| `dev/sample/state.json` | Source JSON for the sample factory state — edit this directly; paste into the dashboard Import dialog to test |
| `dev/my-factory.json` | The user's actual working factory state — primary fixture for previewing real-world layouts. **Gitignored** (personal data). Use `python dev/preview.py --state dev/my-factory.json` to render it. When the user says "my factory" they mean this file. |
| `dev/update_research.py` | Applies a research-level change to a factory state and re-runs only the affected lines (`python dev/update_research.py TECH=LEVEL ... [--state PATH] [--dry-run] [--list]`; default state = `dev/my-factory.json`). Use this instead of hand-editing `research_levels` + manually re-running lines — it reconstructs each line's CLI command from its `cli_args` + shared top-level config, re-solves the affected lines, and rewrites their `cli_result` (LF output). Mining-prod re-runs miner lines; recipe-prod re-runs lines whose steps touch a boosted recipe; lab-only techs (`research-productivity` / `lab-research-speed`) update the field but trigger no re-run. See the **research-level updates** workflow note below. |
| `dev/test_cli.py` | `unittest` suite (281 tests, stdlib only) — dev only |
| `dev/quality_planner.py` | Legendary production planner — separate stdlib-only tool implementing the full quality roadmap (Q1–Q9, see `dev/quality-roadmap.md`). Post-2.1.8 asteroid sourcing = crushing quality roll + ore recycler upcycle (reprocessing no longer accepts quality modules); DP/LP quality-loop solvers, cross-item shuffles, Gleba spoilage-timing warnings (Q3), quality-module placement optimizer (Q4), mixed-tier `--demand`/`--keep-tiers` (Q6), `--beacons` (Q7), `--objective` (Q8), and `--preset` shortcuts (Q9). `--location fulgora` switches to scrap-only sourcing (no asteroid platform; metals terminate at scrap-reachable plates via `forbid_ore_routes`) |
| `dev/test_quality_planner.py` | `unittest` suite (411 tests) for quality_planner |
| `dev/quality_planner.md` | Living spec — current capabilities, architecture, gotchas, and roadmap (consolidates the former v1 / v2 specs) |
| `dev/wiki/crawl.py` | Four subcommands: `crawl` (full crawl, resume-safe), `update` (twice-monthly maintenance via RecentChanges API; also writes gitignored `dev/wiki/edit_summary.json` — per-page wiki byte deltas + edit comments for the cycle), `changes` (read-only print of that summary ranked by churn; `--live` re-queries), and `newpages` (read-only report of RecentChanges titles missing from `urls.json`, bucketed into candidate / redirect / meta / translation; safe to run after `update` because it writes nothing — unlike `update --dry-run`, which truncates `changes.diff`). Use `--workers 1` — the Cloudflare free tier allows 1 request per 10 s (`REQUEST_INTERVAL = 12` for headroom). `--days N` bounds the RecentChanges query via the API's `rcend` parameter, capped at `RC_RETENTION_DAYS = 90` (measured retention, ~89 days). Omit it: the default is `min(90, days_since_last_run + 2)`, read from the last `wiki update complete` line in `findings.md` dated before today (so `newpages` run after `update` still covers the whole cycle). Don't pass a flat value; a wider window re-crawls pages the previous run already covered, costing wall-clock (no tokens, no quota). **`rcdays` is not an API parameter** — `crawl.py` used it until 2026-09-15 and the API silently ignored it, so `--days` bounded nothing and every run pulled the full retention. Credentials via `load_credentials()`: env vars, else `.env` / `.env.local` / `~/.env`; the token needs **Account → Browser Rendering → Edit** |
| `dev/wiki/triage_changes.py` | Reduces `dev/wiki/changes.diff` to reviewable content. **Always use this instead of reading the raw diff** — the renderer resolves links, headings and tables differently between crawls, so the raw diff reports ~every page as changed (2026-07-30: 82/82 pages, 9.4 MB). Strips link targets, image embeds, bare URLs, heading/bullet markers, TOC renumbering, nav-template blobs and footers, then ranks pages by surviving prose changes. **Preserves `\|` cell delimiters** and prints a `[columns] …` header line above changed table rows (recovered from `dev/wiki/pages/<Page>.md`) so multi-column stat tables stay unambiguous. Also normalises the **renderer-drift** axes found on 2026-08-15 (YAML frontmatter, the duplicated `Space Age` badge, doubled icon alt-text in nav templates, nested `<table>` stat cells, inconsistent backslash escaping). Reads `edit_summary.json` to add a `[wiki]` line (byte delta, edit count, latest edit comment) under each page and to run a **drift check**: pages with ≥10 changed lines from <200 B of wiki edits are suspects; a `WARNING` prints when they reach a quarter of the diffed pages. Flags: `--top N`, `--context N`, `--pages NAME,NAME`, `--quiet`, `--diff PATH`, `--edits PATH`, `--pages-dir PATH` |
| Renderer drift (read before trusting a triage ranking) | The Cloudflare renderer's output format is **not stable across time** — on 2026-08-15 it began emitting frontmatter, badges, TOC list items and nested-HTML stat cells, and triage reported 111/111 pages changed until the filters were extended and the corpus re-crawled. Two rules follow. **(1)** Detect it with triage's drift check, not the changed-page count — since `--days` bounds the query, `update` only queues genuinely edited pages, so a clean run shows ~all of them changed (2026-10-01: 65/66). If the check warns, rank by `python dev/wiki/crawl.py changes` (the wiki's own byte deltas + edit comments), which bypasses the renderer entirely. **(2)** Never leave `dev/wiki/pages/` holding a **mix** of formats: a mixed corpus diffs dirty on every page's first re-crawl no matter what the filters do. Normalise it with a full re-crawl (delete `pages/*.md`, then `python dev/wiki/crawl.py crawl --workers 1`, ~2 h at 1 req/12 s). |
| `dev/wiki/urls.json` | Curated list of 647 English gameplay wiki page titles to crawl |
| `dev/wiki/` | Per-page wiki corpus (647 `.md` files); **gitignored** — regenerate with `python dev/wiki/crawl.py crawl` (~2 h at 1 req/12 s) |
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

---

## Arithmetic

All numeric values use `fractions.Fraction` internally. Only converted to `float` in `format_output()`. This eliminates floating-point accumulation errors.

**Exception:** beacon speed bonus uses `math.sqrt(count)` which is irrational, so `machine_count` becomes `float` for any recipe whose machine has a beacon config. Runs with no beacons remain fully `Fraction`.

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

### Fallback routing (data-driven — no fallback tables)

The old `CATEGORY_LOCATION_FALLBACK` / `HARD_CATEGORY_REQUIRES` tables were
removed in the 2.1.8 dataset migration. Routing is now derived from the
recipe's `categories` array plus each machine's `crafting_categories`
(the `register_machines` registry):

- When a recipe's premium machine is planet-locked at the current location,
  `get_machine` falls back to the **assembler** if the recipe also lists a
  generic crafting category (`crafting`, `advanced-crafting`,
  `crafting-with-fluid`), else to another **unlocked dedicated machine** in
  one of its categories.
- A recipe that can ONLY run on locked planet-locked machines (no generic
  category, no unlocked alternative) is filtered out by `pick_recipe` via
  `recipe_requires_locked_machine`.

Explicit `--recipe` and `--recipe-machine` overrides bypass the filtering (user opt-in).

---

## Recipe Selection Logic (`pick_recipe`)

Priority (in `pick_recipe`):
1. Explicit `--recipe ITEM=RECIPE` override passed in from CLI — bypasses planet filtering entirely.
2. Filtering (not selection): when `planet_props` given, remove candidates whose `surface_conditions` are not satisfied; when `location_unlocks` given, drop candidates that can ONLY run on a planet-locked machine not unlocked here (`recipe_requires_locked_machine`). If all candidates are filtered out, return `None`.
3. Entry in `RECIPE_DEFAULTS_BY_LOCATION[location]` — location-specific preferred recipe. Checked BEFORE exact-key-match so location correctness wins over the implicit "recipe key == item key" heuristic.
4. Recipe whose `key == item_key` (exact match).
5. `advanced-oil-processing` (legacy fallback for oil products).
6. Entry in `RECIPE_DEFAULTS` (hard-coded preferred recipes that override the order-sort default when the order-sort winner is un-automatable or causes circular dependencies in the solver).
7. First candidate after sorting all candidates by the game's `order` field.

The order-sort in step 7 ensures the game-preferred variant is chosen when no earlier rule matches (e.g. `solid-fuel-from-petroleum-gas` over the less-efficient heavy-oil and petroleum-gas variants).

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

`dev/test_cli.py` contains 281 tests. For what each class covers, read the `class Test*` definitions in the file.

### `dev/test_quality_planner.py` (411 tests)

Covers the V1+V2 legendary planner in `dev/quality_planner.py`, plus the V3-partial LDS-shuffle wiring. For what each class covers, read the `class Test*` definitions and their docstrings in the file.

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
