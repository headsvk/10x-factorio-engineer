<!-- TOPICS: power, solar, solar panels, accumulators, nuclear power, nuclear reactor, heat exchangers, turbines, Kovarex, uranium, U-235, U-238, enrichment, steam power, boilers, steam engines, fusion power, fusion reactor, fusion generator, fluoroketone, lightning rods, lightning collectors, Fulgora power, lightning, power ratio -->

This file covers all power generation methods in Factorio: solar, nuclear, Kovarex enrichment, steam, fusion, and Fulgora lightning.

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
