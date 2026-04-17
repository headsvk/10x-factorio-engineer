#!/usr/bin/env python3
"""
Generate screenshots of the dashboard across all major visual states.

Groups:
  1. 30 machine-quality × beacon-quality combinations (line cards, expanded)
  2. 13 dashboard section / tab screenshots (header, science, location bar, etc.)
  3. 7 expanded line card variants from real CLI data (planet-specific machines)
  4. 2 full-page README screenshots (dark + light theme)

Usage:
    pip install playwright
    playwright install chromium
    python dev/screenshot_tests.py

Output: dev/screenshots/
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile

from playwright.async_api import async_playwright

DEV_DIR         = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_SRC   = os.path.join(DEV_DIR, "dashboard.html")
SCREENSHOTS_DIR = os.path.join(DEV_DIR, "screenshots")
CLI_PATH        = os.path.join(os.path.dirname(DEV_DIR), "10x-factorio-engineer", "assets", "cli.py")

QUALITIES = ["normal", "uncommon", "rare", "epic", "legendary"]

# From cli.py constants
BEACON_EFFECTIVITY = {"normal": 1.5, "uncommon": 1.7, "rare": 1.9, "epic": 2.1, "legendary": 2.5}
BEACON_POWER_KW    = {"normal": 480, "uncommon": 400, "rare": 320, "epic": 240, "legendary": 80}
SPEED3_BONUS = 0.5  # speed-3 bonus per module

BEACON_LAYOUTS = {
    "normal":    {"count": 8, "module_types": [("speed", 2)]},
    "uncommon":  {"count": 6, "module_types": [("speed", 2)]},
    "rare":      {"count": 5, "module_types": [("speed", 1), ("efficiency", 1)]},
    "epic":      {"count": 4, "module_types": [("speed", 1), ("efficiency", 1)]},
    "legendary": {"count": 3, "module_types": [("speed", 2)]},
}

def beacon_module_quality(beacon_quality: str) -> str:
    return QUALITIES[(QUALITIES.index(beacon_quality) + 2) % len(QUALITIES)]

def make_beacon_spec(beacon_quality: str) -> dict:
    layout = BEACON_LAYOUTS[beacon_quality]
    mq = beacon_module_quality(beacon_quality)
    return {
        "count": layout["count"],
        "modules": [{"count": c, "type": t, "tier": 3, "quality": mq}
                    for t, c in layout["module_types"]],
    }

def _m(count, mtype, quality):
    return {"count": count, "type": mtype, "tier": 3, "quality": quality}

MACHINE_MODULE_CONFIGS = {
    "normal":    [_m(4, "prod",       "normal")],
    "uncommon":  [_m(3, "prod",       "uncommon"), _m(1, "speed",      "uncommon")],
    "rare":      [_m(2, "prod",       "rare"),     _m(2, "speed",      "rare")],
    "epic":      [_m(2, "prod",       "epic"),     _m(1, "speed",      "epic"),  _m(1, "efficiency", "epic")],
    "legendary": [_m(4, "speed",      "legendary")],
}


# ── Shared helpers ────────────────────────────────────────────────────────────

def encode_state(state: dict) -> str:
    json_bytes = json.dumps(state, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(json_bytes).decode("ascii")


def build_html(state: dict, light_theme: bool = False) -> str:
    """Inject state (and optional theme) into localStorage before the first <script> tag."""
    encoded = encode_state(state)
    with open(DASHBOARD_SRC, encoding="utf-8") as f:
        html = f.read()
    theme_line = f"localStorage.setItem('theme', '{'light' if light_theme else 'dark'}');\n"
    seed = (
        f"<script>\n"
        f"{theme_line}"
        f"localStorage.setItem('factorio_engineer_state', {repr(encoded)});\n"
        f"</script>\n"
    )
    return html.replace("<script>", seed + "<script>", 1)


def run_cli(*args) -> dict:
    """Run cli.py with given args and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, CLI_PATH, *args],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def make_minimal_line(item, label, target_rate, effective_rate,
                      wip=False, notes=None, bus_inputs=None):
    """Line with a stub cli_result — renders card header but no expanded steps."""
    return {
        "item": item,
        "label": label,
        "target_rate": target_rate,
        "effective_rate": effective_rate,
        **({"wip": True} if wip else {}),
        **({"player_notes": notes} if notes else {}),
        "cli_result": {
            "item": item,
            "rate_per_min": effective_rate,
            "production_steps": [],
            "raw_resources": {},
            "co_products": {},
            "miners_needed": {},
            "total_power_mw": 0.0,
            "total_power_mw_ceil": 0.0,
            "bus_inputs": bus_inputs or {},
        },
    }


