# Factorio Strategy Topics

This file contains pre-embedded strategy knowledge for the most common Factorio topics.
Key facts from the Factorio wiki and community resources have been crawled and inlined
directly — no on-demand fetching required for covered topics.

**Wiki URLs** (`**Wiki:** URL`) are passive references — open them only if the player
wants the full article or asks for a detail not covered here.

**See also** entries point to forums, community searches, or external sites that
cannot be pre-crawled — surface these to players when relevant.

---

## Early-Game Progression (Vanilla)

**Strategic principle:** Don't over-invest in any science tier. Automate the minimum needed to unlock the next tier, then move on. Early factories are throwaway — build fast, not pretty.

### Science Pack Milestones

| Pack | Colour | Key recipe inputs | What it unlocks |
|---|---|---|---|
| Automation | Red | Copper plate + iron gear wheel | Core automation: belts, inserters, assemblers, miners |
| Logistic | Green | Iron plate + iron gear wheel + copper cable + electronic circuit | Logistics: fast/express belts, bots, roboports, rails |
| Military | Grey | Iron gear wheel + copper plate + firearm magazine + grenade | Combat: gun turrets, better weapons, walls, landmines |
| Chemical | Blue | Circuit board + engine unit + sulfur | Advanced production: oil processing, modules, electric furnaces |
| Production | Purple | Rail + electric furnace + productivity module 1 | End-game factories: assembler-3, electric mining drill-2, stack inserter |
| Utility | Yellow | Processing unit + flying robot frame + low density structure | Rocket components, logistics robots, beacons, power armor |

Space science (white) is produced by launching rockets — not automated in the traditional sense.

### Key Bottlenecks by Stage

- **Red science:** Iron and copper ore throughput. One miner on each is not enough — start 4–6 drills per resource immediately.
- **Green science:** Electronic circuits become the first real bottleneck. Copper cable is the hidden constraint (takes 2× copper plate per circuit). Don't skimp on circuit assemblers.
- **Blue science (chemical):** Oil processing is the unlock gate. Set up basic oil processing before you need blue science — advanced oil processing follows naturally. Engine units (steel + iron gears + pipes) are a common surprise constraint.
- **Purple/yellow science:** Both require processing units (blue circuits), which require red circuits, which require plastic (from oil). Establishing a stable plastic/circuit pipeline before starting purple is strongly recommended.

### Strategic Notes

- **Automate military science opportunistically** — turret ammo is needed anyway; the packs are cheap. A half-belt of grey science keeps military tech advancing in the background at minimal cost.
- **Electric furnaces are a milestone:** Switching from stone furnaces allows modules, removes pollution from smelting, and is required for purple science. Plan the smelting upgrade when you hit blue science.
- **Don't research everything in a tier before moving on.** Research only the techs that directly unblock the next science pack or fix an active bottleneck. Deferring expensive research (stack inserter, logistics network) until you have the production to afford it is usually faster overall.
- **The main bus inflection point:** Build the bus before starting chemical science. By blue science, the number of interconnected items (circuits, steel, plastic, gears) makes ad-hoc spaghetti unmanageable.

---

## Factory Layout Strategies

### Main Bus
**Wiki:** https://wiki.factorio.com/Tutorial:Main_bus

A main bus is a set of parallel belts carrying the most-used intermediate items through the
centre of the base. Sub-factories branch off the side, take what they need, and return
nothing — the bus flows one direction only.

**What to put on the bus (common choices):**
- Iron plates (multiple belts — cornerstone of everything)
- Copper plates (~equal quantity to iron overall)
- Iron gear wheels (half the belt space of iron plates; used in many recipes)
- Electronic circuits (green circuits — demand only grows)
- Advanced circuits (red circuits)
- Processing units (blue circuits)
- Steel plates
- Plastic bars (or coal to make it locally)
- Stone / stone bricks
- Sulfur
- Batteries

**Fluid bus (optional):** sulfuric acid, lubricant, water — pipes run alongside.

**Tip:** Copper cable is better produced on-site rather than bused — it takes more belt
space than the copper plates it's made from.

**Bus width and spacing rules:**
- Leave **2 free tile gaps** per group of 4 belts so underground belts can surface and
  cross-belts can pass through
- Leave **6–10 tile gaps between sub-factories** along the bus for future expansion
- Group only 1–2 different items together — mixing more causes split-off headaches

**Splitting off from the bus:**
- Use a splitter with **output priority** set toward your sub-factory. The belt fills
  completely before overflow continues down the bus — clean, no lane imbalance.
- Avoid taking two belts off a 4-wide group without lane-balancing: the middle splitter
  only delivers half-belt throughput to each side.

**Bus split-off priority trick:**
A splitter with output priority set toward your sub-factory fills the side branch first before overflow continues down the bus. This ensures the side branch gets a full belt even when total supply is tight, rather than sharing evenly. Useful when one production line must always be fed before others. Splitting from 4-wide with priority — the two middle belts in a non-prioritized setup each carry only half a belt to each side; always use priority splitters at split-offs for clean full-belt delivery.

**"Fake bus" anti-pattern:** If your production cannot saturate even one belt of an item, running a full-belt row is misleading — those belts hold less than rated throughput, and the empty-looking belt gives a false sense of capacity. Use blueprint ghosts to reserve space for belts you plan to add, rather than placing undersaturated belts that confuse throughput assessment.

**When to abandon the bus:**
- Once logistic robots are available, many players start moving items by bot instead
- For megabase scale, trains replace the bus entirely — city block designs have no bus
- Transition naturally: add trains/robots for new production, let the bus serve what it
  already feeds

### Belt Throughput & Compression
**Wiki:** https://wiki.factorio.com/Belt_transport_system

**Belt tiers and throughput (items/second per full belt, both lanes):**

| Belt | Color | Items/sec | Items/min | Underground max gap |
|------|-------|-----------|-----------|---------------------|
| Transport belt | Yellow | 15 | 900 | 4 tiles |
| Fast transport belt | Red | 30 | 1,800 | 6 tiles |
| Express transport belt | Blue | 45 | 2,700 | 8 tiles |
| Turbo transport belt (Space Age) | Green | 60 | 3,600 | (same underground mechanic) |

Each straight belt piece holds **8 items**. Belt speed: yellow 1.875 t/s, red 3.75 t/s, blue 5.625 t/s, turbo 7.5 t/s.

