---
name: sdd-review
description: >
  Interactive SDD security review workflow. Use this skill whenever the user
  asks to review SDDs, run the SDD review workflow, triage pending SDDs, or
  check which design documents need security review — even if phrased casually
  (e.g. "let's review some SDDs", "what SDDs are pending?", "run the sdd review").
---

# SDD Security Review Workflow

This skill automates the SDD review process: surfacing pending reviews,
applying involvement criteria, guiding through each review interactively,
updating the tracking log, and optionally notifying the security team via
Slack or Linear.

The canonical tracking file is: `reviews/TRACKING.md`

The involvement criteria and notification behavior are defined in:
`automation/sdd-review.md`

The review guides that drive analysis and question generation:

- `guides/quick-security-review.md` — "Security Steve" 10-question framework
- `guides/architecture-walkthrough-questions.md` — 33 structured questions by domain
- `guides/self-service-checklist.md` — 7-category validation checklist

---

## Step 0 — Determine entry point

When the skill is invoked, check whether a Notion URL was provided as an argument:

- **If a URL was provided** (e.g., `/sdd-review https://notion.so/...`): skip directly to Step 3,
  using that URL. You still need to load platform context (Step 1) and check TRACKING.md for an
  existing row (Step 5), but do not show the queue.

- **If no URL was provided**: ask the user:

  > "How would you like to start?
  > - [U] Paste a Notion SDD URL to review a specific document
  > - [Q] Browse the pending review queue from TRACKING.md"

  - If the user chooses **U**: prompt for the URL, then proceed to Step 3 (after loading context
    in Step 1).
  - If the user chooses **Q**: proceed to Step 1 and Step 2 as normal to show the queue.

Do not load TRACKING.md or show the queue before the user has indicated they want to browse it.

---

## Step 1 — Load context and tracking file

Read the following files from the local filesystem:

**Tracking log:** `reviews/TRACKING.md`

Parse the Review Log table. For each row capture:

- SDD Name
- Notion SDD URL
- Status (Reviewed / In Progress / Pending / Not Reviewed)
- Risk Rating (if filled)
- Sec Relevant (Yes / —)
- Reviewer
- Review Date
- Linear Ticket
- Review File

**Platform context (optional):** `guides/platform-context-template.md`

If the user has a platform context doc available (a standing document describing their
platform architecture, multi-tenancy model, IAM patterns, data pipelines, and existing
security controls), load it into memory. It is used in Step 4 to make analysis specific
to the team's architecture rather than generic.

If no platform context doc exists, ask the user if they have one to provide, or proceed
without it.

---

## Step 2 — Show the pending queue

Filter rows where Status is **Not Reviewed**, **Pending**, or **In Progress**.

Within that set, apply the involvement pre-filter:

- **Priority: High** — Sec Relevant column is "Yes"
- **Priority: Normal** — Sec Relevant column is "—" or empty

Display three tables:

**In Progress (resume these first):**

| # | SDD Name | Notion SDD | Reviewer | Review Date  |
|---|----------|------------|----------|--------------|

Only show this table if any In Progress rows exist. These are reviews that were started but
not completed — surface them first so work isn't lost.

**Security-Relevant SDDs (review next):**

| # | SDD Name | Notion SDD | Status       |
|---|----------|------------|--------------|
| 1 | ...      | SDD link   | Not Reviewed |

**Other Pending SDDs:**

| # | SDD Name | Notion SDD | Status |
|---|----------|------------|--------|

Ask the user:

> "Which SDD would you like to review? Enter a number, a name, or paste a Notion URL.
> Or type 'all sec-relevant' to work through the priority queue one by one."

---

## Step 3 — Fetch the SDD from Notion

When the user selects an SDD:

1. Extract the Notion page URL from the tracking row.
2. Use the Notion MCP `fetch` tool to retrieve the full page content.
3. If fetch fails (404, missing connection), tell the user and ask them to either paste the SDD content directly, or skip this SDD.

Display a short summary of what was fetched (title + first 2-3 paragraphs).

---

## Step 4 — Analyze the SDD using the review guides

This step has three parts: (A) score the involvement level, (B) work through the guide
frameworks to produce grounded findings, and (C) synthesize into a final review output.

### Part A — Involvement scoring

Analyze the SDD content and score it using a NIST 800-30 based model.
Score **Likelihood (1–5)** × **Impact (1–5)** = Risk Score (1–25).

**Required (score 15–25)** — one or more of:

- New external API surface (public endpoints, webhooks, OAuth flows, customer-facing APIs)
- Data classification includes Critical items (credentials, encryption keys, customer PII, auth tokens)
- Authentication or authorization model is being changed or extended
- Customer-supplied code or queries execute on your infrastructure
- Cross-tenant data flows or changes to multi-tenancy isolation
- New third-party integrations that receive, transmit, or store customer data
- New encryption schemes, key management, or cryptographic primitives
- Significant IAM, policy, or cross-account access changes

