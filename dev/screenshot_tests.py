#!/usr/bin/env python3
"""
Generate screenshots of all 30 machine-quality × beacon-quality combinations
for the dashboard production-step cards.

Usage:
    pip install playwright
    playwright install chromium
    python dev/screenshot_tests.py

Output: dev/screenshots/mq-{quality}__[no-beacon|bq-{quality}].png
"""

import asyncio
import base64
import json
import os
import tempfile

from playwright.async_api import async_playwright

DEV_DIR        = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_SRC  = os.path.join(DEV_DIR, "dashboard.html")
SCREENSHOTS_DIR = os.path.join(DEV_DIR, "screenshots")

QUALITIES = ["normal", "uncommon", "rare", "epic", "legendary"]

# From cli.py constants
BEACON_EFFECTIVITY = {"normal": 1.5, "uncommon": 1.7, "rare": 1.9, "epic": 2.1, "legendary": 2.5}
BEACON_POWER_KW    = {"normal": 480, "uncommon": 400, "rare": 320, "epic": 240, "legendary": 80}
SPEED3_BONUS = 0.5  # speed-3 bonus per module

# Beacon layout configs (count + module types) vary by housing quality.
# Module quality is assigned independently using a +2 offset so it never
# matches the housing quality and gives a spread across all 5 tiers.
BEACON_LAYOUTS = {
    "normal":    {"count": 8, "module_types": [("speed", 2)]},
    "uncommon":  {"count": 6, "module_types": [("speed", 2)]},
    "rare":      {"count": 5, "module_types": [("speed", 1), ("efficiency", 1)]},
    "epic":      {"count": 4, "module_types": [("speed", 1), ("efficiency", 1)]},
    "legendary": {"count": 3, "module_types": [("speed", 2)]},
}

def beacon_module_quality(beacon_quality: str) -> str:
    """Return a module quality that differs from the housing quality (+2 offset)."""
    return QUALITIES[(QUALITIES.index(beacon_quality) + 2) % len(QUALITIES)]

def make_beacon_spec(beacon_quality: str) -> dict:
    layout = BEACON_LAYOUTS[beacon_quality]
    mq = beacon_module_quality(beacon_quality)
    return {
        "count": layout["count"],
        "modules": [{"count": c, "type": t, "tier": 3, "quality": mq}
                    for t, c in layout["module_types"]],
    }

# Machine module configs vary by machine quality: different combos + matching quality tier.
def _m(count, mtype, quality):
    return {"count": count, "type": mtype, "tier": 3, "quality": quality}

MACHINE_MODULE_CONFIGS = {
    "normal":    [_m(4, "prod",       "normal")],
    "uncommon":  [_m(3, "prod",       "uncommon"), _m(1, "speed",      "uncommon")],
    "rare":      [_m(2, "prod",       "rare"),     _m(2, "speed",      "rare")],
    "epic":      [_m(2, "prod",       "epic"),     _m(1, "speed",      "epic"),  _m(1, "efficiency", "epic")],
    "legendary": [_m(4, "speed",      "legendary")],
}


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


def encode_state(state: dict) -> str:
    """Encode state the same way dashboard's encodeState() does."""
    json_bytes = json.dumps(state, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(json_bytes).decode("ascii")


def build_html(state: dict) -> str:
    """Inject state into localStorage seed script before the first <script> tag."""
    encoded = encode_state(state)
    with open(DASHBOARD_SRC, encoding="utf-8") as f:
        html = f.read()
    seed = f"<script>\nlocalStorage.setItem('factorio_engineer_state', {repr(encoded)});\n</script>\n"
    return html.replace("<script>", seed + "<script>", 1)


def combinations():
    """Yield (filename, machine_quality, beacon_quality, with_beacon) for all 30 combos."""
    # Group 1: no beacons
    for mq in QUALITIES:
        yield f"mq-{mq}__no-beacon.png", mq, "normal", False
    # Groups 2–6: machine quality × beacon quality
    for mq in QUALITIES:
        for bq in QUALITIES:
            yield f"mq-{mq}__bq-{bq}.png", mq, bq, True


async def run():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 900, "height": 600},
            device_scale_factor=2,
        )

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
                # tab=lines shows the production cards; expand=all opens all cards
                await page.goto(f"file://{tmp_path}?tab=lines&expand=all")
                await page.wait_for_selector(".line-card", timeout=10_000)
                # Small pause so fonts/layout settle
                await page.wait_for_timeout(200)

                card = page.locator(".line-card").first
                out_path = os.path.join(SCREENSHOTS_DIR, filename)
                await card.screenshot(path=out_path)
                await page.close()

                total += 1
                label = f"no-beacon" if not with_beacon else f"bq={bq}"
                print(f"[{total:02d}/30] mq={mq} {label:20s}  →  {filename}")
            finally:
                os.unlink(tmp_path)

        await browser.close()

    print(f"\nDone — {total} screenshots saved to {SCREENSHOTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(run())
