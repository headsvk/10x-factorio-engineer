<!-- TOPICS: space platforms, space platform, platform, asteroids, asteroid processing, thruster, thruster fuel, hub, platform defense, interplanetary logistics, cargo landing pad, orbital drops, platform shape, first platform, platform quality -->

This file covers space platform construction, asteroid processing, defense, and interplanetary logistics.

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
- No robots/roboports, no railway entities, no burner devices on platforms
  (chests and containers are allowed)
- Rockets have a **1-ton payload cap** — each foundation tile weighs 0.2 tons; the hub itself weighs 20 tons (pre-placed, not rocketted). Cargo bays do not add weight, only foundation tiles do.
- Maximum platform size: **200 tiles north** from the center of the hub.
- If the **hub is destroyed**, the entire platform and all contents are permanently lost. The hub cannot be removed.
- **Player travel:** a player traveling to a platform occupies the entire rocket — no inventory items allowed except equipped armor/weapons. Ship everything else separately.
- **Foundation must be one connected area** — no detached islands and no holes. Plan expansions outward from the existing shape; you cannot pre-place a distant section and bridge to it later.
- A new platform starts as a **10×10 foundation with the hub at its centre**, surrounded by empty space; nothing can be built on empty space, so expansion is the first job.
- Players aboard a platform are **locked inside the hub and cannot walk around** — you operate entirely through remote view until dropping to a surface.
- ⚠️ **Spoiled eggs hatch on platforms.** Biter and pentapod eggs that spoil in the hub or on a belt spawn enemies exactly as they would on the ground, and those enemies neither suffocate nor take environmental damage — they simply attack the platform. Egg freight needs the same spoilage discipline in orbit as on Gleba.

### Shape Matters — Go Narrow
Platform width determines drag. Narrower platforms move significantly
faster. This also means fewer asteroids to deal with, which reduces ammo
consumption — all efficiency factors compound starting with platform shape.
- Build **long north-south, not wide east-west**
- Thrusters are always south — design the platform to be a tall rectangle
- **Optimal thruster count = as many as fit without widening the platform.** Drag
  depends strongly on platform **width in tiles** and only weakly on mass, so widening
  the platform to fit another thruster adds drag that cancels the extra thrust — at a
  fixed fuelling rate it makes the platform *slower*. Each thruster is 4 tiles wide, so
  a 32-tile-wide platform tops out at 8. Stacking thrusters vertically along the same
  south edge does not widen the platform and so does not pay this penalty.
- Thrust has diminishing returns in thrusters or fuel **alone**; scaling both together
  is what gives linear gains

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
- **Quality modules do nothing in reprocessing recipes** (the "space casino" nerf,
  FFF-442). Put quality modules in the **crushers** — that's where the roll happens — and
  upcycle the resulting ore in a recycler loop. See `quality.md`.

### Thruster Fuel Efficiency
- A normal-quality thruster burns up to **120 units/s of thruster fuel AND 120 units/s
  of oxidizer** — 240 units/s of fluid total per thruster at full reserves. Scales with
  quality (legendary: 300 + 300).
- **Efficiency is highest at the LOWEST fill and falls monotonically as reserves fill** —
  100% efficiency at ≤10% fill, 86% at 30%, 72% at 50%, 51% at 80%+. There is no
  mid-range sweet spot; a fuller tank is always less efficient per unit of thrust.
- **Thrust caps at ~75% fill.** From 75% to 100% reserve the thruster produces the same
  100% relative thrust, so topping reserves past that buys no speed at all — and going
  from 75% to 80% raises consumption from 186% to 200% for zero thrust gain. Keeping
  reserves below ~75% is free.
- **Throttle band: 15–25% fill** is the practical target when a trip must run on
  pre-stored fuel. Total fuel per trip generally falls as throttle drops (better
  efficiency more than pays for the longer flight), so the true minimum is usually the
  lowest throttle; on wide low-thrust or very heavy platforms the slowest speed is *so*
  slow that a shallow optimum appears around 15–25% instead. Throttle with pumps on a
  circuit.
- For Gleba runs (spoiling science packs): speed matters more than fuel efficiency, so
  run reserves up — but there is still no reason to exceed ~75–80% fill.
- For Aquilo: solar panels output very little that far from the sun.
  Nuclear power is viable on platforms (requires ice → water loop). Fusion
  is the endgame solution. Accumulators can work if charged near inner planets

### Asteroid Sizes and the Split Chain
Destroying an asteroid does not remove it from the fight — it **splits into three of
the next size down**, so ammo demand cascades:

