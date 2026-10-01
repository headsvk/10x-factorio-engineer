"""
triage_changes.py — reduce dev/wiki/changes.diff to the changes that actually matter.

`crawl.py update` writes a raw unified diff of every re-crawled page. That diff is
useless as-is: the markdown renderer resolves relative links, heading markers and
tables differently between crawls, so effectively every page reports as changed
(the 2026-07-30 run: 82 of 82 pages, 9.4 MB of diff). This strips the known
cosmetic axes — link targets, image embeds, bare URLs, heading/bullet markers,
table-of-contents renumbering, nav-template blobs and page footers — and prints
only the surviving prose differences, ranked by volume.

Renderer drift
--------------
The Cloudflare renderer's output format is not stable across time, and a format
shift defeats the filters above wholesale: on 2026-08-15 it began emitting YAML
frontmatter, a duplicated "Space Age" expansion badge, the table of contents as
list items, doubled icon alt text in nav templates, nested `<table>` HTML inside
stat cells, and different backslash-escaping of punctuation — and the run
reported 111 of 111 pages as substantively changed. All six are normalised now.

Two things this cannot paper over, both of which need a full re-crawl
(`crawl.py crawl` against an emptied `pages/`) to resolve:

* Recipe lines are rendered with link labels resolved in the newer format
  (`Time 4 + Electronic circuit 10 → Locomotive 1`) and as bare numbers in the
  older one (`4+10 → 1`). There is no normalisation that reconciles the two.
* While `pages/` holds a MIX of formats, every mixed-format page diffs dirty on
  its first re-crawl regardless. Normalise the corpus rather than trusting the
  ranking during a transition.

"Nearly every page changed" is NOT a drift signal on its own. Since `--days`
started bounding the RecentChanges query (2026-09-15), `update` queues only pages
the wiki itself reports as edited, so a clean run legitimately shows ~all of them
changed (2026-10-01: 65 of 66, every one a real edit). Drift instead shows up as
pages with many changed lines behind tiny wiki edits. So this script reads
`dev/wiki/edit_summary.json` (written by `crawl.py update`: per-page byte deltas
and edit comments straight from the MediaWiki API, bypassing the renderer) and:

* annotates each page header with the wiki's byte delta, edit count and latest
  edit comment — usually the fastest pointer to what changed;
* runs a drift check: a page is a suspect when it shows >= DRIFT_MIN_LINES
  changed lines from < DRIFT_MAX_CHURN bytes of wiki edits (or was diffed with
  no wiki edit recorded at all). A WARNING prints when suspects make up at least
  a quarter of the diffed pages (and at least DRIFT_MIN_SUSPECTS of them).

Known tradeoff: collapsing the renderer's doubled icon labels also collapses
genuine doubled words ("had had" -> "had"). It is applied to both sides of the
diff, so the only edit it can hide is one whose sole change is a doubled word.

Usage:
    python dev/wiki/triage_changes.py [--diff PATH] [--edits PATH] [--top N]
                                      [--context N] [--pages NAME,NAME] [--quiet]

    --diff PATH     diff to read (default: dev/wiki/changes.diff)
    --edits PATH    wiki edit summary (default: dev/wiki/edit_summary.json; optional)
    --top N         only show the N pages with the most changes (default: all)
    --context N     max changed lines shown per page, per direction (default: 8)
    --pages LIST    comma-separated page names to show (substring match)
    --quiet         summary counts only, no per-page detail

Exit status is 0 even when nothing substantive changed — check the printed
"pages with substantive prose changes" count.
"""

import argparse
import io
import json
import re
import sys
from collections import OrderedDict

DEFAULT_DIFF = "dev/wiki/changes.diff"
DEFAULT_PAGES = "dev/wiki/pages"
DEFAULT_EDITS = "dev/wiki/edit_summary.json"

# Drift check thresholds (see "Renderer drift" above). On 2026-10-01, a clean run, one
# page of 66 tripped them (Cargo_landing_pad: 10 lines from 155 B of edits, mostly stub removal).
DRIFT_MIN_LINES = 10
DRIFT_MAX_CHURN = 200
DRIFT_MIN_SUSPECTS = 5

