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
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

URLS_FILE  = "dev/wiki/urls.json"
OUT_DIR    = "dev/wiki"
ERROR_LOG  = "dev/wiki/errors.log"
WIKI_BASE  = "https://wiki.factorio.com/"
CF_BASE    = "https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering"

POLL_INTERVAL     = 4     # seconds between job status polls
                          # formula: max_workers ≈ API_CALLS_PER_SEC × POLL_INTERVAL
                          # 30 workers × (1/4 poll/s) = 7.5 req/s → comfortable under 9/s budget
POLL_TIMEOUT      = 120   # seconds before giving up on a job (30 × 4s polls = plenty)
MIN_CONTENT_BYTES = 300   # files smaller than this are flagged as stubs
API_CALLS_PER_SEC = 9     # stay under 10/sec REST limit (600/min)

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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


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

    with open(URLS_FILE, encoding="utf-8") as f:
        our_pages = set(json.load(f))

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

    # Delete stale files so run_crawl will re-fetch them
    deleted = sum(
        1 for t in to_update
        if os.path.exists(os.path.join(OUT_DIR, title_to_filename(t)))
        and not os.remove(os.path.join(OUT_DIR, title_to_filename(t)))
    )
    print(f"\nDeleted {deleted} stale files. Re-crawling...")
    run_crawl(to_update, account_id, token, args.workers)


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
    p_update.add_argument("--workers", type=int, default=30)
    p_update.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    {"crawl": cmd_crawl, "update": cmd_update}[args.command](args)


if __name__ == "__main__":
    main()