| Size | Spawns | On destruction | HP (normal / promethium) | Key resistances |
|------|--------|----------------|--------------------------|-----------------|
| Huge | Beyond Aquilo | → **3 big** | 5000 / 10000 | Laser 99%, Physical **3000**/10% |
| Big | Beyond Fulgora and Gleba | → **3 medium** | 2000 / 4000 | Laser 95%, Physical **2000**/10% |
| Medium | In space, and orbit of every planet except Nauvis | → **3 small** | 400 / 800 | Laser 90%, Physical 10% |
| Small | Never spawns naturally (only from splits) | → **2 chunks** | 100 / 200 | Laser 20% |
| Chunk | Only type in Nauvis orbit | collectable resource | no health | harmless |

**Promethium asteroids have double the health** of the metallic/carbonic/oxide variants
of the same size — budget roughly 2× the firepower for promethium runs.

Planning consequences:
- One huge asteroid ultimately yields **3 → 9 → 27 bodies and 54 chunks** if killed by
  splitting all the way down. Budget ammo for the whole cascade, not the first hit.
- The physical numbers are **flat reduction**, not percentages: big absorbs 2000 and huge
  3000 damage *per hit* before the 10% multiplier applies. Any weapon whose per-shot
  damage is below that flat value does literally nothing. This is why gun turrets are
  ineffective from big upward (rocket turrets are usually better), and why huge asteroids
  require a **railgun turret** — killing one with small arms isn't slow, it's impossible.
- Laser resistance climbs 20% → 90% → 95% → 99%, so lasers are the wrong answer at every
  size above small.
- Damage scales too: small chips the platform, medium can destroy several foundation
  tiles, big passes straight through destroying everything in its path, and huge will
  end the platform outright if nothing can kill it.
- This is why Nauvis orbit is the safe starting ground — only small chunks appear there.

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

**Asteroid collector, per tier-level** (so ×5 at legendary): **+1 arm**, +5% arm speed,
**+2 collection area** in both dimensions, +5 storage — at the cost of +10% active power
per arm and +10% drain. The extra arms and area are what make quality collectors
disproportionately strong: a legendary collector gains **5 arms** and a 10-tile-larger
catch area, turning collection from the platform's bottleneck into a solved problem.
Solar panels gain +30% output per level and accumulators +100% capacity per level, which
matters on the outer-planet routes where panel area is the binding constraint.

**The starter pack's quality sets the hub's quality.** Launching a higher-quality space
platform starter pack produces a correspondingly higher-quality **space platform hub** —
so hub quality is decided at launch and is not something you retrofit later. The
**foundation is always normal quality regardless**, because tiles are not affected by
quality at all. Every platform starts with the hub plus 46 foundation (10 in the hub's
inventory, 36 placed as a ring around it). Planning consequence: if you intend a platform
to be a long-lived hauler, spend the quality on the starter pack up front rather than
building a normal platform and hoping to upgrade the hub in orbit.

### Interplanetary Logistics
- **Orbital drops are free** — space science packs dropped from orbit cost
  nothing to deliver. Set up a dedicated Nauvis-orbit platform just for
  white science production and drop it down continuously
- **Shipping between worlds is free once the platform exists** — the only
  cost is the rockets used to load the platform
- Automate rocket launches: set the platform hub to "request" items;
  planetary silos auto-launch when the platform is in orbit and requests
  are pending
- Since 2.1.7, orbital requests are far more flexible: the hub can **set its
  requests from the circuit network**, a request can **import from any planet**
  (not just the one below), and platforms can **request from other platforms**.
  Small requests are batched into one rocket, and automated launches can use
  **mixed rockets** filled by hand or by inserters — so low-volume items no
  longer each cost a dedicated rocket
- Create dedicated platforms per route — don't use the same platform as
  both a cargo hauler and a science producer

**Landing pad unloading bay (new building):** solves the long-standing problem that
inserters cannot pull from a cargo bay. The unloading bay *can* be interacted with by
inserters, and it unloads from **all connected cargo bays plus the original landing pad** —
so one bay drains the whole landing-pad complex.
- **4×5 tiles**, so a single row of inserters unloads straight into a waiting cargo wagon.
  This makes rocket-arrival → train the natural planetside pattern; no belt weaving between
  cargo bays.
- **Planetside only** — it cannot be placed on space platforms.
- Must be placed **within 59 tiles of the landing pad**, which constrains where the receiving
  rail stop can sit. Plan the landing-pad block with the unloading bay and stop together.

### First Platform Checklist
1. Build in Nauvis orbit first (safe, chunk-only environment)
2. Set up collector → crusher → belt loop before adding thrusters
3. Establish fuel + oxidizer production with circuit-controlled pumps
4. Automate firearm magazine production from iron ore
5. Add gun turrets along the full perimeter
6. Test travel slowly before committing to long routes
7. Set hub to auto-drop space science packs to base
