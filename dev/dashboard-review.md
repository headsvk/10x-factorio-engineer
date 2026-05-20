# Dashboard streamline review

Source: `dev/dashboard.html` (1888 lines). Screenshots: `dev/screenshots/`.

This walks every visible feature, validates its purpose, and proposes
changes. Changes are tagged **[P0] [P1] [P2]** by impact, plus **[FIND]**
when they directly address the *"hard to find a particular line"* pain.

---

## TL;DR — what to do first

Two-thirds of the bloat sits on the line card and the header. The "find a
line" problem is real and not yet addressed in any way (no search, no
sticky groups, no minimap, no inline filter chips).

The highest-leverage moves, in order:

1. **[P0][FIND] Add a filter box at the top of the Lines tab** — instant
   match against title / item / machine. The current `groups → cards`
   layout is fine; it just needs a needle.
2. **[P0][FIND] Sticky group headers + Collapse-all / Expand-all** —
   constant orientation while scrolling.
3. **[P0][FIND] Inline status chips on the collapsed card** — `WIP`,
   `stale`, `@300%`, plus a compact location pill when looking at lines
   on a multi-location factory. Currently you have to read the colored
   left border to know status.
4. **[P0] Drop the redundant subtitle** when `line.label === label(line.item)`
   — it's just the title shouted in uppercase. Wastes a row on every card.
5. **[P1] Header compression** — one badge row, drop the SPM badge
   (duplicates the headline below), and stop styling the storage pill
   like a button.
6. **[P1] Expanded card consolidation** — merge the three input
   sub-sections (Bus / Logistics / Direct) into one section with chip
   tags, and merge Raw Resources + Miners/Extractors into one table.
7. **[P2] Light-theme contrast pass** — empty progress tracks and
   "warn" amber are washed out on the cream background.

The rest of this doc walks the dashboard top-to-bottom.

---

## 1. Header

**Screenshot:** `section__header-badges.png` (and both `readme__*.png`)

What's there today:
- Title `10X FACTORIO ENGINEER` + save name line.
- 6–8 badges (Space Age, Assembler 3, Electric Furnace, Legendary
  Machines, Blue Belt, Modules, **X SPM**).
- Button cluster: ↓ Export · ↑ Import · ☾/☀ theme · storage pill ·
  ↺ reset.

### Issues

| # | Issue | Severity |
|---|---|---|
| H1 | The **`X SPM`** badge duplicates the much larger SPM headline directly below it. | minor visual noise |
| H2 | Storage pill (`Local only` / `Cloud sync` / `No storage`) is styled like a button and lives inside `.btn-group` — it's *informational*, not interactive. Easy to misclick. | usability |
| H3 | The **↺ reset** button is a single character sitting next to a destructive `confirm()`. No icon affordance, no label. Easy to hit by accident. | safety |
| H4 | Badges describe **global config** (assembler tier, furnace, belt, quality, modules). Today they're read-only — there is no settings panel to change them. Anything that's configured elsewhere (Chat → Claude updates state) should probably be visually distinct from anything you can act on. | clarity |
| H5 | Header is fairly tall on narrow widths (badges wrap, then buttons wrap). | layout |

### Proposed changes

- **[P0]** Drop `X SPM` badge (H1). The headline already says it bigger.
- **[P1]** Move the storage pill **out of `.btn-group`** and pair it
  with the save-name (small text below the title). Treat it as a status
  line. (H2)
- **[P1]** Move **↺ reset** into a "kebab" menu (⋯) along with
  Import/Export, or at minimum give it `opacity: .5` and a clearer
  tooltip. (H3)
- **[P2]** Optional: collapse the badge row into a single "config:
  AM3 · Electric · Blue · Legendary · Modules" line in monospace, so it
  reads as one breadcrumb instead of seven UI chips. (H4)
- **[P2]** Smaller header padding on `<900px` to recover vertical space
  on laptops.

---

## 2. Science Targets section

**Screenshot:** `section__science-space-age.png`, `section__science-vanilla.png`, `light__section-science-vanilla.png`

What's there: `effectiveSPM / targetSPM` headline, then a 1- or 2-column
grid of per-pack progress bars with rate + percent + (when multi-loc)
per-location chips.

### Validation

- **Purpose:** primary KPI. Keep.
- **Style:** science-color gradient is great. The Barlow Condensed
  headline number reads cleanly.
