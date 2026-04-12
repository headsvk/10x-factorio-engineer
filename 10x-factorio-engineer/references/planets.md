<!-- TOPICS: space age, planets, planet order, Vulcanus, Fulgora, Gleba, Aquilo, demolishers, foundry, tungsten, calcite, lava, scrap recycling, holmium, electromagnetic plant, spoilage, biochamber, pentapods, nutrients, Gleba enemies, heating, cryogenic, ammonia, lithium, fusion unlock, space age progression, science packs, metallurgic science, electromagnetic science, agricultural science, cryogenic science, promethium -->

This file covers Space Age planet strategies and the science packs unlocked by each planet.

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
- **Agricultural science packs:** these packs spoil and are destroyed if not consumed in time. A pack gives full science at any freshness level — there is no partial-science scaling based on freshness. The risk is packs reaching 0% and becoming worthless spoilage before the lab consumes them. Keep ag-packs fresh, ship them quickly, and keep Gleba→Nauvis transit time short.
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
- Ice: limited amounts **gathered** (not mined) from lithium ice formations; primarily obtained by crafting via ammoniacal solution separation or ice melting
- Lithium: limited amounts **gathered** from lithium ice formations; primarily crafted from lithium brine (pumpjack)

**Must import:** Stone, iron ore, copper ore, coal — none are available on-planet.

**Unlock requirements for Aquilo:** Requires research from all three prior planets — rocket turrets + advanced asteroid processing + heating towers (from Gleba), asteroid reprocessing (from Vulcanus), and electromagnetic science pack (from Fulgora). Aquilo is explicitly designed as the last planet.

**Fluid exclusivity:** Ammoniacal solution, fluorine, lithium brine, and ammonia cannot be barrelled and transported off Aquilo. Any recipe consuming these fluids is therefore Aquilo-exclusive. This includes: fluoroketone (hot), lithium, fusion power cells, solid fuel from ammonia, and ammonia rocket fuel.

**Quantum processors** can be crafted on Aquilo OR on space platforms — one of the few Aquilo-unlocked items with this flexibility.

**Exclusive unlocks:** Cryogenic plant, Fusion generator, Fusion reactor (all crafted on Aquilo only), Cryogenic science pack, Quantum processor, Foundation (buildable tile for ice ocean), Railgun turret, Railgun.

**Power recommendation:** Bootstrap with nuclear using imported uranium; transition to
fusion reactors long-term. Steam can be generated from melted ice via heat exchangers.
Accumulators charged near inner planets can provide a small buffer.

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