IMG = re.compile(r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)")
# One level of nested parens is allowed in the target, because wiki URLs routinely
# carry them ("Logistics_(research)"). Without that the match stops at the inner
# ")" and leaves residue like: Logistics> "Logistics (research)
LINK = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)")
URL = re.compile(r"https?://\S+")
# The renderer is inconsistent about backslash-escaping punctuation between versions
# ("\-h" vs "-h", "2\." vs "2.", "P\[N\]" vs "P\[N]").
ESCAPE = re.compile(r"\\(?=[^\w\s])")
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?)\]])")
# The newer renderer emits an icon's alt text AND the link label for the same entity,
# so every entry in a nav/infobox template doubles ("Pistol Pistol", "Space Age Space
# Age"). Collapsing an immediately-repeated 1-4 word phrase makes both renderings agree.
DUP_PHRASE = re.compile(r"\b((?:\w[\w'-]*)(?:\s+\w[\w'-]*){0,3})\s+\1\b")
WS = re.compile(r"\s+")
TOC = re.compile(r"^\*?\s*\d+(\.\d+)*\s+\S")     # "* 3 Tips", "* 1.2 Foo", "- 2.1 Biters"
RULE = re.compile(r"^[-=_*\s|]+$")               # horizontal rules, table separators
# Heading / bullet markers. A leading "-" counts only when followed by whitespace,
# i.e. an actual bullet: stripping it unconditionally also ate the sign off negative
# figures ("-16.67% resource drain" -> "16.67% ..."), which is exactly the kind of
# misreading the [columns] header recovery exists to prevent.
LEADIN = re.compile(r"^(?:[#>*\s]|-(?=\s))+")
FILE_HDR = re.compile(r"^--- a/(.*)\.md$")

# --- Renderer-format artifacts (see "Renderer drift" in the module docstring) ---
# The Space Age badge: an icon image plus the literal words "Space Age", wrapped as one
# link. Purely chrome, and the renderer emits it in places it previously omitted, so it
# has to go BEFORE IMG/LINK unwrapping — matching the icon URL keeps prose uses of the
# phrase "Space Age" intact.
BADGE = re.compile(r"\[!\[\]\([^)]*Space_age_icon[^)]*\)\s*Space Age\]\([^)]*\)")
# Stat cells arrive as nested HTML tables (`<table><tr><td>…`) rather than flattened text.
HTML_TAG = re.compile(r"<[^>]+>")
# YAML frontmatter block the renderer now prepends to every page.
FRONTMATTER = re.compile(r'^(?:title:|meta:|"og:title":)')

# Footer / chrome text that every page carries and that changes on its own schedule.
BOILERPLATE = (
    "this page was last edited", "privacy policy", "navigation menu",
    "jump to navigation", "in other languages", "about factorio wiki",
    "disclaimers", "mobile view", "powered by mediawiki",
    "content is available under", "retrieved from", "categories:",
    "hidden categor", "discussion [t]",
)
# NB: entries are matched as substrings anywhere in the line, so a phrase that can
# occur in real prose must not be added here. "mod portal" was tried for the old
# header banner and reverted — it also swallows "...distributed on the mod portal".


def is_noise(s: str) -> bool:
    """True if a normalised line carries no reviewable content."""
    if not s or RULE.match(s):
        return True
    if FRONTMATTER.match(s):
        return True
    low = s.lower()
    if any(b in low for b in BOILERPLATE):
        return True
    if TOC.match(s):
        return True
    # Nav/infobox template blobs: dozens of link residues on one line.
    if s.count('")') >= 3:
        return True
    return False


