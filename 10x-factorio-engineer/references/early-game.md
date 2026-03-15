<!-- TOPICS: early game, science packs, red science, green science, blue science, purple science, yellow science, automation science, logistic science, chemical science, production science, utility science, spaghetti start, blueprints, factorioprints, blueprint string -->

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
| Chemical | Blue | Electronic circuit + engine unit + sulfur | Advanced production: oil processing, modules, electric furnaces |
| Production | Purple | Rail + electric furnace + productivity module 1 | End-game factories: assembler-3, bulk inserter |
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

## Blueprints

### Finding Blueprints
**Libraries:**
- **Factorio Prints:** https://factorioprints.com — largest community collection
- **factorio.school:** https://factorio.school — curated, searchable

**Blueprint string tools:**
- **FactorioBin:** https://factoriobin.com — pastebin for sharing and inspecting blueprint strings
- **Teoxoy Blueprint Editor:** https://teoxoy.github.io/factorio-blueprint-editor/ — design and edit blueprints in the browser without launching the game

Don't try to generate blueprint strings — they are base64+zlib encoded and must come from the game or a verified source. If a player pastes a blueprint string, Claude can explain what's in it conceptually but cannot decode the binary format without tooling.