- **Usability:** mostly good.

### Issues

| # | Issue | Severity |
|---|---|---|
| S1 | When a science line is not started yet, the headline drops to `0` and goes **red**. That's overly alarming — there's nothing wrong, the player just hasn't built it yet. See `section__science-vanilla.png`: military science 0/min 0% glares red while the player is still ramping. | clarity |
| S2 | The `100%` cap on the per-pack bar means a pack producing 250% of target looks identical to one producing exactly 100%. No way to spot over-production. | data fidelity |
| S3 | Per-pack rate `90/min` and the larger header SPM use slightly different fonts at different sizes for the same datum — easy to read but inconsistent. | minor |
| S4 | Per-location chips (`Nauvis 60/min · Vulcanus 30/min`) are nice when present, but the chips themselves use `border-sub` borders that are nearly invisible in dark mode. | contrast |

### Proposed changes

- **[P1]** Soft-start: if the line has never produced anything *and* is
  flagged WIP, show `—` instead of `0%` and use the muted grey palette.
  (S1)
- **[P2]** Show a faint "over-cap" sliver beyond 100% (e.g. extend bar
  past the track with a tinted strip), or surface a `+N%` annotation
  when rate > target. (S2)
- **[P2]** Bump location-chip border to `--border` for visibility. (S4)

---

## 3. Research Productivity section

**Screenshot:** `section__research-collapsed.png`, `section__research-expanded.png`

Collapsible, count pill (`2 active` / `none`), grid of number inputs.

### Validation

- **Purpose:** lets Claude (and the player) flag the line cards as
  stale when research moves. Useful, but secondary.
- **Style:** clean. Subgroup label "SPACE AGE — RECIPE PRODUCTIVITY
  (CAPPED AT +300%)" is fine.
- **Usability:** collapsed-by-default is correct (R1). Tab order on
  the number inputs works.

### Issues

| # | Issue | Severity |
|---|---|---|
| R1 | Section consumes a full row even when collapsed and `none`. For vanilla players who never touch this, that's permanent dead weight at the top of the page. | bloat |
| R2 | The grid stays 2-column on vanilla (only the mining row exists). One row in a 2-col grid leaves an empty right column. | minor visual |

### Proposed changes

- **[P2]** When `none` *and* the player has 0 lines, hide the
  collapsed bar entirely. Surface it the first time Claude sets a
  research level. (R1)
- **[P2]** When vanilla (only mining row), drop to a single column.
  (R2)

---

## 4. Location bar

**Screenshot:** `section__location-bar.png`

Buttons per location + "+ Add" (Space Age only).

### Validation

- **Purpose:** essential. Keep.
- **Style:** active button uses accent border-bottom + accent text on
  input bg — clear.
- **Usability:** the buttons are also the only way to switch locations,
  so they need to read as buttons. They do.

### Issues

| # | Issue | Severity |
|---|---|---|
| L1 | Vanilla games hide the bar entirely (`STATE.dataset !== 'vanilla'`). Good. But the location dropping out of view is a *silent* tab-switch from "Nauvis" to "(no bar)" — anyone moving a vanilla save to Space Age and back can lose orientation. | edge case |
| L2 | "+ Add" is a sibling button of the location chips with `opacity: .7`. Reads as half a location. Should be visually distinct. | clarity |
| L3 | On factories with many lines per location, this bar carries critical context — but the user has no count hint next to each location name (e.g. `NAUVIS (7)` would let me know where the 30 lines actually live). | **find-a-line** |

### Proposed changes

- **[P1][FIND]** Show line count next to each location button:
  `NAUVIS · 7`. Surfaces the "where are my lines" signal at the top of
  the page. (L3)
- **[P2]** Replace `+ Add` with a `+` icon button with a tooltip, or
  separate it after a small gap. (L2)

---

## 5. Bottleneck banner

**Screenshot:** `section__bottleneck-banner.png`

Red banner with `⚠ N BOTTLENECKS` + bullets.

### Validation

- **Purpose:** critical attention-grabber. Keep.
- **Style:** loud and red — correct for a bottleneck.
- **Usability:** good as a passive notice. No interactivity (no jump to
  the offending line/item).

### Issues

