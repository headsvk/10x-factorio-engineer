#!/usr/bin/env python3
"""
update_research.py — apply a research-level change to a factory state and
re-run every affected production line through cli.py.

Manually editing `research_levels` and then re-running the right lines by hand
is fiddly (which lines have miners? which touch a boosted recipe?). This script
does both: it updates the top-level `research_levels` and re-solves only the
lines the change actually affects, rewriting each line's `cli_result` in place.

Usage:
    python dev/update_research.py TECH=LEVEL [TECH=LEVEL ...] [options]
    python dev/update_research.py --list [--state PATH]

Options:
    --state PATH   Factory-state JSON to update (default: dev/my-factory.json)
    --dry-run      Report what would change; don't write the file
    --list         Print current research levels + how many lines each tech
                   affects, then exit

Examples:
    python dev/update_research.py mining-productivity=14 scrap-recycling-productivity=1
    python dev/update_research.py steel-productivity=6 --dry-run
    python dev/update_research.py --list

A TECH is one of cli.py's recipe/mining productivity researches (changing it
re-runs the affected lines) or a lab-only tech — research-productivity /
lab-research-speed — which the dashboard recomputes from `lab_config`, so those
update the field but trigger no line re-run. LEVEL 0 removes the entry.

Each line's command is reconstructed from its `cli_args` plus the shared
top-level config (assembler, furnace, qualities, modules, beacons, recipe
overrides), exactly as the SKILL.md workflow prescribes — so re-running with an
unchanged research set reproduces the existing `cli_result` byte-for-byte (a
good self-check via --dry-run).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_CLI = os.path.join(_REPO, "10x-factorio-engineer", "assets", "cli.py")
sys.path.insert(0, os.path.join(_REPO, "10x-factorio-engineer", "assets"))
import cli  # noqa: E402  (path set above)

DEFAULT_STATE = os.path.join(_HERE, "my-factory.json")

# Techs cli.py understands (recipe + mining productivity). Changing one re-runs
# the lines it touches.
CLI_TECHS = set(cli.PRODUCTIVITY_RESEARCH)
# Lab-only techs: stored in research_levels but never passed to cli.py — the
# dashboard derives lab counts / eSPM from them. Changing one needs no re-run.
LAB_TECHS = {"research-productivity", "lab-research-speed"}
VALID_TECHS = CLI_TECHS | LAB_TECHS


# ── state IO ────────────────────────────────────────────────────────────────

def load_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    # newline="" keeps LF endings (Windows text mode would otherwise write CRLF).
    with open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def iter_lines(state: dict):
    """Yield (location, line) for every line in the state."""
    for loc in state.get("locations", []):
        for line in loc.get("lines", []):
            yield loc, line


def cli_location(loc: dict, ca: dict) -> str:
    """Resolve the --location value for a line. The state's location id can be
    an instance name (e.g. 'space-platform-0') while the CLI wants the canonical
    key ('space-platform'). cli_args.location wins when present; otherwise a
    'space-platform' type maps to 'space-platform' and planets use their id."""
    if ca.get("location"):
        return ca["location"]
    if loc.get("type") == "space-platform":
        return "space-platform"
    return loc["id"]


# ── affected-line detection ─────────────────────────────────────────────────

def line_affected_by(tech: str, line: dict) -> bool:
    """True if changing `tech` would change this line's cli_result."""
    cr = line.get("cli_result") or {}
    if tech == "mining-productivity":
        miners = cr.get("miners_needed") or {}
        return any(m.get("machine") != "offshore-pump" for m in miners.values())
    boosted = set(cli.PRODUCTIVITY_RESEARCH.get(tech, []))
    recipes = {s["recipe"] for s in cr.get("production_steps", [])}
    return bool(boosted & recipes)


# ── command reconstruction ──────────────────────────────────────────────────

def _mod_flags(flag: str, mapping: dict) -> list:
    """Emit one `flag KEY=count:type:tier:quality` per module spec."""
    out = []
    for key, specs in (mapping or {}).items():
        for s in specs:
            out += [flag, f"{key}={s['count']}:{s['type']}:{s['tier']}:{s.get('quality', 'normal')}"]
    return out


