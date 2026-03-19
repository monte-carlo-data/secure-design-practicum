# PR Review vs SDD Review — Pipeline Comparison

**Source of truth:** This file. Update it whenever either pipeline changes.

---

## Summary

| | SDD Review | PR Review |
|---|---|---|
| **Purpose** | Is this design safe to build? | Does this code introduce new risk? |
| **Timing** | Before/during implementation | At PR review time (during/after implementation) |
| **Primary input** | Notion SDD URL | GitHub PR URL (diff) |
| **Design context** | Is the primary input | Optional enrichment (`NOTION_SDD_URL`) |
| **Script** | `sdd_reviewer.py` | `pr_reviewer.py` |
| **Workflow** | `sdd-review.yml`, `sdd-review-reusable.yml` | `pr-review.yml`, `pr-review-reusable.yml` |
| **Config file trigger** | `.github/sdd-review-config.yml` | `.github/pr-review-config.yml` |
| **Artifact names** | `sdd_review_output.json`, `sdd_review_questions.md`, `sdd_review_architecture.drawio` | `pr_review_output.json`, `pr_review_questions.md`, `pr_review_architecture.drawio` |
| **Tracking log** | Updates `reviews/TRACKING.md` | Not tracked — PR reviews are not design review records |

---

## Shared behavior

Both pipelines:

- Produce the same output schema: involvement recommendation, security questions (1–10), data classification, compliance considerations, incident response scenarios, architecture diagrams (draw.io + ASCII)
- Support `workflow_dispatch` (manual) and config-file-triggered (PR-triggered) modes
- Share `sdd_notify.py` for Slack and Linear notifications
- Auto-notify via Slack when `SDD_SLACK_WEBHOOK_URL` is set; create Linear triage tickets for Required reviews when `LINEAR_API_KEY` is set
- Support a `skip_notifications` flag to suppress notifications for test/re-runs
- Fetch accepted risks from a risk register repo and inject them into the prompt so already-accepted risks are not re-raised as findings
- Fail gracefully if the risk register is unavailable

---

## Differences

### Primary input and what is analyzed

| | SDD Review | PR Review |
|---|---|---|
| **Required input** | `NOTION_TOKEN` + Notion SDD URL | `github.token` + GitHub PR URL |
| **What is fetched** | Notion page content | PR diff + changed file list via GitHub API |
| **Scope of analysis** | Design-level: architecture, data flows, trust boundaries, threat model | Code-level: what new risk the specific diff introduces |
| **Source code** | Optional enrichment — fetches top security-relevant files from specified repos | Core input — the diff itself is the primary artifact |
| **Notion** | Required | Optional (design context only; requires `NOTION_TOKEN` if provided) |

### Structured analysis approach

| | SDD Review | PR Review |
|---|---|---|
| **Analysis lenses** | 3 guides: Quick Security Review (10 Qs), Architecture Walkthrough (33 Qs), Self-Service Checklist (7 categories) | Diff-grounded findings; no separate multi-lens framework |
| **Focus instruction** | Analyze the design holistically | Focus on what the diff *introduces* — do not re-audit unchanged code |
| **Source file fetching** | Yes — fetches actual file contents from repos (heuristic scoring or explicit patterns) | No — diff is the sole code input |

### Tracking and notifications

| | SDD Review | PR Review |
|---|---|---|
| **TRACKING.md** | Updated on completion (Status, Risk Rating, Reviewer, Review Date, Linear ticket, Review File) | Not written — PR reviews are not part of the SDD design review log |
| **Linear ticket title** | `SDD Review: <SDD Title>` | `PR Review: <PR Title>` |
| **Slack message** | Links to Notion SDD + Actions run | Links to GitHub PR + Actions run |

### Secrets required

| Secret | SDD Review | PR Review |
|---|---|---|
| `ANTHROPIC_API_KEY` | Required | Required |
| `NOTION_TOKEN` | Required | Required only if `NOTION_SDD_URL` is provided |
| `github.token` | Used automatically for source code fetching and PR comments | Used automatically (fetches diff) |
| `SOURCE_REPO_TOKEN` | Optional (PAT for cross-repo source code access) | Optional (PAT for cross-org PR access) |
| `SDD_SLACK_WEBHOOK_URL` | Optional (auto-notifies if set) | Optional (auto-notifies if set) |
| `LINEAR_API_KEY` | Optional (auto-creates ticket if set, Required only) | Optional (auto-creates ticket if set, Required only) |
| `RISK_REGISTER_REPO` | Optional (override default risk register repo) | Optional (override default risk register repo) |

---

## Relationship between the two

SDD review and PR review are complementary, not interchangeable:

- **SDD review** runs against a design document *before or during implementation*. It catches architecture-level concerns while there is still time to change the design.
- **PR review** runs against actual code changes *at review time*. It catches implementation-level concerns that a design doc would not reveal.

A team doing it right runs both: SDD review when the design is written, PR review when the implementation is ready for merge. When both are run on the same feature, the PR review can optionally receive the SDD as design context (`NOTION_SDD_URL`) so the reviewer can cross-reference implementation against design intent.

PR reviews are intentionally excluded from `TRACKING.md` — that log tracks design-level security decisions, not implementation reviews.
