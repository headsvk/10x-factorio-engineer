---
name: wiki-maintenance
description: Twice-monthly Factorio wiki re-crawl and strategy-reference refresh for this repo — crawl changed pages via the RecentChanges API, triage the diff, and update the embedded facts in 10x-factorio-engineer/references/. Use when running or debugging the factorio-wiki-maintenance routine, or when asked to refresh the wiki-derived strategy references.
---

# Strategy Reference Maintenance (Twice Monthly)

The split reference files in `10x-factorio-engineer/references/` embed facts crawled from the
Factorio wiki, and `dev/wiki/` holds the full per-page corpus (647 pages, gitignored).
The wiki is actively updated, so this workflow re-crawls what changed and refreshes the
embedded facts.

**Driven by a scheduled routine, not by hand.** `factorio-wiki-maintenance` (prompt at
`~/.claude/scheduled-tasks/factorio-wiki-maintenance/SKILL.md`, visible under **Routines**
in the Claude desktop app) fires on the 1st and 15th at 09:00 local and executes the
workflow below. Deliberately tighter than monthly, to keep each diff small enough to triage.

> **Retention is ~90 days, not 30 — corrected 2026-09-15.** This file previously claimed a
> 30-day API limit and blamed the 2026-06-10 → 07-30 gap on it. Measured: the RecentChanges
> feed reaches back ~89 days (`$wgRCMaxAge`), so that gap did **not** lose edits, and a single
> slipped run is recoverable. The cadence stays twice-monthly anyway — a 90-day diff is far
> harder to triage than a 16-day one — but treat a late run as a bigger diff, not lost data.

Credentials come from `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`, resolved by
`crawl.py`'s `load_credentials()` from the environment or `.env` / `.env.local` / `~/.env`.
They live in `~/.env` (outside the repo, read at runtime so no app restart is needed). The
token needs exactly one Cloudflare permission: **Account → Browser Rendering → Edit**.

The last run is recorded as a `wiki update complete` line in `dev/wiki/findings.md` — that
line is how the routine decides whether it's due, so it must be appended on every run.

### Workflow

**Step 1 — Fetch recently changed pages via MediaWiki API:**
```
https://wiki.factorio.com/api.php?action=query&list=recentchanges&rcnamespace=0&rclimit=500&rcdays=30&rctype=edit|new&format=json
```
This returns all English main-namespace pages edited since `rcend`. Filter out
translations (`/zh`, `/ru`, `/de`, etc.) and non-article pages (`Special:`, `File:`, etc.).

**Step 2 — Cross-reference against our crawled page list:**
Our 647-page list is in `dev/wiki/urls.json`. Check which recently-changed wiki pages
appear in that list — those are the ones to re-crawl.

Also check which split reference files embed facts from those changed pages — if any of those changed,
update the embedded summaries too (Step 4).

**Step 3 — Re-crawl changed pages using `dev/wiki/crawl.py`:**
```bash
python dev/wiki/crawl.py update [--days N] [--dry-run]
```
This automates Steps 1–3: queries RecentChanges, cross-references against
`dev/wiki/urls.json`, deletes stale files, and re-crawls via Cloudflare.

Credentials come from env vars `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`.

**Size `--days` from the last run, not at a flat 30:** `min(30, days_since_last_run + 2)`,
where the last run's date is the final `wiki update complete` line in `dev/wiki/findings.md`.
On the intended cadence that is `--days 16`. A flat 30 re-covers ~16 days the previous run
already crawled — on 2026-09-15 it queued 110 pages when only ~20 tracked pages had changed
since the last run, ~18 minutes of redundant wall-clock (no token or quota cost; the free
tier has no daily cap). Never go below `days_since_last_run`: the window must reach back to
the last run, or the gap is simply never inspected. `--days` has no effect
when `dev/wiki/update_queue.json` exists — that run resumes the saved queue without
re-querying.

> **`rcdays` is a trap (found 2026-09-15).** `crawl.py` used to build its query with
> `&rcdays={days}`, but `rcdays` is a Special:RecentChanges **UI** parameter, not an API one.
> The API accepted it silently and ignored it, so `--days` bounded nothing and every run
> queried the full ~90-day retention — `rcdays=1`, `7` and `30` returned byte-identical
> result sets. It now uses `rcend` (a real parameter taking an ISO timestamp), so `--days`
> finally means what it says. If a run's page count looks far larger than the cadence should
> produce, re-check that the bound is actually being applied.

> **Note:** Do NOT use Cloudflare's `modifiedSince` parameter for this — tested and confirmed
> that the Factorio wiki does not serve `Last-Modified` headers that Cloudflare can use.
> All pages are returned as "completed" regardless of whether they changed. Use the
> MediaWiki RecentChanges API (Step 1) to determine what actually changed.

**Step 4 — Update the relevant split reference file(s) for changed embedded pages:**

First reduce the diff — **do not read `changes.diff` directly**:
```
python dev/wiki/triage_changes.py --top 20
```
The raw diff is mostly renderer noise (link resolution, heading markers, TOC renumbering
change between crawls, so nearly every page shows as modified). `triage_changes.py` strips
those axes and ranks pages by surviving prose changes. Use `--pages NAME` to drill into one
page and `--context N` to see more lines.

