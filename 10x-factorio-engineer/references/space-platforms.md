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