# ── Group 1: quality combination state factory ────────────────────────────────

def make_state(machine_quality: str, beacon_quality: str, with_beacon: bool) -> dict:
    if with_beacon:
        spec = make_beacon_spec(beacon_quality)
        effectivity = BEACON_EFFECTIVITY[beacon_quality]
        speed_mods = sum(m["count"] for m in spec["modules"] if m["type"] == "speed")
        beacon_speed_bonus = spec["count"] * speed_mods * SPEED3_BONUS * effectivity
        beacon_power_kw    = spec["count"] * BEACON_POWER_KW[beacon_quality]
        default_beacon     = spec
    else:
        beacon_speed_bonus = 0.0
        beacon_power_kw    = 0.0
        default_beacon     = None

    step = {
        "recipe": "electronic-circuit",
        "machine": "assembling-machine-3",
        "machine_count": 4.0,
        "machine_count_ceil": 4,
        "outputs": {"electronic-circuit": 60.0},
        "inputs": {"iron-plate": 60.0, "copper-cable": 180.0},
        "machine_quality": machine_quality,
        "beacon_speed_bonus": beacon_speed_bonus,
        "power_kw": 600.0,
        "power_kw_ceil": 600.0,
        "beacon_power_kw": beacon_power_kw,
    }

    cli_result = {
        "item": "electronic-circuit",
        "rate_per_min": 60.0,
        "dataset": "space-age",
        "assembler": 3,
        "furnace": "electric",
        "miner": "electric",
        "machine_quality": machine_quality,
        "beacon_quality": beacon_quality,
        "default_beacon": default_beacon,
        "module_configs": {"assembling-machine-3": MACHINE_MODULE_CONFIGS[machine_quality]},
        "beacon_configs": {},
        "recipe_module_overrides": {},
        "recipe_beacon_overrides": {},
        "production_steps": [step],
        "total_power_mw": 0.6,
        "total_power_mw_ceil": 0.6,
        "bus_inputs": {},
    }

    beacon_label = beacon_quality if with_beacon else "none"
    return {
        "save_name": f"mq={machine_quality} bq={beacon_label}",
        "dataset": "space-age",
        "assembler": 3,
        "furnace": "electric",
        "machine_quality": machine_quality,
        "beacon_quality": beacon_quality,
        "module_configs": {},
        "beacon_configs": {},
        "recipe_overrides": {},
        "machine_overrides": {},
        "preferred_belt": "blue",
        "locations": [
            {
                "id": "nauvis",
                "type": "planet",
                "label": "Nauvis",
                "bus_items": [],
                "targets": {},
                "bottlenecks": [],
                "next_steps": [],
                "lines": [
                    {
                        "item": "electronic-circuit",
                        "label": "Electronic Circuit",
                        "target_rate": 60,
                        "effective_rate": 60,
                        "cli_result": cli_result,
                    }
                ],
            }
        ],
        "chat_log": [],
    }


def combinations():
    for mq in QUALITIES:
        yield f"mq-{mq}__no-beacon.png", mq, "normal", False
    for mq in QUALITIES:
        for bq in QUALITIES:
            yield f"mq-{mq}__bq-{bq}.png", mq, bq, True


# ── Group 2: section / tab state factories ────────────────────────────────────

