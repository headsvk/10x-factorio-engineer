# Skill Structure Redesign

**Date:** 2026-03-05
**Status:** Approved

## Goal

Make `skill/` a fully self-contained distributable unit that can be zipped and loaded into claude.com. Keep development tooling outside the package.

## Final Structure

```
10x-factorio-engineer/
├── skill/                          ← distributable package (zip this)
│   ├── SKILL.md
│   ├── assets/
│   │   ├── cli.py                  ← moved from root
│   │   ├── dashboard.jsx           ← already here
│   │   ├── vanilla-2.0.55.json     ← moved from data/
│   │   └── space-age-2.0.55.json   ← moved from data/
│   └── references/
│       └── strategy-topics.md      ← already here
├── dev/                            ← development tooling, never shipped
│   ├── test_cli.py                 ← moved from root
│   ├── generate_preview.py         ← moved from skill/scripts/
│   └── preview.html                ← generated output (gitignored)
├── claude.md
├── README.md
└── .gitignore
```

Removed: `data/`, `skill/scripts/` (scripts merged into assets).

## Key Implementation Details

**cli.py data path:** Change data directory lookup from cwd-relative `data/` to
`__file__`-relative `os.path.dirname(__file__)` — data files are now in the
same folder as the script.

**test_cli.py import:** Add `sys.path.insert` at the top to resolve `cli` from
`skill/assets/`. Run from repo root: `python -m unittest dev.test_cli -v`

**generate_preview.py paths:** Update SKILL_DIR to go up two levels from
`dev/` to repo root, then into `skill/assets/`. Output `preview.html` to
`dev/preview.html`.

**SKILL.md references:** Update all `python cli.py` invocations to
`python skill/assets/cli.py`. Update data path note in Section 2.

**CLAUDE.md:** Update repo layout table, maintenance rules, and Component 1
description to reflect new paths.
