# Secure Design Practicum

Resources and automation for conducting security architecture reviews of System Design Documents (SDDs). Helps engineering teams think like "Security Steve" — considering security implications during design and development.

---

## How to Use This Repo

| Type | Purpose | Flexibility |
|------|---------|-------------|
| **References** | Concepts, analogies, and mental models to understand security | Use as learning material — adapt to your context |
| **Specifications** | Step-by-step checklists and required validations | Follow exactly — these are security requirements |

**Rule of thumb:** If it asks questions, it's a reference. If it has checkboxes, it's a specification.

---

## Quick Start

| I want to... | Use this |
|--------------|----------|
| **Self-review before requesting Security's help** | [Quick Security Review](guides/quick-security-review.md) |
| **Use Claude to help document my architecture** | [Quick Review Prompt](prompts/quick-review-prompt.md) |
| **Prepare for a walkthrough with Security** | [Self-Service Checklist](guides/self-service-checklist.md) |
| **Get automated security questions for my SDD** | [SDD Review Action](#sdd-review-github-action) |
| **Get a security review of a pull request diff** | [PR Review Action](security-review-guide.md#pr-review-github-action) |
| **Run the review interactively in Claude Code** | `/sdd-review` skill in Claude Code |
| **See all resources and workflows** | [Security Review Guide](security-review-guide.md) |
| **See an example of a completed review** | [Example Review](reviews/example_custom_integration/review.md) |

---

## What is "Security Steve"?

Security Steve is a persona that helps engineers think about security concerns during development. When reviewing your feature, ask yourself:

> "What would Security Steve notice? What questions would they ask?"

Key Security Steve questions:
- What could go wrong if a malicious user got access?
- What data could be exposed, and to whom?
- How would we know if something bad happened?

---

## SDD Review GitHub Action

A GitHub Action that reads your SDD from Notion, pulls in source code and context, and generates a security review including:

1. **Security Team Involvement Recommendation** — Required / Recommended / Not Required, with NIST 800-30 risk score
2. **1–10 Security Questions** — specific to your design, prioritized by impact
3. **Data Classification Table** — Critical/High/Medium/Low
4. **Compliance Considerations** — scope changes, data residency, audit logging
5. **Incident Response Scenarios** — what breaks, how to detect, blast radius
6. **Architecture Diagrams** — draw.io (interactive) and ASCII (inline)

See the full [setup instructions and documentation](security-review-guide.md#sdd-review-github-action).

### Files to copy into your repo

```
your-repo/
  .github/
    workflows/
      sdd-review.yml          # from .github/workflows/sdd-review.yml
    scripts/
      sdd_reviewer.py         # from .github/scripts/sdd_reviewer.py
```

### Required secrets

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_TOKEN` | Notion integration secret (see [setup guide](security-review-guide.md)) |
| `SOURCE_REPO_TOKEN` | Optional: GitHub PAT for accessing source code in other repos, and for reading a private risk register repo |
| `SDD_SLACK_WEBHOOK_URL` | Optional: Incoming webhook URL for Slack notifications on Required/Recommended reviews |
| `LINEAR_API_KEY` | Optional: Linear API key for auto-creating triage tickets on Required reviews |
| `LINEAR_TEAM_ID` | Optional: Linear team UUID to create tickets in; required if using Linear integration |
| `LINEAR_TRIAGE_STATUS_ID` | Optional: Linear status UUID for the triage state; required if using Linear integration |

---

## Folder Contents

### `/.github/` — Automation

| File | Purpose |
|------|---------|
| [workflows/sdd-review.yml](.github/workflows/sdd-review.yml) | GitHub Actions workflow (manual + PR-triggered) |
| [scripts/sdd_reviewer.py](.github/scripts/sdd_reviewer.py) | Review script: Notion → Claude → markdown output |

### `/guides/` — How-to Documentation

| File | Purpose |
|------|---------|
| [Quick Security Review](guides/quick-security-review.md) | **Start here.** 10 essential questions for any feature |
| [Tactical Examples](guides/tactical-examples.md) | Step-by-step implementation patterns with code |
| [Self-Service Checklist](guides/self-service-checklist.md) | Detailed checklist for pre-review validation |
| [Architecture Walkthrough Questions](guides/architecture-walkthrough-questions.md) | Full question set for formal reviews |
| [Claude Prompting Guide](guides/claude-prompting-guide.md) | How to use Claude for architecture documentation |
| [Platform Context Template](guides/platform-context-template.md) | Template for describing your platform architecture |

### `/prompts/` — AI Prompts

| File | Purpose |
|------|---------|
| [Quick Review Prompt](prompts/quick-review-prompt.md) | **Start here.** Focused 10-question review with Claude |
| [Architecture Review Assistant](prompts/architecture-review-assistant.md) | Comprehensive guided review session |
| [Notion Comment Response Draft](prompts/notion-comment-response-draft.md) | Pull SDD comments and draft review responses |

### `/reviews/` — Review Records

| File/Folder | Purpose |
|-------------|---------|
| [TRACKING.md](reviews/TRACKING.md) | Canonical log of all SDD reviews |
| [example_custom_integration/](reviews/example_custom_integration/) | Example completed review showing format and depth |

### `/_static/` — Reference Data

| File | Purpose |
|------|---------|
| [sdd-review-flow.drawio](_static/sdd-review-flow.drawio) | Process flow diagram for the SDD review workflow |

### Root Files

| File | Purpose |
|------|---------|
| [Security Architecture Review Template](security-architecture-review-template.md) | Full formal review template |
| [Security Review Guide](security-review-guide.md) | Full reference for all resources and workflows |

### `/.claude/commands/` — Claude Code Skills

| File | Purpose |
|------|---------|
| [sdd-review.md](.claude/commands/sdd-review.md) | Interactive Claude Code skill for the SDD review workflow |

---

## Review Process

### For Engineers (Self-Service)

1. **Quick Review** — Answer the [10 essential questions](guides/quick-security-review.md)
2. **Use Claude** — Paste the [Quick Review Prompt](prompts/quick-review-prompt.md) to get AI assistance
3. **Automated SDD Review** — Use the [SDD Review Action](#sdd-review-github-action) to get security questions from your SDD
4. **Check the Checklist** — Validate against the [Self-Service Checklist](guides/self-service-checklist.md)
5. **Request Review** — If needed, engage your security team

### For Security Team

1. **Prepare** — Review the [Architecture Walkthrough Questions](guides/architecture-walkthrough-questions.md)
2. **Conduct Review** — Use the [Security Architecture Review Template](security-architecture-review-template.md)
3. **Document** — Save the review under `reviews/<feature-name>/review.md`
4. **Track** — Add a row to [reviews/TRACKING.md](reviews/TRACKING.md)

---

## Contributing

When adding new guides or templates:
- Follow the "Security Steve" mindset — focus on practical security thinking
- Prefer "how" questions over yes/no questions
- Keep guides actionable and concise
- Add an entry to `reviews/TRACKING.md` for each completed review
