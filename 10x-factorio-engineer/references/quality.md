<!-- TOPICS: quality, quality modules, quality recycling, legendary, epic, rare, uncommon, quality tiers, upcycling, quality loop, quality chance, module quality, machine quality, beacon quality -->

This file covers quality mechanics in Factorio Space Age, including quality modules, upcycling loops, and when quality is worth pursuing.

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

**Key constraint:** This is item/output intensive — design with buffers. Recyclers output 25% of the input item's ingredient value, so the loop is intentionally lossy. Note: recycling time is based on crafting time only, **not** on the recipe's output count — iron gears (1 output per 0.5s craft) and iron sticks (2 outputs per 0.5s craft) have the same recycling time even though sticks have twice the per-second throughput.
Only run quality loops for high-value items where legendary stats matter (equipment,
modules, beacons, key machines). Do not run quality loops on bulk intermediates.

**Machine quality:** Higher-quality machines craft faster (+30%/+60%/+90%/+150%
speed for uncommon/rare/epic/legendary). Upgrading machines before modules often
gives better throughput returns. The CLI `--machine-quality` flag models this.

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