def _beacon_flags(flag: str, mapping: dict) -> list:
    """Emit `flag [KEY=]bcount:mcount:type:tier:quality` per beacon."""
    out = []
    for key, b in (mapping or {}).items():
        mods = b.get("modules") or []
        if len(mods) != 1:
            raise SystemExit(
                f"update_research: beacon on {key!r} has {len(mods)} module specs; "
                f"the CLI --beacon flag encodes exactly one. Re-run this line by hand."
            )
        m = mods[0]
        prefix = "" if key in (None, "", "_global") else f"{key}="
        out += [flag, f"{prefix}{b['count']}:{m['count']}:{m['type']}:{m['tier']}:{m.get('quality', 'normal')}"]
    return out


def build_argv(state: dict, loc_id: str, ca: dict, research: dict) -> list:
    """Reconstruct the cli.py argv for one line: shared top-level config merged
    with the line's cli_args, using the supplied (already-updated) research."""
    a = ["python", _CLI, "--location", loc_id]

    furnace = ca.get("furnace", state.get("furnace", "electric"))
    a += ["--furnace", furnace]
    a += ["--assembler", str(ca.get("assembler", state.get("assembler", 3)))]

    mq = ca.get("machine_quality", state.get("machine_quality", "normal"))
    if mq != "normal":
        a += ["--machine-quality", mq]
    bq = ca.get("beacon_quality", state.get("beacon_quality", "normal"))
    if bq != "normal":
        a += ["--beacon-quality", bq]
    max_q = state.get("max_quality", "legendary")
    if max_q != "legendary":
        a += ["--max-quality", max_q]

    # research: cli-relevant techs only (lab techs are not CLI flags)
    for name, lvl in research.items():
        if name in CLI_TECHS and lvl:
            a += ["--research", f"{name}={lvl}"]

    # shared dicts overlaid by per-line cli_args (per-line wins per key)
    a += _mod_flags("--modules", {**(state.get("module_configs") or {}), **(ca.get("modules") or {})})
    a += _beacon_flags("--beacon", {**(state.get("beacon_configs") or {}), **(ca.get("beacon") or {})})
    if state.get("default_beacon"):
        a += _beacon_flags("--beacon", {"_global": state["default_beacon"]})
    for item, recipe in {**(state.get("recipe_overrides") or {}), **(ca.get("recipe") or {})}.items():
        a += ["--recipe", f"{item}={recipe}"]
    for recipe, machine in (ca.get("recipe_machine") or {}).items():
        a += ["--recipe-machine", f"{recipe}={machine}"]
    a += _mod_flags("--recipe-modules", ca.get("recipe_modules") or {})
    a += _beacon_flags("--recipe-beacon", ca.get("recipe_beacon") or {})

    # sizing
    if "targets" in ca:
        for t in ca["targets"]:
            a += ["--item", t["item"], "--rate", str(t["rate"])]
    else:
        a += ["--item", ca["item"]]
        if "rate" in ca:
            a += ["--rate", str(ca["rate"])]
        if "machines" in ca:
            a += ["--machines", str(ca["machines"])]
    for recipe, n in (ca.get("step_machines") or {}).items():
        a += ["--step-machines", f"{recipe}={n}"]
    if ca.get("use_ceil"):
        a += ["--use-ceil"]

    # bus / logistics / direct items all map to --bus-item
    for bucket in ("bus_items", "logistics_items", "direct_items"):
        for it in (ca.get(bucket) or []):
            a += ["--bus-item", it]

    if ca.get("quality_pickout"):
        a += ["--quality-pickout"]

    a += ["--format", "json"]
    return a


def total_machines(cr: dict) -> int:
    return sum(s.get("machine_count_ceil") or 0 for s in cr.get("production_steps", []))


def miner_count(cr: dict) -> int:
    n = 0
    for m in (cr.get("miners_needed") or {}).values():
        if m.get("machine") != "offshore-pump":
            n += m.get("machine_count_ceil") or 0
    return n


# ── commands ────────────────────────────────────────────────────────────────

def cmd_list(state: dict) -> None:
    levels = state.get("research_levels") or {}
    print("Current research levels:")
    if not levels:
        print("  (none)")
    for k, v in sorted(levels.items()):
        kind = "lab-only" if k in LAB_TECHS else "cli"
        print(f"  {k:<34} {v:>4}   [{kind}]")
    print("\nAffected lines per cli tech (if you were to change it):")
    for tech in sorted(CLI_TECHS):
        hits = [ln["item"] for _loc, ln in iter_lines(state) if line_affected_by(tech, ln)]
        if hits:
            print(f"  {tech:<34} {len(hits):>3} line(s): {', '.join(hits)}")


