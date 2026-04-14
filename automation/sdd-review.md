# SDD Security Review - GitHub Action

A GitHub Action that reviews System Design Documents (SDDs) from Notion and generates a comprehensive security review including targeted questions, data classification, compliance considerations, and incident response scenarios.

## What the Review Produces

1. **Security Team Involvement Recommendation** - Whether the Security team should be consulted, with rationale and next steps
2. **1-10 Security Questions** - Specific to your design, prioritized by impact
3. **Data Classification Table** - Every data element classified as Critical/High/Medium/Low with storage, transit, and access details
4. **Compliance Considerations** - SOC 2 scope changes, DPA impacts, data residency, audit logging requirements
5. **Incident Response Scenarios** - What could go wrong, how to detect it, blast radius, and mitigation
6. **Team Question Responses** - Direct answers to specific concerns the team raises
7. **Architecture Diagram (draw.io)** - Interactive, color-coded diagram with trust boundaries, data flows, and security controls. Saved as `sdd_review_architecture.drawio` in build artifacts — open it at [app.diagrams.net](https://app.diagrams.net/)
8. **Architecture Diagram (ASCII)** - Text-based version of the architecture embedded in the PR comment and markdown output for quick reference in terminals and code reviews

## When to Involve the Security Team

The review automatically assesses whether your design needs Security team involvement and surfaces a recommendation at the top of the output. Teams can also use this rubric to self-assess before running the action.

The assessment uses a NIST 800-30 based risk model: each design is scored on **Likelihood (1–5) × Impact (1–5)** = Risk Score (1–25). High (15–25) triggers Required, Medium (5–14) triggers Recommended, Low (1–4) is Not Required.

### Required — Security must be consulted before implementation proceeds

- New external API surface (public endpoints, webhooks, OAuth flows, customer-facing APIs)
- Data classification includes Critical items (credentials, encryption keys, customer PII, auth tokens)
- Authentication or authorization model is being changed or extended
- Customer-supplied code or queries execute on your infrastructure (templates, scripts, custom connector runtimes)
- Cross-tenant data flows or changes to multi-tenancy isolation
- New third-party integrations that receive, transmit, or store customer data
- New encryption schemes, key management, or cryptographic primitives
- Significant IAM, policy, or cross-account access changes

**What to do:** Post the SDD link in your security channel before starting implementation.

### Recommended — Security should review but is not blocking

- Net-new service or significant architectural change with moderate risk surface
- New data stores that expand SOC 2 scope
- New internal APIs between services that cross trust boundaries
- Changes to audit logging, monitoring, or alerting for security-relevant events
- New dependency on an open-source library in a security-sensitive area (auth, crypto, serialization)
- Design acknowledges security tradeoffs but defers decisions to implementation

**What to do:** Consider posting in your security channel for a lightweight async review.

### Not Required — Proceed without Security team involvement

- Internal tooling or developer-facing workflows with no customer data
- All data items are Low or Medium sensitivity with existing, well-understood controls
- No new trust boundaries, external integrations, or authentication changes
- Purely additive change (new UI, metric, dashboard) with no infrastructure changes

**What to do:** Proceed with implementation. The security questions in the review output are still worth addressing during code review.

## Why Provide Additional Context?

The SDD in Notion is the primary input, but providing additional context produces significantly better output:

- **Source code repos** - The reviewer fetches actual file contents (not just directory listings) from your repos. It uses heuristics to find security-relevant files: auth modules, models, IAM policies, Dockerfiles, config files. You can also specify exact file patterns to focus on. This lets it cross-reference the SDD against your actual codebase.
- **Source file patterns** - When repos are large, tell the reviewer which paths matter (e.g. `src/auth/,models/,config/iam`). Without patterns, it picks the top 20 security-relevant files automatically.
- **Architecture diagrams** - Reveal data flows, trust boundaries, and system interactions not fully described in text.
- **Specification documents** - Provide detailed requirements the SDD may reference but not fully explain.
- **Security concerns** - Tell the reviewer what you already know is risky. It will dig deeper rather than restating the obvious.
- **Platform context** - A standing markdown doc describing your platform architecture (multi-tenancy model, IAM patterns, data pipelines, existing security controls). This is the institutional knowledge that makes reviews specific to your platform rather than generic.
- **Team questions** - Specific concerns the team wants addressed. For example: "What are the injection risks for customer-authored Jinja templates?" or "What if the customer modifies connector runtime health check responses?" The reviewer will provide direct assessments.

The more context you provide, the more specific and actionable the output will be.

## Two Ways to Run

| Trigger | How it works |
|---------|-------------|
| **Manual (workflow_dispatch)** | Go to Actions > Run workflow, paste your Notion URL and fill in inputs |
| **PR-triggered** | Add a `.github/sdd-review-config.yml` file to your branch — the review runs automatically and posts results as a PR comment |

Both triggers use the same workflow and the same reviewer script.

## Quick Start

### 1. Set Up Notion Integration

You need a Notion integration token so the action can read your SDD pages.

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"New integration"**
3. Name it (e.g., "SDD Security Review")
4. Select your workspace
5. Under **Capabilities**, enable **"Read content"** (that's all it needs)
6. Click **Submit** and copy the **Internal Integration Secret**
7. **Share your SDD page with the integration:** Open the SDD page in Notion, click the `...` menu (top right), select **"Connections"**, and add your integration

> **Important:** You must add the integration as a connection on **every SDD page** you want to review. Without this, the action will fail with a 404 error. If your SDD lives inside a parent page that already has the connection, child pages inherit it automatically.

### 2. Add Repository Secrets

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | API key from [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_TOKEN` | Yes | The integration secret from step 1 |
| `SOURCE_REPO_TOKEN` | No | GitHub PAT with `repo` scope for accessing source code repos (see below) |

The workflow automatically uses `github.token` (provided by GitHub Actions) to fetch source code and post PR comments. However, `github.token` only has access to the repository running the workflow.

> **Important:** If you provide **Source Code Repos** from other repositories, add a `SOURCE_REPO_TOKEN` secret with a PAT or service account token that has read access to those repos. Without it, the source code fetch will fail with a 404. If `SOURCE_REPO_TOKEN` is not set, the workflow falls back to `github.token`.

### 3. Copy the Workflow and Script

Copy these files from the practicum repo into your repository:

```
your-repo/
  .github/
    workflows/
      sdd-review.yml          # from .github/workflows/sdd-review.yml
    scripts/
      sdd_reviewer.py         # from .github/scripts/sdd_reviewer.py
```

### 4. (Optional) Create Context Files

For richer reviews, add these files to your repo:

```
your-repo/
  docs/
    platform_context.md       # platform architecture patterns (see template below)
    team_questions.md          # specific questions for this review
    security_concerns.md       # known risks the team has identified
```

**Platform context template** (`docs/platform_context.md`):

```markdown
# Platform Architecture

## Multi-Tenancy Model
- All customer data is scoped by a tenant ID on every database record
- API requests are authenticated and scoped to a single tenant
- Cross-tenant data access must be flagged as a critical risk in any design

## IAM & Authentication
- Service-to-service calls use signed JWT tokens with short expiry
- Cross-account access uses IAM role assumption with external IDs
- Secrets are stored in a secrets manager — never in code or config files

## Data Pipeline
- Event streams carry data between services
- Object storage is used for artifact storage (encrypted at rest)
- Serverless functions process events from streams

## Existing Security Controls
- All API endpoints require authentication
- Authorization is enforced at the resolver/controller level on every query
- Secrets are stored in a secrets manager; no secrets in environment variables
```

**Team questions template** (`docs/team_questions.md`):

```markdown
# Team Questions for Security Review

- What are the risks of executing customer-authored Jinja templates on our infrastructure?
- How should we handle credential storage for third-party API integrations?
- What monitoring should we add to detect runaway data collection jobs?
```

### 5. Run the Review

Go to **Actions > SDD Security Review > Run workflow** and fill in:

| Input | Required | Description |
|-------|----------|-------------|
| **Notion SDD URL** | Yes | The URL of your SDD page in Notion |
| **Source Code Repos** | No | Comma-separated repo names (e.g., `your-org/data-collector,your-org/backend`) |
| **Source File Patterns** | No | Comma-separated paths to focus on (e.g., `src/auth/,models.py,config/iam`) |
| **Specification Markdown** | No | Path to a spec file in your repo (e.g., `docs/spec.md`) |
| **Architecture Diagram** | No | Path to a diagram file (e.g., `docs/architecture.png`) |
| **Security Concerns** | No | Path to markdown with known security considerations |
| **Platform Context** | No | Path to platform architecture doc (e.g., `docs/platform_context.md`) |
| **Team Questions** | No | Path to markdown with specific questions (e.g., `docs/team_questions.md`) |

## Output

The action produces:

1. **Job Summary** - Full review appears in the GitHub Actions run summary
2. **PR Comment** - If triggered from a PR context, the review is posted as a comment
3. **Artifacts** - `sdd_review_output.json`, `sdd_review_questions.md`, and `sdd_review_architecture.drawio` saved for 90 days

### Example Output

```markdown
## Security Review: Extensible Connector Framework

**Risk Summary:** This design introduces customer-authored code execution within
the pipeline via Jinja templates and custom connector runtime deployments. The primary risks
are injection through template rendering, pipeline disruption from unbounded
collection, and the expanded trust boundary with customer-deployed runtimes.

---

### Security Questions (5)

#### 1. How are customer-authored Jinja templates sandboxed during rendering?
**Area:** Input Validation / Code Injection
**Why it matters:** Templates are rendered server-side to produce SQL. Jinja's
default Environment allows arbitrary Python expressions unless explicitly restricted
with SandboxedEnvironment.

#### 2. What prevents a custom connector runtime from impersonating commands or exfiltrating data?
**Area:** Authentication / Trust Boundary
**Why it matters:** The custom connector runtime inherits the communication protocol of the
existing runtime. If command authentication is weak, a modified runtime could respond
with falsified data or intercept sensitive commands.

---

### Data Classification

| Data Item | Sensitivity | Storage | In Transit | Access |
|-----------|------------|---------|------------|--------|
| Customer DB credentials | Critical | Customer environment | Connector runtime <-> platform endpoint (TLS) | Customer, connector runtime process |
| Jinja SQL templates | High | S3 bucket | Queue, S3 upload | Backend, processor |
| Connector capabilities manifest | Medium | Postgres | Queue | Backend, frontend |

---

### Compliance Considerations

**SOC 2:** New S3 bucket for Jinja templates and new queueing infrastructure are in scope
- *Recommendation:* Ensure bucket encryption, access logging, and lifecycle policies

**Audit Logging:** Custom connector registration and manifest refresh operations need audit trails
- *Recommendation:* Log all `ConnectorDefinitionModel` mutations with actor and timestamp

---

### Incident Response Scenarios

**Scenario:** Customer-defined connector ingests millions of unexpected assets
- **Detection:** Queue lag alarm on the processing worker
- **Blast radius:** Shared queue and processing worker capacity
- **Mitigation:** Disable offending connections via runbook, enforce max_collection_offset
```

The review also includes an **Architecture Diagram** section with an ASCII diagram inline and a draw.io file in the artifacts:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Platform (Trust Zone)                        │
    │                                                                     │
    │  ┌──────────┐     Queue      ┌─────────────┐    S3 (TLS)           │
    │  │ Backend  │───────────────>│ Processor   │──────────────┐        │
    │  │          │    (events)    └─────────────┘              v        │
    │  │          │                                    ┌──────────────┐  │
    │  │ Jinja    │<──── Queue ─── Ingestion Svc  <──  │ Jinja        │  │
    │  │ Render   │    (results)        ^              │ Templates    │  │
    │  └──────────┘                     │ TLS+JWT      │ (S3 bucket)  │  │
    │                                   │              └──────────────┘  │
    └───────────────────────────────────┼─────────────────────────────────┘
                                        │
    ┌───────────────────────────────────┼─────────────────────────────────┐
    │  Customer VPC (External)          │                                 │
    │                          ┌────────┴───────┐                        │
    │                          │ Connector      │                        │
    │                          │ (customer-     │                        │
    │                          │  deployed)     │                        │
    │                          └────────────────┘                        │
    └─────────────────────────────────────────────────────────────────────┘

> A draw.io version of this diagram is available in the build artifacts (`sdd_review_architecture.drawio`).
> Open it at [app.diagrams.net](https://app.diagrams.net/) for an interactive, color-coded view with
> trust boundaries and data flow annotations.

## Running from a Pull Request

The workflow triggers automatically when a PR adds or modifies `.github/sdd-review-config.yml`. The review results are posted as a PR comment and uploaded as artifacts.

### 1. Create a Config File

Add `.github/sdd-review-config.yml` to your branch with the same fields as the manual inputs:

```yaml
# .github/sdd-review-config.yml
notion_sdd_url: "https://www.notion.so/your-workspace/Your-SDD-Page-abc123def456"

# All fields below are optional
source_repos: "your-org/backend,your-org/data-collector"
source_file_patterns: "src/auth/,models.py,config/"
spec_markdown_path: "docs/spec.md"
architecture_diagram_path: "docs/architecture.drawio"
security_concerns_path: "docs/security_concerns.md"
platform_context_path: "docs/platform_context.md"
team_questions_path: "docs/team_questions.md"
```

### 2. Open or Update the PR

When the PR is opened, synchronized, or reopened with changes to that config file, the review runs automatically. Results appear as:

- A **PR comment** with the full security review
- The **job summary** in the Actions run
- **Artifacts** (`sdd_review_output.json`, `sdd_review_questions.md`, `sdd_review_architecture.drawio`)

### 3. Iterate

Update the config file (e.g., add more source repos, refine file patterns, add team questions) and push. The review re-runs on each update to the config file.

## How Source Code Fetching Works

When you provide source repos, the reviewer:

1. Fetches the full git tree from each repo
2. If you specified file patterns, it fetches files matching those patterns
3. If no patterns, it uses heuristics to pick the top 20 security-relevant files by scoring paths for keywords like `auth`, `permission`, `security`, `credential`, `model`, `config`, `dockerfile`, `terraform`, etc.
4. Fetches actual file contents (up to 4KB each, 30KB total per repo)
5. Includes both the directory structure and file contents in the prompt

This means the reviewer sees real code — not just file names — and can cross-reference SDD claims against the actual implementation.

## Accepted Risk Filtering

The SDD review automatically checks for formally accepted business risks. Any risk that has been evaluated and accepted will be excluded from the review to avoid re-raising decisions already made. If the register is unavailable, the review proceeds normally without filtering.

## Troubleshooting

**"Could not extract Notion page ID"**
- Make sure you're using the full Notion page URL
- The URL should contain a 32-character hex ID

**"SDD page appears to be empty"**
- Ensure the Notion integration has been added as a connection to the page
- Check that the page has content (not just a title)

**"Missing required environment variables"**
- Verify `ANTHROPIC_API_KEY` and `NOTION_TOKEN` are set as repository secrets
- Secret names are case-sensitive

**"Could not fetch tree for repo"**
- The workflow uses `github.token` by default — verify it has read access to the specified repos
- For private repos in a different org, add a `SOURCE_REPO_TOKEN` PAT with `repo` scope

**Review output is too generic**
- Provide source code repos with file patterns targeting relevant code
- Add a platform context doc so the reviewer understands your architecture
- Add team questions to focus the review on specific concerns
- Make sure the SDD itself is detailed enough for meaningful analysis

## Security Notifications

After the involvement decision is made, the workflow automatically notifies the Security team via Slack and/or creates a triage ticket in Linear — **no extra configuration needed beyond adding the secrets below**.

### When notifications fire

| Involvement level | Slack notification | Linear triage ticket |
|-------------------|--------------------|-----------------------|
| **Required** | Yes (if `SDD_SLACK_WEBHOOK_URL` is set) | Yes (if `LINEAR_API_KEY`, `LINEAR_TEAM_ID`, and `LINEAR_TRIAGE_STATUS_ID` are set) |
| **Recommended** | Yes (if `SDD_SLACK_WEBHOOK_URL` is set) | No |
| **Not Required** | No | No |

Linear ticket creation only triggers for **Required** because those designs must involve Security before implementation proceeds. Recommended designs are lower urgency — a Slack ping is sufficient.

### Setup

Add these secrets to the repository running the workflow. Once they're set, notifications fire automatically.

| Secret | Used for |
|--------|----------|
| `SDD_SLACK_WEBHOOK_URL` | Slack incoming webhook URL for your security channel |
| `LINEAR_API_KEY` | Linear API key with permission to create issues in the Security team |
| `LINEAR_TEAM_ID` | Linear team UUID where triage issues should be created |
| `LINEAR_TRIAGE_STATUS_ID` | Linear status UUID for the triage state |

### Suppressing notifications for a specific run

If you're testing or re-running a review and don't want to spam Slack, set `skip_notifications: true`:

**Manual trigger (`workflow_dispatch`)** — check the "Skip notifications" box when running the workflow.

**PR-triggered** — add to `.github/sdd-review-config.yml`:

```yaml
notion_sdd_url: "https://www.notion.so/your-workspace/Your-SDD-Page-abc123def456"
skip_notifications: true
```

**Reusable workflow** — pass the input from your caller workflow:

```yaml
jobs:
  sdd-review:
    uses: <organization>/secure-design-practicum/.github/workflows/sdd-review-reusable.yml@main
    with:
      notion-sdd-url: "https://www.notion.so/..."
      skip-notifications: true
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
      SDD_SLACK_WEBHOOK_URL: ${{ secrets.SDD_SLACK_WEBHOOK_URL }}
      LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
      LINEAR_TEAM_ID: ${{ secrets.LINEAR_TEAM_ID }}
      LINEAR_TRIAGE_STATUS_ID: ${{ secrets.LINEAR_TRIAGE_STATUS_ID }}
```

### Slack message format

The Slack notification is posted as an attachment with color coding (red for Required, yellow for Recommended) and includes:

- SDD title (linked to Notion)
- Recommendation level
- Risk score (Likelihood × Impact)
- Rationale
- Criteria met
- Link to the full review in GitHub Actions

### Linear ticket format

The Linear ticket is created in the Security team's **Triage** queue, unassigned, with:

- Title: `SDD Review: <SDD title>`
- Description: rationale, risk score, criteria met, risk summary, links to the Notion SDD and Actions run
- Status: **Triage**
- Assignee: none (team triages and assigns)
