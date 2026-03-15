<!-- TOPICS: factory layout, main bus, bus, belts, belt throughput, balancer, transport belt, fast belt, express belt, turbo belt, splitter, underground belt, inserter, stack inserter, bulk inserter, city blocks, city block, spaghetti, organic growth, ribbon base, ribbon world, hybrid base, bus to trains, megabase layout transition -->

This file covers factory layout strategies for Factorio, from main bus designs to city blocks and megabase transitions.

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
**Wiki:** https://wiki.factorio.com/Tutorial:Main_bus (bus comparison context)
**See also:** https://forums.factorio.com/viewtopic.php?t=117167 (megabase thread)
**See also:** https://factoriobin.com — largest blueprint sharing site; search "city block" for community designs
**Community reference:** **Nilaus** (YouTube) — "Base-In-A-Book" series and "City Block 2.0" guide are the community gold standard for city block design. Most players learning city blocks start here.

A city block design divides the factory into identical, interchangeable chunks. Each block handles one production task; all inputs and outputs move by train. Blueprints are tiled repeatedly — the entire megabase grows by dropping more copies of the same block.

**Why city blocks instead of a bus:**
- Blueprint reuse: design one block once, print it 50 times.
- Rail scalability: trains replace belts as the throughput backbone — no belt lane count limit.
- Clean expansion: adding a new product = adding a new block type, not reorganising the bus.
- Suited for 1,000+ SPM; overkill below ~500 SPM.
- **Single-purpose blocks are easiest to manage** — one block only smelts iron, another only makes green circuits. Mixed-purpose blocks create inter-block logistics complexity that defeats the blueprint-reuse advantage.

**Common block sizes:**

| Size | Use case | Notes |
|------|----------|-------|
| 50×50 tiles | Compact style | Less room for beacons; suits simpler production lines |
| 100×100 tiles | Most popular balance point | Fits 4-wide rail grid neatly; enough room for beaconed assembler arrays |
| 128×128 tiles | Power-of-2 / roboport-aligned | Aligns with chunk boundaries; cleaner for symmetric layouts |
| 200×200 tiles | Large-block designs | Fewer junctions, more room, but harder to fill efficiently early |

**Rail grid interface:**
- Standard: 4-tile-wide double-track rail around the perimeter of every block.
- Junctions at each corner (or mid-side) with chain signals on entry, rail signals on exit.
- Each block typically has **2–4 train stops**: one or two per input item type, one per output type.
- Roboports along the rail perimeter provide construction coverage and connect to the block's bot network.

**Inside a block:**
- One production category (e.g., all electronic circuit assemblers, or one science pack).
- Requester chests pull inputs from train wagon → bots distribute to machines.
- Active provider chests at machine outputs → bots load onto outbound wagon.
- A substation grid powers machines and roboports; no external power poles needed inside.

**Block-to-block logistics:**
- Each block exports only one item type to a "common pool" station (or to dedicated pickup points).
- Train limits on stations prevent queuing trains that block junctions.
- A LTN (Logistics Train Network) mod or vanilla circuit dispatch (station enables when item > threshold) manages routing automatically.

**When to commit to city blocks:**
- You are planning 1,000+ SPM and want repeatable growth.
- Your bus has reached 4–8 belts wide and is hard to expand further.
- You want most of the factory to run unattended while you focus on bottleneck blocks.

### Spaghetti / Organic Growth
**Community reference:** **KatherineOfSky** (YouTube) — long-form commentary explaining the reasoning behind layout decisions; good for players transitioning out of spaghetti.

