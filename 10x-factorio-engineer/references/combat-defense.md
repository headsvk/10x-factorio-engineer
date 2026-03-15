<!-- TOPICS: combat, defense, turrets, gun turret, laser turret, flamethrower turret, rocket turret, tesla turret, railgun turret, artillery, artillery turret, turret creep, biters, biter, spitters, worms, demolishers, pentapods, wrigglers, strafers, stompers, damage types, resistances, walls, nest clearing, perimeter defense -->

This file covers combat and defense in Factorio, including turret types, enemy mechanics, and turret creep strategies.

---

## Combat & Defense

### New Space Age Turrets Overview
**Wiki:** https://wiki.factorio.com/Turret for the full list.
| Turret | Unlocked | Power | Ammo | Best use |
|---|---|---|---|---|
| Gun turret | Nauvis early | No | Bullets | Cheap early coverage |
| Laser turret | Nauvis mid | Yes (high idle drain) | None | Reliable mid-game |
| Flamethrower turret | Nauvis mid | No | Fluid (light oil) | Mass biter crowds |
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
- Primary use: space platforms (asteroid defense); can be shipped to any planet for ground defense
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

### Aquilo (No Ground Enemies — Heating Is the Threat)
**Wiki:** https://wiki.factorio.com/Aquilo

**⚠️ Aquilo has NO ground enemies.** During development, floating jellyfish-like creatures were planned but cut before release because they made early Aquilo progression "much slower" (FFF #429). The Enemies wiki page lists no Aquilo entry. The real challenge on Aquilo is purely environmental: the cold.

**The heating constraint is the entire game on Aquilo:**
Every electric building freezes and stops working unless it is within 1 tile (orthogonally or diagonally) of a heat source above 30°C. See the Aquilo planet section (§ Space Age Strategies) for the full heat consumption table and building placement rules.

**What turrets are actually for (Aquilo context):**
- **Ground turrets on Aquilo serve no defensive purpose** — there are no enemies on the surface. You do not need to build a defensive perimeter on Aquilo.
- Railgun turrets are **unlocked by Aquilo research** but are deployed on your **space platform**, not on the Aquilo surface. The route to Aquilo has extremely high asteroid density (oxide chunks at 25% rate), so the platform needs heavy asteroid defense before making the trip.
- Railgun turrets can also be shipped back to Nauvis or other planets for ground defense there — they are not Aquilo-exclusive in use, only in unlock.

**Bots on Aquilo:**
- Robots consume **500% energy** compared to Nauvis. Factor this into power planning — a roboport cluster that barely worked on Nauvis will drain significant power here.
- Construction bots are still essential for building on the ice — avoid manual placement wherever possible.
- Keep roboport networks small and power-stable; large bot swarms significantly stress the power grid.

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
**Community reference:** **Michael Hendriks** (YouTube) — "Ultimate Deathworld" series is the definitive guide to optimised early-to-mid-game combat; the most thorough Factorio combat strategy content available. **Trupen** (YouTube) — concise, fast-paced turret pushing and combat mechanic tutorials.

Turret creep is a manual technique for expanding your safe perimeter on Nauvis by using turrets as a mobile frontline rather than a static wall.

**The core loop:**
1. Identify the nearest enemy nest cluster at the edge of your current safe zone.
2. Place gun turrets (or laser turrets) **20–25 tiles from the nearest nest** — close enough to shoot it, far enough to be outside the nest's immediate guard biter aggro radius (~7–10 tiles from the nest edge).
3. Manually supply ammo (gun turrets) or ensure power reaches the line (laser turrets).
4. Wait. Turrets will kill approaching biters and eventually wear down the nest.
5. Once the nest is cleared, advance the turret line 15–20 tiles toward the next nest cluster and repeat.

**Handling worms:**
Worms are stationary and fire acid at long range (small worm: 25 tiles, big worm: 38 tiles, behemoth worm: 48 tiles). Before advancing turrets into worm range:
- Use a tank or car to kite and snipe the worm from maximum personal weapon range.
- Cannon shells deal explosion damage — effective against worm fire resistance.
- Alternatively, use artillery once researched (see below).

**Turret type comparison for creep:**

| Turret | Best use in creep | Weakness |
|--------|------------------|----------|
| Gun turret | Cheapest; effective against all biter sizes with piercing/uranium ammo | Ammo logistics |
| Flamethrower | Devastates dense biter crowds; great for nest clearing | Needs light oil supply; large AoE can hit your own turrets |
| Laser | No ammo logistics; reliable unmanned outposts | High power draw; idle drain; needs power infrastructure extended to front |

**Ammo supply:**
Ammo depletion is the most common failure mode.
- **Early game trick:** Hold **Z** while dragging across a row of gun turrets — this rapidly inserts a half-stack of ammo into each turret from your inventory. Fastest way to arm a new frontline in seconds.
- Run a yellow belt from your main base to the creep line for continuous supply, or use construction bots with a personal roboport and a "trash everything" filter to auto-resupply.
- **Never leave a gun turret frontline without a live ammo feed.**

**Laser turret deployment shortcut:**
Create a **blueprint** of laser turrets grouped around a medium power pole or substation (e.g., 6 laser turrets around 1 substation). With a personal roboport equipped, your bots build the entire fortified cluster instantly from your inventory — far faster than placing each turret manually. Extend power poles back to your base and the cluster is self-sustaining.

**Tesla turrets in creep:**
Tesla turrets arc between enemies, slow them, and push them back — excellent for buying time while gun/laser turrets reload. Place 1–2 Tesla turrets at the frontline to stun counterattack waves so they can be finished off before they close to melee range.

**When Artillery replaces turret creep:**
Once **Artillery turrets** are researched (requires military 4, Vulcanus or late Nauvis), turret creep becomes mostly obsolete:
- Artillery has a 224-tile range (far outside biter retaliation range of ~35 tiles).
- "Shoot to decimate" mode automatically attacks nests within range.
- Artillery can clear a ~224-tile radius perimeter while you do something else.
- Turret creep is still useful for **targeted expansion** (clearing one specific nest to build an outpost) or when artillery ammunition is constrained.

**Tips:**
- Bring wall segments to build a small perimeter around your frontline turrets — walls buy time against concentrated attacks without requiring more turrets.
- Watch for biter nest respawn: nests do not respawn once killed, but biters from other nearby nests may rush the new line.
- Decrement your perimeter systematically: clear east, then south, then west — don't try to expand in all directions simultaneously.