def _base_state(save_name="Test Factory", dataset="space-age") -> dict:
    return {
        "save_name": save_name,
        "dataset": dataset,
        "assembler": 3,
        "furnace": "electric",
        "machine_quality": "normal",
        "beacon_quality": "normal",
        "module_configs": {"assembling-machine-3": MACHINE_MODULE_CONFIGS["normal"]},
        "beacon_configs": {},
        "recipe_overrides": {},
        "machine_overrides": {},
        "preferred_belt": "blue",
        "chat_log": [],
    }


def _loc(loc_id, label, lines=None, bus_items=None, targets=None,
         bottlenecks=None, next_steps=None, loc_type="planet"):
    return {
        "id": loc_id,
        "type": loc_type,
        "label": label,
        "bus_items": bus_items or [],
        "targets": targets or {},
        "bottlenecks": bottlenecks or [],
        "next_steps": next_steps or [],
        "lines": lines or [],
    }


def make_state_header_badges() -> dict:
    """Header with Space Age badge, Legendary Machines, Blue Belt, Modules, and SPM badge."""
    state = _base_state("Space Age Factory")
    state["machine_quality"] = "legendary"
    state["preferred_belt"] = "blue"
    line = make_minimal_line(
        "automation-science-pack", "Automation Science", 90, 90,
    )
    state["locations"] = [_loc(
        "nauvis", "Nauvis",
        lines=[line],
        targets={"automation-science-pack": 90},
    )]
    return state


def make_state_science_vanilla() -> dict:
    """4 science packs at ok/warn/bad/missing rates — triggers 2-column grid."""
    state = _base_state("Vanilla Science", dataset="vanilla")
    state["module_configs"] = {}
    lines = [
        make_minimal_line("automation-science-pack",  "Automation Science",  90,  90),
        make_minimal_line("logistic-science-pack",    "Logistic Science",    90,  72),
        make_minimal_line("chemical-science-pack",    "Chemical Science",    90,  45),
        make_minimal_line("military-science-pack",    "Military Science",    90,   0),
    ]
    state["locations"] = [_loc(
        "nauvis", "Nauvis",
        lines=lines,
        targets={
            "automation-science-pack": 90,
            "logistic-science-pack": 90,
            "chemical-science-pack": 90,
            "military-science-pack": 90,
        },
    )]
    return state


def make_state_science_space_age() -> dict:
    """Space Age dataset — 2 locations both contributing to automation science."""
    state = _base_state("Multi-Planet Science")
    nauvis_line = make_minimal_line(
        "automation-science-pack", "Automation Science", 60, 60,
    )
    vulcanus_line = make_minimal_line(
        "automation-science-pack", "Automation Science (Vulcanus)", 30, 30,
    )
    state["locations"] = [
        _loc("nauvis",   "Nauvis",   lines=[nauvis_line],
             targets={"automation-science-pack": 90}),
        _loc("vulcanus", "Vulcanus", lines=[vulcanus_line],
             targets={"automation-science-pack": 90}),
    ]
    return state


def make_state_location_bar() -> dict:
    """Space Age — 3 planet locations (Nauvis active)."""
    state = _base_state("Three-Planet Factory")
    state["locations"] = [
        _loc("nauvis",   "Nauvis",   lines=[make_minimal_line("iron-plate", "Iron Plate", 60, 60)]),
        _loc("vulcanus", "Vulcanus", lines=[]),
        _loc("gleba",    "Gleba",    lines=[]),
    ]
    return state