**What spaghetti is:** A factory built without upfront layout planning — inserters cross each other, belts curve and loop unpredictably, and the whole thing "just works" but is impossible to read. This is the natural result of building reactively (placing machines wherever there's space).

**Why spaghetti is fine early:** You don't yet know what you'll need. Spending 30 minutes planning a perfect bus for red science is wasted effort — build fast, learn what actually bottlenecks, tear it down later. Many players launch their first rocket from a spaghetti base.

**Golden rule of transitioning:** **Never tear down your starter base until the new base is 100% operational.** Let your spaghetti factory churn out the rails, modules, and assemblers needed to build the organised replacement a few chunks away. Running both in parallel means zero downtime and no science drought.

**Signs spaghetti has outgrown itself:**
- Adding one new assembler requires moving three others.
- You cannot identify bottlenecks by looking at the factory.
- Science packs queue up while one ingredient is missing and you can't find where.
- The map view shows a dense, circular mass with no open expansion paths.

**Spaghetti-to-bus transition (without starting over):**
1. Build the new bus *adjacent* to (or past the edge of) the spaghetti — don't route through it.
2. Tap into the spaghetti's outputs as inputs to the new bus: run a belt from the old assembler cluster to the new bus lane.
3. Build new sub-factories off the bus side-by-side with the old spaghetti clusters.
4. As each old cluster is replaced by a bus-fed version, decommission the old belts.
5. The spaghetti can run in parallel for weeks — you don't need a single cutover moment.

**Organic growth philosophy:** It is valid to extend and patch a spaghetti factory indefinitely. The goal is a working factory, not a beautiful one. Many experienced players deliberately use messy "bootstrap" factories for early-game throughput and only clean up when they decide to scale to megabase SPM.

**Tips for managing spaghetti:**
- Use circuit-connected chests to read inventories and spot starvation without tracing belts visually.
- Blueprint the sections you want to *replace* (not the spaghetti itself) so you can paste the new version quickly.
- Label train stops and inserters with constant combinators so you can find what feeds what.

### Ribbon Base
**Community reference:** **Zisteau** (YouTube) — "Meiosis" series is the classic ribbon world masterclass. **DoshDoshington** (YouTube) — highly constrained and heavily modded survival runs; good for extreme ribbon challenges.

A ribbon base constrains the factory to a narrow horizontal (or vertical) strip — typically 50–200 tiles wide — running the full length of the map. The design trades spatial freedom for extreme simplicity of defense and resource flow.

**Map settings to create a ribbon world:**
- Water coverage: Very High or Maximum
- Terrain segmentation: High or Very High
- Map size: Large or Maximum (need length)
- Result: long, narrow land corridors separated by large water bodies — only 2 exposed fronts (east and west), water walls the north and south.

**Design principles:**
- **One-directional flow:** Ore enters on one end, processed goods exit the other. Everything moves left-to-right (or right-to-left).
- **Single main belt or bus:** Run one or two rows of express belts down the centre. Sub-factories branch off the sides, return nothing upstream.
- **Width discipline:** Keep the ribbon as narrow as possible — **~128 tiles** is a common practical width (aligns to chunk grid); 100–150 is comfortable. Wider = harder to defend the flanks and violates the forced-linear discipline.
- **Strictly linear train network:** Your main rail artery must run the full ribbon length with zero bottlenecks — you can only expand strictly east or west. Trains are essential from the start; running belts 2,000+ tiles is not viable.

**Advantages:**
- **Natural walls:** Water flanks eliminate two of four biter attack directions. Only east and west walls need turrets — biter defense becomes trivially easy at the two chokepoints.
- **Forced linearity:** You cannot build circular dependencies — everything flows one direction.
- **Simple expansion:** Extend the ribbon eastward; all infrastructure follows the same axis.

**Disadvantages:**
- **Long transit distances:** End-to-end distances can exceed 2,000 tiles on a large map. Trains become essential early.
- **Oil patch position:** Oil patches may appear only at one end of the ribbon — plan accordingly.
- **No backtracking:** Because your main artery must be efficient with zero bottlenecks, a congested rail segment blocks the entire factory.
- **Space Age:** The ribbon map applies only to Nauvis. Other planets generate independently with normal terrain — you'll need standard factory layouts on Vulcanus, Fulgora, Gleba, and Aquilo.

**Recommended ribbon width:** ~128 tiles for a clean grid-aligned factory; narrower (50–80 tiles) for a hardcore challenge run.

### Hybrid (Bus → Train → City Block progression)
**Community reference:** **Yamacara / Yama Kara** (YouTube) — covers bus-to-train transition strategy and hybrid base building.

Most factories naturally evolve through several phases. You do not need to commit to one paradigm — many successful megabases run all three simultaneously.

**Phase 1 — Spaghetti bootstrap (0 to ~50 SPM):**
Build fast, don't plan. Get red + green + blue science automated. The factory will be messy — that's fine.

**Phase 2 — Main bus (50 to ~200 SPM):**
When you have 3+ science packs and throughput is the bottleneck, build a bus. The bus inflection point is typically at blue science — oil processing creates too many cross-dependencies for ad-hoc layouts. Trigger: adding one belt worth of iron plates requires moving 5 inserters.

**Phase 3 — Train outposts alongside the bus (200 to ~500 SPM):**
When nearby ore patches deplete (need to go 300+ tiles for fresh ore), add trains. Key trigger: running a belt >200–300 tiles. Also the right time to **smelt at the mine mouth** — plates stack to 100 vs ore stacks to 50, so a wagon holds 2× more resource-equivalent in plates. Trains handle ore and plates; the bus handles intermediates.

**Phase 4 — Trains as primary logistics (500 to ~1,000 SPM):**
New production lines get train stops instead of bus connections. The bus narrows to a "local feeder" for a cluster of related assemblers. New ore → new mine outpost → train to central smelter → train to consumers. Each new factory module is self-contained.

**Phase 5 — City block megabase (1,000+ SPM):**
Tear down the old patchwork and lay out a consistent rail grid. Every production block is a blueprint copy. The bus disappears entirely — trains carry everything. Trigger: SPM target requires more throughput than even 8-lane express belts can carry, or you want to mass-print blueprints without redesigning each time.

**Practical hybrid pattern (most common real factories):**
- Main bus → handles circuits, steel, plastic, other intermediates (keep it; don't replace what works)
- Trains → handle ore, plates, coal, stone, oil products — add trains when local ore runs out (300+ tiles to next patch)
- Robots → handle science pack delivery to labs, module insertion, station loading/unloading
- **Keep the bus for the mall and low-volume science lines** even in late-game hybrid play. Trains excel for bulk high-volume items; mixing in trains for a 1-belt science ingredient is over-engineering.

You will likely never fully abandon one mode before the next. The hybrid is the destination, not a stepping stone.

**See also:** https://forums.factorio.com (search "megabase progression") — official forums have the best transition guides. Prefer posts dated 2024+ for Factorio 2.0 accuracy.