**Recommended (score 5–14)** — one or more of:

- Net-new service or significant architectural change with moderate risk surface
- New data stores that expand SOC 2 scope
- New internal APIs between services that cross trust boundaries
- Changes to audit logging, monitoring, or alerting for security-relevant events
- New dependency on an open-source library in a security-sensitive area
- Design acknowledges security tradeoffs but defers decisions to implementation

**Not Required (score 1–4)** — all of:

- Internal tooling or developer-facing workflows with no customer data
- All data items are Low or Medium sensitivity with existing, well-understood controls
- No new trust boundaries, external integrations, or authentication changes
- Purely additive change (new UI, metric, dashboard) with no infrastructure changes

Output the involvement block:

```text
### Involvement Recommendation: [Required / Recommended / Not Required]

**Risk Score:** [Likelihood] × [Impact] = [Score]

**Rationale:** [2-3 sentence summary of why]

**Criteria met:**
- [criterion 1]
- [criterion 2]
```

### Part B — Structured analysis using the review guides

Work through each of the following lenses against the SDD content. For each domain, note
what the SDD addresses, what it leaves unanswered, and flag gaps. Only surface items
that are relevant to this design — skip domains where nothing applies.

#### Lens 1 — Quick Security Review (10 questions)

Apply the "Security Steve" framework from `guides/quick-security-review.md`.
For each of the 10 questions, answer it based on the SDD content:

1. What does this feature do, and who uses it? (persona, internal vs. customer-facing)
2. What data does it touch? (types, sensitivity, source, destination)
3. How do users authenticate? (SSO, API keys, service accounts, credential storage)
4. What can different users do? (permission levels, cross-user data access, enforcement)
5. What external services does this integrate with? (APIs, data sent, credential management)
6. Where are secrets stored? (code, config, secret manager, rotation capability)
7. What gets logged? (user actions, errors, security events, sensitive data in logs)
8. What could a malicious user do? (credential compromise, privilege escalation, data access)
9. How would you know if something went wrong? (detection, traceability, alerting)
10. What is the team worried about? (any explicit concerns raised in the SDD)

For each question: if the SDD answers it clearly, note that. If it's silent or ambiguous, flag it as a gap.

#### Lens 2 — Architecture Walkthrough domains

Apply the domain structure from `guides/architecture-walkthrough-questions.md`.
Work through the relevant sections for this SDD:

- **System overview** — main components, tech stack, where it runs, deployment model
- **Data flow** — typical user workflow, what data is created/read/modified, where it goes
- **Authentication** — how users and services authenticate, machine-to-machine auth
- **Authorization** — roles, permission enforcement, cross-tenant access prevention
- **Input/output security** — input validation, output encoding, common vuln prevention
- **Secrets & configuration** — secret storage, env separation, config management
- **Third-party integrations** — external services called, data shared, auth for each
- **Logging & monitoring** — what's logged, how incidents would be detected
- **Incident response** — rollback capability, access revocation, notification path
- **Compliance** — SOC 2 scope changes, data residency, audit logging requirements

For each domain: summarize what the SDD says, and call out gaps or concerns.

#### Lens 3 — Self-Service Checklist gaps

Apply the 7-category checklist from `guides/self-service-checklist.md`.
Identify which items the SDD implies are handled vs. which appear unaddressed:

1. Authentication & Access Control
2. Data Security (classification, protection, data flow)
3. Application Security (input validation, output encoding, dependencies)
4. Infrastructure & Configuration (env separation, secrets, network exposure)
5. Logging & Monitoring
6. Third-Party Integrations
7. Documentation (architecture, data flow, API docs, incident response)

Flag any category with multiple unchecked items as a priority area for the review.

### Part C — Synthesize into review output

After working through all three lenses, produce the full review output.

**Security Questions** — prioritized by impact, grounded in specific gaps found above:

```text
#### 1. [Question title]
**Domain:** [Authentication / Authorization / Data / Integrations / etc.]
**Why it matters:** [1-2 sentences on the risk]
**SDD gap:** [What the SDD says or doesn't say]

#### 2. ...
```

Aim for 3–8 questions. Fewer sharp questions beat a long generic list.
Every question must map to a specific gap from the lens analysis — no generic filler.

**Data Classification Table** — for every data element mentioned in the SDD:

| Data Element | Sensitivity | Storage | In Transit | Access |
|--------------|-------------|---------|------------|--------|

**Gaps Summary** — a bulleted list of the most important unanswered checklist items the
team should address before or during implementation.

Ask the user:

> "Does this assessment look right? You can adjust the involvement level or flag anything
> I missed before we record it."

---

## Step 5 — Save the review and record the decision

### Part A — Offer to write a review file

Ask the user:

> "Would you like me to save this review as a `review.md` file in the repo? (Y/N)"

If yes:

