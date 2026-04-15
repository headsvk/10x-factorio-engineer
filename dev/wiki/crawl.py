"""
crawl.py — Factorio wiki crawler and monthly updater.

Commands:
    python dev/wiki/crawl.py crawl   [--workers N] [--dry-run]
        Crawl all pages in dev/wiki/urls.json → dev/wiki/*.md
        Skips pages already written (resume-safe).

    python dev/wiki/crawl.py update  [--days N] [--workers N] [--dry-run]
        Monthly maintenance: query MediaWiki RecentChanges, re-crawl changed pages.
        Automatically cross-references against dev/wiki/urls.json.

Credentials: env vars CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN
             (also checks .env, .env.local, ~/.env)

Note: Cloudflare modifiedSince does NOT work for the Factorio wiki — the wiki does
not serve usable Last-Modified headers. Always use the RecentChanges API (update cmd).
"""

import argparse
import json
import os
import re
import sys
import time
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


class QuotaExhaustedError(Exception):
    """Raised when Cloudflare returns HTTP 429 — daily free-tier quota exhausted."""

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

URLS_FILE  = "dev/wiki/urls.json"
OUT_DIR    = "dev/wiki/pages"
ERROR_LOG  = "dev/wiki/errors.log"
WIKI_BASE  = "https://wiki.factorio.com/"
CF_BASE    = "https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering"

POLL_INTERVAL     = 4     # seconds between job status polls
                          # formula: max_workers ≈ API_CALLS_PER_SEC × POLL_INTERVAL
                          # 30 workers × (1/4 poll/s) = 7.5 req/s → comfortable under 9/s budget
POLL_TIMEOUT      = 120   # seconds before giving up on a job (30 × 4s polls = plenty)
MIN_CONTENT_BYTES = 300   # files smaller than this are flagged as stubs
API_CALLS_PER_SEC = 9     # stay under 10/sec REST limit (600/min)
MIN_PAGE_INTERVAL = 20    # seconds; Cloudflare free tier: 1 new browser instance per 20 s
QUEUE_FILE        = "dev/wiki/update_queue.json"  # resume queue for multi-day update runs
STAGING_DIR       = "dev/wiki/pages/.staging"      # new crawls land here; diffed then promoted

RC_API = (
    "https://wiki.factorio.com/api.php"
    "?action=query&list=recentchanges"
    "&rcnamespace=0&rclimit=500&rctype=edit|new&format=json"
    "&rcdays={days}"
)
LANG_PATTERN = re.compile(r"/[a-z]{2}(-[a-z]{2})?$")


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def load_credentials() -> tuple[str, str]:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token      = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if account_id and token:
        return account_id, token
    for envfile in [".env", ".env.local", os.path.expanduser("~/.env")]:
        if not os.path.exists(envfile):
            continue
        with open(envfile, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k == "CLOUDFLARE_ACCOUNT_ID" and not account_id:
                    account_id = v
                if k == "CLOUDFLARE_API_TOKEN" and not token:
                    token = v
        if account_id and token:
            break
    return account_id, token


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, calls_per_second: float):
        self._interval = 1.0 / calls_per_second
        self._lock = threading.Lock()
        self._last = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

_rate_limiter = RateLimiter(API_CALLS_PER_SEC)


# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------

def title_to_filename(title: str) -> str:
    safe = title.replace("/", "--")
    safe = re.sub(r'[\\:*?"<>|]', "_", safe)
    safe = re.sub(r"\s+", "_", safe).strip("_")
    return safe + ".md"


# ---------------------------------------------------------------------------
# Cloudflare API
# ---------------------------------------------------------------------------

def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    _rate_limiter.acquire()
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise QuotaExhaustedError("Cloudflare 429 — daily free-tier quota exhausted") from exc
        raise