| # | Issue | Severity |
|---|---|---|
| B1 | The bullet text is a sentence written by Claude. Long-form prose reads slower than a structured row (item · status · delta). | readability |
| B2 | Each bullet is a dead-end — no link to the line that's bottlenecked or the bus item that's short. | navigation |

### Proposed changes

- **[P2]** Optional: when the bullet text mentions a known bus item or
  line label, make it clickable to scroll the relevant card/section
  into view. (B2)
- **[P2]** Otherwise leave as-is — the banner is meant to *interrupt*.

---

## 6. Tabs

**Screenshot:** `section__tab-list.png`

Tabs: Overview · Lines (n) · Logistics (n) · Actions (n) · Chat.

### Validation

- **Purpose:** primary navigation. Keep.
- **Style:** active tab uses accent fill — clear.
- **Usability:** counts in parentheses on Lines / Logistics / Actions
  are a nice signal.

### Issues

| # | Issue | Severity |
|---|---|---|
| T1 | "Actions" was renamed from what looks like "Issues" internally (the empty-state still says `No next steps`, the section header is `Next Steps`). The tab label is the third name for the same thing. | naming |
| T2 | Tab name "Chat" doesn't hint that it's an AI co-pilot. New users may skip it expecting a multi-player chat. | discoverability |

### Proposed changes

- **[P2]** Pick one name for the steps tab — `Steps` reads cleaner
  than `Actions` and matches the section header. (T1)
- **[P2]** Rename `Chat` → `Claude` (matches the bubble sender label
  and `window.claude.complete`). (T2)

---

## 7. Overview tab — Power + Bus Balance

**Screenshots:** `tab__overview.png`, `section__bus-balance.png`

Power overview card + Belt Bus group + Pipe Network group.

### Validation

- **Purpose:** at-a-glance throughput health. Keep.
- **Style:** belt/pipe split with colored group labels is great.
- **Usability:** consumed/supply bar with `+/-` net delta in the right
  column is one of the best parts of the dashboard.

### Issues

| # | Issue | Severity |
|---|---|---|
| O1 | The "Power" card is yellow-bordered with `⚡ POWER` label. It's fine, but two pieces of info (`X MW / Y MW (ceil)`) for the entire factory feels under-utilized. No breakdown by line, no per-location split. | scope |
| O2 | Bus rows show net **as a belt fraction** (`+0.62 BLUE BELT`) — great. Below, the meta line says `720/min (0.27 blue belt) consumed` — *triple-encoding* the same datum (raw + belt-fraction + label). | redundancy |
| O3 | "BELT BUS" / "PIPE NETWORK" sub-labels only render when *both* types are present. When only one type exists the label is hidden — which is correct, but leaves no header at all on the section. | minor |

### Proposed changes

- **[P2]** Compact the bus row meta to a single line:
  `720 → 2,400 /min (used 30%)` instead of two flanking captions. (O2)
- **[P2]** Add a clickable expand on the Power card to break it down
  by line (we already have `line.cli_result.total_power_mw_ceil`). (O1)

---

## 8. Lines tab — the core pain point

**Screenshots:** `tab__lines-collapsed.png`, `light__tab-lines-collapsed.png`

Groups: `Science / Smelting / Circuits / Other`. Each line card collapsed
shows: chevron · title (`line.label`) · subtitle (`label(line.item)`) ·
status chips · rate · belt-unit.

### Issues — bloat

| # | Issue | Severity |
|---|---|---|
| LB1 | **`card-subtitle` is redundant** when `line.label === label(line.item)`. The sample state has this on 9/10 lines. The whole row is dead pixels. | **bloat** |
| LB2 | The rate is split into two stacked rows on the right (`90/min` and `0.03 blue belt`). Same info, two rows. | bloat |
| LB3 | Group header `style="margin:12px 0 8px"` between every group adds extra vertical air on top of the card's own 8px margin-bottom. | minor |
| LB4 | When all groups are present (Science / Smelting / Circuits / Other), the page becomes 4 separate accordions stacked. Status (ok/warn/bad) and location aren't surfaced *at the group level* — only on individual cards. | structure |

### Issues — finding