def make_state_bus_balance() -> dict:
    """4 bus items at different saturations: ok / warn / full / deficit."""
    state = _base_state("Bus Balance Test")
    # Supply declared in bus_items; demand via bus_inputs on lines
    bus_items = [
        {"item": "iron-plate",    "rate": 2400},
        {"item": "copper-plate",  "rate": 1800},
        {"item": "steel-plate",   "rate": 600},
        {"item": "petroleum-gas", "rate": 400, "fluid": True},
    ]
    line = make_minimal_line(
        "electronic-circuit", "Green Circuits", 60, 60,
        bus_inputs={
            "iron-plate":    720,   # 30 %
            "copper-plate":  1500,  # 83 %
            "steel-plate":   600,   # 100 %
            "petroleum-gas": 510,   # 127 % → deficit
        },
    )
    state["locations"] = [_loc(
        "nauvis", "Nauvis",
        lines=[line],
        bus_items=bus_items,
    )]
    return state


def make_state_overview() -> dict:
    """Overview tab: ⚡ Power section + bus balance."""
    state = _base_state("Overview State")
    bus_items = [
        {"item": "iron-plate",   "rate": 2400},
        {"item": "copper-plate", "rate": 1800},
    ]
    line = make_minimal_line(
        "electronic-circuit", "Green Circuits", 120, 120,
        bus_inputs={"iron-plate": 720, "copper-plate": 540},
    )
    # Give the line non-zero power so the ⚡ Power section renders
    line["cli_result"]["total_power_mw"]      = 2.4
    line["cli_result"]["total_power_mw_ceil"] = 2.4
    state["locations"] = [_loc(
        "nauvis", "Nauvis",
        lines=[line],
        bus_items=bus_items,
    )]
    return state


def make_state_lines_statuses() -> dict:
    """Lines tab (collapsed): ok / warn / bad / wip status variants."""
    state = _base_state("Status Variants")
    lines = [
        make_minimal_line("automation-science-pack", "Automation Science",  90,  90),
        make_minimal_line("logistic-science-pack",   "Logistic Science",    90,  72),
        make_minimal_line("chemical-science-pack",   "Chemical Science",    90,  40),
        make_minimal_line("military-science-pack",   "Military Science (WIP)", 60, 60, wip=True),
    ]
    state["locations"] = [_loc("nauvis", "Nauvis", lines=lines)]
    return state


def make_state_with_bottleneck() -> dict:
    """Bottleneck banner + Actions tab (bottlenecks + next steps) + 3 lines for badge count."""
    state = _base_state("Bottleneck Factory")
    lines = [
        make_minimal_line("automation-science-pack", "Automation Science", 90, 90),
        make_minimal_line("logistic-science-pack",   "Logistic Science",   90, 72),
        make_minimal_line("chemical-science-pack",   "Chemical Science",   90, 40),
    ]
    state["locations"] = [_loc(
        "nauvis", "Nauvis",
        lines=lines,
        bottlenecks=[
            "petroleum-gas bus at 400/min; processing-unit line needs 510/min — 110/min short.",
            "iron-plate bus undersupplied by 240/min during peak hours.",
        ],
        next_steps=[
            "Expand pumpjack field or add heavy-oil cracking to close petroleum-gas gap.",
            "Add 4 more electric furnace stacks to iron-plate smelting.",
        ],
    )]
    return state


def make_state_chat() -> dict:
    """Chat tab — 3 messages (player → claude → player)."""
    state = _base_state("Chat Test")
    state["chat_log"] = [
        {"from": "player", "text": "Green circuit line is up — about 60/min from 4 assembler-3s."},
        {"from": "claude", "text": "Logged. 4 Assembler 3s → 60 Green Circuits/min. "
                                   "Raw demand: 90 copper-ore/min, 60 iron-ore/min. "
                                   "Make sure your bus has 90 copper-plate/min headroom."},
        {"from": "player", "text": "Starting a processing unit line next. Using 2×Prod-3 on the assemblers."},
    ]
    state["locations"] = [_loc(
        "nauvis", "Nauvis",
        lines=[make_minimal_line("electronic-circuit", "Green Circuits", 60, 60)],
    )]
    return state


