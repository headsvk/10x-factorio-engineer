<!-- TOPICS: trains, train network, rail, railway, signals, rail signals, chain signals, deadlock, train schedule, train groups, interrupts, wildcard, stacker, train stop, circuit dispatch, train limits, elevated rails, no path, megabase trains -->

This file covers train networks, signalling, scheduling, and megabase train design in Factorio.

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

### Locomotive quality and fuel (2.1.10+)

**Wiki:** https://wiki.factorio.com/Locomotive

Since **2.1.10**, locomotive quality improves both **max speed** and **acceleration** —
it is no longer just a survivability stat. On wood/coal the max-speed ladder runs
259 → 267 → 275 → 283 → **298 km/h** from normal to legendary (~+15%), and acceleration
scales alongside it. The gain applies on top of whatever fuel you burn, so quality
locomotives and better fuel compound.

Planning implications:
- Upcycling locomotives is a genuine throughput upgrade on long hauls, not a cosmetic one
  — worth doing before adding track or more trains to a saturated line.
- **Trains throttle their burn rate once they reach max speed**, so the fuel duration
  quoted for any fuel is a *minimum*. Real-world fuel life on long straight runs is
  longer than the table suggests, which makes refuelling intervals easier than they look
  on paper.
- **Quality locomotives are more fuel-efficient, not less.** A locomotive always burns at
  its listed energy-consumption rate — a flat **600 kW**, identical in vanilla and Space
  Age — so the extra acceleration power that quality grants is *free*: the same fuel buys
  more accelerating force. Combined with the throttling above, a quality loco spends less
  of the trip accelerating and more of it coasting at max speed, so it travels further per
  unit of fuel. The effect is marginal on light trains and **large on trains heavy enough
  to accelerate badly** — which is exactly where you would otherwise be tempted to add a
  second locomotive. Quality fuel stacks with this for the same reason.

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

### Why a train picked that route — pathfinding penalties

**Wiki:** https://wiki.factorio.com/Railway/Train_path_finding

Trains run A* over rail *segments*, scoring each candidate path and taking the lowest total.
Base cost is simply segment length, then penalties dominate:

| Situation in a block on the path | Penalty |
|---|---|
| Path routes **through a train stop** | **+2000** |
| Manually controlled train parked, **no passenger** | **+7000** |
| Automatic train with no schedule | +7000 |
| Manually controlled train parked, with passenger | +2000 |
| Rail signal forced red by circuit network | +1000 |
| Train stopped at a stop with no other valid stops in schedule | +1000 |
| Train with no path | +1000 |
| Train stopped at a train stop | +500 |
| Train arriving at a stop or signal | +100 |
| Train waiting at a signal | +100, +0.1 per tick already waited |
| Block occupied by a train | +2 × block length ÷ blocks-from-start |

What this means in practice:
- **Never run a mainline through a station.** The +2000 for passing through a stop is larger
  than most detours, so through-station routing distorts the whole network — but it also means
  trains reliably prefer bypass tracks, so building them works.
- **A parked manual train without a passenger is a 7000-point wall.** Leaving a personal train
  on a shared line is the most common cause of "my network suddenly reroutes everything."
  Park on a siding, not the main.
- Occupied-block penalties are **divided by distance from the train**, so congestion far ahead
  barely affects routing — trains do not plan around traffic they haven't reached. Don't expect
  self-balancing across long routes; use stackers and train limits instead.
- **Circuit-red signals cost 1000, not infinity** — a red signal discourages a route rather
  than forbidding it, which makes circuit-controlled signals a soft routing tool.
- Waiting trains accrue +0.1/tick, so a long-blocked path gradually becomes unattractive and
  the train eventually looks elsewhere. Repathing at chain signals is re-checked every 5 s.

### Train Limits & Circuit Dispatch
**Wiki:** https://wiki.factorio.com/Circuit_network_cookbook

Set a **train limit** on a station to prevent trains queuing at a full station. Combine with
circuit conditions to dynamically enable/disable stations based on chest contents — the standard
pattern for decentralised ore pickup (station enables itself when ore > threshold, disables when empty).

### Megabase Train Design

For 1000+ SPM: consistent train size matters more than which size you pick (1-4, 2-4, and 1-8
are all common). All stations for the same resource must accommodate the same train length.
Stacker loops before busy stations prevent trains blocking the main line while waiting.