Then compare the surviving changes against what's embedded in the split reference files in `10x-factorio-engineer/references/`.
Update any facts that changed. Focus on **mechanics, strategic constraints, and planning guidance** — not raw stats or recipe ingredients (the CLI provides those on demand). Prioritise: spoilage timers, planet-specific constraints, combat mechanics, circuit patterns, and infrastructure ratios (solar/nuclear/fusion) that the CLI doesn't model.

> **Table columns are preserved and labelled.** `triage_changes.py` keeps the `|` cell
> delimiters and prints a `[columns] …` header line above changed table rows, recovered
> from the crawled page. This exists because the first version flattened the pipes: the
> asteroid table's two health columns (`metallic/carbonic/oxide` vs `promethium`) read as
> a single run of numbers and nearly put wrong HP values into the references on
> 2026-07-30. Still spot-check any figure that will be quoted verbatim against
> `dev/wiki/pages/<Page>.md` — headers are recovered heuristically (first-cell match, then
> walk back to the `|---|` separator) and can come back empty for nested or malformed
> tables, in which case no `[columns]` line is printed and the numbers are unlabelled.

> **⚠️ If triage reports ~every page as changed, suspect renderer drift — not the wiki.**
> The Cloudflare renderer's output format is not stable across time. On 2026-08-15 it
> started emitting YAML frontmatter, a duplicated `Space Age` badge, the TOC as list
> items, doubled icon alt-text in nav templates, and nested `<table>` HTML in stat cells;
> triage reported **111 of 111** pages substantively changed and was useless for that run.
> Those axes are filtered now, but the failure mode will recur if the format shifts again.
>
> **Fallback signal:** the MediaWiki RecentChanges API returns its own byte delta and edit
> comment per revision, which bypasses the renderer completely. Add
> `&rcprop=title|timestamp|comment|sizes|user` to the Step 1 query, drop revisions older
> than the last run's date (the window overlaps work already done), and rank pages
> by `newlen - oldlen`. On 2026-08-15 that reduced 86 flagged pages to 25 genuinely edited
> ones, of which only 3 touched an embedded fact.
>
> **Keep the corpus single-format.** A `pages/` directory holding a mix of renderer
> formats diffs dirty on every page's first re-crawl regardless of filtering. After any
> confirmed drift, normalise it once: delete `dev/wiki/pages/*.md` and run
> `python dev/wiki/crawl.py crawl --workers 1` (~2 h for 647 pages, resume-safe).

**Step 5 — Also check for new high-value pages:**
```bash
python dev/wiki/crawl.py newpages --days 30      # add --show-filtered to see what was dropped
```
Read-only — it writes nothing, so it is safe to run *after* `update` (`update --dry-run`
is not: it truncates `changes.diff` before the dry-run check).

It reports RecentChanges titles missing from `dev/wiki/urls.json`, bucketed so that only
the **candidates** need a decision; add the player-relevant ones (new buildings, mechanics,
Space Age content) to `dev/wiki/urls.json` and run `python dev/wiki/crawl.py crawl
--workers 1` to fetch them (resume-safe: it fetches only what is missing).

> **Do not hand-roll this query.** The one-liner this step used to carry made a single
> `rclimit=500` request with no `continue` pagination, so it silently truncated the
> changed-set — on 2026-09-01 it saw ~200 of 431 titles and missed pages entirely. It also
> filtered translations by the `/xx` suffix alone, which does not catch the bare-Hangul
> Korean titles that now dominate RecentChanges (307 of 314 untracked titles that run).
> `newpages` paginates properly and filters by script block; see `classify_untracked()`.

Three buckets are filtered automatically and need no action: **translations** (suffixed or
non-Latin-script titles), **meta** pages (`Version history*`, `Roadmap*`, `News`,
`Data.raw`, `Mod portal API`, `Main Page*`, `Factorio:*`), and **redirects** that resolve
onto a page already in `urls.json`. Two judgement calls remain yours: a page marked
*candidate for deletion* is not worth tracking (a `{{delete}}` banner above a `#REDIRECT`
also stops MediaWiki reporting it as a redirect, so it surfaces as a candidate), and a
subpage whose parent is already tracked usually adds nothing.

### Notes
- RecentChanges retains ~90 days (`RC_RETENTION_DAYS` in `crawl.py`); `--days` above that is capped
- `render: false` crawls won't follow links between unrelated pages — crawl each target URL directly
- `dev/wiki/findings.md` tracks crawl history (gitignored, local only)
- Cloudflare free tier (Quick Actions `/markdown` endpoint): 1 request/10 s, no daily cap — use `--workers 1`
- `dev/wiki/pages/` is gitignored — regenerate with `python dev/wiki/crawl.py crawl` (~2 h for 647 pages at 1 req/12 s; resume-safe, so it can be interrupted and restarted)
- `crawl.py update` appends its own `wiki update complete` line to `findings.md` — don't add a second one by hand
- Leftover files in `dev/wiki/pages/.staging/` mean a previous crawl aborted before promoting them. Check their dates against the live copies: on 2026-07-30 seven files staged on 06-10 were newer than the April-era copies in `pages/`, so they were promoted rather than discarded.
