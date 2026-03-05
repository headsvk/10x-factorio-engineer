# Factorio Strategy Topics

This file lists discussion topics Claude can help with, along with the best
sources to fetch on demand. When a topic comes up, fetch the listed URLs,
read the content, and use it to ground the discussion. Don't pre-load — only
fetch when the player actually asks.

Claude already has strong training knowledge on most of these topics. Fetch
sources when the player wants specifics, current blueprints, or when the
topic is Space Age content (newer, less represented in training data).

---

## Factorio Cheat Sheet (factoriocheatsheet.com)

**What it is:** A compendium of the most common Factorio game facts — build
ratios, tips/tricks, and links to further information. Covers early game
through late game in a linear progression. Useful for both new and veteran
players.

**Fetch limitation:** The site itself is a JavaScript app — Claude cannot
fetch `https://factoriocheatsheet.com/` directly and get useful content.

**Instead, fetch individual section HTML files from GitHub source:**

Base URL pattern:
```
https://raw.githubusercontent.com/deniszholob/factorio-cheat-sheet/master/src/app/cheat-sheets/game-base/<section>/<section>.component.html
```

**Known sections and when to fetch them:**

| Section | Fetch URL suffix | Fetch when player asks about... |
|---|---|---|
| `belts/belts` | belt throughput, compression, lane balancing |
| `balancers/balancers` | belt balancers, input/output balancing, blueprint strings for balancers |
| `mining/mining` | mining drill ratios, ore patch coverage, electric vs burner drills |
| `oil/oil` | oil processing ratios, cracking, petroleum vs light vs heavy |
| `nuclear/nuclear` | reactor neighbor bonus, heat exchanger/turbine counts, pump ratios |
| `modules/modules` | productivity, speed, efficiency modules, beacon setups |
| `tips/tips` | general tips, keyboard shortcuts, early game advice |
| `train-colors/train-colors` | train station color coding conventions |
| `blueprint-copier/blueprint-copier` | how to copy/share blueprints |

**How to read the fetched HTML:**
The files use Angular component syntax — ignore wrapper tags like
`<app-cheat-sheet-template>` and `<app-ratio-card>`. The human-readable
content (ratios, tables, explanations) is in plain text and standard HTML
inside them. Extract and present that content directly.

**Version caveat:** The cheat sheet's last tagged release was explicitly
"Last Factorio v1" — content is reliable for vanilla mechanics but may be
incomplete for Factorio 2.0 changes and Space Age. Cross-reference with
the Factorio wiki for anything 2.0-specific.

