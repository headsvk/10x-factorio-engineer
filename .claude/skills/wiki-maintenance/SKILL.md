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

**Steps 1–3 — Query RecentChanges, cross-reference, re-crawl: all one command.**
```bash
python dev/wiki/crawl.py update --workers 1 > wiki-update.log 2>&1
```
`update` queries the MediaWiki RecentChanges API (paginated, main namespace, translations
and non-article titles filtered), intersects it with the 647 titles in `dev/wiki/urls.json`,
and re-crawls the matches via Cloudflare into `pages/.staging/`, then diffs and promotes them.
Do not hand-roll the API query — `crawl.py`'s `fetch_recent_changes()` is the one place
the query (and its `rcend` bound) lives.

Credentials come from env vars `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`.

**The window sizes itself.** With no `--days`, `update` reads the last `wiki update complete`
line in `dev/wiki/findings.md` and uses `min(90, days_since_last_run + 2)` — the `+2` is
overlap for pages edited after the previous run's query, the 90 is RecentChanges retention.
On the intended cadence that is ~16–18 days. Pass `--days N` only to override; never go below
`days_since_last_run`, or the gap between runs is never inspected. (A flat 30 on 2026-09-15
queued 110 pages when only ~20 had changed since the previous run — wasted wall-clock, no
token or quota cost.) `--days` has no effect when `dev/wiki/update_queue.json` exists —
that run resumes the saved queue without re-querying.

**`update` also writes `dev/wiki/edit_summary.json`**: per tracked page, the wiki's own byte
delta, edit count and edit comments for this cycle. Read it with
```bash
python dev/wiki/crawl.py changes            # --top N; --live re-queries instead of reading the file
```
It is the best first pointer into a run: on 2026-10-01 the edit comments alone
("Railgun shooting speed no longer capped", "2.1.7 Pull fuel from passengers") identified
every page that touched a reference fact before triage ran.

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
> MediaWiki RecentChanges API (via `crawl.py update`) to determine what actually changed.

**Step 4 — Update the relevant split reference file(s) for changed embedded pages:**

First reduce the diff — **do not read `changes.diff` directly**:
```
python dev/wiki/triage_changes.py --top 20
```
The raw diff is mostly renderer noise (link resolution, heading markers, TOC renumbering
change between crawls, so nearly every page shows as modified). `triage_changes.py` strips
those axes and ranks pages by surviving prose changes. Use `--pages NAME` to drill into one
page and `--context N` to see more lines. Each page header carries a `[wiki]` line from
`edit_summary.json` — byte delta, edit count and latest edit comment — and the summary
block at the top runs a drift check (below).

Before writing a mechanic change into a reference, confirm it against the official patch
notes — `Version history/2.1.0` on the wiki (fetch its wikitext via the MediaWiki API,
`action=query&prop=revisions&rvprop=content&rvslots=main&titles=Version_history/2.1.0`, and
grep it). Pages contradict themselves while editors catch up: on 2026-10-01 the Locomotive
infobox said consumption scales with quality while older prose on the same page said a flat
600 kW; the 2.1.7 changelog settled it.

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

> **⚠️ Renderer drift — trust triage's drift check, not the changed-page count.**
> The Cloudflare renderer's output format is not stable across time. On 2026-08-15 it
> started emitting YAML frontmatter, a duplicated `Space Age` badge, the TOC as list
> items, doubled icon alt-text in nav templates, and nested `<table>` HTML in stat cells;
> triage reported **111 of 111** pages substantively changed and was useless for that run.
> Those axes are filtered now, but the failure mode will recur if the format shifts again.
>
> "~Every page changed" is **not** itself the symptom any more. Since `--days` bounds the
> query, `update` only queues pages the wiki reports as edited, so a clean run shows nearly
> all of them changed (2026-10-01: 65 of 66, all real edits). Drift looks different: many
> changed lines behind tiny wiki edits. Triage checks exactly that against
> `edit_summary.json` — a page is a suspect at ≥10 changed lines from <200 B of edits — and
> prints `WARNING: likely renderer drift` when suspects reach a quarter of the diffed pages
> (2026-10-01: 1 suspect of 66). On a warning, rank by `python dev/wiki/crawl.py changes`
> instead; on 2026-08-15 that signal cut 86 flagged pages to 25 genuinely edited ones, of
> which only 3 touched an embedded fact.
>
> **Keep the corpus single-format.** A `pages/` directory holding a mix of renderer
> formats diffs dirty on every page's first re-crawl regardless of filtering. After any
> confirmed drift, normalise it once: delete `dev/wiki/pages/*.md` and run
> `python dev/wiki/crawl.py crawl --workers 1` (~2 h for 647 pages, resume-safe).

**Step 5 — Also check for new high-value pages:**
```bash
python dev/wiki/crawl.py newpages      # add --show-filtered to see what was dropped
```
Read-only — it writes nothing, so it is safe to run *after* `update` (`update --dry-run`
is not: it truncates `changes.diff` before the dry-run check). Its window defaults the same
way as `update`'s, ignoring the findings line `update` wrote today, so both cover the same
cycle.

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