def crawl_page(wiki_title: str, account_id: str, token: str) -> str | None:
    """Crawl one wiki page. Returns markdown string or None on failure."""
    wiki_url = WIKI_BASE + wiki_title.replace(" ", "_")
    crawl_url = CF_BASE.format(account_id=account_id) + "/crawl"

    # Start job
    resp = _request("POST", crawl_url, token, {
        "url": wiki_url, "limit": 1, "render": False, "formats": ["markdown"],
    })
    if not resp.get("success"):
        raise RuntimeError(f"API error: {resp}")
    job_id = resp["result"]

    # Poll until complete
    status_url = crawl_url + f"/{job_id}?limit=1"
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        s = _request("GET", status_url, token)
        status = s.get("result", {}).get("status", "")
        if status == "completed":
            break
        if status.startswith("cancelled") or status == "errored":
            return None
    else:
        return None  # timed out

    # Fetch markdown from completed records
    base = crawl_url + f"/{job_id}"
    cursor = None
    while True:
        url = f"{base}?status=completed&limit=50"
        if cursor:
            url += f"&cursor={cursor}"
        resp = _request("GET", url, token)
        for rec in resp.get("result", {}).get("records", []):
            md = rec.get("markdown", "")
            if md and md.strip():
                return md
        cursor = resp.get("result", {}).get("cursor")
        if not cursor:
            break
    return None


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def crawl_and_save(title: str, account_id: str, token: str,
                   print_lock: Lock) -> tuple[str, str, int]:
    out_path = os.path.join(OUT_DIR, title_to_filename(title))
    wiki_url = WIKI_BASE + title.replace(" ", "_")
    try:
        md = crawl_page(title, account_id, token)
    except Exception as exc:
        with print_lock:
            print(f"  ERROR  {title!r}: {exc}", flush=True)
        return title, "error", 0

    if not md:
        with print_lock:
            print(f"  EMPTY  {title!r}", flush=True)
        return title, "empty", 0

    with open(out_path, "w", encoding="utf-8") as fout:
        fout.write(f"<!-- Source: {wiki_url} -->\n\n")
        fout.write(md)

    size = os.path.getsize(out_path)
    status = "stub" if size < MIN_CONTENT_BYTES else "ok"
    with print_lock:
        print(f"  {status.upper():<5}  {title!r} ({size // 1024}KB)", flush=True)
    return title, status, size


# ---------------------------------------------------------------------------
# Parallel crawl runner (shared by both commands)
# ---------------------------------------------------------------------------

def run_crawl(titles: list[str], account_id: str, token: str, workers: int):
    os.makedirs(OUT_DIR, exist_ok=True)
    # Case-insensitive check (Windows FS is case-insensitive but Python str compare isn't)
    existing = {f.lower() for f in os.listdir(OUT_DIR) if f.endswith(".md")}
    to_crawl = [t for t in titles if title_to_filename(t).lower() not in existing]

    skip_count = len(titles) - len(to_crawl)
    print(f"Total: {len(titles)}  |  Already done: {skip_count}  |  To crawl: {len(to_crawl)}  |  Workers: {workers}")

    if not to_crawl:
        print("Nothing to crawl.")
        return

    errors, stubs = [], []
    done = 0
    print_lock = Lock()
    start_time = time.time()

    with open(ERROR_LOG, "a", encoding="utf-8") as err_log:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(crawl_and_save, title, account_id, token, print_lock): title
                for title in to_crawl
            }
            for future in as_completed(futures):
                title, status, size = future.result()
                done += 1
                elapsed = time.time() - start_time
                rate = done / (elapsed / 60)
                remaining = (len(to_crawl) - done) / rate if rate > 0 else 0
                with print_lock:
                    print(f"  [{done}/{len(to_crawl)}] {rate:.1f}/min  ~{remaining:.0f}min left", flush=True)
                if status in ("error", "empty"):
                    errors.append(title)
                    err_log.write(f"{status.upper()} {title!r}\n")
                    err_log.flush()
                elif status == "stub":
                    stubs.append(title)

    print(f"\n{'='*60}")
    print(f"Done.  Crawled: {done - len(errors)}  Errors: {len(errors)}  Stubs: {len(stubs)}")
    if errors:
        print(f"Errors logged to {ERROR_LOG}")
    if stubs:
        print(f"Stub pages (< {MIN_CONTENT_BYTES}B): {stubs}")


DIFF_FILE = "dev/wiki/changes.diff"


