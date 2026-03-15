<!-- TOPICS: megabase, megabase planning, SPM, science per minute, UPS, UPS optimization, updates per second, lag, beacons, beacon, speed modules, productivity modules, direct insertion, rail grid, blueprint organization, smelting at mine -->

This file covers megabase planning, UPS optimization, and beacon design for high-SPM Factorio factories.

---

## Megabase Planning

### General Megabase Advice
**See also:** https://forums.factorio.com/viewtopic.php?t=117167 (Space Platform 101 / megabase thread)

**Step 1 — Pick your SPM target first.**
Use the CLI (`python 10x-factorio-engineer/assets/cli.py --item <science-pack> --rate <N>`) to calculate exact machine counts, raw resource rates, and power requirements for each target. Work backward from your end product — if your milestone is 1,000 SPM, calculate exactly how many blue belts of copper and iron you need, then design your train and smelting capacity to match. Common targets:
- **1,000 SPM**: manageable first megabase; can be done with a hybrid bus+train layout.
- **10,000 SPM**: full city block design essentially required; dedicated smelting, massive train network.

**Planning tools:**
- **CLI** (this tool): calculates exact machine counts, raw resource rates, power for any SPM target
- **Helmod** (in-game mod): interactive production planner with multi-product support
- **Factory Planner** (in-game mod): visual production planning inside the game
- **FactorioLab / Kirk McDonald**: web calculators for quick sanity checks
- **Xterminator's "Base Tours" series** (YouTube): real player megabases showing how throughput problems were actually solved — useful for layout inspiration before you commit to a design

**Infrastructure before production:**
Build rail backbone, power grid, and roboport coverage *before* placing production blocks. The cardinal mistake is building 200 assemblers and then realising there's no rail to feed them.

**Rail grid design:**
- Choose a consistent rail block size (100×100 or 128×128) and commit to it everywhere. Inconsistent block sizes create junction nightmares.
- 4-lane unidirectional rails (2 lanes each direction on dedicated tracks) scale better than 2-lane bidirectional for high-density megabases.
- Pre-place junctions at every block corner — even when you don't need them yet. They're cheap; re-routing rails through a dense base later is very expensive.
- **Leave at least 4 tiles** between rail track and production area for signals, roboports, and future expansion.

**Smelting at mine mouth (most impactful early step):**
Ore stacks to 50 per slot; plates stack to 100. A cargo wagon holds 2× more resource value in plates than ore. Moving smelting to the mine removes half your ore train traffic and frees up belt/train capacity in the main base. This is the single easiest decentralisation step with the biggest payoff.

**Power planning:**
- Nuclear is the megabase standard. A 2×4 reactor array (8 reactors, 1,120 MW) is a tileable unit; replicate as needed.
- Fusion reactors (Space Age) are more power-dense when Aquilo is unlocked — ideal for space-constrained city blocks.
- Solar requires enormous land area at megabase scale and has poor UPS/tile ratio due to large accumulator counts.

**Consistent train length:**
Pick one train length (1-4, 2-4, or 1-8 wagons) and use it everywhere for a given resource. All stations for the same resource must match. Mixing lengths leads to partially-filled wagons and circuit logic complexity.

**Blueprint book organisation:**
- Separate books for: Rail infrastructure, Power (nuclear/solar/fusion tiles), Production blocks, Mining outposts, Defences.
- Use the blueprint "favourite" bar for the 5–8 most-placed items.
- Grid-snap all blueprints before the megabase build — misalignment by even 1 tile propagates into every copy.

### UPS Optimization
**Wiki:** https://wiki.factorio.com/UPS
**See also:** https://reddit.com/r/technicalfactorio — dedicated subreddit for deep UPS analysis

**What UPS means:** Updates Per Second — the game targets 60 UPS (one update every 16.7ms). When a single update takes longer than 16.7ms, the game slows below real-time. UPS is the megabase endgame; most players hit issues somewhere between 1,000 and 5,000 SPM depending on PC specs and factory design.

**Biggest UPS costs (rough order of impact):**

| Entity type | Why it costs UPS | Mitigation |
|-------------|-----------------|------------|
| Belts (items on them) | Every item on every belt is simulated individually | Direct insertion, fewer belt runs |
| Inserters (active swings) | Each swing is calculated per tick | Use bulk inserters at full stack size; reduce inserter count via direct insertion |
| Electric network | Updates per entity per tick | Merge substations; use big electric poles for fewer entities |
| Robots in flight | Each bot is an individual pathfinding entity | Avoid bots for continuous high-volume flows |
| Pollution cloud | Per-chunk simulation with pollution | Biters off / artillery to clear nests far out |
| Fluid simulation | Per-segment per tick | Fewer pipe segments via pumps and storage tanks |