SECTION_SCENARIOS = [
    # (filename,                            state_factory,               selector,             tab,       light)
    ("section__header-badges.png",          make_state_header_badges,    ".header",            "overview", False),
    ("section__science-vanilla.png",        make_state_science_vanilla,  ".science-section",   "overview", False),
    ("section__science-space-age.png",      make_state_science_space_age,".science-section",   "overview", False),
    ("section__location-bar.png",           make_state_location_bar,     ".loc-bar",           "overview", False),
    ("section__bottleneck-banner.png",      make_state_with_bottleneck,  ".bottleneck-banner", "overview", False),
    ("section__tab-list.png",               make_state_with_bottleneck,  ".tab-list",          "overview", False),
    ("section__bus-balance.png",            make_state_bus_balance,      ".bus-section",       "overview", False),
    ("tab__overview.png",                   make_state_overview,         ".tab-panel.active",  "overview", False),
    ("tab__lines-collapsed.png",            make_state_lines_statuses,   ".tab-panel.active",  "lines",    False),
    ("tab__actions.png",                    make_state_with_bottleneck,  ".tab-panel.active",  "issues",   False),
    ("tab__chat.png",                       make_state_chat,             ".tab-panel.active",  "chat",     False),
    ("light__tab-lines-collapsed.png",      make_state_lines_statuses,   ".tab-panel.active",  "lines",    True),
    ("light__section-science-vanilla.png",  make_state_science_vanilla,  ".science-section",   "overview", True),
]


# ── Group 3: line card variant state factories ────────────────────────────────

def _line_card_state(save_name, loc_id, loc_label, item, line_label,
                     rate, cli_result, dataset="space-age") -> dict:
    state = _base_state(save_name, dataset=dataset)
    state["locations"] = [_loc(
        loc_id, loc_label,
        lines=[{
            "item": item,
            "label": line_label,
            "target_rate": rate,
            "effective_rate": rate,
            "cli_result": cli_result,
        }],
    )]
    return state


def make_state_line_foundry_vulcanus():
    cli = run_cli("--item", "metallurgic-science-pack", "--rate", "30", "--location", "vulcanus")
    return _line_card_state(
        "Vulcanus – Metallurgic Science", "vulcanus", "Vulcanus",
        "metallurgic-science-pack", "Metallurgic Science", 30, cli,
    )


def make_state_line_biochamber_gleba():
    cli = run_cli("--item", "agricultural-science-pack", "--rate", "30", "--location", "gleba")
    return _line_card_state(
        "Gleba – Agricultural Science", "gleba", "Gleba",
        "agricultural-science-pack", "Agricultural Science", 30, cli,
    )


def make_state_line_centrifuge_uranium():
    cli = run_cli("--item", "uranium-fuel-cell", "--rate", "30")
    return _line_card_state(
        "Uranium Fuel Cells", "nauvis", "Nauvis",
        "uranium-fuel-cell", "Uranium Fuel Cell", 30, cli,
    )


def make_state_line_oil_refinery():
    cli = run_cli("--item", "processing-unit", "--rate", "10")
    return _line_card_state(
        "Processing Units", "nauvis", "Nauvis",
        "processing-unit", "Processing Unit", 10, cli,
    )


def make_state_line_holmium_fulgora():
    cli = run_cli(
        "--item", "holmium-plate", "--rate", "30",
        "--location", "fulgora",
        "--miner", "big",
        "--bus-item", "holmium-ore",
        "--bus-item", "lava",
    )
    return _line_card_state(
        "Fulgora – Holmium Plate", "fulgora", "Fulgora",
        "holmium-plate", "Holmium Plate", 30, cli,
    )


def make_state_line_cryogenic_aquilo():
    cli = run_cli(
        "--item", "cryogenic-science-pack", "--rate", "10",
        "--location", "aquilo",
        "--bus-item", "holmium-plate",
        "--bus-item", "tungsten-plate",
    )
    return _line_card_state(
        "Aquilo – Cryogenic Science", "aquilo", "Aquilo",
        "cryogenic-science-pack", "Cryogenic Science", 10, cli,
    )