def _promote_staging(staged: list[str]) -> None:
    """Move successfully crawled files from STAGING_DIR to OUT_DIR.

    Writes a unified diff of every changed page to DIFF_FILE and prints a
    summary table so you know which pages to focus on for Step 4.
    """
    import difflib
    import shutil

    if not staged:
        return

    print(f"\n{'='*60}")
    print(f"Diff summary ({len(staged)} page(s) crawled):")
    print(f"  {'Page':<40} {'Old':>6} {'New':>6} {'Delta':>7}")
    print(f"  {'-'*40} {'-'*6} {'-'*6} {'-'*7}")

    changed_pages: list[tuple[int, str]] = []  # (abs_delta, title)

    with open(DIFF_FILE, "a", encoding="utf-8") as diff_out:
        diff_out.write(f"\n# Batch crawled {time.strftime('%Y-%m-%d %H:%M')} ({len(staged)} page(s))\n")
        for title in sorted(staged):
            fname = title_to_filename(title)
            src   = os.path.join(STAGING_DIR, fname)
            dst   = os.path.join(OUT_DIR, fname)

            try:
                old_lines = open(dst, encoding="utf-8").readlines()
            except FileNotFoundError:
                old_lines = []
            new_lines = open(src, encoding="utf-8").readlines()

            delta = sum(
                max(i2 - i1, j2 - j1)
                for tag, i1, i2, j1, j2
                in difflib.SequenceMatcher(None, old_lines, new_lines).get_opcodes()
                if tag != "equal"
            )
            marker = "NEW" if not old_lines else f"{delta:+d}" if delta else "  ="
            print(f"  {title:<40} {len(old_lines):>6} {len(new_lines):>6} {marker:>7}")

            if delta or not old_lines:
                changed_pages.append((delta, title))
                diff_out.write(f"{'='*70}\n")
                diff_out.write(f"--- {dst}\n+++ {src}\n")
                diff_out.writelines(difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"a/{fname}", tofile=f"b/{fname}",
                ))

            shutil.move(src, dst)

    print()
    if changed_pages:
        print(f"Pages with meaningful changes ({len(changed_pages)}):")
        for _, t in sorted(changed_pages, key=lambda x: -x[0]):
            print(f"  {t}")
        print(f"\nFull diff: {DIFF_FILE}")
        print("Review changed pages against 10x-factorio-engineer/references/ for Step 4.")
    else:
        print("No meaningful content changes detected.")


FINDINGS_FILE = "dev/wiki/findings.md"


def _log_completion(queried_date: str, completed_date: str, crawled: int, errors: int) -> None:
    """Append a one-line crawl record to findings.md."""
    entry = f"- {completed_date}: wiki update complete — queried {queried_date}, crawled {crawled} pages"
    if errors:
        entry += f", {errors} error(s)"
    entry += "\n"
    with open(FINDINGS_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"Logged to {FINDINGS_FILE}")


