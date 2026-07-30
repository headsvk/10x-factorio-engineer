"""
triage_changes.py — reduce dev/wiki/changes.diff to the changes that actually matter.

`crawl.py update` writes a raw unified diff of every re-crawled page. That diff is
useless as-is: the markdown renderer resolves relative links, heading markers and
tables differently between crawls, so effectively every page reports as changed
(the 2026-07-30 run: 82 of 82 pages, 9.4 MB of diff). This strips the known
cosmetic axes — link targets, image embeds, bare URLs, heading/bullet markers,
table-of-contents renumbering, nav-template blobs and page footers — and prints
only the surviving prose differences, ranked by volume.

Usage:
    python dev/wiki/triage_changes.py [--diff PATH] [--top N] [--context N]
                                      [--pages NAME,NAME] [--quiet]

    --diff PATH     diff to read (default: dev/wiki/changes.diff)
    --top N         only show the N pages with the most changes (default: all)
    --context N     max changed lines shown per page, per direction (default: 8)
    --pages LIST    comma-separated page names to show (substring match)
    --quiet         summary counts only, no per-page detail

Exit status is 0 even when nothing substantive changed — check the printed
"pages with substantive prose changes" count.
"""

import argparse
import re
import sys
from collections import OrderedDict

DEFAULT_DIFF = "dev/wiki/changes.diff"
DEFAULT_PAGES = "dev/wiki/pages"

IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"https?://\S+")
WS = re.compile(r"\s+")
TOC = re.compile(r"^\*?\s*\d+(\.\d+)*\s+\S")     # "* 3 Tips", "* 1.2 Foo"
RULE = re.compile(r"^[-=_*\s|]+$")               # horizontal rules, table separators
LEADIN = re.compile(r"^[#>*\s]+")                # heading / bullet markers
FILE_HDR = re.compile(r"^--- a/(.*)\.md$")

# Footer / chrome text that every page carries and that changes on its own schedule.
BOILERPLATE = (
    "this page was last edited", "privacy policy", "navigation menu",
    "jump to navigation", "in other languages", "about factorio wiki",
    "disclaimers", "mobile view", "powered by mediawiki",
    "content is available under", "retrieved from", "categories:",
    "hidden categor", "discussion [t]",
)


def is_noise(s: str) -> bool:
    """True if a normalised line carries no reviewable content."""
    if not s or RULE.match(s):
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
    s = IMG.sub("", s)
    s = LINK.sub(r"\1", s)              # [text](url) -> text
    s = URL.sub("", s)
    s = s.replace("**", "").replace("_", "")
    s = LEADIN.sub("", s)
    s = s.replace('")', " ")            # residue left by stripped link titles
    s = WS.sub(" ", s).strip()
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diff", default=DEFAULT_DIFF)
    p.add_argument("--pages-dir", default=DEFAULT_PAGES,
                   help="crawled pages, used to recover table headers")
    p.add_argument("--top", type=int, default=0)
    p.add_argument("--context", type=int, default=8)
    p.add_argument("--pages", default="")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    # Wiki content is full of non-cp1252 characters; never let a print crash the run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        pages = parse_diff(args.diff)
    except FileNotFoundError:
        print(f"No diff at {args.diff} — run `python dev/wiki/crawl.py update` first.")
        return 0

    real = substantive_changes(pages)
    print(f"pages in diff: {len(pages)}")
    print(f"pages with substantive prose changes: {len(real)}")
    if not real or args.quiet:
        return 0

    wanted = [w.strip().lower() for w in args.pages.split(",") if w.strip()]
    shown = [t for t in real if not wanted or any(w in t[0].lower() for w in wanted)]
    if args.top:
        shown = shown[:args.top]

    print("=" * 70)
    for page, removed, added in shown:
        print(f"\n### {page}  (-{len(removed)} / +{len(added)})")
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
