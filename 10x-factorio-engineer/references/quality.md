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

The quality upcycling loop is a **Markov chain** — each item either becomes higher quality (with probability q per quality tier) or is recycled (–75% items). After enough cycles, every item either becomes legendary or is destroyed.

**Key design insight:** The loop transformation matrix (reassembly × recycler) converges: for typical 5×legendary quality-3 modules in an EM plant + recycler, roughly **1.3 legendary items are produced per 100 normal inputs**. Adding productivity modules to the reassembly stage greatly improves this ratio — productivity multiplies the number of items at each stage, giving more chances to hit quality rolls.

**Worked example: upcycling assembling machine 3 to legendary**
- Setup: EM plant with 4× quality-3 modules (normal quality) for reassembly; recycler with 4× quality-3 modules (normal quality) for recycling.
- Quality-3 module base chance: **+2.5% per slot** → 4 slots = **10% effective quality chance** per craft.
- Per recycle: recycler returns 25% of ingredients (75% loss); each recycled item also has a 10% quality upgrade chance.
- Steady-state result (normal quality-3 modules, no productivity): approximately **1.3 legendary per 100 normal inputs** fed into the loop.
- With **legendary quality-3 modules** (×2.5 mult → **6.25% per slot**, 4 slots = **25% effective chance**): approximately **11–12 legendary per 100 normal inputs** — roughly a 9× improvement.
- Adding productivity modules to the EM plant (e.g. 2× prod-3 + 2× quality-3): each craft produces more items before recycling, compounding quality roll opportunities. This is often the highest-leverage upgrade.
- Key constraint: recyclers cannot accept productivity modules (hard game rule) — only quality modules go in the recycler.

**Module allocation strategy:**
- Reassembly machines (making the item): use a mix of productivity + quality modules. Productivity increases item count (more items = more quality rolls). More quality modules = higher per-item chance. The optimal split depends on the machine's prod bonus and module slot count.
- Recycler machines: quality modules only (recyclers cannot accept productivity modules — this is a hard game rule).
- Machines making legendary output: switch to productivity + speed modules once a machine is only processing legendary inputs — quality modules waste slots on 100%-legendary lines.

**Quality skip probability:** When an item does roll quality, there is always a **10% chance to skip a tier** (e.g., go directly from normal to rare, bypassing uncommon). This is fixed and cannot be changed by modules. At most 10% of items that "get quality" will be rare or better.

**When quality upcycling is worth it:**
- High-value items with large per-stat multipliers: modules, beacons, equipment grid items, space platform machines
- Items with many uses downstream: legendary assembler-3 runs faster, reducing the machine count for everything it produces
- **Not worth it** for: bulk intermediates (iron plates, circuits) where the throughput cost is higher than the value. Focus quality loops on the final machine or equipment tier.

**Selector combinator "Quality filter" mode:** The standard circuit pattern for quality routing. Filter inserters connected to the selector set to "Quality filter ≥ legendary" output only legendary items to keep; the remainder loops back to the recycler. No arithmetic combinator needed — the selector handles quality comparison directly.
