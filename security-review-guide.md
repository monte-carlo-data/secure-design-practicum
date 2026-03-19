# Security Review Guide

> **Note:** This guide does not replace a full security review. It is designed to help engineers generate informed questions and identify potential concerns when preparing a design document for review.

## What do I need?

| Your situation | Do this | Where |
| -------------- | ------- | ----- |
| Quick security gut-check for my feature | Answer the [10 Security Questions](guides/quick-security-review.md) | guides/ |
| I want Claude to walk me through it | Use the [Quick Review Prompt](prompts/quick-review-prompt.md) | prompts/ |
| I want Claude Code to run the review interactively | Use the [Claude Code Skill](#claude-code-sdd-review-skill) (`/sdd-review` in Claude Code) | Claude Code CLI |
| Preparing for a formal security review | Complete the [Self-Service Checklist](guides/self-service-checklist.md) | guides/ |
| I have an SDD in Notion and want automated review | Use the [SDD Review Action](#sdd-review-github-action) (manual or PR-triggered) | [automation/sdd-review.md](automation/sdd-review.md) |
| I want a security review of a pull request diff | Use the [PR Review Action](#pr-review-github-action) (manual or PR-triggered) | [automation/pr-review.md](automation/pr-review.md) |
| I want AI-powered vulnerability scanning of my code | See [Claude Code Security (Optional)](#claude-code-security-optional) (research preview) | Claude Code CLI |
| Full architecture documentation | Use the [Architecture Review Assistant](prompts/architecture-review-assistant.md) | prompts/ |

---

## SDD Review GitHub Action

A GitHub Action that reads your SDD from Notion, pulls in source code and context, and generates a security review with questions, data classification, compliance notes, and incident scenarios.

### How to use it

**Option A: Manual (workflow_dispatch)**

1. Copy the workflow and script from `automation/` into your repo's `.github/` directory
2. Add `ANTHROPIC_API_KEY` and `NOTION_TOKEN` as repo secrets
3. Go to **Actions > SDD Security Review > Run workflow**
4. Paste your Notion SDD URL and optionally add source repos, file patterns, and context files

**Option B: PR-triggered**

1. Copy the workflow and script into your repo (same as above)
2. Add `ANTHROPIC_API_KEY` and `NOTION_TOKEN` as repo secrets
3. Add a `.github/sdd-review-config.yml` file to your branch:
   ```yaml
   notion_sdd_url: "https://www.notion.so/your-workspace/Your-SDD-Page-abc123"
   source_repos: "your-org/backend"
   source_file_patterns: "src/auth/,models.py"
   platform_context_path: "docs/platform_context.md"
   ```
4. Open a PR (or push to an existing one) — the review runs automatically and posts results as a PR comment

See the [full setup instructions](automation/sdd-review.md).

### Inputs

| Input | Required | What it does |
|-------|----------|-------------|
| Notion SDD URL | Yes | The SDD page to review |
| Source Code Repos | No | Repos to fetch code from (fetches actual file contents, not just directory listings) |
| Source File Patterns | No | Focus on specific paths like `src/auth/,models.py` |
| Spec Markdown | No | Requirements doc in your repo |
| Architecture Diagram | No | PNG, SVG, or draw.io file |
| Security Concerns | No | Known risks you want to dig deeper into |
| Platform Context | No | Standing doc describing your platform architecture (see [template](guides/platform-context-template.md)) |
| Team Questions | No | Specific concerns you want answered |

### Accepted Risk Filtering

The SDD review automatically checks the risk register repo for formally accepted business risks. Any risk that has been evaluated and accepted will be excluded from the review — the reviewer will not generate questions or findings that overlap with accepted risks.

This prevents duplicate findings for risks that have already been through the review process. The risk register is fetched at review time using the workflow's GitHub token. If the register is unavailable (repo doesn't exist yet, token lacks access), the review proceeds normally without filtering.

### What you get back

- **Security Team Involvement Recommendation** — Required / Recommended / Not Required, with a NIST 800-30 risk score (Likelihood × Impact), rationale, and next steps. Appears as a banner at the top of every output.
- **1–10 Security Questions** prioritized by impact (excluding accepted risks)
- **Data Classification Table** (Critical/High/Medium/Low)
- **Compliance Considerations** (SOC 2, DPA, data residency, audit logging)
- **Incident Response Scenarios** (what breaks, how to detect, blast radius)
- **Team Question Responses** (if you provided questions)
- **Architecture Diagram (draw.io)** — color-coded interactive diagram with trust boundaries, data flows, and security controls. Download from build artifacts and open at [app.diagrams.net](https://app.diagrams.net/)
- **Architecture Diagram (ASCII)** — text-based version of the same diagram, embedded directly in the PR comment and markdown output for quick reference during code reviews

---

## PR Review GitHub Action

A GitHub Action that fetches a pull request diff, prioritizes security-relevant changed files, and generates the same structured security review as the SDD action — without requiring a Notion SDD. Optionally accepts a Notion SDD URL for design context.

### Setup

#### Option A: Manual (workflow_dispatch)

1. Copy the workflow and script from `.github/workflows/pr-review.yml` and `.github/scripts/pr_reviewer.py` in the practicum repo into your repo
2. Add `ANTHROPIC_API_KEY` as a repo secret
3. Go to **Actions > PR Security Review > Run workflow**
4. Paste the GitHub PR URL (e.g. `https://github.com/org/repo/pull/42`)

#### Option B: PR-triggered

1. Copy the workflow and script into your repo (same as above)
2. Add a `.github/pr-review-config.yml` file to your branch:
   ```yaml
   pr_review_url: "https://github.com/org/repo/pull/42"
   notion_sdd_url: "https://www.notion.so/..."  # optional
   ```
3. Open a PR — the review runs automatically and posts results as a PR comment

#### Option C: Reusable workflow (no files to copy)

Call the canonical workflow directly from your pipeline — scripts are fetched automatically:

```yaml
jobs:
  pr-review:
    uses: monte-carlo-data/secure-design-practicum/.github/workflows/pr-review-reusable.yml@main
    with:
      pr-review-url: "https://github.com/org/repo/pull/42"
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

See the [full setup instructions](automation/pr-review.md).

### Differences from the SDD Review

| Aspect | SDD Review | PR Review |
| ------ | ---------- | --------- |
| **Primary input** | Notion SDD | GitHub PR diff |
| **Best used** | Early design phase | During or after implementation |
| **Notion required** | Yes | No (optional context only) |

### PR Review output

Same structured output as the SDD Review: involvement recommendation, security questions, data classification, compliance notes, incident scenarios, and architecture diagrams.

---

## Claude Code SDD Review Skill

The SDD review is also available as a Claude Code skill (`/sdd-review`). This is the fastest way to run a review interactively — no pipeline setup or GitHub Actions required.

In Claude Code, type `/sdd-review` and follow the prompts. The skill will:

1. Ask for the Notion SDD URL and any optional context (source repos, security concerns, team questions)
2. Fetch the SDD from Notion and gather relevant context
3. Generate the same structured output as the pipeline: risk recommendation, security questions, data classification, compliance notes, and incident scenarios

The skill uses the same underlying prompt and logic as the GitHub Action. Output is shown inline in your Claude Code session rather than posted as a PR comment. Use the GitHub Action when you want automated PR-triggered reviews or persistent CI output.

---

## Self-Service Resources

| Resource | What it is | When to use it |
| -------- | --------- | ------------- |
| [10 Security Questions](guides/quick-security-review.md) | Mental checklist for any feature | Early in development |
| [Quick Review Prompt](prompts/quick-review-prompt.md) | Claude walks you through the 10 questions | When you want a documented summary |
| [Self-Service Checklist](guides/self-service-checklist.md) | Checkbox-style validation | Before requesting a formal review |
| [Architecture Review Assistant](prompts/architecture-review-assistant.md) | Full 7-phase guided review with Claude | New applications or complex systems |
| [Claude Prompting Guide](guides/claude-prompting-guide.md) | Specialized prompts for specific tasks | Threat modeling, API docs, gap analysis |
| [Architecture Walkthrough Questions](guides/architecture-walkthrough-questions.md) | 33 questions for live reviews | Preparing for a walkthrough |

---

## Claude Code Security (Optional)

[Claude Code Security](https://www.anthropic.com/news/claude-code-security) is an AI-powered vulnerability scanner from Anthropic, currently in limited research preview. Unlike traditional SAST tools that rely on pattern matching, it uses Claude to reason about code the way a human security researcher would — tracing data flows across files, understanding component interactions, and catching business logic flaws that rule-based tools miss.

### Why it matters

- Found 500+ vulnerabilities in production open-source projects undetected for decades
- Multi-stage adversarial verification reduces false positives
- Suggests targeted patches that maintain code style (human approval required)
- Complements existing SAST tools by covering their blind spots

### When to use it

Claude Code Security is **optional and supplementary** — it does not replace the SDD Review Action or manual security reviews. It is best suited for:

| Use Case | When |
| -------- | ---- |
| Deep vulnerability scan of repos referenced in an SDD review | After running the SDD Review Action, to surface code-level issues |
| Periodic scanning of critical repos | Quarterly or after major releases |
| Post-incident targeted analysis | After a security event, to find related vulnerabilities |

### Status

Currently a research preview for Enterprise and Team plan customers. Open-source maintainers get expedited free access.

---

## Review Process

### For Engineers

1. Run the [SDD Review Action](#sdd-review-github-action) or `/sdd-review` skill on your Notion SDD — this is your primary self-service tool
2. Run the [PR Review Action](#pr-review-github-action) on your pull request diff to catch implementation-level risks
3. Complete the [Self-Service Checklist](guides/self-service-checklist.md) before requesting a formal review
4. If either review returns **Required** or **Recommended**, engage your security team before proceeding

### For Security Team

1. Review the [Architecture Walkthrough Questions](guides/architecture-walkthrough-questions.md)
2. Use the [Security Architecture Review Template](security-architecture-review-template.md)
3. Document findings in `reviews/<slug>/review.md`
4. Add a row to [reviews/TRACKING.md](reviews/TRACKING.md) with status, reviewer, date, and ticket

---

## Tips

- **Start early** — Think about security during design, not after implementation
- **Provide context** — The more context you give the SDD review (code, diagrams, questions), the better the output
- **Don't paste secrets** — Never include real API keys or credentials in prompts
- **AI is a starting point** — It's not a final security review, but it catches things humans miss
