<!-- TOPICS: logistic robots, robots, roboport, construction bots, logistic bots, chests, requester chest, provider chest, buffer chest, storage chest, circuit network, combinators, arithmetic combinator, decider combinator, selector combinator, constant combinator, circuit patterns, fluid system, pipes, pumps, storage tanks, fluid mixing, equipment, armor, power armor, mech armor, personal equipment, exoskeleton, vehicles, tank, spidertron, car, cargo landing pad -->

This file covers logistic networks, fluid systems, circuit automation, and equipment/vehicles in Factorio.

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

- Base size: **8×8 tiles**, 80 inventory slots. **Multiple can be placed on the same surface** — there is no limit on cargo landing pads per planet.
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