| # | Issue | Severity |
|---|---|---|
| LF1 | **No search or filter.** With 7–30+ lines this is the #1 ergonomic miss. | **find-a-line** |
| LF2 | **No sticky group headers.** Scroll halfway down and you've lost which group you're in. | **find-a-line** |
| LF3 | **No collapse-all / expand-all.** A power user opens a few cards, scrolls, loses position; reset is "tab away and tab back". | **find-a-line** |
| LF4 | **No status filter.** "Show me only the lines with issues" / "WIP only" / "stale only" — all impossible. | **find-a-line** |
| LF5 | **No keyboard navigation.** No `/` to focus search, no `j/k` to step cards. | nice-to-have |
| LF6 | Card status (ok/warn/bad/wip) is communicated **only** by the 3px colored left border. Easy to miss at a glance, especially in light theme where the border colors are subdued. | **find-a-line** |
| LF7 | When viewing a multi-location factory, **the Lines tab shows only the current location's lines** with no hint that lines exist elsewhere. There's nothing on a science line card that says "this is the Vulcanus instance of Automation Science". | **find-a-line** |
| LF8 | The grouping bucket logic is hard-coded:
  `Science / Smelting / Circuits / Other`. There's no view that groups
  by *machine type* (foundries vs assemblers vs cryo plants) or by
  *health* (bottlenecked vs ok). | structure |
| LF9 | The `data-card="${idx}"` is an index into the unsorted lines array. If the player reorders lines (a future feature), expansion state could collapse the wrong cards. | code-smell, low priority |

### Proposed changes — finding (top priority)

- **[P0][FIND]** **Filter input** at the top of the Lines tab.
  - Match against `line.label`, `label(line.item)`, and machine names
    in `line.cli_result.production_steps`.
  - Live filter (no submit button). `Esc` clears, `/` focuses (when
    no input has focus).
  - Show "N of M lines" caption when filtered.
- **[P0][FIND]** **Sticky group headers** — `position: sticky; top: 0`
  on `.group-label`, with a small chip on the right showing visible /
  total count inside the group.
- **[P0][FIND]** **Status filter chips** next to the search box: `All`
  · `Needs attention (bad)` · `Below target (warn)` · `WIP` ·
  `Stale` · `@300% cap`. Toggle to filter.
- **[P0][FIND]** **Collapse-all / Expand-all** button. Two-state
  toggle: when any card is expanded, the button reads `Collapse all`;
  otherwise `Expand all`.
- **[P1][FIND]** **Inline status badge on collapsed card**, next to
  the title — same palette as the left border but as a 1-char glyph
  (`●`) tinted ok/warn/bad/wip. Makes scanning a tall column trivial.
- **[P1][FIND]** **Location pill on the card header** when the factory
  has > 1 location, even if the user filtered to one location. Helps
  when search results span multiple locations.
- **[P2][FIND]** Keyboard: `/` focus search, `n`/`p` to step cards,
  `Enter` to toggle expansion. (LF5)

### Proposed changes — bloat

- **[P0]** Hide subtitle when `line.label === label(line.item)`. Use
  a one-liner truthy check in `renderLineCard`. Recovers ~15px per card. (LB1)
- **[P1]** Combine rate columns into one line: `90/min · 0.03 blue belt`
  (or `90/min (0.03 ·blue)`) instead of stacked. (LB2)
- **[P2]** Tighten group-header `margin` from `12px 0 8px` to
  `8px 0 4px`. (LB3)
- **[P2]** Add a second view-mode toggle: **By status** vs
  **By type** (current). (LF8, LB4)

---

## 9. Line card — expanded body

**Screenshots:** `line-card__oil-refinery.png`, `line-card__centrifuge-uranium.png`,
`line-card__biochamber-gleba.png`, `line-card__multi-target.png`,
`line-card__research-stale.png`, `line-card__research-capped.png`,
`line-card__step-machines-buffer.png`, plus Vulcanus, Fulgora, Aquilo, space platform.

The expanded card stacks: **Machines** (table with per-step inputs/outputs)
→ **Totals** (chips) → **Outputs** → **Reserve → Logistics** →
**Bus Inputs** → **From Logistics** → **Belt-fed Direct** → **Raw
Resources** → **Miners / Extractors** → **Sized by** → **Player notes**.

That's *up to 11 sections* on a single card.

### Validation

- **Purpose:** the dense card is the dashboard's killer feature — at a
  glance you can see machine counts, beacons, raws, and power. Keep
  the data, compress the layout.
- **Style:** the per-step `inputs / outputs` grid (blue + green left
  borders, color-coded item names) is excellent.