**Direct insertion (highest-impact optimization):**
Machine output → inserter → machine input directly, bypassing belts and chests. This eliminates belt entity updates and chest access calculations. Standard pattern: assembler-3 → inserter → next assembler-3 in the production chain. Every step removed from belt-and-chest saves simulation time.

**Beacons + productivity modules (second-highest-impact):**
Assembler-3 with 4 productivity-3 modules + 8 speed-3 beacons produces 2–3× the output of an unmodulated assembler-3 while occupying the same tile footprint. Fewer machines for the same SPM = better UPS. The `--modules` and `--beacon` flags in the CLI calculate exact machine count reductions.

**Robots vs belts for UPS:**
At megabase scale, bots hurt UPS more than express belts for continuous high-volume flows — each bot is an individual entity with pathfinding. Belts with direct insertion are more UPS-efficient for ore → plate → circuit pipelines. Bots excel for irregular, low-volume deliveries (modules, science packs, ammo) where the alternative would be complex belt routing.

**Sleeping/idle entities:**
Inserters with nothing to do enter a sleep state (zero UPS cost). An inserter oscillating between awake and asleep (half-fed machine) costs more than one that is permanently awake (fully fed) or permanently asleep (input empty). Design for steady-state: machines should either be fully saturated or completely idle, not flickering.

**Electric network merging:**
Large substations (18×18 supply area) cover 4× the area of medium poles. Fewer power entities = fewer network update calculations. Prefer one substation per production cluster over many medium poles.

**Map chunk management:**
Every explored chunk is stored and partially updated even when empty. Radar scans expand the map. For UPS-critical play, disable radars in areas already fully charted and avoid over-exploring the map edges.

**Common UPS misconception — concrete floors:**
Placing concrete on the ground has **zero impact on UPS**. It increases player walking speed and changes map aesthetics, but the game engine does not run any different calculations for biters pathfinding on concrete vs. dirt. Paving the entire world only slightly bloats save file size. Do not spend time or resources on concrete for UPS reasons.

**Community benchmarkers (r/technicalfactorio):**
- **Flame_Sla** — publishes rigorous UPS benchmark saves; definitive source for per-entity costs
- **mulark** — detailed analysis of belt, inserter, and circuit network overhead at scale
These benchmark results are the basis for most UPS advice in the community.

### Beacons
**Wiki:** https://wiki.factorio.com/Beacon

- **What beacons do:** Transmit module effects to nearby machines (non-burner only). Each machine inside the beacon's area receives the module effects, but at reduced **distribution effectivity** (50% for normal quality beacons).
- **Coverage area:** 9×9 tiles centered on the beacon. Any machine with module slots whose footprint overlaps this area is affected.
- **Distribution effectivity:** normal quality = 1.5 (not 0.5 — the tooltip shows the effectivity, not the penalty). Two speed-3 modules in a beacon at normal quality apply +50% × 2 × 1.5 = +150% total speed (vs. +100% if placed in the machine directly). The CLAUDE.md formula: `beacon_speed = BEACON_EFFECTIVITY[quality] × sqrt(count) × 2 × SPEED_MODULE_BONUS[tier] × MODULE_QUALITY_MULT[module_quality]`.
- **Productivity modules cannot go in beacons** — only speed modules and efficiency modules are permitted. This is a hard game rule.
- **Standard layout for assembler-3:** offset rows of assembler-3s and beacons so each machine is covered by **8 beacons** (each with 2 speed-3 modules). This gives maximum speed boost in the most common array layout.
- **Diminishing returns:** the transmission strength per beacon decreases as more beacons overlap the same machine. Surrounding machines around beacons (not beacons around machines) is more efficient. The wiki's multi-row array math gives optimum row count for large production blocks.
- **Don't over-beacon without productivity:** beacon speed increases machine rate, which increases raw material consumption proportionally. Only beacon machines that also run productivity modules (in the machine itself) — otherwise you're just spending more resources faster.
- **Space Age quality stacking:** beacon housing quality raises distribution effectivity (1.5→1.7→1.9→2.1→2.5 for normal→legendary). Machine quality raises crafting speed (+30%/+60%/+90%/+150%). Both stack multiplicatively with module bonuses.
