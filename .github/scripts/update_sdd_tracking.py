#!/usr/bin/env python3
"""
Appends a draft row to review-software/reviews/TRACKING.md after a successful
SDD security review run, and writes a PR body to sdd_tracking_pr_body.md.
"""

import json
import os
import datetime
import pathlib
import sys

TRACKING = pathlib.Path("review-software/reviews/TRACKING.md")
REVIEW_JSON = pathlib.Path("sdd_review_output.json")
PR_BODY_FILE = pathlib.Path(".github/scripts/sdd_tracking_pr_body.md")

if not REVIEW_JSON.exists():
    print("No sdd_review_output.json found, skipping TRACKING.md update")
    sys.exit(0)

with open(REVIEW_JSON, encoding="utf-8") as f:
    result = json.load(f)

sdd_title = result.get("sdd_title", "Unknown SDD")
notion_url = os.environ.get("NOTION_SDD_URL", "")
run_url = os.environ.get("RUN_URL", "")
actor = os.environ.get("ACTOR", "")
today = datetime.date.today().isoformat()

notion_link = f"[SDD]({notion_url})" if notion_url else "\u2014"
run_link = f"[{today}]({run_url})" if run_url else today

risk_summary = result.get("risk_summary", "")
risk_rating = "\u2014"
for rating in ("Critical", "High", "Medium", "Low"):
    if rating.lower() in risk_summary.lower():
        risk_rating = rating
        break

new_row = (
    f"| {sdd_title} | {notion_link} | In Progress"
    f" | {risk_rating} | \u2014 | {actor} | {run_link} | \u2014 | \u2014 |"
)

existing = TRACKING.read_text(encoding="utf-8")

# Update the existing row if one exists for this SDD title, otherwise append.
lines = existing.splitlines(keepends=True)
updated = False
for i, line in enumerate(lines):
    # Match table rows whose first cell equals sdd_title exactly.
    # Row format: "| <title> | ..."
    stripped = line.lstrip()
    if stripped.startswith("|"):
        cells = [c.strip() for c in stripped.split("|")]
        # cells[0] is empty (before first |), cells[1] is the SDD Name column
        if len(cells) > 1 and cells[1] == sdd_title:
            lines[i] = new_row + "\n"
            updated = True
            break

if updated:
    TRACKING.write_text("".join(lines), encoding="utf-8")
    print(f"Updated existing row for: {sdd_title}")
else:
    TRACKING.write_text(existing.rstrip() + "\n" + new_row + "\n", encoding="utf-8")
    print(f"Appended draft row for: {sdd_title}")

pr_body = (
    "Automated draft entry added to `TRACKING.md` after running the"
    " SDD Security Review action.\n\n"
    "Before merging, update the row:\n"
    "- [ ] Set Status to `Reviewed`\n"
    "- [ ] Confirm Reviewer name\n"
    "- [ ] Add the Linear ticket link\n"
    "- [ ] Add a link to the `review.md` file if one was saved\n\n"
    f"SDD: {notion_url or '(not provided)'}\n"
    f"Actions run: {run_url}\n"
)

PR_BODY_FILE.write_text(pr_body, encoding="utf-8")
print(f"Wrote PR body to {PR_BODY_FILE}")