### Issues — bloat

| # | Issue | Severity |
|---|---|---|
| E1 | **The standalone "Outputs" section is redundant when there are no co-products.** The card header already shows the primary rate. See `line-card__research-stale.png` (Iron Ore Mining): the "Outputs" section is just a chip restating `Iron Ore: 120/min` that's already in the card header. | bloat |
| E2 | **Three sibling input sections** (`Bus Inputs`, `From Logistics 🤖`, `Belt-fed Direct`). They are mutually exclusive sets but each gets its own section-label row. For Flying Robot Frame Block (a typical case) you can have all three at once — three labels, three chip rows. | bloat |
| E3 | **`Raw Resources` and `Miners / Extractors` cover the same set of items twice.** Raw shows the rate, Miners shows the count for the same ore. Could be one row per item. See `line-card__centrifuge-uranium.png`: Uranium Ore appears in both, Iron Ore appears in both. | bloat |
| E4 | The "Sized by" chip is monospace text that just echoes the CLI args (`30/min · AM3` etc.). Useful for debugging, but it's in the visual hierarchy as a full section. Could be a small caption under the title. | placement |
| E5 | `Reserve → Logistics 🤖` chips for items at `0/min` are dimmed but still render. If a reserve produces 0 it's likely a bug worth flagging, not a quiet ghost chip. | clarity |
| E6 | The amber "+N/m buf" buffer annotation on a step output is a 10px-font, 0.85-opacity text-shadow that's easy to miss. See `line-card__step-machines-buffer.png`. | visibility |
| E7 | The "@300% cap" chip uses `--text-dim` on `--bg-input` — visually it's nearly indistinguishable from chrome. Compared to "stale" which has a colored ring, "capped" feels like a side note even though it indicates "more research is wasted on this line". | severity mismatch |
| E8 | The Machines table on a multi-step recipe (e.g. Processing Unit, Holmium Plate, Cryogenic Science) **doesn't sort**. Step order is whatever CLI emits. A user trying to find one step in a 10-step recipe has to scan top-to-bottom. | usability |
| E9 | The per-step input/output sub-grid (`.step-io-grid`) is great, but pads with `padding: 5px 8px 8px` and adds a `margin-bottom: 2px` outside its own `border-radius: 0 0 3px 3px`. On dense recipes (10+ steps), this stacks. | dense layout |

### Issues — usability

| # | Issue | Severity |
|---|---|---|
| E10 | Inputs/outputs on the step sub-grid show only the per-machine rate. For a line with 10× of a step you can't easily see "is the total bottlenecked?" at the line scope. | minor |
| E11 | When `chain_throttled === true`, the warning is a 10px text annotation in the Machines section-label — easy to miss given how much else is on the card. | visibility |
| E12 | Power is reported both at section-label level (`360 KW TOTAL (CEIL)`) and per-step (`Power` column). Mostly good — but the Overview tab's Power card sums these without showing the line breakdown. | cross-section |

### Proposed changes

- **[P0]** **Skip the "Outputs" section** when there are no co-products
  (`coProds.length === 0`). The card header already shows the primary
  rate. (E1)
- **[P0]** **Merge the three input sub-sections** (`Bus Inputs`,
  `From Logistics`, `Belt-fed Direct`) into one **"Inputs"** section.
  Each chip carries a small source tag: 🤖 for bots, → for direct,
  none for bus. Saves 2 section-label rows + 2 chip-row margins per
  card. (E2)
- **[P1]** **Combine Raw Resources + Miners/Extractors** into a single
  "Raws" section with one row per ore: `Iron Ore: 120/min · 12× Mining
  Drill · ⚡540 kW`. (E3)
- **[P1]** Make the **`@300% cap` chip warn-colored** (amber border /
  amber text) — it's a constraint the player should notice, not chrome.
  (E7)
- **[P1]** Make the buffer annotation a real chip (`+45/m buf` in a
  small amber chip with border) instead of inline text. (E6)
- **[P2]** Move **`Sized by`** to a small grey caption directly under
  the card title in expanded mode, not a separate section. (E4)
- **[P2]** Sort the Machines table: primary recipe (the one producing
  `line.item`) first; the rest by depth in the chain. (E8)
- **[P2]** Hide `Reserve → Logistics` chips at 0/min by default and
  surface a "0 reserves with no output" warning instead. (E5)
