<!-- TOPICS: quality, quality modules, quality recycling, legendary, epic, rare, uncommon, quality tiers, upcycling, quality loop, quality chance, module quality, machine quality, beacon quality -->

This file covers quality mechanics in Factorio Space Age, including quality modules, upcycling loops, and when quality is worth pursuing.

**Mod structure note:** the recycler no longer ships inside the Quality mod — it lives in
its own **Recycler** mod, which is a dependency of both Quality and Space Age. Quality
itself is *recommended but optional* for Space Age. So recycling is available in every
configuration, but quality tiers can be switched off; don't assume a Space Age save has
quality enabled. See `planets.md` for the full dependency graph.

---

## Quality Mechanics

**Wiki:** https://wiki.factorio.com/Quality and https://wiki.factorio.com/Quality_module
**Quality module base chances (at normal module quality):**

| Module tier | Quality chance | Speed penalty |
|-------------|---------------|---------------|
| Quality module 1 | +1% | −5% |
| Quality module 2 | +2% | −5% |
| Quality module 3 | +2.5% | −5% |

Quality modules themselves can be higher quality — the chance bonus is multiplied by the
module's quality tier (same MODULE_QUALITY_MULT as other modules: ×1.3 uncommon, ×1.6 rare,
×1.9 epic, ×2.5 legendary). Example: legendary quality-3 module gives +6.25% per slot.

**Quality tiers:** normal (0) → uncommon (1) → rare (2) → epic (3) → legendary (**5**). Note: legendary is a 2-tier jump over epic — quality attributes scale with tier strength, so legendary items have 2.5× the bonus of uncommon (not 1.25×).

**The universal rule (Wiki: Quality):** every quality effect is **per tier-level and
additive**. A legendary item gets 5 × the per-level effect. Worked example from the wiki: a
productivity module 3 (base +10%) at legendary grants **+25%** — 10% × (1 + 5 × 0.30) = 25%.
This one rule generates the whole `MODULE_QUALITY_MULT` table (1 / 1.3 / 1.6 / 1.9 / **2.5**),
so you can derive any quality effect from its normal-tier value rather than looking it up.

**Effects worth knowing beyond crafting speed** (all per tier-level, so ×5 at legendary):

| Effect | Per level | At legendary |
|---|---|---|
| Beacon power consumption | **−16.67%** | 480 kW → **80 kW** |
| Miner / pumpjack resource drain | **−16.67%**, *multiplicative with productivity* | patch lasts ~6× longer |
| Solar panel output | +30% | ×2.5 |
| Accumulator capacity | +100% (+5 MJ) | ×6 |
| Boiler / steam engine / turbine / reactor output | +30% | ×2.5 |
| Lightning rod & collector reach + efficiency | +30% | ×2.5 |
| Turret and weapon range | +10% | +50% |
| Ammo damage | +30% | ×2.5 |
| Chest inventory | +30% (rounded down) | ×2.5 |
| Consumable durability (repair packs, science packs) | +100% | ×6 |
| Spoil time (most spoilable items) | +30% | ×2.5 |

Two traps in that table: **steam-chain output gains raise consumption *and* pollution at the
same rate** (quality boilers are denser, not more efficient), and the miner drain reduction is
*multiplicative* with productivity rather than additive — so it compounds with mining-prod
research instead of being swamped by it.

**Rounding:** positive module effects from quality are rounded **down** — to the nearest 0.1%
for quality modules, and the nearest 1% for all other module types. `cli.py` computes these as
exact `Fraction`s without rounding, so its module bonuses can read a hair high versus in-game.
The gap is far below any planning threshold, but it's the reason for tiny discrepancies against
FactorioLab or in-game tooltips.

**Unlock requirements:**
- Uncommon + Rare: Quality module research (needs production science)
- Epic: Epic quality research (needs utility + space science + agricultural science from Gleba)
- Legendary: Legendary quality research (needs all science packs including Fulgora, Gleba, Aquilo, and Vulcanus)

A machine with quality modules rolls each cycle; if it succeeds, the output is one tier higher (up to legendary).

**Quality recycling loop (endgame):**
To push items to legendary: produce quality items in a machine with quality modules →
recycle non-target-quality outputs in a recycler (also with quality modules) → feed
recyclates back. The recycler preserves quality tier of outputs, and quality modules
in the recycler can upgrade products further. The loop is:
1. Machine with quality modules → produces mix of quality tiers
2. Filter inserters separate legendary (keep) from lower tiers (recycle)
3. Recycler with quality modules → recycled outputs can roll higher tier
4. Loop until legendary fraction accumulates

**Key constraint:** This is item/output intensive — design with buffers. Recyclers output 25% of the input item's ingredient value, so the loop is intentionally lossy.
Only run quality loops for high-value items where legendary stats matter (equipment,
modules, beacons, key machines). Do not run quality loops on bulk intermediates.

**⚠️ Recycling time now scales with output count (changed in 2.1.13).** Recipe generation
scales recycle time with the item result count, so **things generally recycle much faster**
than they used to — concrete, for example, recycles about **10× faster**. The older rule
that recycling time depended on crafting time *alone* (making a 1-output and a 2-output
0.5 s recipe recycle at the same rate) is obsolete. Practical consequence: recycler counts
in upcycling loops are lower than pre-2.1.13 blueprints and forum ratios assume — re-derive
them rather than reusing an old ratio, especially for high-output-count recipes.