def make_state_line_space_crusher():
    cli = run_cli("--item", "space-science-pack", "--rate", "30", "--location", "space-platform")
    return _line_card_state(
        "Space Platform – Space Science", "space-platform", "Space Platform",
        "space-science-pack", "Space Science", 30, cli,
        # space-platform is not in PLANET_IDS so type must be space-platform
    )


LINE_CARD_SCENARIOS = [
    ("line-card__foundry-vulcanus.png",    make_state_line_foundry_vulcanus),
    ("line-card__biochamber-gleba.png",    make_state_line_biochamber_gleba),
    ("line-card__centrifuge-uranium.png",  make_state_line_centrifuge_uranium),
    ("line-card__oil-refinery.png",        make_state_line_oil_refinery),
    ("line-card__holmium-fulgora.png",     make_state_line_holmium_fulgora),
    ("line-card__cryogenic-aquilo.png",    make_state_line_cryogenic_aquilo),
    ("line-card__space-crusher.png",       make_state_line_space_crusher),
]


# ── Group 4: README full-page screenshots ────────────────────────────────────

def make_state_readme() -> dict:
    """Rich multi-planet state that showcases science overview, bus balance, and a bottleneck."""
    state = _base_state("Mid-Game Factory")
    state["module_configs"] = {"assembling-machine-3": MACHINE_MODULE_CONFIGS["normal"]}
    bus_items = [
        {"item": "iron-plate",    "rate": 7200},
        {"item": "copper-plate",  "rate": 10800},
        {"item": "steel-plate",   "rate": 1800},
        {"item": "petroleum-gas", "rate": 400, "fluid": True},
    ]
    lines = [
        make_minimal_line("automation-science-pack",  "Automation Science",  90,  90,
                          bus_inputs={"iron-plate": 90}),
        make_minimal_line("logistic-science-pack",    "Logistic Science",    90,  72,
                          bus_inputs={"iron-plate": 72, "copper-plate": 72}),
        make_minimal_line("chemical-science-pack",    "Chemical Science",    90,  45,
                          bus_inputs={"copper-plate": 135, "petroleum-gas": 405}),
        make_minimal_line("military-science-pack",    "Military Science",    90,   0),
        make_minimal_line("electronic-circuit",       "Green Circuits",     1800, 1800,
                          bus_inputs={"iron-plate": 1800, "copper-plate": 5400}),
    ]
    state["locations"] = [
        _loc("nauvis", "Nauvis",
             lines=lines,
             bus_items=bus_items,
             targets={
                 "automation-science-pack": 90,
                 "logistic-science-pack": 90,
                 "chemical-science-pack": 90,
                 "military-science-pack": 90,
             },
             bottlenecks=[
                 "petroleum-gas bus at 400/min; chemical-science-pack needs 405/min — 5/min short.",
             ],
             next_steps=[
                 "Add 1 more oil refinery or expand cracking to close petroleum-gas gap.",
                 "Build military-science-pack line: 6 assembling-machine-3s.",
             ]),
        _loc("vulcanus", "Vulcanus", lines=[]),
    ]
    return state


README_SCENARIOS = [
    # (filename,             state_factory,    tab,        light)
    ("readme__dark.png",   make_state_readme, "overview", False),
    ("readme__light.png",  make_state_readme, "overview", True),
]


# ── Playwright helpers ────────────────────────────────────────────────────────

async def capture_section(context, state, selector, tab, out_path,
                           light_theme=False, url_suffix=""):
    """Render state, navigate to tab, and screenshot the first matching element."""
    html = build_html(state, light_theme=light_theme)
    with tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(html)
        tmp_path = tmp.name
    try:
        page = await context.new_page()
        await page.goto(f"file://{tmp_path}?tab={tab}{url_suffix}")
        await page.wait_for_selector(selector, timeout=10_000)
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(200)
        await page.locator(selector).first.screenshot(path=out_path)
        await page.close()
    finally:
        os.unlink(tmp_path)