- **[P2]** When `chain_throttled`, render the chip as a full-width
  warn-styled banner at the top of the card body, not a 10px label
  annotation. (E11)

---

## 10. Logistics tab

**Screenshots:** `tab__logistics.png`, `section__logistics-table.png`

Table: Item · Supply/min · Demand/min · Net/min. Sorted by net ascending
(scarcest first).

### Validation

- **Purpose:** essential when bots are used. Keep.
- **Style:** clean table, `name-col` Barlow Condensed against monospace
  numeric — good visual rhythm.
- **Usability:** "supply only" / "demand only" annotations are helpful.

### Issues

| # | Issue | Severity |
|---|---|---|
| G1 | "Net" turns red when negative — good. But "+0" (balanced) renders in green, same as a strong positive. Visually identical to "+75" yet semantically very different (no margin vs ample buffer). | clarity |
| G2 | No way to click an item and jump to the producing/consuming line. | navigation |
| G3 | Sort order is fixed (`net ascending`). No column sort. | minor |
| G4 | Table has no row-level separator beyond `border-top`. Hover does highlight (`tbody tr:hover { background: var(--bg-input) }`), which is good. | minor |

### Proposed changes

- **[P2]** Add a column-sort affordance (click headers). (G3)
- **[P2]** Make item names clickable: filter the Lines tab to lines
  producing/consuming that item. (G2)
- **[P2]** Use a muted color (text-muted) for "+0", distinct from
  positive green. (G1)

---

## 11. Actions / Next Steps tab

**Screenshot:** `tab__actions.png`

Group label `Next Steps` + a list of green-bordered ok-styled rows with
an `→` arrow.

### Validation

- **Purpose:** Claude-suggested actions. Keep.
- **Style:** green palette for *to-do* items reads as "completed" — see
  the green left border + `var(--ok-bg)` background. These are pending
  actions, not successes. Mismatch. (Issue A1.)

### Issues

