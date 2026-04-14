#!/usr/bin/env python3
"""
Security Review — notification step.

Reads the review output JSON and automatically:
  1. Posts a Slack message to #team-security when SLACK_WEBHOOK_URL is set
     and involvement is Required or Recommended.
  2. Creates an unassigned Linear triage ticket in the Security team when
     LINEAR_API_KEY is set and involvement is Required.

Fires automatically when secrets are present — no opt-in flags needed.
Neither action blocks the review workflow — failures are logged as warnings.

Env vars:
  REVIEW_OUTPUT_FILE  — path to review JSON (default: sdd_review_output.json)
                        PR review callers must set this to pr_review_output.json
                        to avoid reading the wrong file when both pipelines run.
  REVIEW_URL          — URL to link back to (PR URL, Notion URL, etc.)
  RUN_URL             — GitHub Actions run URL for the full review
  SLACK_WEBHOOK_URL   — if set, posts to Slack
  LINEAR_API_KEY      — if set, creates Linear ticket for Required reviews
"""

import json
import os
import sys
import requests

REVIEW_JSON = os.getenv("REVIEW_OUTPUT_FILE", "sdd_review_output.json")

LINEAR_TEAM_ID = "923e741b-0f2d-49dd-aad9-8100b88b08bd"   # Security team
LINEAR_TRIAGE_STATUS_ID = "6f91add6-bb14-4340-9c14-a9acc684c6fb"  # Triage
LINEAR_API_URL = "https://api.linear.app/graphql"

NOTIFY_LEVELS = {"Required", "Recommended"}


def load_review() -> dict:
    if not os.path.exists(REVIEW_JSON):
        print(f"Warning: {REVIEW_JSON} not found — skipping notifications")
        sys.exit(0)
    with open(REVIEW_JSON, encoding="utf-8") as f:
        return json.load(f)


def post_slack(webhook_url: str, result: dict, review_url: str, run_url: str) -> None:
    involvement = result.get("security_involvement", {})
    rec = involvement.get("recommendation", "")
    title = result.get("sdd_title", result.get("pr_title", "Unknown"))
    rationale = involvement.get("rationale", "")
    likelihood = involvement.get("likelihood")
    impact = involvement.get("impact")
    risk_score = involvement.get("risk_score")
    criteria = involvement.get("trigger_criteria", [])
    intake_note = involvement.get("intake_note", "")

    criteria_text = "\n".join(f"• {c}" for c in criteria) if criteria else ""
    color = "#eb5757" if rec == "Required" else "#f2c94c"

    # Clear action line at the top
    if rec == "Required":
        action = ":rotating_light: *Action required:* Reply here or in the Linear ticket to assign a reviewer before implementation proceeds."
    else:
        action = ":eyes: *Action suggested:* Reply here if you'd like a lightweight async review."

    title_link = f"<{review_url}|{title}>" if review_url else title

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":lock: *Security Review — {rec}*\n{title_link}",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": action},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Recommendation:*\n{rec}"},
                {"type": "mrkdwn", "text": f"*Risk score:*\n{risk_score}/25 (L{likelihood} × I{impact})" if risk_score else "*Risk score:*\n—"},
            ],
        },
    ]

    if rationale:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Rationale:* {rationale}"},
        })

    if criteria_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Criteria met:*\n{criteria_text}"},
        })

    context_parts = [f"<{run_url}|View full review in GitHub Actions>"]
    if intake_note:
        context_parts.append(intake_note)

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": " · ".join(context_parts)}],
    })

    payload = {
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ]
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"Slack notification sent (recommendation: {rec})")
    except Exception as e:
        print(f"Warning: Slack notification failed: {e}")


def create_linear_ticket(api_key: str, result: dict, review_url: str, run_url: str) -> None:
    """Creates an unassigned triage ticket in the Security Linear team."""
    involvement = result.get("security_involvement", {})
    rec = involvement.get("recommendation", "")
    title = result.get("sdd_title", result.get("pr_title", "Unknown"))
    rationale = involvement.get("rationale", "")
    risk_score = involvement.get("risk_score")
    likelihood = involvement.get("likelihood")
    impact = involvement.get("impact")
    criteria = involvement.get("trigger_criteria", [])
    risk_summary = result.get("risk_summary", "")
    is_pr_review = bool(result.get("pr_review_mode"))

    criteria_md = "\n".join(f"- {c}" for c in criteria) if criteria else ""
    risk_line = (
        f"**Risk score:** {risk_score}/25 (Likelihood {likelihood}/5 × Impact {impact}/5)"
        if risk_score is not None else ""
    )

    source_label = "PR" if is_pr_review else "SDD"
    source_link = f"[{title}]({review_url})" if review_url else title

    description = f"""Security review flagged this {source_label} as **{rec}** for Security team involvement.

**{source_label}:** {source_link}
**Full review:** {run_url}

---

**Rationale:** {rationale}

{risk_line}

{"**Criteria met:**" + chr(10) + criteria_md if criteria_md else ""}

---

**Risk summary:** {risk_summary}

---

*This ticket was created automatically by the Security Review action.*
*Assign to the appropriate team member and complete the review before implementation proceeds.*
"""

    issue_title = f"Security Review ({source_label}): {title}"

    mutation = """
mutation CreateIssue($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      url
    }
  }
}
"""

    variables = {
        "input": {
            "teamId": LINEAR_TEAM_ID,
            "stateId": LINEAR_TRIAGE_STATUS_ID,
            "title": issue_title,
            "description": description,
            # No assignee — intentionally left unassigned for triage
        }
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            LINEAR_API_URL,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        issue = data.get("data", {}).get("issueCreate", {}).get("issue", {})
        if issue:
            print(f"Linear triage ticket created: {issue.get('identifier')} — {issue.get('url')}")
        else:
            errors = data.get("errors", [])
            print(f"Warning: Linear ticket creation returned no issue. Errors: {errors}")
    except Exception as e:
        print(f"Warning: Linear ticket creation failed: {e}")


def main():
    result = load_review()
    involvement = result.get("security_involvement", {})
    rec = involvement.get("recommendation", "")

    if rec not in NOTIFY_LEVELS:
        print(f"Involvement level is '{rec}' — no notification needed")
        sys.exit(0)

    print(f"Involvement level is '{rec}' — sending notifications...")

    # REVIEW_URL: PR URL or Notion SDD URL — used as the primary link in notifications
    review_url = os.getenv("REVIEW_URL", os.getenv("NOTION_SDD_URL", ""))
    run_url = os.getenv("RUN_URL", "")

    slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
    if slack_webhook:
        post_slack(slack_webhook, result, review_url, run_url)
    else:
        print("SLACK_WEBHOOK_URL not set — skipping Slack notification")

    linear_api_key = os.getenv("LINEAR_API_KEY", "")
    if linear_api_key and rec == "Required":
        create_linear_ticket(linear_api_key, result, review_url, run_url)
    elif linear_api_key and rec == "Recommended":
        print("Involvement is 'Recommended' — Linear ticket creation only runs for 'Required'")
    else:
        print("LINEAR_API_KEY not set — skipping Linear ticket creation")


if __name__ == "__main__":
    main()