async def capture_full_page(context, state, tab, out_path, light_theme=False):
    """Render state and screenshot the full viewport (header + tabs + content)."""
    html = build_html(state, light_theme=light_theme)
    with tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(html)
        tmp_path = tmp.name
    try:
        page = await context.new_page()
        await page.set_viewport_size({"width": 900, "height": 720})
        await page.goto(f"file://{tmp_path}?tab={tab}")
        await page.wait_for_selector(".tab-panel.active", timeout=10_000)
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(300)
        await page.screenshot(path=out_path, full_page=True)
        await page.close()
    finally:
        os.unlink(tmp_path)


# ── Test group runners ────────────────────────────────────────────────────────

async def run_quality_combinations(context):
    total = 0
    for filename, mq, bq, with_beacon in combinations():
        state = make_state(mq, bq, with_beacon)
        html  = build_html(state)

        with tempfile.NamedTemporaryFile(
            suffix=".html", mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(html)
            tmp_path = tmp.name

        try:
            page = await context.new_page()
            await page.goto(f"file://{tmp_path}?tab=lines&expand=all")
            await page.wait_for_selector(".line-card", timeout=10_000)
            await page.evaluate("document.fonts.ready")
            await page.wait_for_timeout(200)

            card = page.locator(".line-card").first
            out_path = os.path.join(SCREENSHOTS_DIR, filename)
            await card.screenshot(path=out_path)
            await page.close()

            total += 1
            label = "no-beacon" if not with_beacon else f"bq={bq}"
            print(f"  [{total:02d}/30] mq={mq} {label:20s}  →  {filename}")
        finally:
            os.unlink(tmp_path)

    return total


async def run_sections(context):
    total = 0
    for filename, state_factory, selector, tab, light_theme in SECTION_SCENARIOS:
        state    = state_factory()
        out_path = os.path.join(SCREENSHOTS_DIR, filename)
        theme_tag = " [light]" if light_theme else ""
        try:
            await capture_section(context, state, selector, tab, out_path,
                                   light_theme=light_theme)
            total += 1
            print(f"  section  {filename}{theme_tag}")
        except Exception as exc:
            print(f"  SKIP     {filename} — {exc}")

    return total


async def run_line_card_variants(context):
    total = 0
    for filename, state_factory in LINE_CARD_SCENARIOS:
        out_path = os.path.join(SCREENSHOTS_DIR, filename)
        try:
            state = state_factory()
            # Patch space-platform location type so the location bar renders
            for loc in state.get("locations", []):
                if loc["id"] == "space-platform":
                    loc["type"] = "space-platform"
            await capture_section(
                context, state, ".line-card", "lines", out_path,
                url_suffix="&expand=all",
            )
            total += 1
            print(f"  line-card {filename}")
        except Exception as exc:
            print(f"  SKIP      {filename} — {exc}")

    return total


async def run_readme_screenshots(context):
    total = 0
    for filename, state_factory, tab, light_theme in README_SCENARIOS:
        state    = state_factory()
        out_path = os.path.join(SCREENSHOTS_DIR, filename)
        theme_tag = " [light]" if light_theme else " [dark]"
        try:
            await capture_full_page(context, state, tab, out_path, light_theme=light_theme)
            total += 1
            print(f"  readme   {filename}{theme_tag}")
        except Exception as exc:
            print(f"  SKIP     {filename} — {exc}")
    return total


# ── Entry point ───────────────────────────────────────────────────────────────

async def run():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 900, "height": 600},
            device_scale_factor=2,
        )

        print("\n── Group 1: quality combinations (30) ──")
        n1 = await run_quality_combinations(context)

        print("\n── Group 2: section / tab screenshots ──")
        n2 = await run_sections(context)

        print("\n── Group 3: line card variants ──")
        n3 = await run_line_card_variants(context)

        print("\n── Group 4: README screenshots ──")
        n4 = await run_readme_screenshots(context)

        await browser.close()

    total = n1 + n2 + n3 + n4
    print(f"\nDone — {total} screenshots saved to {SCREENSHOTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(run())