def run_update_crawl(to_update: list[str], queried_date: str, account_id: str, token: str, workers: int):
    """Resume-safe update crawl with staging.

    New pages are crawled into STAGING_DIR instead of OUT_DIR.  After each
    successful page the QUEUE_FILE is rewritten so partial runs can resume
    tomorrow.  When all pages are done (or when interrupted and restarted),
    successfully crawled files are diffed against the existing OUT_DIR copies
    and promoted in place, giving a clear picture of what actually changed
    before touching any references/ files.

    Rate-limiting: with workers=1 each page is padded to MIN_PAGE_INTERVAL
    seconds to respect the Cloudflare free-tier limit of 1 new browser/20s.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(STAGING_DIR, exist_ok=True)

    print_lock = Lock()
    queue_lock = Lock()
    queue: list[str] = list(to_update)   # shrinks as pages succeed
    staged: list[str] = []               # pages successfully written to STAGING_DIR
    errors: list[str] = []
    stubs:  list[str] = []
    done = 0
    start_time = time.time()

    def crawl_one(title: str) -> tuple[str, str, int]:
        page_start = time.monotonic()
        wiki_url = WIKI_BASE + title.replace(" ", "_")
        out_path = os.path.join(STAGING_DIR, title_to_filename(title))
        try:
            md = crawl_page(title, account_id, token)
        except QuotaExhaustedError:
            raise  # propagate — stops the whole crawl
        except Exception as exc:
            with print_lock:
                print(f"  ERROR  {title!r}: {exc}", flush=True)
            elapsed = time.monotonic() - page_start
            if MIN_PAGE_INTERVAL - elapsed > 0:
                time.sleep(MIN_PAGE_INTERVAL - elapsed)
            return title, "error", 0

        if not md:
            with print_lock:
                print(f"  EMPTY  {title!r}", flush=True)
            elapsed = time.monotonic() - page_start
            if MIN_PAGE_INTERVAL - elapsed > 0:
                time.sleep(MIN_PAGE_INTERVAL - elapsed)
            return title, "empty", 0

        with open(out_path, "w", encoding="utf-8") as fout:
            fout.write(f"<!-- Source: {wiki_url} -->\n\n")
            fout.write(md)

        size = os.path.getsize(out_path)
        status = "stub" if size < MIN_CONTENT_BYTES else "ok"
        with print_lock:
            print(f"  {status.upper():<5}  {title!r} ({size // 1024}KB)", flush=True)

        # Pad to MIN_PAGE_INTERVAL to respect 1-new-browser/20s free-tier limit.
        elapsed = time.monotonic() - page_start
        if MIN_PAGE_INTERVAL - elapsed > 0:
            time.sleep(MIN_PAGE_INTERVAL - elapsed)
        return title, status, size

    quota_hit = False
    pool = ThreadPoolExecutor(max_workers=workers)
    with open(ERROR_LOG, "a", encoding="utf-8") as err_log:
        futures = {pool.submit(crawl_one, t): t for t in queue}
        for future in as_completed(futures):
            title = futures[future]
            try:
                title, status, size = future.result()
            except QuotaExhaustedError:
                print(f"\n  QUOTA  Daily free-tier quota exhausted after {done} page(s).")
                print(f"  Queue saved — run again tomorrow to resume.")
                err_log.write("QUOTA_EXHAUSTED\n")
                quota_hit = True
                pool.shutdown(wait=False, cancel_futures=True)
                break
            except Exception as exc:
                with print_lock:
                    print(f"  CRASH  {title!r}: {exc}", flush=True)
                errors.append(title)
                err_log.write(f"CRASH {title!r}: {exc}\n")
                err_log.flush()
                done += 1
                continue
            done += 1
            elapsed = time.time() - start_time
            rate = done / (elapsed / 60) if elapsed > 0 else 0
            remaining_count = len(queue) - done
            eta = remaining_count / rate if rate > 0 else 0
            with print_lock:
                print(f"  [{done}/{len(to_update)}] {rate:.1f}/min  ~{eta:.0f}min left", flush=True)
            if status in ("ok", "stub"):
                with queue_lock:
                    staged.append(title)
                    if title in queue:
                        queue.remove(title)
                    with open(QUEUE_FILE, "w", encoding="utf-8") as qf:
                        json.dump({"queried": queried_date, "pages": queue}, qf, indent=2)
                if status == "stub":
                    stubs.append(title)
            else:
                errors.append(title)
                err_log.write(f"{status.upper()} {title!r}\n")
                err_log.flush()

    if not quota_hit:
        pool.shutdown(wait=True)

    # Promote whatever was staged before quota hit (or full run).
    _promote_staging(staged)

    if quota_hit:
        return

    completed_date = time.strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    if not queue:
        if os.path.exists(QUEUE_FILE):
            os.remove(QUEUE_FILE)
        print("All pages updated — queue file removed.")
        _log_completion(queried_date, completed_date, done - len(errors), len(errors))
    else:
        print(f"{len(queue)} page(s) still pending — saved to {QUEUE_FILE}. Run update again to resume.")
    print(f"Crawled: {done - len(errors)}  Errors: {len(errors)}  Stubs: {len(stubs)}")
    if errors:
        print(f"Errors logged to {ERROR_LOG}")
    if stubs:
        print(f"Stub pages (< {MIN_CONTENT_BYTES}B): {stubs}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_crawl(args):
    account_id, token = load_credentials()
    if not args.dry_run and (not account_id or not token):
        sys.exit("ERROR: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be set")

    with open(URLS_FILE, encoding="utf-8") as f:
        titles = json.load(f)

    if args.dry_run:
        existing = {f.lower() for f in os.listdir(OUT_DIR) if f.endswith(".md")} if os.path.exists(OUT_DIR) else set()
        to_crawl = [t for t in titles if title_to_filename(t).lower() not in existing]
        print(f"[dry-run] Would crawl {len(to_crawl)} of {len(titles)} pages with {args.workers} workers")
        for t in to_crawl[:10]:
            print(f"  {t!r} -> {title_to_filename(t)}")
        if len(to_crawl) > 10:
            print(f"  ... and {len(to_crawl) - 10} more")
        return

    run_crawl(titles, account_id, token, args.workers)


def cmd_update(args):
    if args.days > 30:
        print("WARNING: MediaWiki API only goes back 30 days — capping at 30.")
        args.days = 30

    # Resume from a saved queue if one exists (e.g. yesterday's partial run).
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, encoding="utf-8") as f:
            queue_data = json.load(f)
        queried_date = queue_data["queried"]
        to_update = queue_data["pages"]
        print(f"Resuming from saved queue (queried {queried_date}): {len(to_update)} page(s) remaining")
    else:
        # Fresh run — query MediaWiki RecentChanges.
        with open(URLS_FILE, encoding="utf-8") as f:
            our_pages = set(json.load(f))

        queried_date = time.strftime("%Y-%m-%d")
        print(f"Querying MediaWiki RecentChanges (last {args.days} days)...")
        url = RC_API.format(days=args.days)
        changed = set()
        while True:
            req = urllib.request.Request(url, headers={"User-Agent": "factorio-wiki-updater/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            for rc in data["query"]["recentchanges"]:
                title = rc["title"]
                if LANG_PATTERN.search(title):
                    continue
                if ":" in title and not title.startswith("Tutorial:"):
                    continue
                changed.add(title)
            if "continue" not in data:
                break
            url = RC_API.format(days=args.days) + "&rccontinue=" + urllib.request.quote(data["continue"]["rccontinue"])

        to_update = sorted(our_pages & changed)
        print(f"Wiki pages changed: {len(changed)}  |  In our list: {len(to_update)}")

        if not to_update:
            print("Nothing to update.")
            return

        # Save queue before touching any files — this is the resume checkpoint.
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump({"queried": queried_date, "pages": to_update}, f, indent=2)
        print(f"Saved queue of {len(to_update)} pages -> {QUEUE_FILE}")
        # Reset diff file so it covers exactly this update cycle.
        open(DIFF_FILE, "w", encoding="utf-8").close()

    print("\nPages to re-crawl:")
    for title in to_update:
        exists = os.path.exists(os.path.join(OUT_DIR, title_to_filename(title)))
        print(f"  {'[exists]' if exists else '[new]  '} {title}")

    if args.dry_run:
        print("\n[dry-run] Stopping here.")
        return

    account_id, token = load_credentials()
    if not account_id or not token:
        sys.exit("ERROR: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be set")

    run_update_crawl(to_update, queried_date, account_id, token, args.workers)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Factorio wiki crawler and updater",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # crawl subcommand
    p_crawl = sub.add_parser("crawl", help="Full crawl of wiki_crawl_urls.json")
    p_crawl.add_argument("--workers", type=int, default=30)
    p_crawl.add_argument("--dry-run", action="store_true")

    # update subcommand
    p_update = sub.add_parser("update", help="Re-crawl pages changed recently")
    p_update.add_argument("--days", type=int, default=30,
                          help="Days of RecentChanges to check (max 30)")
    p_update.add_argument("--workers", type=int, default=1,
                          help="Concurrent crawlers (default 1; free tier allows 1 new browser/20s)")
    p_update.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    {"crawl": cmd_crawl, "update": cmd_update}[args.command](args)


if __name__ == "__main__":
    main()
