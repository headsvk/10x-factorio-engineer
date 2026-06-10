"""
check_wiki_update.py — SessionStart hook: remind when wiki is overdue for update.

Reads dev/wiki/findings.md, finds the last "wiki update complete" entry, and
prints a JSON systemMessage if it's been more than 20 days. Silent otherwise.
"""

import json
import os
import re
import sys
from datetime import date, datetime

FINDINGS = "dev/wiki/findings.md"
THRESHOLD_DAYS = 20

if not os.path.exists(FINDINGS):
    sys.exit(0)

last_date = None
with open(FINDINGS, encoding="utf-8") as f:
    for line in f:
        m = re.search(r"(\d{4}-\d{2}-\d{2}).*wiki update complete", line)
        if m:
            last_date = m.group(1)

if not last_date:
    sys.exit(0)

days_ago = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
if days_ago > THRESHOLD_DAYS:
    print(json.dumps({
        "systemMessage": f"Wiki last updated {days_ago} days ago ({last_date}). Run: python dev/wiki/crawl.py update --workers 1"
    }))