| # | Issue | Severity |
|---|---|---|
| A1 | Green styling on action items implies success/done. They're action items waiting to be done. | semantic |
| A2 | No way to mark an action done or dismiss it. (Claude can rewrite the list, but the player can't.) | UX |
| A3 | Empty state ("`✓ No next steps.`") uses the success-tick glyph and ok color — *that* is the appropriate place for green. Just not on pending items. | semantic consistency |

### Proposed changes

- **[P1]** Switch pending-action style to neutral (accent border-left,
  `--bg-input` background) instead of ok green. (A1)
- **[P2]** Add a small "✓" button on each row to dismiss (just removes
  from the local list; Claude can repopulate on next sync). (A2)

---

## 12. Chat tab

**Screenshot:** `tab__chat.png`

Optional warning banner, scrollable messages (max-height 380px),
textarea + send button.

### Validation

- **Purpose:** in-artifact co-pilot. Keep.
- **Style:** player bubble uses warn accent border, Claude bubble uses
  text-muted on bg-input — clear distinction.
- **Usability:** ⟳ spinner during send, Enter to send / Shift+Enter for
  newline — standard chat affordances.

### Issues

| # | Issue | Severity |
|---|---|---|
| C1 | Warning banner says `window.claude.complete is not available — sign into Claude.ai for chat to work.` That's the developer's framing. A player reading it has no signal of what to actually do (this dashboard ran in a published artifact). | wording |
| C2 | Once dismissed, the warning is gone forever (localStorage). If `window.claude.complete` is *still* unavailable when they next open the tab, the chat is just silently disabled. | error state |
| C3 | Chat history is in `STATE.chat_log` and gets exported with the state. Very large chat logs make the export blob (base64) large. No truncation in UI. | scale |
| C4 | The "send" button is `↑` (unicode arrow). On some fonts this renders narrower than 36×36. Could use an SVG. | rendering |

### Proposed changes

- **[P2]** Rephrase the warning to be player-friendly: *"AI chat is
  unavailable in this artifact context. Other dashboard features
  remain functional."* (C1)
- **[P2]** Even when dismissed, if `window.claude.complete` is still
  unavailable, disable the input with a placeholder *"AI chat
  unavailable — use the textarea on claude.ai"*. (C2)
- **[P2]** Add a "Clear chat" affordance (one-click, with confirm)
  somewhere unobtrusive. (C3)

---

## 13. Dialogs (Export / Import / Add Location)

Three `<dialog>` elements, 480px wide, backdrop dim 0.6 in dark / 0.18
in light.

### Validation

- **Purpose:** import/export & add-location. Necessary.
- **Style:** consistent with the rest of the UI.
- **Usability:** OK, but no keyboard shortcut to apply.

### Issues

| # | Issue | Severity |
|---|---|---|
| D1 | The export blob is base64 of a UTF-8 JSON dump — *not human-readable* once encoded. The Import dialog accepts both, but the Export only shows base64. A power user copying their state to grep / diff has to manually decode. | power-user UX |
| D2 | The "Add Location" dialog mixes two interaction patterns: click a planet button OR type a name + press Add. The mode is implicit. | UX |
| D3 | No confirmation on overwrite when importing — Apply replaces the entire state silently (no diff preview). | safety |

### Proposed changes

- **[P2]** Offer a toggle in the Export dialog: *base64 compact* /
  *JSON pretty*. (D1)
- **[P2]** Show a brief "Replacing: X locations, N lines" preview
  above the Apply button in Import. (D3)

---

## 14. Theme + light-mode pass

**Screenshots:** `readme__light.png`, `light__section-science-vanilla.png`,
`light__tab-lines-collapsed.png`

### Issues

| # | Issue | Severity |
|---|---|---|
| TH1 | Empty progress tracks in light mode (`--bg-input: #f0e8d5`) are too close to the page background (`--bg: #faf9f2`) — see `light__section-science-vanilla.png` Military Science: the empty bar is barely visible. | contrast |
| TH2 | Warn color in light mode is `#b45309` (brownish) — visually reads as a brand color, not as a warning. A line at 80% looks closer to "amber/accent" than to "warning". | semantic |
| TH3 | Light-mode card backgrounds (`#fffcf0` cream) on the page bg (`#faf9f2` cream) are *very* close — cards almost dissolve into the page. Hover state (`--bg-input`) helps but at rest the borders carry all the weight. | depth |

### Proposed changes

- **[P1]** Darken `--bg-input` in light mode slightly (e.g. `#e6dcc0`)
  for empty-bar visibility. (TH1)
- **[P2]** Pick a distinct warn hue for light mode (e.g. amber #d97706
  rather than dark brown). (TH2)

---

## 15. Cross-cutting code observations

These don't affect users directly but make incremental UI work cheaper:

- `dashboard.html` is one giant file (~1900 lines) with one global
  `STATE` and a top-level `render()` that rebuilds *everything* on
  every change. Filter + sticky-headers wouldn't need a framework, but
  preserving scroll position on re-render would need a small fix
  (`requestAnimationFrame` or persist `window.scrollY` across render).
- `expandedCards` is a `Set` of array indices — fragile if line order
  ever changes (see E9). Switching to a Set of `line.label` or a stable
  `line.id` (if we add one) would be cleaner.
- The four magic groups in `renderLinesTab` (Science / Smelting /
  Circuits / Other) are hard-coded. A small `groupLines(lines)` helper
  with rules would make it easy to add view-modes (by status, by
  location, by machine).

---

## Suggested rollout

If we want this to land in two or three PRs rather than one:

**PR 1 — Find a line (P0/FIND, ~half a day)**
- Filter input + status chips on the Lines tab
- Collapse-all / Expand-all toggle
- Sticky group headers with visible/total count
- Inline status `●` dot on collapsed card header
- Location pill on card when > 1 location
- Show line count in location bar buttons
- Drop redundant subtitle (LB1)

**PR 2 — Streamline (P0/P1 bloat, ~half a day)**
- Header: drop SPM badge, demote storage pill, demote reset
- Card expanded: merge inputs sections, merge raw+miners, skip
  Outputs when no co-products, recolor `@300%` chip
- Combine rate columns into one line
- Action items: neutral palette instead of green

**PR 3 — Polish (P2, time-permitting)**
- Light-mode contrast fixes
- Tab rename (Actions → Steps)
- Power card line-breakdown expansion
- Logistics ↔ Lines cross-navigation
- Keyboard shortcuts (`/` focus search, `n`/`p` step cards)

Total estimated diff: ~250–400 net lines added to `dev/dashboard.html`
(the new lines tab toolbar + view-state). No new dependencies, no JS
framework.