**Lane compression:**
- A belt is "compressed" when both lanes are continuously full — this is maximum throughput.
- Inserters place items onto **one lane only** (the far lane from the inserter's perspective, or the right lane if the belt runs parallel). Inserters taking from a belt prefer the near lane.
- Side-loading (inserting from the side) fills only the near lane. Use a splitter or two facing inserters to balance both lanes.
- An uncompressed belt (gaps between items) delivers less than rated throughput downstream — compress belts early by feeding them fully before the consumer.

**Underground belts:**
- Tile limits are **interior** tiles (not counting the two endpoint tiles): yellow = 4 gap, red = 6 gap, blue = 8 gap.
- Different underground belt tiers can be "braided" through the same tile column without mixing — each tier only connects to its own type.

**Splitter balancing:**
- A 4-belt → 4-belt balancer ensures all four output belts receive equal throughput from any combination of active inputs. Essential for city-block and megabase bus designs.
- Splitters have a **priority** setting (one input or output prioritized) and a **filter** setting (one item type directed to one output) — independent of each other.

### Balancer throughput: limited vs unlimited
**Wiki:** https://wiki.factorio.com/Balancer_mechanics

A balancer is **throughput limited** if it cannot provide maximum output when one or more outputs are blocked. A balancer is **throughput unlimited** when it satisfies two conditions: (1) 100% throughput under full load, AND (2) any subset of active input belts can saturate any subset of active output belts.

Many compact 4→4 balancers are throughput limited — the classic symptom is feeding 2 of 4 inputs and getting only 1 belt of output instead of 2. The fix is adding more splitter stages at the output side.

**Guaranteed method for throughput unlimited:** Place two complete balancers back to back. This uses more splitters but guarantees full throughput under any partial-load condition. For n→n balancers (n a power of 2), minimum splitter count = `n × log2(n) − n/2` (Beneš network formula).

**Universal balancers:** Handle the case where some outputs back up or are disabled. A standard balancer isn't a functional n→(n−1) balancer, but a universal balancer loops unused outputs back around to inputs. Universal balancers can still be throughput limited when many outputs back up simultaneously.

**Lane balancers:** Distinct from belt balancers — a lane balancer equalizes the two lanes of a single belt (near lane vs far lane), not multiple belts. Use one after a split-off when only one lane is getting fed.

### Transport method comparison
**Wiki:** https://wiki.factorio.com/Tutorial:Transport_use_cases

| Criterion | Belts | Trains | Logistic robots |
|-----------|-------|--------|-----------------|
| Best distance | Short/medium (< ~500 tiles) | Long distance | Short range (< 50–200 tiles) |
| Best for | High sustained throughput, one or two item types | Bulk ore/plate between outpost and factory | Many item types, irregular demand |
| Parallelization | Linear cost scaling | Two parallel tracks multiply throughput | Degrades with distance and scale |
| UPS cost | Low (compressed, few inserters) | Low | High (many entities in air) |
| Flexibility | Low — new route = new belt run | Medium — new stop on existing network | Very high — any two points |

Key rule: belts become wasteful over ~500 tiles because ~4000 items sit in transit on a 500-tile run, taking ~5 minutes to arrive. Smelt ore at mine mouth and ship plates — doubles wagon capacity and shortens smelting bus.

Bots shine at train station loading/unloading: train arrives in bursts, bots have time to recharge between trains. Avoid bots for continuous high-volume flows (ore feeds, furnace lines).

### Inserter Throughput
**Wiki:** https://wiki.factorio.com/Inserters

**Inserter types (base game + Space Age):**

| Inserter | Speed | Hand size (base) | Notes |
|----------|-------|-----------------|-------|
| Burner inserter | Slowest | 1 | Fuel-powered only |
| Inserter | ~0.83 items/s | 1 | Standard electric |
| Long-handed inserter | ~0.83 items/s | 1 | 2-tile reach |
| Fast inserter | ~2.31 items/s | 1 | 3× faster than standard |
| Bulk inserter | ~2.31 items/s | 1–12 | Same speed as fast, moves stacks |
| Stack inserter (Space Age) | ~2.31 items/s | 1–12 | Same speed, can stack on belt |

**Bulk/stack inserter with hand size research:**
- "Inserter capacity bonus" research (7 levels) increases the bulk/stack inserter hand size from 1 up to 12.
- At max research, a bulk inserter moves up to 12 items per swing — this is the primary throughput multiplier for loading/unloading trains and chests.
- Stack inserter (Space Age) functions like bulk inserter but can also **stack items on a belt** (multiple items on one belt slot), enabling higher belt compression.

**Throughput numbers (approximate, chest-to-chest at max research):**
- Standard inserter: ~0.83 items/s (no hand size research applies)
- Fast inserter: ~2.31 items/s
- Bulk inserter at hand size 12: ~28 items/s (12 items × ~2.3 swings/s)

**Circuit-controlled inserters:**
- Set inserter enable/disable via a circuit condition (e.g., "enable when iron-plate < 100").
- On bulk/stack inserters: set the **stack size** override signal via circuit network for precise flow control — e.g., reduce stack size to 1 when the destination is nearly full, preventing overfilling.

### City Blocks
**Key points:**
- Each block is self-contained: inputs/outputs via train
- Block size tradeoff: bigger = more flexible, smaller = more modular
- Common sizes: 100×100, 128×128, 200×200 tiles — rail grid must be consistent
- Best suited for megabase scale, overkill for early game

### Spaghetti / Organic Growth
Claude knows this well. Only look up specific teardown/reorganization advice if asked.

### Ribbon Base
Player asks about ribbon world maps or horizontal-only designs.

### Hybrid (Bus → Train → City Block progression)

Prefer official forums over Steam discussions — Steam threads are often 1.x era.

---

## Train Networks

**Wiki:** https://wiki.factorio.com/Railway

### Infrastructure basics

- Rails are placed on a **2-tile grid** — you cannot shift a rail by 1 tile.
- Train stops must be on the **right-hand side** of the track (from the forward-facing locomotive's perspective).
- For two-way track, rail signals must be placed **opposite each other** — hover one to confirm it highlights its pair.
- A **rail chain signal** shows blue when at least one forward path is blocked but not all; use at junctions to prevent deadlock.

**Elevated rails (Space Age):** New building type — rail ramps + rail supports. Required to
bridge Fulgora's oil ocean, Vulcanus lava rivers, and Gleba's water. Press **G** while using
the rail planner to switch levels; hold **SHIFT** + target a rail on the other level to auto-place
ramps. Supports are required every **16 straight tiles**. Players cannot walk on elevated rail.
Buildings too tall for elevated rail: big electric pole, roboport, oil refinery, rocket silo,
cargo landing pad, agricultural tower, cargo bay, lightning rod/collector.

### Signals and deadlock prevention

- Signals split the network into **blocks** — only one train per block at a time.
- Rail signal: green = block free, yellow = reserved, red = occupied.
- Chain signal: same as rail signal + blue = at least one path blocked (not all).
- **Deadlock rule:** Never create a loop where every block can fill simultaneously.
  The standard fix is making one segment one-way, or adding a bypass/passing loop.
- Manual driving **ignores all signals** — automatic trains will not yield to a player driving manually.

### Train schedule and wait conditions

The locomotive GUI lets you set a schedule (ordered list of stops + wait conditions).
There are 15 wait condition types; the most useful:

| Condition | Use case |
|-----------|---------|
| **Full cargo** | Leave loading station when full |
| **Empty cargo** | Leave unloading station when empty |
| **Inactivity** | Leave when inserters stop moving (N seconds of no change) |
| **Item count** | Leave when specific item count threshold is met |
| **Circuit condition** | Dynamic dispatch via circuit network |
| **Station is full / not full** | Queue management with train limits |
| **Time passed** | Simple fixed-time stop |

Multiple conditions can be combined with AND / OR. Logic is evaluated as **disjunctive normal
form** (DNF): each OR group is evaluated as a unit, first group that is fully true wins.

### Train groups (2.0)

Assign trains to a named group — editing one train's schedule changes **all trains in the group**.
Essential for managing fleets of identical ore/plate haulers.

### Schedule interrupts (2.0)

Interrupts let a train **override its schedule** when a condition is met — e.g., divert to a
refueling station when fuel is low, then resume the original schedule automatically.

**Wildcard interrupts:** Special signals (Item, Fuel, Fluid, Signal) that match against the
train's actual cargo. A wildcard interrupt can route a train to a station whose name contains
an icon matching the cargo — enabling a single generic train to self-route to the right unloader.

### Signal rules (from Tutorial:Train_signals)
**Wiki:** https://wiki.factorio.com/Tutorial:Train_signals

**Core rule:** Use **chain signals** at all junction entrances and internal junction blocks. Use **rail signals** only at junction exits and on open track segments. A train behind a chain signal will only enter if its entire path through the junction is clear to the next rail signal.

**Why this prevents deadlock:** A train waiting at a chain signal cannot block a junction — it waits before entering rather than inside. This guarantees no train gets stranded on a crossing blocking perpendicular traffic.

**Block size and train length:** After every rail signal exit of a junction, the next signal must be at least as far away as the longest train in your system. If signal blocks are shorter than your trains, a train's tail end can occupy the previous junction block while its front waits — causing a deadlock between two adjacent junctions.

**Stacker design — parallel vs sequential:**
- **Parallel (recommended):** Multiple waiting spots branch off perpendicular from the main line. Easily extensible, multiple stations can share one stacker. Chain signals lead trains into the stacker, rail signals separate waiting bays, chain signals exit toward the station.
- **Sequential:** Waiting spots in a line behind each other. Simpler to build but cannot be shared across multiple stations.

**Throughput tip:** Splitting a large junction block into smaller internal blocks with signals allows multiple trains to traverse the junction simultaneously (e.g., one train going left→right and another going right→straight can use different blocks at the same time).

**Too many chain signals warning:** If a large portion of your network uses chain signals, a single train entering reserves a very long reservation chain of blocks — this blocks other trains unnecessarily. Use rail signals on open stretches; reserve chain signals for junction approach + interior blocks only.

### Troubleshooting "no path"

1. Can the train reach the stop driving **forwards only**? (Automatic trains cannot reverse unless
   a second locomotive faces the other direction.)
2. Is the stop on the **right-hand side** of the track?
3. Are signals blocking forward travel in the correct direction?
4. CTRL + hover on tracks in map view highlights the planned path — follow it until it disappears
   to locate the break or signal error.

### Train Limits & Circuit Dispatch
**Wiki:** https://wiki.factorio.com/Circuit_network_cookbook

Set a **train limit** on a station to prevent trains queuing at a full station. Combine with
circuit conditions to dynamically enable/disable stations based on chest contents — the standard
pattern for decentralised ore pickup (station enables itself when ore > threshold, disables when empty).

### Megabase Train Design

For 1000+ SPM: consistent train size matters more than which size you pick (1-4, 2-4, and 1-8
are all common). All stations for the same resource must accommodate the same train length.
Stacker loops before busy stations prevent trains blocking the main line while waiting.

---

## Megabase Planning

### General Megabase Advice
**Key points:**
- Pick SPM target first, use calculator to work backward
- Consistent train size matters more than which size you pick
- Grid-aligned blueprints for rail/power/roboports save enormous time
- Move smelting to mine mouth first — it's the easiest decentralization step

### UPS Optimization
**Key points:** Fewer entities = better UPS. Prefer direct insertion over
belts where possible at megabase scale. Beacon coverage matters.

### Beacons
**Wiki:** https://wiki.factorio.com/Beacon

- **What beacons do:** Transmit module effects to nearby machines (non-burner only). Each machine inside the beacon's area receives the module effects, but at reduced **distribution effectivity** (50% for normal quality beacons).
- **Coverage area:** 9×9 tiles centered on the beacon. Any machine with module slots whose footprint overlaps this area is affected.
- **Distribution effectivity:** normal quality = 1.5 (not 0.5 — the tooltip shows the effectivity, not the penalty). Two speed-3 modules in a beacon at normal quality apply +50% × 1.5 = +75% total speed (vs. +100% if placed in the machine directly). The CLAUDE.md formula: `beacon_speed = BEACON_EFFECTIVITY[quality] × sqrt(count) × 2 × SPEED_MODULE_BONUS[tier] × MODULE_QUALITY_MULT[module_quality]`.
- **Productivity modules cannot go in beacons** — only speed modules and efficiency modules are permitted. This is a hard game rule.
- **Standard layout for assembler-3:** offset rows of assembler-3s and beacons so each machine is covered by **8 beacons** (each with 2 speed-3 modules). This gives maximum speed boost in the most common array layout.
- **Diminishing returns:** the transmission strength per beacon decreases as more beacons overlap the same machine. Surrounding machines around beacons (not beacons around machines) is more efficient. The wiki's multi-row array math gives optimum row count for large production blocks.
- **Don't over-beacon without productivity:** beacon speed increases machine rate, which increases raw material consumption proportionally. Only beacon machines that also run productivity modules (in the machine itself) — otherwise you're just spending more resources faster.
- **Space Age quality stacking:** beacon housing quality raises distribution effectivity (1.5→1.7→1.9→2.1→2.5 for normal→legendary). Machine quality raises crafting speed (+30%/+60%/+90%/+150%). Both stack multiplicatively with module bonuses.

---

## Blueprints

### Finding Blueprints
**Libraries:**
- **Factorio Prints:** https://factorioprints.com — largest community collection
- **factorio.school:** https://factorio.school — curated, searchable

**Blueprint string tools:**
- **FactorioBin:** https://factoriobin.com — pastebin for sharing and inspecting blueprint strings
- **Teoxoy Blueprint Editor:** https://teoxoy.github.io/factorio-blueprint-editor/ — design and edit blueprints in the browser without launching the game

Don't try to generate blueprint strings — they are base64+zlib encoded and must come from the game or a verified source. If a player pastes a blueprint string, Claude can explain what's in it conceptually but cannot decode the binary format without tooling.

---

## Space Age Strategies

### General Space Age Progression
**Wiki:** https://wiki.factorio.com/Space_Age
**What Space Age adds:** 4 new planets, space platforms, 5 new science packs, 22 new buildings, 5 new weapons, 2 new enemy types, 30 new intermediate products, 8 hours of original music. End goal: build a space platform capable of reaching the solar system edge (not just launching a rocket).

Space Age is actually three mods bundled together: Space Age (planets/platforms), Quality (item quality tiers + recycler), and Elevated Rails. Quality and Elevated Rails can be enabled separately without Space Age.

**Recommended planet order (community consensus):**
1. Vulcanus — easiest, great for bootstrapping production
2. Fulgora — harder but holmium unlocks key recipes
3. Gleba — hardest logistics due to spoilage
4. Aquilo — last, requires most infrastructure

### Vulcanus (Foundry / Tungsten)
**Wiki:** https://wiki.factorio.com/Vulcanus
**Key points:** Foundry is 4× speed — move all smelting here eventually.
Demolishers patrol but have fixed paths. Calcite + lava = free smelting.

**Planet stats:**
- Solar power: **400%** — solar panels are 4× as effective; excellent for cheap power
- Day/night cycle: **1.5 minutes** — nights are very short, accumulators drain minimally
- No pollution

**Terrain — three biomes:**
- **Ashlands**: dry plateaus with coal patches, sparse vegetation. Best building terrain — relatively flat, no lava rivers.
- **Lava basins**: winding lava rivers; tungsten ore deposits here (requires big mining drill).
- **Mountains**: large volcanoes with lava pools, sulfuric acid geysers, and calcite patches.

**Resources:**
- Tungsten ore: Vulcanus-exclusive, requires big mining drill. Only minable tungsten source in the game.
- Lava: pumped from lava lakes via offshore pumps. Processed into molten iron or molten copper in a foundry.
- Calcite: mined from mountain patches (also obtainable from advanced oxide asteroid crushing on platforms).
- Coal: mineable from ashland patches.
- No crude oil — use simple coal liquefaction (coal + calcite + sulfuric acid → heavy oil) for oil products.
- Water: no natural water. Obtained via acid neutralisation (sulfuric acid + calcite → water + stone) or steam condensation.
- Iron ore / copper ore: very limited (volcanic rock only) — get plates from lava processing instead.
- Stone: byproduct of lava → molten iron/copper processing.

**Demolisher territories:**
- Each territory belongs to exactly one demolisher. Territories are Voronoi-like, tightly packed, non-overlapping.
- Territory boundaries shown as opaque red lines on map; interior marked with translucent diagonal red lines.
- Demolishers do NOT respawn — killing one permanently frees its territory. Only the starting area is demolisher-free at game start.
- If you build inside a territory, the demolisher will beeline toward your buildings.

**Power options:**
- Solar at 400% output is strong and cheap — go solar early.
- Acid neutralisation generates 500°C steam for turbines — free power from sulfuric acid. Note: steam turbines require nuclear power or heating tower research (done on Nauvis/Gleba first); steam engines can be used as a temporary workaround.

**Unlocks exclusive to Vulcanus:**
Metallurgic science pack, Foundry, Big mining drill, Turbo belts (all tiers), Acid neutralisation recipe. Also unlocks (can craft elsewhere): Artillery turret/wagon/shells, Simple coal liquefaction, Coal liquefaction, Speed module 3, Asteroid reprocessing (research).

### Fulgora (Scrap Recycling / Holmium)
**Wiki:** https://wiki.factorio.com/Fulgora
**Key points:** No water, lightning power only. Scrap recycling is
probabilistic — design for averages not exact ratios. Electromagnetic
plant has 5 module slots.

**Planet stats:**
- Solar power: **20%** (orbit: 120%) — solar is weak; lightning is the primary power source
- Day/night cycle: **3 minutes**
- No pollution

**Scrap recycling output probabilities (per recycler cycle):**

| Item | Probability |
|------|------------|
| Iron gear wheel | 20% |
| Solid fuel | 7% |
| Concrete | 6% |
| Ice | 5% |
| Steel plate | 4% |
| Battery | 4% |
| Stone | 4% |
| Copper cable | 3% |
| Advanced circuit | 3% |
| Processing unit | 2% |
| Low-density structure | 1% |
| Holmium ore | 1% |

**Additional scrap facts:**
- Scrap **stack size: 200**. Mining yield per scrap entity: 1 scrap per deposit.
- Recycler cycle time for scrap: **0.2 seconds** at crafting speed 1 (the recycler runs fast — scrap throughput is limited by belt speed, not recycler count).
- Each probability is rolled **independently** — a single scrap cycle can produce more than one output item simultaneously.
- Total output probability adds up to **60%** — recycling a full belt of scrap produces a belt that is only ~60% full on average.
- **Quality does NOT affect scrap recycling output probabilities** — the chances listed above are fixed regardless of recycler quality. Higher quality recyclers only run faster (same speed bonus as other machines).
- Further recycling the primary outputs (gears, circuits, etc.) can yield additional resources: iron plate, copper plate, plastic, and more — but chemistry products (crude oil, lubricant, coal, sulfur) cannot be recovered from scrap via recycling.

Design for throughput averages — the probabilistic output means you need buffers before
each consumer. Holmium is rare (1%) so many recyclers are needed; running recyclers at
full throughput is always better than throttling.

**Scrap recycling strategy (from Tutorial:Scrap_recycling_strategies):**
**Wiki:** https://wiki.factorio.com/Tutorial:Scrap_recycling_strategies

The key constraint: **if any output backs up, all recycling stops.** Every item the recycler produces must have a drain, or belts fill and the whole line halts. Design every output with a consumer or a sink.

**Useful item chains from scrap outputs:**
- Iron gear wheels → recycle for iron plates (most abundant output, reliable iron source)
- Processing units → recycle for electronic circuits (best source of green circuits on Fulgora)
- Advanced circuits → recycle for green circuits + plastic bars
- Low-density structures → recycle for copper plates + plastic bars (LDS is rare; also best copper source)
- Batteries → recycle for copper + iron plates
- Steel → use for refined concrete (needed for island expansion) or craft steel chests (40× faster sink than direct recycling)

**Trashing excess (items with no use):** Loop a recycler's output back to its own input — items with no recyclable recipe have a 75% chance of destruction per cycle. Preferred "fast trash" routes (speed at which one assembler-3 + one recycler can eliminate excess):
- Steel → craft steel chests, then recycle (40× speedup vs direct)
- Iron plates → craft iron chests, then recycle (8× speedup)
- Stone → craft landfill, then recycle into recycler (10× speedup)
- Concrete → craft hazard concrete, then recycle (6× speedup)

**Quality modules in scrap recyclers:** Productive recyclers cannot hold productivity modules (game rule — prevents net-positive loops). Quality modules are the correct choice for scrap recyclers. Higher quality scrap outputs can seed a quality-manufacturing line. Note: uncommon or higher holmium ore is worthless — holmium solution is a fluid and loses quality; don't bother sorting holmium ore by quality.

**Terrain:**
- **Plateaus** (islands): only place where factories can be built. Split into small (resource-rich, cramped), medium (moderate resources, moderate space), and large (no resources, most room). Islands can overlap to form larger buildable areas.
- **Oilsands** (lowlands between islands): cannot build anything except rail supports. Offshore pumps on the oilsand shore produce **unlimited heavy oil** — this is Fulgora's only native fluid resource.
- Islands too far apart for roboport coverage or big electric poles — each island needs its own logistic and power networks until foundation is researched.
- Alien ruins are scattered on islands. **Fulgoran lightning attractors** (ruins) protect nearby buildings from lightning before you build your own rods — useful on first landing.

**Lightning priority:** Lightning collector (10,000) >> Lightning rod (1,000) >> alien ruins (~91–95) >> other metal entities (priority 1). Lightning strikes the highest-priority entity in range. Wooden chests, walls, rail pieces, and trains are immune to lightning.

**Resources unique to Fulgora:** Scrap (only minable resource), Heavy oil (unlimited from oilsand offshore pump).
**No water on-planet.** Ice can come from scrap recycling (5% chance) — usable for water via melting.

**Electromagnetic plant:** Speed 2, 5 module slots (more than assembler-3's 4).
Use productivity modules to amplify holmium plate output. Handles `electronics`,
`electromagnetics`, `electronics-or-assembling`, and `electronics-with-fluid` recipe categories.

### Gleba (Agriculture / Spoilage)
**Wiki:** https://wiki.factorio.com/Gleba
**Key production points:**
- Organic items spoil — avoid buffers, design tight throughput loops
- Biochamber for agricultural recipes, nutrients are the key input
- Pentapod eggs are a key ingredient for Biochambers — but they spoil and
  hatch into enemies if left too long. Automate carefully.

**Spoilage timings (normal quality, longer = more forgiving to buffer):**

| Item | Spoilage time | Notes |
|------|--------------|-------|
| Yumako | 1 hour | Harvested from yumako trees |
| Jellynut | 1 hour | Harvested from jellystem |
| Bioflux | 2 hours | Most shelf-stable biological item |
| Pentapod egg | 15 minutes | ⚠️ Spoiled eggs hatch into enemies |
| Nutrients | 5 minutes | Very short — keep flow moving |
| Yumako mash | 3 minutes | Process yumako quickly after crushing |
| Jelly | 4 minutes | Process jellynut quickly after crushing |

**Spoilage mechanics (how it works):**
- Every spoilable item has a fixed spoil time — a countdown from 100% freshness to 0%. Items spoil everywhere: in chests, machine input/output slots, inserter hands, and belts. Nothing stops the timer except items still inside a captive biter spawner (eggs don't count down until removed).
- **Stacking averages freshness:** when inserters combine items into a stack, the resulting freshness is the weighted average. A large stack of 80%-fresh items mixed with 100%-fresh items ends up somewhere between — plan for this in fast-throughput loops.
- **Freshness transfers through recipes:** if a recipe consumes a spoilable input to produce a spoilable output, the output inherits the input's freshness percentage. Multiple spoilable inputs → average freshness is used.
- **Agricultural science packs are doubly affected:** lower freshness = the lab consumes the pack faster without producing more science. A 50% fresh pack gives half the science value. Keep ag-packs fresh, ship them quickly, and keep Gleba→Nauvis transit time short.
- **Machine trash slots:** any machine handling spoilable items gains internal trash slots. If an input or output stack spoils, items move to trash slots — the machine can stall if trash slots fill. Any output inserter can take from trash slots; use filter inserters to route spoilage separately from products.
- **Biter/pentapod egg spoiling is dangerous:** spoiled biter eggs spawn big biters; spoiled pentapod eggs spawn wrigglers. Never let these items sit in open storage.

Design rule: process items before they spoil. Yumako/jellynut buffers (1 hour) are fine;
nutrients/mash/jelly buffers (3–5 min) are dangerous. Build short loops, not long belts.

**Biochamber stats:**
- Crafting speed: **2** (normal quality), up to 5 at legendary
- Module slots: **4**
- Fuel: **nutrients only** (2 MJ per nutrient = 4 seconds per nutrient at 500 kW)
- Built-in **50% productivity bonus** — one of the few machines with a base prod bonus
- **Negative pollution** — absorbs pollution from the environment rather than producing it;
  a large biochamber array actually reduces your pollution cloud and attack frequency
- Size: 3×3 tiles
- Handles recipe categories: `organic`, `organic-or-assembling`, pressing, and more

**Nutrients production chain:**

| Recipe | Inputs | Outputs | Time | Notes |
|--------|--------|---------|------|-------|
| From yumako mash | 4 mash | 6 nutrients | 4s | Primary loop |
| From spoilage | 10 spoilage | 1 nutrients | 2s | Waste-to-nutrients |
| From bioflux | 5 bioflux | 40 nutrients | 2s | Efficient but wastes bioflux |
| From biter egg | 1 egg | 20 nutrients | 2s | Automatable |
| From raw fish | 1 fish | 20 nutrients | 2s | Not automatable |

The yumako mash route is the primary sustainable loop. Feed nutrients back into biochambers
as fuel; the cycle is self-sustaining once primed.

**Pentapod egg mechanics:**
- Spoilage: 15 minutes → spawns a **Big premature wriggler** (enemy) when it spoils
- Sources: natural egg rafts on-planet, stompers drop them, or biochamber can breed them
  (recipe: 30 nutrients + 1 egg + 60 water → 2 eggs, 15s — net +1 per cycle)
- Stack size: 20. ⚠️ Never let eggs sit in chests — automate processing or use immediately
- Required for: agricultural science pack (1 egg + 1 bioflux = 1 pack, 4s in biochamber)

**Captive biter spawner:**
- How to get: fire a capture bot rocket at a wild biter spawner on Nauvis; can also craft
  after reaching Aquilo and researching the unlock
- Output: biter eggs at **0.5/s** (5 eggs per 10 seconds), max 100 in output slot
- Fuel: bioflux only (6 MJ per bioflux = 1 minute per bioflux at 100 kW)
- Module slots: **0** — cannot be boosted by modules or beacons
- Quality of spawner does NOT affect egg quality — eggs are always normal quality

**Agricultural science pack recipe:**
- 1× bioflux + 1× pentapod egg → 1× agricultural science pack (4s, biochamber)
- ⚠️ The pack itself spoils — ship to Nauvis promptly; run a dedicated fast platform

**Terrain and nest control:**
- Pentapod nests can only form on **shallow water tiles** — midlands and highlands act as natural expansion barriers.
- Landfilling shallow water prevents pentapod nest expansion — a viable active defense strategy.
- Marshland biomes (red/green) are where Jellystem and Yumako trees grow; also contain iron/copper stromatolites.

**Resources (no crude oil):**
- Iron ore: grown via iron bacteria cultivation in biochambers; copper ore same via copper bacteria.
- Coal: synthesised via coal synthesis recipe in biochambers.
- No crude oil. Bio-substitutes available: bioplastic → plastic bars, biosulfur → sulfur, biolubricant → lubricant, rocket fuel from jelly recipe. For flamethrower turrets, heavy oil must be imported (or coal liquefaction if calcite is shipped in from platforms/Vulcanus).
- Stone: mined normally from surface patches.
- Water: readily available via offshore pumps.

**Power:** Heating tower (burner device) generates 500°C heat for heat exchangers + turbines. Gleba renewably generates rocket fuel, making it self-sufficient for burner power. Traditional boilers also work. Solar at 50% output is usable.

**Space routes:** Gleba connects to Nauvis (15,000 km), Vulcanus (15,000 km), Fulgora (15,000 km), and Aquilo (30,000 km — longest route, double distance).

**⚠️ Gleba enemies — widely considered the hardest combat in Space Age:**
- Enemies are **pentapods** (not biters) — three types: Wrigglers, Strafers, Stompers
- **Walls are useless** — pentapods were explicitly designed to ignore walls.
  Defense must be raw firepower, not containment
- Stompers are already small-Behemoth tier from the start, have high
  resistances, and ignore terrain features including walls
- Spores from agricultural activity attract pentapods — the larger your
  farm, the bigger the spore cloud, the harder the attacks
- Egg rafts (spawners) sit in shallow marshland near your harvest areas —
  exactly where you need to build
- Pentapod eggs that spoil inside your factory hatch into enemies —
  a factory logistics failure can spawn enemies from within

**Recommended defense (from community):**
- Gun + laser turrets for early small pentapods
- Rocket turrets essential for medium/big Stompers (unlocked via Gleba science)
- Tesla turrets excellent for slowing Stompers so other turrets can finish them
- Spread turret lines out — Stompers that can't stomp a dozen turrets
  at once do far less damage
- Robot network essential to auto-repair destroyed turrets and rails
- Cannon shells and tanks work well for clearing egg rafts proactively
- Artillery (once available) is highly effective for pushing back nest perimeter

### Aquilo (Cryogenics)
**Wiki:** https://wiki.factorio.com/Aquilo
**Key points:** Everything freezes without heating. Ammonia + ice + lithium
are key resources. Carbon fibre unlocks late recipes. Hardest planet.

**⚠️ Heating mechanics — the defining constraint of Aquilo:**
Almost every building freezes and stops working unless it is adjacent (orthogonally or
diagonally within 1 tile) to a heat source above 30°C. Heat sources: nuclear reactor,
heating tower (unlocked on Gleba), and heat pipes. Heat pipes distribute heat without
loss but only to adjacent entities.

**Heat consumption per building type (approximate):**
- Transport belts (yellow/red/blue/turbo): **10 kW each**
- Underground belts: **50–200 kW** (higher tiers cost more)
- Splitters: **40 kW**
- Pipes: **1 kW**; Pipes-to-ground: **150 kW**
- Pumps: **30 kW**
- Storage tanks: **100 kW**
- Inserters: **30–50 kW**
- Assembling machines / chemical plants / labs: **100 kW**
- Oil refineries / artillery turrets: **200 kW**
- Beacons: **400 kW**

Buildings that do NOT need heating: burner machines, offshore pumps, chests, electric
poles, solar panels, accumulators, lamps, combinators, robots, vehicles, trains, and
rail infrastructure.

**Planet stats:**
- Solar power: **0.6 kW peak (1% of Nauvis)** — effectively useless, plan for nuclear or fusion
- Day/night cycle: **20 minutes**
- Robot energy usage: **500%** — bots drain power fast; factor into power planning
- No pollution

**Terrain:**
- Cannot place regular landfill or foundation on ice ocean — use **ice platforms** instead
- Most buildings on ice require **concrete** (not stone bricks) as flooring
- Ice platforms are crafted from ammonia + ice (from ammoniacal solution separation)

**Resources available locally:**
- Ammoniacal solution (offshore pump on ammonia ocean)
- Lithium brine (pumpjack)
- Fluorine (pumpjack)
- Crude oil (pumpjack)
- Ice (mined from lithium ice formations, or crafted)
- Lithium (mined or crafted from lithium brine)

**Must import:** Stone, iron ore, copper ore, coal — none are available on-planet.

**Unlock requirements for Aquilo:** Requires research from all three prior planets — rocket turrets + advanced asteroid processing + heating towers (from Gleba), asteroid reprocessing (from Vulcanus), and electromagnetic science pack (from Fulgora). Aquilo is explicitly designed as the last planet.

**Fluid exclusivity:** Ammoniacal solution, fluorine, lithium brine, and ammonia cannot be barrelled and transported off Aquilo. Any recipe consuming these fluids is therefore Aquilo-exclusive. This includes: fluoroketone (hot), lithium, fusion power cells, solid fuel from ammonia, and ammonia rocket fuel.

**Quantum processors** can be crafted on Aquilo OR on space platforms — one of the few Aquilo-unlocked items with this flexibility.

**Exclusive unlocks:** Cryogenic plant, Fusion generator, Fusion reactor (all crafted on Aquilo only), Cryogenic science pack, Quantum processor, Foundation (buildable tile for ice ocean), Railgun turret, Railgun.

**Power recommendation:** Bootstrap with nuclear using imported uranium; transition to
fusion reactors long-term. Steam can be generated from melted ice via heat exchangers.
Accumulators charged near inner planets can provide a small buffer.

---

## Power

### Solar + Accumulators
**Wiki:** https://wiki.factorio.com/Solar_panel
**See also:** https://forums.factorio.com/viewtopic.php?t=119040 for the
definitive community deep-dive including quality combinations.

**⚠️ Cheat sheet solar ratio is Nauvis-only — always note this when Space Age
is involved. The ratio changes dramatically per planet.**

**Accumulators per solar panel (normal quality, Factorio 2.0):**

| Planet | Solar output | Day/night cycle | Acc/panel ratio | Practical ratio |
|---|---|---|---|---|
| Nauvis | 60 kW (100%) | 420s | **0.84672** | 25 panels : 21 acc |
| Vulcanus | 240 kW (400%) | 90s | **0.72576** | 25 panels : 18 acc |
| Gleba | 30 kW (50%) | 600s | **0.6048** | 25 panels : 15 acc |
| Fulgora | 12 kW (20%) | 180s | **0.072576** | solar barely viable — use lightning |
| Aquilo | 0.6 kW (1%) | 1200s | **0.024192** | solar not viable here |
| Space platform | varies by location | — | depends on star proximity | — |

**Key points Claude should always cover:**
- Nauvis blueprint reused on Vulcanus slightly over-builds accumulators — fine
  but wasteful. Vulcanus nights are so short accumulators may hit throughput
  limits before fully discharging — factor in accumulator output (300 kW normal)
- Gleba solar is usable but space-inefficient; pollution still attracts
  pentapods so a large solar field does increase attack frequency
- Fulgora: solar output is weak — lightning collectors are the intended power
  source. Solar is a minor supplement at best
- Aquilo: solar is essentially useless (1% output). Use fusion power or
  import fuel for heating towers
- Quality affects both output and storage — higher quality accumulators store
  more but the ratio still shifts; always upgrade accumulators before panels
- Universal layout tip: a 2.117 acc/panel ratio works on all planets at all
  quality combinations but is very wasteful — only use if you want one
  blueprint for everything

### Nuclear Power
**Wiki:** https://wiki.factorio.com/Tutorial:Nuclear_power
**Core units:**
- 1 reactor = **40 MW** base output
- 1 heat exchanger = **10 MW** consumption → produces **103.09 steam/sec**
- 1 steam turbine = **5.82 MW** max output, consumes **60 steam/sec**
- 1 offshore pump = **1200 water/sec** → supplies **116.4 heat exchangers**

**⚠️ The cheat sheet "1 reactor → 4 exchangers → 7 turbines" is for a
single isolated reactor only. Ratios change significantly with neighbor bonuses.**

**Neighbor bonus:** Every reactor gains +100% heating power per adjacent
active reactor (sides only, not diagonals). A 2×2 block gives each reactor
2 neighbors = 3× base output = **120 MW per reactor**.

**Heat exchanger count formula:**
```
Total MW = sum of (40 MW × (1 + neighbor_count)) per reactor
Heat exchangers = Total MW / 10
```

**Turbine count formula:**
```
Turbines = Heat exchangers × 1.718  (exact ratio, round up)
Practical shortcut: 7 turbines per 4 heat exchangers (slight overcapacity, clean layout)
```

**Common build ratios (vanilla 2.0):**

| Layout | Reactors | MW total | Heat exchangers | Turbines | Offshore pumps |
|---|---|---|---|---|---|
| Single reactor | 1 | 40 MW | 4 | 7 | 1 |
| 1×2 (line of 2) | 2 | 160 MW | 16 | 28 | 1 |
| **2×2 (standard)** | **4** | **480 MW** | **48** | **83** | **1** |
| 1×4 (line of 4) | 4 | 480 MW | 48 | 83 | 1 |
| 2×4 | 8 | 1120 MW | 112 | 193 | 1 |
| 2×8 | 16 | 2400 MW | 240 | 413 | 2 |

**2×2 is the most common starter build** — 480 MW, tileable, fits a clean
blueprint. The cheat sheet commonly shows this layout.

**Water supply (2.0):**
- In Factorio 2.0, 1 water now produces 10 steam in heat exchangers — this
  dramatically reduced pump requirements compared to pre-2.0
- Having one pump is now enough for nuclear power in 2.0 where previously
  you might need many pumps
- A single offshore pump (1200 water/sec) is sufficient up to and including
  a 2×4 array. Only very large arrays (2×8+) need more than one pump

**⚠️ Pipe pressure loss is gone in 2.0:**
- Factorio 2.0 completely rewrote the fluid system — there is no longer
  realistic fluid flow through pipes; fluid pushed to a segment is immediately
  available at any point along it
- Pre-2.0 advice about pump placement, pipe length limits, and pressure drop
  workarounds is obsolete — pipes just work
- The cheat sheet and many forum posts predate this change — ignore any
  advice about needing pumps mid-pipeline to combat pressure loss

**Fuel efficiency:**
- Reactors consume one fuel cell every 200 seconds regardless of load —
  use circuit logic to only insert fuel when temperature drops below ~900°C
- Steam storage tanks between exchangers and turbines let you buffer output
  and run reactors at full efficiency during low demand
- Reactor stuck at 1000°C = heat going nowhere — add more exchangers or
  check pipe connections

**Heat pipe distance:**
- Heat pipes still have a thermal throughput limit — run parallel heat pipe
  runs for very large arrays (2×8+)
- Unlike water pipes, heat pipe distance still matters for heat transfer rate
- Rough throughput limits: 1 pipe handles ~21 exchangers one side / ~31 both sides.
  Two parallel pipes: ~29 one side / ~42 both sides. Beyond ~133 tiles from reactor,
  a single 40 MW path loses efficiency.

**Fuel supply:**
- Fuel cell recipe: 1× U-235 + 19× U-238 + 10× iron plate → 10 fuel cells. Each cell = 8 GJ.
- U-235 yield: ~7 U-235 per 10,000 ore processed (0.07%). Expect 1 U-235 per ~1,428 ore.
- Rule of thumb: ~1 uranium processing centrifuge per reactor for steady U-235 supply.
- In 2.0, reactors can be **wired directly to read their own heat level** — no steam tank workaround needed to trigger fuel insertion via circuit.

### Kovarex Enrichment Process
**Wiki:** https://wiki.factorio.com/Kovarex_enrichment_process

- **What it does:** Enriches U-238 into U-235 using existing U-235 as a catalyst. Run in a centrifuge.
- **Recipe (gross):** 40 U-235 + 5 U-238 → 41 U-235 + 2 U-238. **Net per cycle: +1 U-235, −3 U-238.**
- **Catalytic recipe:** The 40 U-235 and 2 U-238 are treated as catalysts, not consumed. Productivity bonuses apply only to the net +1 U-235 output — extra production from productivity generates +1 U-235 (not +41).
- **Bootstrapping is the hard part:** The centrifuge needs 40 U-235 loaded before it can run. Early uranium processing yields ~0.07% U-235, so expect ~570 ore to reach 40 U-235. Patience required before the loop starts.
- **Once running:** U-235 is no longer the bottleneck — each cycle nets at least 1 U-235 (more with productivity modules). A single centrifuge running Kovarex can supply multiple reactors.
- **Productivity modules stack very well here** — each productivity module increases the net U-235 yield per cycle. Fill the centrifuge with productivity-3 modules for best return.
- **Common setup:** Filter inserter configured to keep exactly 40 U-235 in the centrifuge input; a second inserter outputs excess U-235 and the U-238 byproduct to separate storage.

### Steam (Early Game)
**Wiki:** https://wiki.factorio.com/Power_production

**Core ratio:** 1 boiler : 2 steam engines. Each boiler produces 60 steam/s at 1.8 MW thermal; each steam engine consumes 30 steam/s and outputs **900 kW**. One boiler feeds exactly 2 engines = 1.8 MW output.

**Standard build block:** 1 offshore pump → 20 boilers → 40 steam engines → **36 MW** per block.
- Offshore pump: 1200 water/s. Each boiler consumes 6 water/s → 200 boilers max per pump. In practice build 20-boiler segments; one pump covers 10 such segments.
- Coal: each boiler burns coal at ~0.45 coal/s (4 MJ/coal ÷ 1.8 MW thermal output × efficiency). A full 20-boiler block needs ~9 coal/s — one yellow belt (~13.3/s) comfortably feeds 20 boilers.

**When to build it:**
- Place steam power at game start — it's available before any tech research.
- A single 20-boiler block (36 MW) sustains early automation (red + green science) comfortably.
- Build a second block before starting chemical science (blue) production.

**When to transition away:**
- Solar becomes cost-effective once you can mass-produce accumulators and solar panels (~mid-green-science).
- Nuclear is strictly better than steam at scale — plan the transition around the time you unlock blue science or shortly after.
- Common trigger: coal supply becoming a constraint (competing with smelting / plastic production).

**Common early-game mistakes:**
- Forgetting burner inserters on boilers: if coal stops and all inserters are electric, the whole power grid deadlocks — keep at least one burner inserter per boiler line.
- Underbuilding: 4–8 steam engines feels like enough until green circuits hit. Build 40 engines minimum before starting red science automation.
- Not expanding coal mining before it runs out — steam power competes directly with smelting for coal.

### Fusion Power (Space Age)
**Wiki:** https://wiki.factorio.com/Fusion_reactor and https://wiki.factorio.com/Fusion_generator
**Core units:**
- 1 fusion reactor = **100 MW** plasma output base, requires **10 MW** electricity to run
- 1 fusion generator = **50 MW** max electrical output
- Neighbor bonus: +100% plasma output per adjacent reactor (plasma connection only,
  not all 3 sides like nuclear — one shared fluid connection is enough)
- Fusion fuel cells scale with load — **no wasted fuel** unlike nuclear reactors

**Generator ratio formula:**
```
Generators per reactor = 2 × (1 + neighbor_count)
```

**Common build ratios:**

| Layout | Reactors | MW total | Generators needed |
|---|---|---|---|
| Single reactor | 1 | 100 MW | 2 |
| 1×2 (line, 1 neighbor each) | 2 | 400 MW | 8 |
| 1×3 (center gets 2 neighbors) | 3 | 800 MW | 16 |
| Large array (avg 2+ neighbors) | N | varies | 2 × (1 + avg_neighbors) × N |

**Key mechanics:**
- Fluoroketone is not permanently consumed — it circulates as coolant,
  converted to plasma by the reactor and returned as hot fluoroketone by
  generators. Only the initial fill is needed; top up as the system grows
- Starting a fusion setup requires external power to bootstrap — once
  plasma is flowing through generators the system can power itself
- Generators produce hot fluoroketone as a byproduct — must be piped
  to a cryogenic plant to cool back to fluoroketone (cold) and recirculate.
  If hot fluoroketone backs up, generators stop producing power
- Each reactor consumes at most **4 cold fluoroketone/second**. Rule of thumb: **1 cryogenic plant per reactor** is sufficient to keep the coolant loop flowing (no modules).
- Do not build more generators than the ratio supports — excess generators
  deplete stored plasma and cause others to show "no fluid input"
- Higher quality reactors give more power per tile but worse fuel
  efficiency due to losing neighbor bonuses. Normal quality reactors with
  more neighbors out-perform legendary isolated reactors on fuel per MWh.
  Quality is worth it only when space is constrained (e.g. space platforms)

**Fusion vs Nuclear:**
- Fusion is strictly more power-dense and fuel-efficient at scale
- Nuclear is simpler to bootstrap and doesn't require Aquilo fluoroketone
- For space platforms: fusion preferred due to space constraints once unlocked
- For Aquilo base power: fusion is the intended endgame solution

---

### Lightning Rods & Collectors (Fulgora only)
**Wiki:** https://wiki.factorio.com/Lightning_rod and https://wiki.factorio.com/Lightning_collector
**Two buildings:**

| Building | Unlock | Range (normal quality) | Energy efficiency | Recipe cost |
|---|---|---|---|---|
| Lightning rod | On arrival | 15 tiles | 20% normal → 50% legendary | Cheap (steel + copper + brick) |
| Lightning collector | After EM science | 25 tiles | 40% normal → 100% legendary | Expensive (holmium + batteries) |

Both buildings cannot be crafted on any planet other than Fulgora (other planets lack the required magnetic field strength).

**How lightning power works:**
- Lightning rods protect an area from strikes — any lightning in their
  radius hits the rod instead of your buildings, generating a burst of power.
  Peak output is limited only by the connected grid's demand, with 150 MW
  internal drain
- Lightning rods convert threat into resource — the sky tries to kill
  you but you exploit it. Lightning collectors are the upgrade, protecting
  a much larger area and converting more of each bolt's energy to electricity
- Only one rod/collector benefits from each strike — if multiple overlap
  the same area, only one fires. Space them out to cover more area and
  capture more total strikes
- Placing multiple rods in the same small area does not generate more
  power — coverage area is what matters, not density

**Accumulator sizing:**
- Lightning storms only happen at night — accumulators must power the entire
  day cycle from stored charge
- Fulgora day/night cycle is 180 seconds. To sustain X MW through the day:
  `Accumulators needed = X MW × 90s ÷ 5 MJ (per accumulator) = X × 18`
- Example: 100 MW base needs ~1800 normal accumulators just for daytime power
- A single lightning strike can spike to 2 GW and charge a bank
  almost instantly — the limiting factor is total storage capacity,
  not charge rate
- Quality accumulators store more per tile — upgrade accumulators before
  worrying about rod quality

**Rod vs Collector choice:**
- Legendary lightning collectors have 100% efficiency vs 50% for
  legendary rods, and 3× the coverage area — making them far superior
  late game. But holmium is always a bottleneck, making rods much cheaper
  to mass produce early on
- Early Fulgora: use rods, they're cheap and effective enough
- Late Fulgora: transition to collectors for power-hungry EM plant arrays
- Very late: import a fusion reactor — at that point lightning becomes
  supplemental rather than primary power

**Island power isolation:**
- Islands cannot share power grids until Foundations are unlocked late
  in the game — even legendary electric poles can't bridge most island gaps
- Each island needs its own lightning rods + accumulator bank
- Small mining islands: a substation + handful of accumulators is enough
- Use efficiency modules everywhere until power is stable — EM plants are
  very power-hungry

**⚠️ First landing tip:**
- Lightning rods cannot act as electricity poles — they protect and
  generate but don't distribute power. You need substations or electric
  poles to connect them to your grid. Bring substation tech researched
  before landing — small and medium poles require iron sticks which can't
  be crafted without a powered recycler, creating a potential softlock

---

## Combat & Defense

### New Space Age Turrets Overview
**Wiki:** https://wiki.factorio.com/Turret for the full list.
| Turret | Unlocked | Power | Ammo | Best use |
|---|---|---|---|---|
| Gun turret | Nauvis early | No | Bullets | Cheap early coverage |
| Laser turret | Nauvis mid | Yes (high idle drain) | None | Reliable mid-game |
| Flamethrower turret | Nauvis mid | No | Fluid (oil) | Mass biter crowds |
| Rocket turret | Space Age | No | Rockets | Behemoths, demolishers, stompers |
| Tesla turret | Fulgora | Yes (very high) | None | Crowd control + synergy |
| Railgun turret | Aquilo | No | Railgun shells | Massive single targets, line damage |
| Artillery turret | Nauvis late | No | Shells | Nest clearing, range push |

**Rocket turret:**
- Space Age exclusive, resembles a Spidertron head
- Best used to target only Behemoth biters/spitters — let laser turrets handle smaller enemies to conserve ammo
- Essential for dealing with Demolishers on Vulcanus and Stompers on Gleba
- Can be connected to circuit network for target filtering

**Tesla turret:**
- Primary role is crowd control, not raw damage — arcs stun targets, push them back, and slow them after the stun wears off. Keeps enemies clustered for flamethrower/rocket area damage
- Uses only electricity, no ammo — a common misconception from Factoriopedia's "ammo category" tag
- Must be manufactured on Fulgora, so unavailable everywhere until mid-Space Age. A few Tesla turrets placed at artillery forts or chokepoints make a big difference
- Very high power draw — ensure stable power before deploying at scale

**Railgun turret:**
- Limited 72° firing arc but can be placed in 8 directions. Does massive damage to everything in its line of fire — including your own buildings, so aim carefully
- Extremely effective against Demolishers, especially when fired down their bodies — shells can hit multiple segments at once
- Primary use: space platforms (asteroid defense) and Aquilo
- Note: railgun turret firing speed is currently animation-locked with an effective cap well below what infinite research suggests — a known bug

---

### Damage Types and Resistances
**Wiki:** https://wiki.factorio.com/Damage

**Damage types in Factorio:**
| Type | Sources |
|------|---------|
| Physical | Bullets, shotgun shells, railgun ammo, biters (melee), wriggler pentapods |
| Physical + explosion | Cannon shells, artillery shells |
| Impact | Train/car/tank collision |
| Fire | Flamethrower ammo, flamethrower turret |
| Acid | Spitters, worms, stomper pentapods |
| Poison | Poison capsule, wriggler pentapods |
| Explosion | Rockets, grenades, landmines, strafer pentapods |
| Laser | Laser turret, personal laser defense |
| Electric | Tesla turret, destroyer capsule |

**Flat resistance vs % resistance:** Flat resistance subtracts fixed damage per hit (very effective vs weak projectiles, useless vs high damage). % resistance reduces after flat. Behemoths have high flat physical resistance — firearm magazine bullets do almost nothing; use piercing or uranium rounds which deal much higher raw damage that exceeds the flat resistance.

**Cannon shell piercing:** Tank cannon shells have a piercing power value — one shell can kill multiple enemies in a line. Piercing power decreases with each enemy killed. Uranium cannon shells have very high piercing, effective in dense crowds.

**Stomper acid:** Stompers deal acid damage in an area around them. Energy shields absorb this; physical armor does not. Tesla turrets' slow effect reduces the duration of stomper contact.

### Nauvis (Biters)
**Wiki:** https://wiki.factorio.com/Enemies
**Key points:**
- Wall + flamethrower + laser turret is the classic reliable setup
- Artillery for passive nest clearing once researched
- Circuit network target priorities help conserve ammo — set rocket turrets
  to Behemoth-only, lasers handle the rest
- Setting laser turrets to prioritize spitters reduces damage taken in large attacks

### Vulcanus (Demolishers)
**Wiki:** https://wiki.factorio.com/Enemies (Demolisher section)
**Key points:**
- Demolishers patrol fixed paths — scout before building
- Small Demolishers can be killed with tanks + cannon shells early on
- Railgun is very effective against Demolishers, especially fired along their body length
- Walls are useful here unlike Gleba — Demolishers don't ignore them
- Rocket turrets essential for medium and large Demolishers
- No biter expansion — only fixed patrol routes, so aggressive expansion
  is safer than Nauvis once paths are mapped

### Gleba (Pentapods)
**Wiki:** https://wiki.factorio.com/Enemies (Pentapod section — Stomper info is on the Enemies page, no separate Stomper article)
**Key points:**
- Three enemy types: Wrigglers (small), Strafers (ranged), Stompers (massive)
- Stompers simply walk over walls — walls are not a viable containment strategy. Brute force firepower is required
- Rocket turrets for Stompers, Tesla to slow them so rockets can connect
- Artillery is effective for clearing nests within your spore cloud — fewer nests means fewer attack waves
- Landmines surprisingly effective as supplemental damage against Stompers
- Redundant roboport coverage essential — auto-repair keeps defenses up
  after Stomper attacks destroy turrets
- Egg hatching inside factory is a real threat — automate egg processing
  and don't let them sit in chests

### Aquilo (Mites / Coldsnap)
**Wiki:** https://wiki.factorio.com/Aquilo
**Key points:**
- Enemies are Mites — less aggressive than other planets but the environment
  itself (freezing) is the real threat
- Railgun turret unlocked here — effective for large targets
- Bots have 500% energy usage on Aquilo — factor into power planning
- Defense is less of a concern than keeping the factory from freezing

### Space Platforms (Asteroids)
**Wiki:** https://wiki.factorio.com/Space_platform
**Key points:**
- Asteroids are the only threat — no enemy units
- Gun turrets handle small asteroids, rocket turrets for medium/large
- Railgun turrets are very effective against huge asteroids due to high physical damage bypassing flat resistance
- Aquilo-bound platforms must carry rocket turrets to survive large asteroid density on that route
- Ammo supply on platforms is a logistics puzzle — belt-fed turrets from
  onboard production is the reliable approach
- Ice-heavy asteroid zones (near Aquilo) can starve metal production — plan for mixed asteroid chunk collection

### Turret Creep
**Key points:**
- Place turrets just outside biter attack range, let them clear nests,
  advance, repeat
- Tesla turrets make turret creep safer by slowing counterattacks
- Artillery mostly replaces turret creep once available

---

## Logistic Network (Robots)

**Wiki:** https://wiki.factorio.com/Logistic_network

### Roboport stats (Factorio 2.0.7+)

| Stat | Value |
|------|-------|
| Logistic area (orange) | 50×50 tiles |
| Construction area (green) | 110×110 tiles |
| Charging slots | 4 |
| Charge rate per slot | **500 kW** (reduced from 1 MW in patch 2.0.7) |
| Time to charge one bot | **3 seconds** (1.5 MJ ÷ 500 kW) |
| Bots charged per minute | ~80 per roboport |
| Internal battery | 100 MJ |
| Robot storage slots | 7 × 50 bots each (+ 7 repair pack slots) |
| Built-in radar | 2 chunks (added in 2.0.7) |

**⚠️ Quality does NOT affect coverage area size** — a legendary roboport still covers 50×50/110×110.
Higher quality roboports charge robots more quickly (quicker per charge slot cycle).

**Connecting roboports:** Two roboports form one network when their orange zones touch (yellow dashed line appears).
Robots never migrate between separate networks. Keep coverage contiguous.

### Robot stats

| Stat | Logistic bot | Construction bot |
|------|-------------|-----------------|
| Energy stored | 1.5 MJ | 1.5 MJ |
| Constant power draw | 3 kW | 3 kW |
| Energy per tile | 5 kJ | 5 kJ |
| Base speed | 3 tiles/s | 3.6 tiles/s |
| Max range (base, no research) | **250 tiles** | **257 tiles** |
| Cargo (base) | 1 item | — |
| Cargo (max, fully researched) | **4 items** | — |

Max range formula: `1500 ÷ (3 × speed + 5)`

Robots recharge when at 20% energy. When out of power they fly at 20% speed.
In 2.0.7+ robots consider charger queue length before choosing a roboport,
and can now be assigned multiple tasks simultaneously (not just one at a time).

### Chest types

| Chest | Behaviour |
|-------|-----------|
| **Active provider** | Pushes all stored items into the network immediately — bots come to empty it |
| **Passive provider** | Makes items available on request — bots only come when someone requests them |
| **Storage chest** | Accepts overflow items not wanted elsewhere; can be filtered to one type |
| **Requester chest** | Pulls specific items from the network until configured quantity is reached |
| **Buffer chest** | Hybrid: requests items like a requester AND provides them like a passive provider |

**Robot pickup priority (highest first):** active provider > storage/buffer chests > passive provider > cargo landing pads

### Throughput and charger bottleneck

The primary bottleneck in a busy robot network is charger throughput, not robot count.
At ~80 bots/min per roboport, a dense factory needs **one roboport per ~80 active bots**.
Symptoms of charger starvation: bots queue floating in the air, delivery times balloon.

**Fix:** Add more roboports within the same logistic area (overlap orange zones — they
share robots). A cluster of 4 roboports in one spot quadruples local charging throughput
and is the standard pattern for high-throughput areas (science labs, train stations).

### Bots vs belts

| Use bots when... | Use belts when... |
|-----------------|------------------|
| Short-range point-to-point delivery | Long-distance bulk transport |
| Many different items going many places | Few item types, high sustained throughput |
| Train station loading/unloading | Items move in one direction continuously |
| Personal logistics (armor/Spidertron requests) | UPS-critical megabases |
| Construction and repair | — |

Robots are ideal for assembler input/output because items go many places in small batches.
Belts are ideal for ore/plate/circuit highways where one item floods one direction.

### Key design tips

- **Active vs passive provider:** Use active provider at machine outputs (empties immediately,
  prevents machines backing up). Use passive provider only when you want manual control over
  when items enter the network.
- **Buffer chests:** Excellent for pre-staging ingredients at a production cluster —
  request items into buffer chests near machines, then passive-provide locally. Reduces
  cross-network travel distance for bots.
- **Negative numbers in the logistic GUI** are not a bug — they mean bots have reserved
  items in advance. A bot reserves its full carry capacity even if fewer items exist.
- **Logistics groups** (named sets of requests) are global — the same group name in two
  different chests uses exactly the same request list. Changes to one update all.
- **Personal logistics (armor slot):** Once logistic robotics is researched the player can
  set item requests in their own inventory. Bots will deliver requested items and take
  away trash automatically when the player is inside a logistic network.
- **Cargo size research** (worker robot cargo size): increases bot carry capacity from 1 to 4.
  Fully researching this multiplies bot network throughput 4×. Prioritise this research.

### Space Age additions

- **Cargo landing pad**: places items at the logistic network's disposal; also requests items
  from space platforms in orbit (two-way logistics between planet and platform)
- **Rocket silo**: in Space Age, can automatically request items from the logistic network
  based on platform requests — no manual silo loading needed
- Personal logistic requests work on space platforms (player requests satisfied by platform inventory)

### Cargo landing pad mechanics
**Wiki:** https://wiki.factorio.com/Cargo_landing_pad

- Base size: **8×8 tiles**, 80 inventory slots. Only **one can be placed per surface** (you cannot build two landing pads on the same planet).
- Acts as a **passive provider chest** — inserters can pull items out, but cannot insert in. Bots can access it like any other passive provider.
- In Space Age: also acts as a **requester chest** for orbiting platforms. When a platform is stopped over the planet, it drops cargo to satisfy the landing pad's requests. Only one stack drops at a time (unless cargo bays are attached).
- **Cargo bays** (placed adjacent to the landing pad) each add 20 inventory slots AND increase simultaneous drop stack count. Use cargo bays to increase throughput for high-demand items.
- **"Trash unrequested" toggle:** If enabled, the pad moves unrequested items to trash slots, keeping the inventory clear for new deliveries.
- Can be read by the circuit network to check contents — useful for triggering automated rocket launches when buffer is empty.
- **Planetary logistics pattern:** Set the landing pad to request materials from your platform (e.g., green circuits, modules). The platform auto-launches a rocket when in orbit and request is pending. The pad distributes to the logistic network via bots. This is the standard "import on demand" pattern for Space Age bases.

---

## Fluid System (2.0)

**Wiki:** https://wiki.factorio.com/Fluid_system

### How Pipes Work in 2.0

- **Pressure simulation was removed in 2.0.** A continuous pipeline (not split by pumps) transfers fluid **instantly** with no flow restriction, regardless of distance — as long as the segment is not too long (max ~320×320 tiles / 10×10 chunk area). Pipe length is the only practical constraint.
- **Maximum segment length:** if a pipeline spans more than ~320×320 tiles without a pump, fluid stops flowing and the pipe overlay turns red. Break long runs with a pump to reset the limit.
- **Connection throughput limit:** each individual pipe input/output connection has a practical cap of ~4,200 fluid/second (theoretical max 6,000). This is per connection, not per machine — a machine with two output sockets for the same fluid gets ~8,400/s practical throughput.
- **Underground pipes** still have a maximum gap distance (like underground belts) and only connect in two opposite directions. They can cross other underground pipes without mixing.

### Pumps

- Pumps use electricity to push fluid in one direction and block backflow — they "pressurize" the downstream segment, keeping it as full as possible.
- Pumps are **not needed for pressure** in 2.0 (pressure is gone). Use pumps for: splitting long pipelines to stay within the segment length limit, preventing backflow, and circuit-controlled fluid switching.
- Pumps can be disabled by the circuit network, stopping all fluid flow through them — the standard pattern for circuit-controlled fluid routing.
- **The old advice about placing pumps every N tiles to combat pressure loss is obsolete in 2.0.** This was a 1.x mechanic.

### Fluid Mixing

- A pipe segment can only contain **one fluid type**. If two different fluids are routed into the same segment, the game will delete one of them. This is irreversible — the lower-quantity fluid is destroyed.
- The game prevents most accidental mixing when placing pipes (it won't let you connect a water pipe to a crude oil pipe directly), but complex layouts can still cause it. Watch for it when sharing pipe infrastructure.

### Storage Tanks & Circuit Control

- Storage tanks behave like large pipes — they connect to adjacent pipes and attempt to equalize fluid levels with the connected network.
- Tanks can be connected to the **circuit network** to read their fluid level (as a signal) or to receive enable/disable conditions. Use a decider combinator + pump for level-triggered fluid control.

## Circuits & Automation

### Circuit Network Basics
**Wiki:** https://wiki.factorio.com/Circuit_network
The circuit network lets entities communicate via integer signals. Two wire colors exist — **red** and **green** — and each forms a completely separate network. Both can coexist on the same power pole or entity without merging. Signals from a red network and a green network on the same entity are summed together when read.

**Connecting wires:**
- Click one entity, then another to connect them. Wire length is limited per span (stretches further when routed through poles).
- Wires can run pole-to-pole across any distance — run wires from device to pole base.
- Removing a connection: place the same color wire over an existing connection to erase it.
- Shift-click a pole to remove all its connections (first click removes power, second removes circuit wires).
- When connecting to a combinator, attach to the correct input or output side — use "Show details" mode to see orientation.

**What entities can connect:**
Inserters, belts, splitters (2.0.67+), chests, train stops, mining drills, pumpjacks, pumps, offshore pumps, lamps, power switches, storage tanks, roboports, turrets, assembling machines, chemical plants, oil refineries, centrifuges, furnaces (2.0.35+), radars, agricultural towers, programmable speakers, and combinators.

**Signals:** Each signal is a named integer channel — any item, fluid, or virtual signal. Virtual signals include numbers, letters, arrows, planet icons, and 177–241 total options (241 in Space Age). Three special logic signals (Everything, Anything, Each) apply bulk operations.

### Combinators
**Wiki:** https://wiki.factorio.com/Arithmetic_combinator and https://wiki.factorio.com/Decider_combinator
**Constant combinator:**
- Emits up to 20 fixed signals continuously. Acts as an on/off switch (right-click → enable/disable).
- Cannot distinguish which wire color it outputs to — use two constant combinators if you need red vs green separation.
- Two slots with the same signal channel sum their values.

**Arithmetic combinator:**
- Inputs from one side (left/input terminals), outputs from the other (right/output terminals).
- Supported operations: `+`, `−`, `×`, `÷`, `%` (modulo), `^` (power), `<<` (left shift), `>>` (right shift), `AND`, `OR`, `XOR`.
- Can use the **Each** signal for both input and output — applies the operation to every non-zero input channel individually and broadcasts all results on the output side.
- Input and output are separate networks — feeding output back into input creates a feedback loop (e.g., incrementing a counter). Rate of increment = one tick per game update.
- Can join both red and green networks on the input side; their signals are summed.

**Decider combinator:**
- Tests a condition (e.g., iron-plate > 1000) and outputs signals only when the condition is true.
- Since 2.0.7: supports multiple conditions and multiple outputs in a single combinator.
- Output options: output the **input value** of the matching signal, or output a fixed **1**.
- "Output input count" mode: when the condition is true, passes through the actual count of the input signal rather than always outputting 1.
- Special logic signals:
  - **Everything**: condition is true only if it holds for ALL input signals (universal).
  - **Anything**: condition is true if it holds for AT LEAST ONE signal (existential).
  - **Each**: applies condition per-signal; outputs each matching signal.
- Right-hand side of a comparison can be a signal (not just a constant) — when using Everything/Anything, the comparison signal is implicitly excluded from checking itself.

**Selector combinator (Space Age, 2.0.7+):**
Six operating modes:
- **Select input** — sorts input signals by value and outputs one: sort descending (highest), sort ascending (lowest non-zero), or by index position.
- **Count inputs** — outputs the count of unique non-zero input signals on a chosen output channel.
- **Random input** — passes through a random input signal every N game ticks (default: every tick).
- **Stack size** — outputs the stack size of each input item signal. Ignores fluids and virtual signals. Useful for train loading logic: "insert until wagon has N stacks".
- **Rocket capacity** — outputs how many of each item fit in one rocket cargo section. Useful for automating rocket launches: trigger when buffer holds exactly one rocket's worth. Does not output fluids, virtual signals, or items too heavy for a rocket (atomic bomb, rocket silo).
- **Quality filter** (Space Age) — passes through only signals whose item quality meets a condition (greater than, less than, equal to, etc. a chosen quality tier). The key tool for quality recycling loops: filter legendary items to keep, route lower tiers back to the recycler.
- **Quality transfer** (Space Age) — attaches a specific quality grade to a target signal, either directly or by copying the quality from another input signal. Used for quality-aware routing and sorting.

### Common Circuit Patterns
**Wiki:** https://wiki.factorio.com/Circuit_network_cookbook
**See also:** https://wiki.factorio.com/Tutorial:Combinator_tutorial
**Smart chest limits (most common beginner pattern):**
Connect a passive provider chest or storage chest to an inserter. Set the inserter to only operate when the signal for the chest's item is below a threshold — stops filling when full, preventing overflow.

**Train dispatch (station enable/disable):**
Connect a train stop to a chest or belt reader. Set the stop to disable when item count drops below a threshold — trains only visit when there's cargo to pick up. Combine with train limits (set limit to 1 when enabled, 0 when disabled) to prevent queuing.

**Reactor fuel control:**
Read the reactor's temperature via circuit. Insert a fuel cell only when temperature falls below ~900°C. Prevents fuel waste when the reactor is already hot. Use a decider combinator to convert temperature to an inserter enable signal.

**Buffer/overflow circuit:**
Arithmetic combinator computing `current_stock − target_stock` → if result is negative, enable production (inserter on). Keeps a machine running only until a target buffer is reached.

**Clock/timer:**
Arithmetic combinator in feedback loop: `[clock] + 1 → [clock]`. Decider combinator resets it when clock reaches the desired interval. Output a pulse signal on each reset to trigger periodic actions.

**Oil cracking control (classic pattern):**
Connect all oil storage tanks and all cracking pumps to a single circuit network. Set each pump's enable condition to `[input fluid] > [output fluid]`. Example: heavy oil cracking pump enabled when `heavy-oil > light-oil`; light oil cracking pump enabled when `light-oil > petroleum-gas`. This equalizes fluid levels naturally and prevents deadlocks where one tank overflows and stops production.

**Backup steam power (SR latch pattern):**
Connect accumulator to a decider combinator (SR latch). Set: activate steam when accumulator charge < 20%; reset (deactivate) when charge > 90%. The latch prevents rapid on/off cycling (hysteresis). Connect a power switch between the steam generator and main grid.

**Balanced train loading (even chest fill):**
Arithmetic combinator takes `each chest item × (-1/n)`, output each. Connect all n loading chests and all inserters to same red wire. Connect each inserter also to its own chest via green wire. Inserter condition: `everything < 0`. Result: inserters only load into the chest that is below the average — keeps all chests evenly filled. (MadZuri's smart loading station pattern)

**SR latch in a single decider (2.0):**
A decider combinator with multiple conditions can implement both set and reset in one combinator. Set condition latches the output on; a second condition in the same combinator (OR logic) can clear it. Eliminates the need for two combinators in simple latch patterns.

**Combinator tick delay:** Every combinator adds exactly 1 game tick of latency (1/60 second). Chains of combinators accumulate delay — factor this in for time-critical circuits like train safety gates.

**Wire color as network separator:** Use red and green wires as two completely separate networks on the same entities. An arithmetic combinator set to `each + 0 → each` acts as a "color swapper" — it reads one wire color's network and outputs to the other. Also prevents backfeed from an output network into an upstream input network.

---

## Equipment & Vehicles (Space Age Changes)

### Armor Progression
**Wiki:** https://wiki.factorio.com/Mech_armor
| Armor | Grid | Inventory bonus | Notes |
|---|---|---|---|
| Modular armor | 5×5 | +10 | Early, barely enough for basics |
| Power armor Mk1 | 7×7 | +30 | Comfortable mid-game |
| Power armor Mk2 | **6×8** | +40 | Changed from 7×7 in 2.0.7 patch |
| **Mech armor** | **10×12** | **+50** | Space Age exclusive, unlocked via Fulgora |

**Mech armor:**
- Described by the devs as the player "locking themselves in a metal
  sarcophagus, transcending humanity to become the perfect Factorio machine"
- Allows free flight over all obstacles — water, lava, cliffs. Automatically
  flies over trains too (no hotkey needed, it just happens)
- **Demolisher smoke clouds disable flight** and force the player to land,
  even if over lava — intentional design to make Demolisher fights dangerous
- Legendary mech armor scales to a **15×17 grid (255 slots)** — quality
  matters a lot here

### Personal Equipment Changes in 2.0 + Space Age
**Wiki:** https://wiki.factorio.com/Portable_fusion_reactor and
https://wiki.factorio.com/Portable_fission_reactor
**⚠️ Common confusion — fission vs fusion reactors:**
- The old "portable fusion reactor" from pre-2.0 was **renamed** to portable
  fission reactor and kept in the base game (unlocked after yellow science,
  requires uranium fuel cells, 750 kW output)
- A brand new **portable fusion reactor** was added as Space Age exclusive
  content (unlocked near Aquilo, 2.5 MW, no fuel needed, 4×4 grid slot)
- All portable fusion reactors crafted before patch 2.0.7 were automatically
  converted to fission reactors
- One portable fusion reactor is enough to power a fully-loaded combat suit

**Key equipment:**
- **Exoskeleton** — ~30% speed per unit, stack multiple for fast traversal
- **Personal roboport** — construction bots follow you; stack 4 for good
  coverage. Add a battery Mk2 when using roboports — recharge spikes during
  large construction jobs can exceed what the reactor supplies
- **Energy shield Mk2** — essential for Stompers and Demolishers
- **Personal laser defense** — auto-shoots nearby enemies; power-hungry but
  great for clearing small enemies
- **Belt immunity** — prevents belts from moving you. Put this in Spidertrons
  to stop them being swept off belts on Nauvis
- **Night vision** — quality of life on dark planets

**Recommended combat suit (Power armor Mk2 / Mech armor):**
1–2× portable fusion reactor (or 3× fission pre-Space Age), 2× energy
shield Mk2, 2–4× exoskeleton, 4–6× personal laser defense, 1–2× personal
roboport (swap for more shields in active combat zones)

### Vehicles (2.0 Changes)
**Wiki:** https://wiki.factorio.com/Spidertron
- **Tank** now has an equipment grid in 2.0 (add shields, exoskeletons,
  roboports) and can be **remote-controlled from anywhere** on the map
- **Car** also received a small equipment grid in 2.0
- **Spidertron** recipe was simplified in Space Age — no longer requires a
  portable fusion reactor, making it easier to automate. Still needs
  components from multiple planets (raw fish from Nauvis, etc.)
- Spidertron tip: since it walks for you, you can fill your own armor with
  roboports instead of exoskeletons — your Spidertron handles legs, your
  armor handles construction coverage

---

## Space Platforms

**Wiki:** https://wiki.factorio.com/Space_platform
**First thing to know:** Build your first platform in Nauvis orbit. Only
small chunks appear there — no large asteroids, no combat pressure. It's
a safe environment to learn the mechanics before committing to travel.

### Core Rules
- Asteroid collectors and thrusters can only be placed on the **edge** of
  the platform. Thrusters on the **south edge only**, with an 82-tile no-
  build zone extending north from each thruster
- The entire platform foundation acts as a power grid — **no power poles
  needed anywhere**
- No robots/roboports, no railway entities, no chests, no burner devices
  on platforms
- Rockets have a **1-ton payload cap** — each foundation tile weighs 0.2 tons; the hub itself weighs 20 tons (pre-placed, not rocketted). Cargo bays do not add weight, only foundation tiles do.
- Maximum platform size: **200 tiles north** from the center of the hub.
- If the **hub is destroyed**, the entire platform and all contents are permanently lost. The hub cannot be removed.
- **Player travel:** a player traveling to a platform occupies the entire rocket — no inventory items allowed except equipped armor/weapons. Ship everything else separately.

### Shape Matters — Go Narrow
Platform width determines drag. Narrower platforms move significantly
faster. This also means fewer asteroids to deal with, which reduces ammo
consumption — all efficiency factors compound starting with platform shape.
- Build **long north-south, not wide east-west**
- Thrusters are always south — design the platform to be a tall rectangle
- 5 thrusters start hitting diminishing speed returns; adding width to fit
  more thrusters costs more than it gains

### Asteroid Processing
Three types: **metallic** (→ iron ore), **carbonic** (→ carbon),
**oxide** (→ ice → water). All three are needed.

- **Best early layout:** single belt loop past all crushers, with filtered
  inserters pulling out products and returning byproducts to the belt for
  reprocessing
- Thruster fuel = carbon + water. Thruster oxidizer = iron ore + water.
  Thrusters need a **1:1 ratio of fuel to oxidizer** — use circuit logic
  to only run pumps when both fluids are available, or one will deplete and
  stall the other
- **Automate ammo on the platform** — ammo is heavy and expensive to launch
  from the ground. A small assembly machine making firearm magazines from
  iron ore (crushed from metallic asteroids) is standard
- Use circuit logic on crushers to swap recipes dynamically — reprocessing
  unwanted chunk types to get needed ones. Circuits don't benefit from
  productivity modules but greatly improve efficiency
- Dump unwanted items overboard with inserters pointing off the edge — this
  is the intended mechanic, not a trick

### Thruster Fuel Efficiency
- Normal quality thrusters consume **120 fluid/second each** at full thrust
- Thrusters are more fuel-efficient at lower fill levels (30–40% internal
  fuel = best efficiency). Full tanks = faster but disproportionately more
  consumption. For early platforms with limited asteroid processing, throttle
  with pumps on a circuit
- For Gleba runs (spoiling science packs): run full throttle, speed matters
  more than fuel efficiency
- For Aquilo: solar panels output very little that far from the sun.
  Nuclear power is viable on platforms (requires ice → water loop). Fusion
  is the endgame solution. Accumulators can work if charged near inner planets

### Defense During Travel
- Traveling to a new planet sends the platform through a **thick asteroid
  field**. Gun turrets are the most effective for the first legs of a journey
  — add them before the first trip, not after
- Laser turrets are poor against asteroids — stick to gun turrets early,
  upgrade to rocket turrets later, railgun turrets for large asteroids
- Place most defenses at the **front of the platform** — that's where ~90%
  of impacts occur during transit
- Don't add more thrusters than your defense and fuel production can support
  — more speed = more asteroids per second
- After landing and building on a planet, remember to **restock ammo** on
  the platform before the return trip

### Quality on Platforms
Quality multiplies on platforms more than anywhere else:
higher quality collectors have more arms, solar panels need less space,
gun turrets have more range (more time to shoot before impact), chemical
plants produce fuel faster, and all entities have more health to tank hits.
If you have quality components anywhere in your game, use them here first.

### Interplanetary Logistics
- **Orbital drops are free** — space science packs dropped from orbit cost
  nothing to deliver. Set up a dedicated Nauvis-orbit platform just for
  white science production and drop it down continuously
- **Shipping between worlds is free once the platform exists** — the only
  cost is the rockets used to load the platform
- Automate rocket launches: set the platform hub to "request" items;
  planetary silos auto-launch when the platform is in orbit and requests
  are pending
- Create dedicated platforms per route — don't use the same platform as
  both a cargo hauler and a science producer

### First Platform Checklist
1. Build in Nauvis orbit first (safe, chunk-only environment)
2. Set up collector → crusher → belt loop before adding thrusters
3. Establish fuel + oxidizer production with circuit-controlled pumps
4. Automate firearm magazine production from iron ore
5. Add gun turrets along the full perimeter
6. Test travel slowly before committing to long routes
7. Set hub to auto-drop space science packs to base

---

## Quality Mechanics

**Wiki:** https://wiki.factorio.com/Quality and https://wiki.factorio.com/Quality_module
**Quality module base chances (at normal module quality):**

| Module tier | Quality chance | Speed penalty |
|-------------|---------------|---------------|
| Quality module 1 | +1% | −5% |
| Quality module 2 | +2% | −5% |
| Quality module 3 | +2.5% | −5% |

Quality modules themselves can be higher quality — the chance bonus is multiplied by the
module's quality tier (same MODULE_QUALITY_MULT as other modules: ×1.3 uncommon, ×1.6 rare,
×1.9 epic, ×2.5 legendary). Example: legendary quality-3 module gives +6.25% per slot.

**Quality tiers:** normal (0) → uncommon (1) → rare (2) → epic (3) → legendary (**5**). Note: legendary is a 2-tier jump over epic — quality attributes scale with tier strength, so legendary items have 2.5× the bonus of uncommon (not 1.25×).

**Unlock requirements:**
- Uncommon + Rare: Quality module research (needs production science)
- Epic: Epic quality research (needs utility + space science + agricultural science from Gleba)
- Legendary: Legendary quality research (needs all science packs including Fulgora, Gleba, Aquilo, and Vulcanus)

A machine with quality modules rolls each cycle; if it succeeds, the output is one tier higher (up to legendary).

**Quality recycling loop (endgame):**
To push items to legendary: produce quality items in a machine with quality modules →
recycle non-target-quality outputs in a recycler (also with quality modules) → feed
recyclates back. The recycler preserves quality tier of outputs, and quality modules
in the recycler can upgrade products further. The loop is:
1. Machine with quality modules → produces mix of quality tiers
2. Filter inserters separate legendary (keep) from lower tiers (recycle)
3. Recycler with quality modules → recycled outputs can roll higher tier
4. Loop until legendary fraction accumulates

**Key constraint:** This is item/output intensive — design with buffers. Recyclers
output 25% of the input item's ingredient value, so the loop is intentionally lossy.
Only run quality loops for high-value items where legendary stats matter (equipment,
modules, beacons, key machines). Do not run quality loops on bulk intermediates.

**Machine quality:** Higher-quality machines craft faster (+30%/+60%/+90%/+150%
speed for uncommon/rare/epic/legendary). Upgrading machines before modules often
gives better throughput returns. The CLI `--machine-quality` flag models this.

### Quality upcycling loop design (from Tutorial:Quality_upcycling_math)
**Wiki:** https://wiki.factorio.com/Tutorial:Quality_upcycling_math

The quality upcycling loop is a **Markov chain** — each item either becomes higher quality (with probability q per quality tier) or is recycled (–75% items). After enough cycles, every item either becomes legendary or is destroyed.

**Key design insight:** The loop transformation matrix (reassembly × recycler) converges: for typical 5×legendary quality-3 modules in an EM plant + recycler, roughly **1.3 legendary items are produced per 100 normal inputs**. Adding productivity modules to the reassembly stage greatly improves this ratio — productivity multiplies the number of items at each stage, giving more chances to hit quality rolls.

**Worked example: upcycling assembling machine 3 to legendary**
- Setup: EM plant with 4× quality-3 modules (normal quality) for reassembly; recycler with 4× quality-3 modules (normal quality) for recycling.
- Quality-3 module base chance: **+2.5% per slot** → 4 slots = **10% effective quality chance** per craft.
- Per recycle: recycler returns 25% of ingredients (75% loss); each recycled item also has a 10% quality upgrade chance.
- Steady-state result (normal quality-3 modules, no productivity): approximately **1.3 legendary per 100 normal inputs** fed into the loop.
- With **legendary quality-3 modules** (×2.5 mult → **6.25% per slot**, 4 slots = **25% effective chance**): approximately **11–12 legendary per 100 normal inputs** — roughly a 9× improvement.
- Adding productivity modules to the EM plant (e.g. 2× prod-3 + 2× quality-3): each craft produces more items before recycling, compounding quality roll opportunities. This is often the highest-leverage upgrade.
- Key constraint: recyclers cannot accept productivity modules (hard game rule) — only quality modules go in the recycler.

**Module allocation strategy:**
- Reassembly machines (making the item): use a mix of productivity + quality modules. Productivity increases item count (more items = more quality rolls). More quality modules = higher per-item chance. The optimal split depends on the machine's prod bonus and module slot count.
- Recycler machines: quality modules only (recyclers cannot accept productivity modules — this is a hard game rule).
- Machines making legendary output: switch to productivity + speed modules once a machine is only processing legendary inputs — quality modules waste slots on 100%-legendary lines.

**Quality skip probability:** When an item does roll quality, there is always a **10% chance to skip a tier** (e.g., go directly from normal to rare, bypassing uncommon). This is fixed and cannot be changed by modules. At most 10% of items that "get quality" will be rare or better.

**When quality upcycling is worth it:**
- High-value items with large per-stat multipliers: modules, beacons, equipment grid items, space platform machines
- Items with many uses downstream: legendary assembler-3 runs faster, reducing the machine count for everything it produces
- **Not worth it** for: bulk intermediates (iron plates, circuits) where the throughput cost is higher than the value. Focus quality loops on the final machine or equipment tier.

**Selector combinator "Quality filter" mode:** The standard circuit pattern for quality routing. Filter inserters connected to the selector set to "Quality filter ≥ legendary" output only legendary items to keep; the remainder loops back to the recycler. No arithmetic combinator needed — the selector handles quality comparison directly.

---

## Space Age Science Packs

Key ingredients are listed below. For full recipes and research costs, see each planet's wiki page.

Each Space Age planet unlocks one science pack; these are produced on-planet and
shipped back to Nauvis for research. Planet order affects which packs are available.

| Science pack | Planet | Key ingredients (approximate) |
|---|---|---|
| Metallurgic science pack | Vulcanus | Tungsten plate, foundry product (big drill / carbide), calcite |
| Electromagnetic science pack | Fulgora | Superconductor, holmium plate, EM plant product |
| Agricultural science pack | Gleba | Bioflux, nutrients, biochamber product |
| Cryogenic science pack | Aquilo | Quantum processor, lithium plate, cryogenic plant product |
| Promethium science pack | Space (Aquilo route) | Promethium shard (collected from asteroids near Aquilo) |

**⚠️ Exact recipes change with patches — run the CLI
(`--dataset space-age --item metallurgic-science-pack`) for current accurate values.**

**Logistics note:** Science packs spoil (agricultural pack especially — short timer).
Gleba packs must be shipped quickly after production; dedicate a fast platform to
the Gleba→Nauvis route or use a very short hop with full-speed thrusters.

---

## Where to Find More Guides & Resources

**When to use:** Player asks where to learn more, which YouTubers to watch,
or where to find blueprints and community resources.

### Official & Primary Sources
- **Official wiki:** https://wiki.factorio.com — best for mechanics, recipes,
  and tech details. Space Age content is well-documented. ALT + left-click
  any item in-game to open its wiki page directly
- **Friday Facts (FFF):** https://factorio.com/blog — developer design blog
  explaining *why* features work the way they do. FFF #381 covers space
  platforms, FFF #433 covers mech armor, FFF #420 covers the fission/fusion
  reactor rename
- **Official forums:** https://forums.factorio.com — detailed technical
  discussion, megabase planning, and the definitive Space Platform 101 thread
  at viewtopic.php?t=117167

### Reference Tools
- **Kirk McDonald Calculator:** https://kirkmcdonald.github.io/calc.html —
  production chain calculator, best for vanilla and Vulcanus
- **FactorioLab:** https://factoriolab.github.io/space-age — full Space Age
  support including all planets
- **Factorio Cheat Sheet:** https://factoriocheatsheet.com — quick ratios and
  tips (primarily vanilla, some Space Age content)

### Community
- **r/factorio:** https://reddit.com/r/factorio — active community, weekly
  "ask anything" threads, build showcases
- **r/technicalfactorio:** https://reddit.com/r/technicalfactorio — UPS optimization, megabase circuit logic, deep engine theory
- **Official Discord:** https://discord.gg/factorio — linked from the
  official site, very active

### YouTube (Officially Endorsed Channels)
The following channels are listed on the official Factorio website:
**Nilaus**, **KatherineOfSky**, **Trupen**, **Tuplex**, **Xterminator**,
**JD-Plays**, **Michael Hendriks**, **Yama Kara**

- **Nilaus** — methodical tutorials and Master Class series, good for
  structured learning. Space Age series covers each planet in depth
- **Trupen** — entertaining deep-dives, strong Space Age content
- **KatherineOfSky** — long-form commentary, explains reasoning well

Search tip: "Factorio Space Age [planet name] guide" on YouTube — most
major creators did dedicated planet guides at launch.

### For New Players
- **Factoriopedia (Shift+E in-game):** Real-time stats for every item, machine, and recipe based on your current research and planet — more accurate than any external source for your specific save
- The in-game tutorials and tips cover basics well — don't skip them
- Hover everything before googling — tooltips in Factorio are excellent
- First run advice: don't optimize, just build. Spaghetti is fine.
  Understanding *why* things don't scale comes from experience, not guides
- Space Age requires a much larger and more automated base than vanilla —
  if your Nauvis base can't rebuild itself while you're away, strengthen
  it before launching

---

## Reference Guidelines

- **Wiki URLs** in this file are passive references. Open them if the player asks
  for a detail not covered here or wants to read the full article themselves.
- **See also** entries (forums, community searches, factorioprints.com) cannot be
  pre-crawled — surface them to players when the topic comes up.
- **Maintenance:** Every 30 days, run the strategy-topics.md wiki maintenance
  workflow documented in `CLAUDE.md` to re-crawl recently changed pages.