**Direct link to give players:** https://factoriocheatsheet.com/
(works in browser even though Claude can't fetch it directly)

---

## Factory Layout Strategies

### Main Bus
**Fetch:** https://wiki.factorio.com/Tutorial:Main_bus
**When to fetch:** Player asks how to set up a bus, what to put on it, how
wide to make it, when to abandon it, or how to transition away.
**Claude knows:** Core concept well. Fetch wiki for specific ratios and
diagrams.

### City Blocks
**Fetch:** Search `site:forums.factorio.com city block design` or
`site:factorioprints.com city block`
**When to fetch:** Player asks about block sizing, rail grid alignment,
whether city blocks are worth it, or how to start one.
**Claude knows:** Concept and tradeoffs well. Community pattern not on wiki —
fetch forums for specific sizing discussions (common choices: 100x100,
128x128, 200x200).
**Key points Claude should cover without fetching:**
- Each block is self-contained: inputs/outputs via train
- Block size tradeoff: bigger = more flexible, smaller = more modular
- Rail grid must be consistent across all blocks
- Best suited for megabase scale, overkill for early game

### Spaghetti / Organic Growth
**Fetch:** Rarely needed — Claude knows this well.
**When to fetch:** Only if player wants specific teardown/reorganization advice.

### Ribbon Base
**Fetch:** Search `site:forums.factorio.com ribbon base`
**When to fetch:** Player asks about ribbon world maps or horizontal-only designs.

### Hybrid (Bus → Train → City Block progression)
**Fetch:** Search `site:forums.factorio.com bus to train city block transition`
**When to fetch:** Player asks about when to transition between strategies
or how to evolve their factory over the course of a playthrough.
**Note:** Prefer official forums over Steam discussions — Steam threads are
often 1.x era and may not reflect 2.0 changes.

---

## Train Networks

### Basic Train Setup
**Fetch:** https://wiki.factorio.com/Tutorial:Train_network
**When to fetch:** Player asks about signaling, deadlocks, or station setup.

### Train Limits & Circuit Logic
**Fetch:** https://wiki.factorio.com/Circuit_network_cookbook
**When to fetch:** Player asks about dynamic train dispatch, stack limits,
or avoiding congestion.

### Megabase Train Design
**Fetch:** https://forums.factorio.com/viewtopic.php?t=78544
**When to fetch:** Player planning 1000+ SPM factory with train-based logistics.

---

## Megabase Planning

### General Megabase Advice
**Fetch:** Search `site:forums.factorio.com megabase planning 2.0`
**When to fetch:** Player asks about SPM targets, module planning, UPS
optimization, or where to start a megabase.
**Key points without fetching:**
- Pick SPM target first, use calculator to work backward
- Consistent train size matters more than which size you pick
- Grid-aligned blueprints for rail/power/roboports save enormous time
- Move smelting to mine mouth first — it's the easiest decentralization step

### UPS Optimization
**Fetch:** Search `site:forums.factorio.com UPS optimization megabase`
**When to fetch:** Player complains about lag or asks about performance.
**Key points:** Fewer entities = better UPS. Prefer direct insertion over
belts where possible at megabase scale. Beacon coverage matters.

---

## Blueprints

### Finding Blueprints
**Primary sites to recommend:**
- https://factorioprints.com — largest community collection
- https://factorio.school — curated, searchable
- https://www.reddit.com/r/factorio/wiki/index — links to notable blueprint books

**When player asks for blueprints:** Send them to factorioprints.com and
suggest search terms. Don't try to generate blueprint strings — they are
base64+zlib encoded and must come from the game or a verified source.

**Decoding blueprint strings:** If a player pastes a blueprint string,
Claude can explain what's in it conceptually but cannot decode the binary
format without tooling.

### Notable Blueprint Collections (fetch page for current links)
**Fetch:** https://factorioprints.com when player asks for specific blueprint books.
- Nilaus's city block book — widely used reference
- Megabase Modular Train Grid (2.0): https://factorioprints.com/view/-NVIYNeGyxfJfkfz3MGF
  (note: minimal Space Age updates per author)

---

## Space Age Strategies

### General Space Age Progression
**Fetch:** https://wiki.factorio.com/Space_Age
**When to fetch:** Player asks about planet order, what to prioritize, or
how Space Age changes the endgame.
**Recommended planet order (community consensus):**
1. Vulcanus — easiest, great for bootstrapping production
2. Fulgora — harder but holmium unlocks key recipes
3. Gleba — hardest logistics due to spoilage
4. Aquilo — last, requires most infrastructure

### Vulcanus (Foundry / Tungsten)
**Fetch:** https://wiki.factorio.com/Vulcanus
**Key points:** Foundry is 4× speed — move all smelting here eventually.
Demolishers patrol but have fixed paths. Calcite + lava = free smelting.

### Fulgora (Scrap Recycling / Holmium)
**Fetch:** https://wiki.factorio.com/Fulgora
**Key points:** No water, lightning power only. Scrap recycling is
probabilistic — design for averages not exact ratios. Electromagnetic
plant has 5 module slots.

### Gleba (Agriculture / Spoilage)
**Fetch:** https://wiki.factorio.com/Gleba and https://forums.factorio.com/viewtopic.php?t=120218
**When to fetch:** Player asks about Gleba logistics, spoilage, or combat.

**Key production points:**
- Organic items spoil — avoid buffers, design tight throughput loops
- Biochamber for agricultural recipes, nutrients are the key input
- Pentapod eggs are a key ingredient for Biochambers — but they spoil and
  hatch into enemies if left too long. Automate carefully.

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
**Fetch:** https://wiki.factorio.com/Aquilo
**Key points:** Everything freezes without heating. Ammonia + ice + lithium
are key resources. Carbon fibre unlocks late recipes. Hardest planet.

---

## Power

### Solar + Accumulators
**Fetch:** https://wiki.factorio.com/Solar_panel for the official per-planet
multipliers, or https://forums.factorio.com/viewtopic.php?t=119040 for the
definitive community deep-dive including quality combinations.

**When to fetch:** Player asks about solar on any Space Age planet, or about
quality interactions with solar. For plain Nauvis solar Claude knows the ratio well.

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
**Fetch:** https://wiki.factorio.com/Tutorial:Nuclear_power
**When to fetch:** Player asks about nuclear ratios, neighbor bonus, water
supply, steam storage, or fuel efficiency.

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

### Steam (Early Game)
**Fetch:** Never needed — Claude knows this well.

### Fusion Power (Space Age)
**Fetch:** https://wiki.factorio.com/Fusion_reactor and https://wiki.factorio.com/Fusion_generator
**When to fetch:** Player asks about fusion setup, generator ratios, fluoroketone
loop, neighbor bonuses, or fusion vs nuclear.

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
**Fetch:** https://wiki.factorio.com/Lightning_rod and https://wiki.factorio.com/Lightning_collector
**When to fetch:** Player asks about Fulgora power setup, accumulator sizing,
rod vs collector choice, or island power management.

**Two buildings:**

| Building | Unlock | Protection radius | Energy efficiency | Recipe cost |
|---|---|---|---|---|
| Lightning rod | On arrival | Small | ~25% normal, 50% legendary | Cheap (steel + copper + brick) |
| Lightning collector | After EM science | Large (~3× area) | ~50% normal, 100% legendary | Expensive (holmium + batteries) |

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
**Fetch:** https://wiki.factorio.com/Turret for the full list.
**When to fetch:** Player asks which turret to use, where to unlock them,
or how they compare.

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

### Nauvis (Biters)
**Fetch:** https://wiki.factorio.com/Enemies
**When to fetch:** Player asks about pollution spread, biter evolution, or
expansion behavior.
**Key points:**
- Wall + flamethrower + laser turret is the classic reliable setup
- Artillery for passive nest clearing once researched
- Circuit network target priorities help conserve ammo — set rocket turrets
  to Behemoth-only, lasers handle the rest
- Setting laser turrets to prioritize spitters reduces damage taken in large attacks

### Vulcanus (Demolishers)
**Fetch:** https://wiki.factorio.com/Demolisher
**When to fetch:** Player asks how to deal with Demolishers or expand on Vulcanus.
**Key points:**
- Demolishers patrol fixed paths — scout before building
- Small Demolishers can be killed with tanks + cannon shells early on
- Railgun is very effective against Demolishers, especially fired along their body length
- Walls are useful here unlike Gleba — Demolishers don't ignore them
- Rocket turrets essential for medium and large Demolishers
- No biter expansion — only fixed patrol routes, so aggressive expansion
  is safer than Nauvis once paths are mapped

### Gleba (Pentapods)
**Fetch:** https://wiki.factorio.com/Pentapod and https://wiki.factorio.com/Stomper
**When to fetch:** Player struggles with Gleba defense or asks about pentapod types.
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
**Fetch:** https://wiki.factorio.com/Aquilo
**When to fetch:** Player asks about Aquilo enemies or defense.
**Key points:**
- Enemies are Mites — less aggressive than other planets but the environment
  itself (freezing) is the real threat
- Railgun turret unlocked here — effective for large targets
- Bots have 500% energy usage on Aquilo — factor into power planning
- Defense is less of a concern than keeping the factory from freezing

### Space Platforms (Asteroids)
**Fetch:** https://wiki.factorio.com/Space_platform
**When to fetch:** Player asks about platform defense or asteroid management.
**Key points:**
- Asteroids are the only threat — no enemy units
- Gun turrets handle small asteroids, rocket turrets for medium/large
- Railgun turrets are very effective against huge asteroids due to high physical damage bypassing flat resistance
- Aquilo-bound platforms must carry rocket turrets to survive large asteroid density on that route
- Ammo supply on platforms is a logistics puzzle — belt-fed turrets from
  onboard production is the reliable approach
- Ice-heavy asteroid zones (near Aquilo) can starve metal production — plan for mixed asteroid chunk collection

### Turret Creep
**Fetch:** Search `site:forums.factorio.com turret creep`
**When to fetch:** Player asks about pushing back biters aggressively.
**Key points:**
- Place turrets just outside biter attack range, let them clear nests,
  advance, repeat
- Tesla turrets make turret creep safer by slowing counterattacks
- Artillery mostly replaces turret creep once available

---

## Circuits & Automation

### Circuit Network Basics
**Fetch:** https://wiki.factorio.com/Circuit_network
**When to fetch:** Player is new to circuits and asks how to get started.

### Combinator Logic
**Fetch:** https://wiki.factorio.com/Arithmetic_combinator and
https://wiki.factorio.com/Decider_combinator
**When to fetch:** Player asks about specific combinator setups.

### Common Circuit Recipes
**Fetch:** https://wiki.factorio.com/Circuit_network_cookbook
**When to fetch:** Player asks for a specific automation pattern
(e.g. smart train dispatch, auto-balancing storage, kill-switch for machines).

---

## Equipment & Vehicles (Space Age Changes)

### Armor Progression
**Fetch:** https://wiki.factorio.com/Mech_armor
**When to fetch:** Player asks about mech armor abilities, unlock requirements,
or quality grid scaling.

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
**Fetch:** https://wiki.factorio.com/Portable_fusion_reactor and
https://wiki.factorio.com/Portable_fission_reactor
**When to fetch:** Player asks about the portable fusion vs fission confusion,
or power budgets for armor setups.

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
**Fetch:** https://wiki.factorio.com/Spidertron
**When to fetch:** Player asks about Spidertron recipe, vehicle grids, or
tank remote control.

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

**Fetch:** https://wiki.factorio.com/Space_platform
**When to fetch:** Player asks about platform design, asteroid processing,
thruster fuel, defense, or interplanetary logistics.

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
- Rockets have a **1-ton payload cap** — foundation (steel + copper) is
  cheap but heavy. Expect 5–10 rockets of foundation for a full platform.
  Cargo bays do not add weight, only foundation does

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
- **Factorio Prints:** https://factorioprints.com — largest community
  blueprint collection
- **factorio.school:** https://factorio.school — curated, searchable blueprints

### Community
- **r/factorio:** https://reddit.com/r/factorio — active community, weekly
  "ask anything" threads, build showcases
- **r/technicalfactorio** — circuit network and advanced optimization
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
- The in-game tutorials and tips cover basics well — don't skip them
- Hover everything before googling — tooltips in Factorio are excellent
- First run advice: don't optimize, just build. Spaghetti is fine.
  Understanding *why* things don't scale comes from experience, not guides
- Space Age requires a much larger and more automated base than vanilla —
  if your Nauvis base can't rebuild itself while you're away, strengthen
  it before launching

---

## Fetch Guidelines

- **Always fetch Space Age wiki pages** — newer content, less in training data
- **Fetch forums/Steam discussions** for city blocks and megabase topics —
  these are community patterns not covered by the wiki
- **Don't fetch** for basic mechanics (belts, inserters, furnaces), vanilla
  recipes, or early-game advice — Claude knows these well
- **Fetch factorioprints.com** only when player wants an actual blueprint,
  not for general discussion
- When fetching, read the page and synthesize — don't quote large blocks