**Machine quality:** Higher-quality machines craft faster (+30%/+60%/+90%/+150%
speed for uncommon/rare/epic/legendary). Upgrading machines before modules often
gives better throughput returns. The CLI `--machine-quality` flag models this.

### Asteroid quality sourcing — the "space casino" nerf

**Reprocessing recipes no longer accept quality modules.** Asteroid *reprocessing*
(chunk → other chunk types) used to take quality modules, which let a platform launder
ordinary chunks up to legendary and then produce legendary raw materials from them. The
devs named this the **"space casino"** in FFF-442 and removed it deliberately: *"it is too
strong to leave it alone."* The term is dev/community slang — no wiki page uses it, so
searching the wiki for "casino" finds nothing.

What still works for space-sourced quality:
- **The quality roll happens at crushing**, not reprocessing — quality modules in
  *crushers* still produce higher-tier ore/carbon/ice.
- **Upcycle the ore in a recycler loop** afterwards, the same way as any other item.

So the route is *crushing quality roll → recycler upcycle*, and any plan that assumes
module-driven reprocessing gains is out of date. `dev/quality_planner.py` already models
the post-nerf behaviour; if its numbers disagree with an older guide, the planner is right.

### Quality upcycling loop design (from Tutorial:Quality_upcycling_math)
**Wiki:** https://wiki.factorio.com/Tutorial:Quality_upcycling_math

The quality upcycling loop is a **Markov chain** — each item either becomes higher quality or is destroyed by the recycler (–75% items). All items eventually either reach legendary or are consumed.

**Machine capabilities:**

| Machine | Module slots | Base productivity |
|---|---|---|
| Chemical plant | 3 | 0% |
| Assembling machine 3 | 4 | 0% |
| Foundry | 4 | +50% |
| Electromagnetic plant | 5 | +50% |
| Cryogenic plant | 8 | 0% |

Foundry and EM plant's +50% base productivity multiplies output count before quality rolls fire — each craft produces 1.5× items, compounding quality opportunities. This is why the foundry beats assembler-3 despite identical slot count.

**Optimal module allocation (normal quality-3 modules):**

For non-legendary tiers: fill with quality modules — the goal is tier promotion, not producing more same-tier items. For the legendary-producing machine: switch entirely to productivity — quality rolls do nothing on legendary outputs.

| Machine | Normal / uncommon / rare tiers | Epic tier | Legendary tier |
|---|---|---|---|
| Chemical plant | 3× quality-3 | 3× quality-3 | 3× prod-3 |
| Assembling machine 3 | 4× quality-3 | 4× quality-3 | 4× prod-3 |
| Foundry | 4× quality-3 | 4× quality-3 | 4× prod-3 |
| Electromagnetic plant | 5× quality-3 | 5× quality-3 | 5× prod-3 |
| Cryogenic plant | 6× quality-3 + 2× prod-3 | 6–7× quality-3 + 1–2× prod-3 | 8× prod-3 |

Recyclers: quality modules only — productivity modules are not allowed in recyclers (hard game rule).

**Yield and machine count ratios (normal quality-3 modules; recyclers loaded with 4 legendary quality-3):**

Machine counts needed to keep **1 legendary-producing machine** running continuously:

| Machine | Yield % | Recyclers | Normal-tier | Uncommon-tier | Rare-tier | Epic-tier | Legendary-tier |
|---|---|---|---|---|---|---|---|
| Chemical plant | 0.034% | 53 | 198 | 23 | 7 | 2 | 1 |
| Assembling machine 3 | 0.046% | 31 | 123 | 18 | 6 | 2 | 1 |
| Foundry | 0.134% | 14 | 53 | 12 | 5 | 2 | 1 |
| Electromagnetic plant | 0.177% | 14 | 56 | 16 | 7 | 3 | 1 |
| Cryogenic plant | 0.119% | 9 | 41 | 16 | 8 | 4 | 1 |

Yield % = legendary outputs per 100 normal inputs. EM plant with legendary quality-3 modules reaches ~1.3% yield (≈7× improvement over normal modules) — upgrading module quality is the single highest-leverage investment once the loop is built. Use these ratios to size the loop: if you want 10 legendary outputs per hour, multiply all counts accordingly.

**Quality tier-skip probabilities:** When an item rolls a quality upgrade, the tier jump is: **90%** chance +1 tier, **9%** chance +2 tiers, **0.9%** chance +3 tiers, **0.1%** chance +4 tiers (normal straight to legendary in one roll). Higher-starting-tier items cap out earlier — an epic item can only jump +1 to legendary.

**When quality upcycling is worth it:**
- High-value items with large per-stat multipliers: modules, beacons, equipment grid items, space platform machines
- Items with many uses downstream: legendary assembler-3 runs faster, reducing machine count for everything it produces
- **Not worth it** for bulk intermediates (iron plates, circuits) — throughput cost exceeds value. Focus loops on final machines and equipment.

**Selector combinator "Quality filter" mode:** Standard circuit pattern for quality routing. Set selector to "Quality filter ≥ legendary" — legendary items exit to keep, everything else loops back to the recycler. No arithmetic combinator needed.