1. Derive a slug from the SDD name (lowercase, spaces to underscores, strip special chars).
2. Write the review output to `reviews/<slug>/review.md`.

Use this structure for the file:

```markdown
# Security Review: <SDD Title>

**Date:** <review date>
**Reviewer:** <reviewer>
**Notion SDD:** <URL>
**Involvement:** <Required / Recommended / Not Required>
**Risk Score:** <Likelihood> × <Impact> = <Score>

---

## Involvement Recommendation

<rationale>

**Criteria met:**
- <criterion 1>

---

## Security Questions

<questions from Part C>

---

## Data Classification

<data classification table from Part C>

---

## Gaps Summary

<gaps summary from Part C>
```

Show the user the file path and content before writing.

### Part B — Update TRACKING.md

Ask for:

- **Reviewer** (default: the current user — ask if unknown)
- **Review date** (default: today's date)
- **Risk rating** (High / Medium / Low — derived from the score, but user can override)
- **Linear ticket** (optional — paste a ticket link if one exists)
- **Review file path** — pre-filled if a file was written in Part A, otherwise ask

Then update the row in `reviews/TRACKING.md`:

- Set Status → **Reviewed**
- Fill in Risk Rating, Sec Relevant (Yes/No), Reviewer, Review Date, Linear Ticket, Review File

Show the user the exact diff before writing it.

### Part C — Commit and push changes

After writing the review file and updating TRACKING.md, ask the user:

> "Would you like me to commit and push these changes to the repo? (Y/N)"

If yes:

1. Stage both files:
   - `reviews/<slug>/review.md` (if written)
   - `reviews/TRACKING.md`
2. Propose a commit message: `sec: add security review for <SDD Name>`
3. Show the user the exact files being committed and the message, and confirm before running.
4. Run `git add <files> && git commit -m "<message>" && git push`.
5. Report the result to the user (success or error output).

If push fails (e.g. no upstream, auth error), surface the error clearly and suggest the user push manually.

### Part D — Optional: push architecture diagram to Lucid

If the review was run via the GitHub Actions pipeline, the pipeline produces a
`sdd_review_architecture.drawio` artifact in the Actions run. Ask the user:

> "Do you have the `.drawio` architecture diagram from the Actions run? I can push it to
> Lucid so it's accessible to the team alongside this review. Paste the file path or
> contents and I'll import it using the Lucid MCP."

Use the Lucid MCP to import the diagram if the user provides it.

---

## Step 6 — Optional: notify Security

If the involvement level is **Required** or **Recommended**, ask:

> "Would you like to notify the Security team?
> - [S] Post to Slack
> - [L] Create a Linear triage ticket (Required only)
> - [B] Both
> - [N] Skip notifications"

### Slack notification

Post to your security channel using the Slack MCP tool. Ask the user for the channel name
if not already known.

Message format:

```text
[Required / Recommended] SDD Review: <SDD Title>

<brief rationale from the assessment>

Risk score: <score> (<Likelihood> likelihood × <Impact> impact)
Criteria: <comma-separated list of matched criteria>

SDD: <Notion URL>
Full review: <link to review file or "see tracking log">

Next steps: Post a reply here with your availability or DM <reviewer>.
```

Color code: red for Required, yellow for Recommended.

### Linear triage ticket

Create a ticket using the Linear MCP in your Security team's Triage queue (only for Required):

- **Title**: `SDD Review: <SDD Title>`
- **Status**: Triage
- **Assignee**: none

Description:

```text
## SDD Security Review — Action Required

**Involvement:** Required

**Risk Score:** <score> (<Likelihood> × <Impact>)

**Rationale:** <rationale>

**Criteria met:**
- <criterion 1>
- <criterion 2>

---

**Links:**
- Notion SDD: <URL>
- Review file: <path or —>
- Reviewer: <name>
```

After creating, report the Linear ticket URL to the user and update the tracking row with it.

---

## Step 7 — Continue or finish

After completing a review, ask:

> "Done with `<SDD Name>`. Continue to the next pending SDD? (Y/N)"

If yes, return to Step 2 (re-read the tracking file to reflect changes) and surface the next item.

If no, summarize what was reviewed this session:

```text
Session summary:
- Reviewed: [list with involvement level]
- Skipped: [list]
- Notifications sent: [Slack/Linear links]
```

---

## Notes

- Always show the user the exact TRACKING.md diff before writing.
- If the Notion fetch fails, allow the user to paste SDD content or skip the SDD.
- Never mark an SDD as Reviewed without explicit user confirmation.
- If the user says "skip" at any point, move to the next SDD without modifying the tracking file.
- Sec Relevant column should be set to "Yes" if involvement is Required or Recommended, "No" if Not Required.
- The review file path convention is `reviews/<slug>/review.md`.

## Exception: SDD not in tracking file

If the user pastes a Notion URL that is not in TRACKING.md, offer to add it as a new row
with Status "Pending" before proceeding with the review.
