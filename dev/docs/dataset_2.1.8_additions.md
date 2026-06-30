# Dataset additions on top of the 2.1.8 export

The upstream 2.1.8 export (see `data_diff_report.md`) moved most machine/quality
stats into the dataset, but a handful of numbers the Python CLIs need were still
not exported. Those fields are added directly to the vendored
`10x-factorio-engineer/assets/space-age-2.1.8.json` and `vanilla-2.1.8.json` so
the CLIs can be fully data-driven. **The export tooling should be updated to emit
these natively.** All values match the in-game 2.1.8 numbers.

| Field | Location | Value(s) | Replaces (was hardcoded) | Consumed by |
|---|---|---|---|---|
| `quality` | each `modules[]` entry with `category == "quality"`, inside `effect` | `quality-module` 0.01, `quality-module-2` 0.015, `quality-module-3` 0.025 | `cli.QUALITY_MODULE_BONUS` | quality_planner quality-loop DP; cli quality-pickout |
| `quality_tier_skip_distribution` | top-level | `[0.9, 0.09, 0.009, 0.001]` (+1/+2/+3/+4 split when a quality roll succeeds) | `cli.QUALITY_TIER_SKIP_DIST` / `qp.TIER_SKIP_DIST` | cli quality output, quality_planner |
| `module_slots` | `beacon` | `2` | `cli.BEACON_SLOTS` | cli beacon power/effect |
| `tile_size` | each `crafting_machines[]`, `mining_drills[]`, `rocket_silo[]`, `agricultural_tower[]` entry (longest footprint dimension) | per machine (e.g. assembler 3, foundry 5, rocket-silo 9, stone/steel furnace 2) | `cli.MACHINE_SIZE` | cli `_beacon_sharing_factor` |

## Notes

- **Space Age only:** quality modules and the tier-skip split are meaningful only
  in Space Age. The `quality` module effect is absent from `vanilla-2.1.8.json`
  (vanilla has no quality modules); `quality_tier_skip_distribution` is added to
  both for uniformity but is unused in vanilla (only `normal` quality exists).
- **Speed-module quality penalty** is intentionally *not* a separate dataset
  field. In the project's model a speed module reduces quality chance by the same
  per-tier magnitude a quality module of equal tier adds, so it is derived in code
  from the quality-module `quality` effect rather than duplicated in the data.
- All other formerly-hardcoded stats (crafting/mining/pumping speeds, beacon
  `distribution_effectivity`/`energy_usage`, module `effect` values, per-quality
  scaling via `qualities[].level`) are read straight from the upstream 2.1.8
  fields and required no additions here.
- Formatting matches the upstream serializer exactly (4-space indent, inline
  `[ … ]` scalar arrays, `[ { … } ]` object arrays, alphabetically sorted keys),
  so the diff is limited to the added fields.