def cmd_update(state: dict, path: str, changes: dict, dry_run: bool) -> int:
    research = dict(state.get("research_levels") or {})
    # apply changes (level 0 removes the entry)
    cli_changed, lab_changed = set(), set()
    for tech, lvl in changes.items():
        old = research.get(tech, 0)
        if lvl:
            research[tech] = lvl
        else:
            research.pop(tech, None)
        if lvl != old:
            (lab_changed if tech in LAB_TECHS else cli_changed).add(tech)
        print(f"  {tech}: {old} -> {lvl}")

    if lab_changed:
        print(f"\nlab-only techs updated (dashboard recomputes, no line re-run): "
              f"{', '.join(sorted(lab_changed))}")

    # union of lines affected by any changed CLI tech
    affected = []
    for loc, ln in iter_lines(state):
        if any(line_affected_by(t, ln) for t in cli_changed):
            affected.append((loc, ln))

    if not cli_changed:
        print("\nNo cli-relevant techs changed; nothing to re-run.")
    elif not affected:
        print("\nNo lines are affected by the changed techs; nothing to re-run.")
    else:
        print(f"\nRe-running {len(affected)} affected line(s):")
        for loc, ln in affected:
            lid = loc["id"]
            ca = ln["cli_args"]
            argv = build_argv(state, cli_location(loc, ca), ca, research)
            res = subprocess.run(argv, capture_output=True, text=True, cwd=_REPO)
            if res.returncode != 0:
                print(f"  FAIL {ln['item']} @ {lid}\n    {' '.join(argv)}\n    {res.stderr.strip()[:400]}")
                return 1
            new_cr = json.loads(res.stdout)
            old_cr = ln.get("cli_result") or {}
            om, nm = total_machines(old_cr), total_machines(new_cr)
            od, nd = miner_count(old_cr), miner_count(new_cr)
            # rate change matters for --machines-sized lines (machines fixed, rate rises)
            orate, nrate = old_cr.get("rate_per_min"), new_cr.get("rate_per_min")
            rate_part = (f" | rate {orate}->{nrate}"
                         if orate is not None and nrate is not None and orate != nrate else "")
            ln["cli_result"] = new_cr
            tag = "" if dry_run else " (updated)"
            print(f"  {ln['item']:<30} @ {lid:<14} machines {om}->{nm} | drills {od}->{nd}{rate_part}{tag}")

    # the field update is always applied (even for lab-only changes)
    state["research_levels"] = research
    if dry_run:
        print("\n--dry-run: state NOT written.")
    else:
        save_state(path, state)
        print(f"\nWrote {path}")
    return 0


# ── arg parsing ─────────────────────────────────────────────────────────────

def parse_change(arg: str) -> tuple:
    if "=" not in arg:
        raise SystemExit(f"update_research: expected TECH=LEVEL, got {arg!r}")
    name, _, raw = arg.partition("=")
    name = name.strip()
    if name not in VALID_TECHS:
        raise SystemExit(
            f"update_research: unknown research {name!r}.\n"
            f"Valid: {', '.join(sorted(VALID_TECHS))}"
        )
    try:
        lvl = int(raw)
    except ValueError:
        raise SystemExit(f"update_research: level for {name!r} must be an integer, got {raw!r}")
    if lvl < 0:
        raise SystemExit(f"update_research: level for {name!r} must be >= 0")
    return name, lvl


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="update_research.py",
        description="Update factory research levels and re-run affected lines.",
    )
    p.add_argument("changes", nargs="*", metavar="TECH=LEVEL",
                   help="research techs to set (LEVEL 0 removes)")
    p.add_argument("--state", default=DEFAULT_STATE, help="state JSON (default: dev/my-factory.json)")
    p.add_argument("--dry-run", action="store_true", help="report without writing")
    p.add_argument("--list", action="store_true", help="show current levels + affected lines, then exit")
    args = p.parse_args(argv)

    if not os.path.exists(args.state):
        raise SystemExit(f"update_research: state file not found: {args.state}")
    state = load_state(args.state)

    if args.list:
        cmd_list(state)
        return 0
    if not args.changes:
        p.error("provide at least one TECH=LEVEL (or use --list)")

    changes = dict(parse_change(c) for c in args.changes)
    return cmd_update(state, args.state, changes, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
