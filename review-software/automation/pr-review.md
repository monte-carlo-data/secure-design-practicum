# PR Security Review - GitHub Action

A GitHub Action that reviews pull request diffs and generates a structured security review focused on what new risk the code changes introduce. Optionally accepts a Notion SDD URL for design context.

## What the Review Produces

1. **Security Team Involvement Recommendation** - Whether the Security team should be consulted, with rationale and next steps
2. **1-10 Security Questions** - Specific to the code changes, prioritized by impact
3. **Data Classification Table** - Every data element classified as Critical/High/Medium/Low with storage, transit, and access details
4. **Compliance Considerations** - SOC 2 scope changes, DPA impacts, data residency, audit logging requirements
5. **Incident Response Scenarios** - What could go wrong, how to detect it, blast radius, and mitigation
6. **Architecture Diagram (draw.io)** - Interactive, color-coded diagram with trust boundaries, data flows, and security controls. Saved as `pr_review_architecture.drawio` in build artifacts — open it at [app.diagrams.net](https://app.diagrams.net/)
7. **Architecture Diagram (ASCII)** - Text-based version embedded in the PR comment and markdown output for quick reference

## How It Differs from the SDD Review

| | [SDD Review](sdd-review.md) | PR Review |
|--|--|--|
| **Primary input** | Notion SDD page | GitHub PR diff |
| **Best used** | Early design phase | During or after implementation |
| **Notion required** | Yes | No (optional context only) |
| **File prioritization** | Source repos via heuristics | Security-relevant changed files first |
| **Output prefix** | `sdd_review_*` | `pr_review_*` |

Both use the same NIST 800-30 risk model and produce the same structured output format.

## Three Ways to Run

| Trigger | How it works |
|---------|-------------|
| **Manual (workflow_dispatch)** | Go to Actions > PR Security Review > Run workflow in `mc-security`, paste the PR URL |
| **PR-triggered (config file)** | Add a `.github/pr-review-config.yml` file to your branch — the review runs automatically and posts results as a PR comment |
| **Reusable workflow** | Call `pr-review-reusable.yml@main` from your own pipeline — no files to copy, scripts are fetched automatically from `mc-security` |

## Quick Start

### 1. Add Repository Secrets

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | API key from [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_TOKEN` | Only if providing SDD URL | Notion integration secret (see [SDD Review setup](sdd-review.md#1-set-up-notion-integration)) |
| `SOURCE_REPO_TOKEN` | No | GitHub PAT with `repo` scope if the PR is in a private repo the workflow can't access |

The workflow uses `github.token` (provided automatically by GitHub Actions) by default for fetching PR diffs and posting comments.

### 2. Choose How to Run

**Preferred — Reusable workflow (no files to copy):**

Call the canonical workflow directly from your pipeline. Scripts are fetched automatically from `mc-security` at run time:

```yaml
jobs:
  pr-review:
    uses: monte-carlo-data/mc-security/.github/workflows/pr-review-reusable.yml@main
    with:
      pr-review-url: "https://github.com/org/repo/pull/42"
      # notion-sdd-url: "https://www.notion.so/..."               # optional
      # context-repos: "monte-carlo-data/agent-hub"               # optional, comma-separated, max 3
      skip-notifications: false
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}          # only if using SDD context
      SDD_SLACK_WEBHOOK_URL: ${{ secrets.SDD_SLACK_WEBHOOK_URL }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
```

**Alternative — Copy the workflow and script manually:**

If you need to customise the workflow or run it in an environment without access to `mc-security`, copy these files:

```
your-repo/
  .github/
    workflows/
      pr-review.yml          # from mc-security/.github/workflows/pr-review.yml
    scripts/
      pr_reviewer.py         # from mc-security/.github/scripts/pr_reviewer.py
      sdd_notify.py          # from mc-security/.github/scripts/sdd_notify.py
```

### 3. Run the Review

**Manual:** Go to **Actions > PR Security Review > Run workflow** and fill in:

| Input | Required | Description |
|-------|----------|-------------|
| **GitHub PR URL** | Yes | Full URL of the PR (e.g. `https://github.com/org/repo/pull/42`) |
| **Notion SDD URL** | No | Adds design context — requires `NOTION_TOKEN` |
| **Context repos** | No | Comma-separated `org/repo` slugs (max 3) — code and markdown fetched for additional context |
| **Skip notifications** | No | Suppress Slack/Linear notifications (useful for testing) |

## Running from a Pull Request

The workflow triggers automatically when a PR adds or modifies `.github/pr-review-config.yml`.

### 1. Create a Config File

Add `.github/pr-review-config.yml` to your branch:

```yaml
# .github/pr-review-config.yml
pr_review_url: "https://github.com/org/repo/pull/42"

# Optional — adds design context from Notion (requires NOTION_TOKEN secret)
notion_sdd_url: "https://www.notion.so/montecarlodata/Your-SDD-Page-abc123def456"

# Optional — fetch code and markdown from related repos for additional context (max 3)
# context_repos: "monte-carlo-data/agent-hub,monte-carlo-data/sdk"

# Optional — suppress Slack/Linear notifications
skip_notifications: false
```

### 2. Open or Update the PR

When the PR is opened, synchronized, or reopened with changes to that config file, the review runs automatically. Results appear as:

- A **PR comment** with the full security review
- **Inline review comments** on specific diff lines for questions that reference a file and line number
- The **job summary** in the Actions run
- **Artifacts** (`pr_review_output.json`, `pr_review_questions.md`, `pr_review_architecture.drawio`)

> **Note:** If the same commit SHA has already been reviewed on this PR, the workflow skips automatically to avoid duplicate comments.

## How File Prioritization Works

The reviewer fetches the PR's changed files and scores each one for security relevance before building the diff context. Files are included in priority order within a 30KB total budget (6KB cap per file).

Files score higher when their path contains keywords like `auth`, `permission`, `security`, `credential`, `token`, `iam`, `rbac`, `encrypt`, `config`, `terraform`, `dockerfile`, `migration`, `schema`, `sql`, or `cors`. Patch content is also scanned — files whose diff touches sensitive patterns rank higher regardless of path.

This means a change to `src/auth/jwt.py` will always be reviewed before a change to `src/ui/button.tsx`, even if the button change is larger.

## Output

The action produces:

1. **Job Summary** - Full review appears in the GitHub Actions run summary
2. **PR Comment** - If triggered from a PR context, the review is posted as a top-level comment
3. **Inline PR Comments** - Questions that reference a specific file and line are also posted as inline review comments on the diff
4. **Artifacts** - `pr_review_output.json`, `pr_review_questions.md`, and `pr_review_architecture.drawio` saved for 90 days

### Security Questions

Each question includes:

- **Confidence score** (0.7–1.0) — how certain the reviewer is this is a real, exploitable issue. Questions below 0.7 are suppressed from the PR comment but retained in `pr_review_output.json`. The suppressed count is noted at the bottom of the comment.
- **Exploit scenario** — a concrete, attacker-perspective description: what payload, what path, what preconditions, and what outcome. Not theoretical.
- **Affected file and line** — when present, triggers an inline comment directly on the relevant diff line.

## Security Notifications

After the involvement decision is made, the workflow automatically notifies the Security team via Slack and/or creates a triage ticket in Linear.

| Involvement level | Slack notification | Linear triage ticket |
|-------------------|--------------------|-----------------------|
| **Required** | Yes (if `SDD_SLACK_WEBHOOK_URL` is set) | Yes (if `LINEAR_API_KEY` is set) |
| **Recommended** | Yes (if `SDD_SLACK_WEBHOOK_URL` is set) | No |
| **Not Required** | No | No |

Add these secrets to suppress or enable notifications:

| Secret | Used for |
|--------|----------|
| `SDD_SLACK_WEBHOOK_URL` | Slack incoming webhook URL for [#team-security](https://montecarlo.enterprise.slack.com/archives/C09BZKBNUK0) |
| `LINEAR_API_KEY` | Linear API key with permission to create issues in the Security team |

To suppress notifications for a specific run, check **Skip notifications** in the manual trigger or set `skip_notifications: true` in your config file.

## Reusable Workflow

For repositories that want to call the PR review from their own pipelines:

```yaml
jobs:
  pr-review:
    uses: monte-carlo-data/mc-security/.github/workflows/pr-review-reusable.yml@main
    with:
      pr-review-url: "https://github.com/org/repo/pull/42"
      notion-sdd-url: "https://www.notion.so/..."               # optional
      context-repos: "monte-carlo-data/agent-hub"               # optional, comma-separated, max 3
      skip-notifications: false
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      SOURCE_REPO_TOKEN: ${{ secrets.SOURCE_REPO_TOKEN }}  # only if PR repo is private/cross-org
      NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
      SDD_SLACK_WEBHOOK_URL: ${{ secrets.SDD_SLACK_WEBHOOK_URL }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
```

The reusable workflow sparse-checks out the `mc-security` scripts rather than requiring you to copy them manually.

## Troubleshooting

**"Could not parse GitHub PR URL"**
- Make sure the URL is a full PR URL: `https://github.com/org/repo/pull/N`

**"GitHub API error fetching PR"**

- The workflow uses `github.token` by default — verify it has read access to the PR repo
- For PRs in a different org or private repo, pass `SOURCE_REPO_TOKEN` (a PAT with `repo` scope) as a secret to the reusable workflow

**"NOTION_TOKEN is required when NOTION_SDD_URL is set"**
- Either remove `notion_sdd_url` from your config or add the `NOTION_TOKEN` secret

**Review output is too generic**
- Provide a Notion SDD URL to add design context
- Make sure the PR itself has a descriptive title and body — the reviewer uses this as context