def normalize(line: str, *, strip_marker: bool = True) -> str:
    """Strip a diff line down to comparable prose.

    Cell delimiters are deliberately PRESERVED. Wiki stat tables carry several
    numeric columns (e.g. the asteroid table's health for metallic/carbonic/oxide
    vs promethium); flattening the pipes turns those into an ambiguous run of
    numbers and invites transcribing the wrong figure into a reference file.
    """
    s = line[1:] if strip_marker else line
    s = BADGE.sub(" ", s)               # expansion badge, before the link unwrapping
    s = IMG.sub("", s)
    s = LINK.sub(r"\1", s)              # [text](url) -> text
    s = URL.sub("", s)
    s = HTML_TAG.sub(" ", s)            # flatten nested <table> stat cells
    s = ESCAPE.sub("", s)
    s = s.replace("**", "").replace("*", "").replace("_", "")
    s = LEADIN.sub("", s)
    s = s.replace('")', " ")            # residue left by stripped link titles
    s = WS.sub(" ", s).strip()
    # Removing an inline badge or image leaves a gap in front of the following
    # punctuation ("Gleba , there are"), which would otherwise diff against the
    # same sentence rendered without the badge.
    s = SPACE_BEFORE_PUNCT.sub(r"\1", s)
    # Applied repeatedly: one pass leaves the odd survivor in a long nav row, since
    # overlapping repeats cannot all match in a single scan.
    for _ in range(3):
        collapsed = DUP_PHRASE.sub(r"\1", s)
        if collapsed == s:
            break
        s = collapsed
    # Collapse the padding wiki tables use, but keep the delimiters themselves.
    if "|" in s:
        s = " | ".join(c.strip() for c in s.split("|")).strip()
        s = re.sub(r"(\s*\|\s*)+$", "", s)
        s = re.sub(r"^(\s*\|\s*)+", "", s)
    return s.strip()


def is_table_row(s: str) -> bool:
    return s.count("|") >= 2


_PAGE_CACHE: dict[str, list[str]] = {}


def _page_lines(page: str, pages_dir: str) -> list[str]:
    """Normalised lines of the crawled page, for header recovery."""
    if page not in _PAGE_CACHE:
        path = f"{pages_dir}/{page}.md"
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read().splitlines()
        except OSError:
            raw = []
        _PAGE_CACHE[page] = [normalize(l, strip_marker=False) for l in raw]
    return _PAGE_CACHE[page]


def table_header_for(row: str, page: str, pages_dir: str) -> str | None:
    """Find the header row of the table that `row` belongs to.

    Locates the row in the crawled page, walks back to the `|---|---|`
    separator, and returns the line above it — so multi-column numbers in the
    diff arrive with their column names attached.
    """
    lines = _page_lines(page, pages_dir)
    if not lines:
        return None
    first_cell = row.split("|")[0].strip()[:40]
    if not first_cell:
        return None
    for i, cand in enumerate(lines):
        if not cand.startswith(first_cell):
            continue
        for j in range(i - 1, max(-1, i - 40), -1):
            if RULE.match(lines[j]) and "|" in lines[j]:
                header = lines[j - 1] if j > 0 else ""
                return header or None
        return None
    return None


def parse_diff(path: str) -> "OrderedDict[str, tuple[list[str], list[str]]]":
    pages: "OrderedDict[str, tuple[list[str], list[str]]]" = OrderedDict()
    current = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = FILE_HDR.match(line)
            if m:
                current = m.group(1)
                pages.setdefault(current, ([], []))
                continue
            if current is None or line.startswith(("+++", "@@", "--- ")):
                continue
            if line.startswith("-"):
                pages[current][0].append(line)
            elif line.startswith("+"):
                pages[current][1].append(line)
    return pages


def _surviving(a: list[str], b: list[str]) -> list[str]:
    """Lines in `a` with no counterpart in `b` (multiset difference)."""
    pool = list(b)
    out = []
    for x in a:
        if x in pool:
            pool.remove(x)
        else:
            out.append(x)
    return out


def substantive_changes(pages) -> list[tuple[str, list[str], list[str]]]:
    real = []
    for page, (minus, plus) in pages.items():
        nm = [x for x in (normalize(v) for v in minus) if not is_noise(x)]
        np_ = [x for x in (normalize(v) for v in plus) if not is_noise(x)]
        removed = _surviving(nm, np_)
        added = _surviving(np_, nm)
        if removed or added:
            real.append((page, removed, added))
    real.sort(key=lambda t: -(len(t[1]) + len(t[2])))
    return real


def load_edits(path: str) -> dict[str, dict] | None:
    """Per-page wiki edit metadata keyed like the diff's page names, or None if absent."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)["pages"]
    except (OSError, ValueError, KeyError):
        return None


def drift_suspects(pages, real, edits: dict[str, dict]) -> list[str]:
    """Diffed pages whose changed-line volume the wiki's own edits can't explain."""
    lines = {page: len(r) + len(a) for page, r, a in real}
    suspects = []
    for page in pages:
        e = edits.get(page)
        if e is None:
            if lines.get(page, 0):
                suspects.append(f"{page} ({lines[page]} lines, no wiki edit recorded)")
        elif lines.get(page, 0) >= DRIFT_MIN_LINES and e["churn"] < DRIFT_MAX_CHURN:
            suspects.append(f"{page} ({lines[page]} lines from {e['churn']} B of edits)")
    return suspects


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diff", default=DEFAULT_DIFF)
    p.add_argument("--edits", default=DEFAULT_EDITS,
                   help="wiki edit summary written by `crawl.py update` (optional)")
    p.add_argument("--pages-dir", default=DEFAULT_PAGES,
                   help="crawled pages, used to recover table headers")
    p.add_argument("--top", type=int, default=0)
    p.add_argument("--context", type=int, default=8)
    p.add_argument("--pages", default="")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    # Wiki content is full of non-cp1252 characters; never let a print crash the run.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        pages = parse_diff(args.diff)
    except FileNotFoundError:
        print(f"No diff at {args.diff} — run `python dev/wiki/crawl.py update` first.")
        return 0

    real = substantive_changes(pages)
    edits = load_edits(args.edits)
    print(f"pages in diff: {len(pages)}")
    print(f"pages with substantive prose changes: {len(real)}")
    if edits is None:
        print(f"no wiki edit summary at {args.edits} — drift check skipped "
              "(cross-check with `python dev/wiki/crawl.py changes --live`)")
    else:
        suspects = drift_suspects(pages, real, edits)
        print(f"drift check: {len(suspects)} of {len(pages)} page(s) show changes "
              "the wiki's own edits don't explain")
        for s in suspects[:10]:
            print(f"    {s}")
        if len(suspects) >= max(DRIFT_MIN_SUSPECTS, len(pages) / 4):
            print("WARNING: likely renderer drift — rank by `crawl.py changes` instead of "
                  "this output, and normalise the corpus with a full re-crawl.")
    if not real or args.quiet:
        return 0

    wanted = [w.strip().lower() for w in args.pages.split(",") if w.strip()]
    shown = [t for t in real if not wanted or any(w in t[0].lower() for w in wanted)]
    if args.top:
        shown = shown[:args.top]

    print("=" * 70)
    for page, removed, added in shown:
        print(f"\n### {page}  (-{len(removed)} / +{len(added)})")
        e = edits.get(page) if edits else None
        if e:
            # RecentChanges lists newest first, so comments[0] is the latest edit.
            latest = e["comments"][0] if e["comments"] else "(no edit comment)"
            print(f"    [wiki] {e['net']:+d} B, {e['edits']} edit(s); latest: {latest[:100]}")
        seen_headers: set[str] = set()

        def emit(marker: str, rows: list[str]) -> None:
            for x in rows[:args.context]:
                if is_table_row(x):
                    hdr = table_header_for(x, page, args.pages_dir)
                    if hdr and hdr not in seen_headers:
                        seen_headers.add(hdr)
                        print(f"    [columns] {hdr}")
                print(f"  {marker} {x}")

        emit("-", removed)
        emit("+", added)
        extra_r = max(0, len(removed) - args.context)
        extra_a = max(0, len(added) - args.context)
        if extra_r or extra_a:
            print(f"  ... {extra_r} more removed, {extra_a} more added"
                  f" (raise --context to see them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
