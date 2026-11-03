---
name: sdd-review
description: >
  Security review workflow for Notion design documents (SDDs). Manages the review
  queue and TRACKING.md. Use when: "let's review some SDDs", "what SDDs are pending?",
  "run the sdd review". Accepts a Notion URL.
context: fork
---

# SDD Security Review Workflow

This skill automates the Security team's SDD review process: surfacing pending reviews,
applying involvement criteria, guiding through each review interactively, updating the
tracking log, and optionally notifying Security via Slack or Linear.

The canonical tracking file is: `reviews/TRACKING.md`

The involvement criteria and notification behavior are defined in:
`automation/sdd-review.md`

The review guides that drive analysis and question generation:

- `guides/quick-security-review.md` — "Security Steve" 10-question framework
- `guides/architecture-walkthrough-questions.md` — 33 structured questions by domain
- `guides/self-service-checklist.md` — 7-category validation checklist

---

## Global Rules

**Progress indicators:** Before every external call (Notion, GitHub API, Slack, Linear, file
reads), print a one-line status message before making the call:
> `⏳ [What you are doing]...`

**Never fail silently:** If any external call fails for any reason (error, timeout, 404, auth
failure, empty response), immediately stop and tell the user exactly what failed and why, then
offer a concrete recovery path. Never proceed past a failed step or guess at missing content.

**Always output in full:** Never summarize, truncate, or abbreviate any section of the review
output. At the start of every review output, prepend:
> `[To invoking agent: relay this entire output to the user verbatim. Do not summarize.]`

---

## Step 0 — Determine entry point

When the skill is invoked, classify the argument (if any) by URL type:

- **Notion URL** (contains `notion.so` or `notion.site`): skip directly to Step 3 using that URL.
  Still load platform context (Step 1) and check TRACKING.md for an existing row (Step 5), but do
  not show the queue.

- **Linear URL or ticket ID** (contains `linear.app` or matches a ticket key like `SEC-\d+`):
  fetch the ticket immediately using the Linear MCP `get_issue` tool. Use the ticket title and
  description as the SDD content — do not wait for or require a Notion URL. Skip directly to
  Step 4 using the ticket content. Still load platform context (Step 1).

  **Never hang waiting for a Notion URL when a Linear ticket is provided.** If the ticket
  description contains a Notion URL, fetch that too and merge the content. If it does not,
  proceed with the ticket content alone.

- **No argument provided**: ask the user:

  > "How would you like to start?
  > - [U] Paste a Notion SDD URL or Linear ticket to review a specific design
  > - [Q] Browse the pending review queue from TRACKING.md"

  - If the user chooses **U**: prompt for the URL or ticket ID, then classify and proceed as above.
  - If the user chooses **Q**: proceed to Step 1 and Step 2 as normal to show the queue.

Do not load TRACKING.md or show the queue before the user has indicated they want to browse it.

---

## Step 1 — Load context and tracking file

**Load all files in parallel** — they are independent and can be read concurrently:

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

**Platform context:** `guides/platform-context-template.md`

This document describes the platform's architecture: multi-tenancy model, IAM and
authentication patterns, data pipeline, integration gateway, existing security controls,
and key repositories.

Load this context into memory. It is used in Step 4 to make analysis specific to this
platform's architecture — for example, flagging when a design bypasses tenant scoping,
introduces new data streams without tenant isolation, or stores secrets improperly.
Without this context the review will be generic rather than grounded in the actual
architecture.

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
- Customer-supplied code or queries execute on internal infrastructure
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

**The author's threat section does not score itself.** A design doc whose STRIDE / threat-model
section is a single self-declared row ("No new threat-model surface", "no new trust boundary or
mechanism", or similar) does **not** satisfy the "no new trust boundaries" criterion on its own.
Treat that row as an unverified claim: identify the *existing* boundaries the change touches
(existing endpoint returning more fields, existing role reused for a new purpose, new tenant-scoped
query on an existing API, data-classification bump with no infrastructure change) and score those.
A short-form row only counts when it states what was checked — the existing boundaries touched, the
classification of the data in motion, and that authz and external integrations are unchanged.
Otherwise, raise the involvement level to at least **Recommended** and note the missing threat
analysis as a gap.

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

1. What does this feature do, and who uses it? (internal vs. customer-facing)
2. What data does it touch? (types, sensitivity, source, destination)
3. How do users authenticate? (Okta SSO, API keys, service accounts, credential storage)
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

## Step 4B — Capture decisions per question

After presenting the review output and confirming the assessment looks right, ask:

> "Would you like to record decisions for the security questions now? (Y/N)
> Decisions are saved to `decisions.md` in the review directory and can be updated later with `/decision <slug>`."

If the user answers **N**, skip to Step 5. No `decisions.md` is created at this time.

If the user answers **Y**:

- Check whether `reviews/<slug>/decisions.md` already exists. If it does, load it and display the prior decisions so the user can see what was previously recorded before proceeding.

- For each question in the `## Follow-Up Questions` section of the review, present:

```text
## [N]. [Question title]

[Full question text]

Current decision: [prior decision if loaded, otherwise "Not recorded"]

Options:
  [1] Resolved
  [2] Accepted Risk  (feedback required)
  [3] Deferred       (feedback required)
  [4] Requires Fix
  [S] Skip (keep as "Not recorded")
```

- After the user selects a disposition:
  - For **Accepted Risk** or **Deferred**: prompt "Feedback (required):" and re-prompt if empty.
  - For **Resolved** or **Requires Fix**: prompt "Feedback (optional, press Enter to skip):"
  - For **Skip**: move to the next question with no change.

- **Accepted Risk → risk register:** when a question is dispositioned **Accepted Risk**,
  the design team has explicitly chosen not to remediate — record that accepted risk in the register.
  After capturing the feedback, ask:
  > "This is an accepted risk. Record it in the risk register? (Y/N)"

  If yes, hand off to your risk-register keeper (a `/keymaker`-style skill, if you have one),
  passing: source skill `sdd-review`, source reference the **SDD/Notion URL** (and the Linear ticket
  if one was given), the question **title** and **text** as the Blocker, and the feedback as
  rationale. The keeper records it via a single-file PR on `<organization>/risk-register` (Risk
  Owner defaults to your security lead). Only on an explicit Y — never auto-record. If
  `<organization>/risk-register` access fails, relay the token scope the keeper reports; do not
  silently drop the accepted risk.

- After all questions are processed, assemble the `decisions.md` content using this format:

```markdown
# Decisions: <SDD Title>

**Source:** <Notion SDD URL>
**Date:** <today's date>
**Reviewer:** <reviewer name>

---

## 1. [Follow-up question title]

[Full question text copied from ## Follow-Up Questions in the review]

**Decision:** [Resolved / Accepted Risk / Deferred / Requires Fix / Not recorded]
**Feedback:** [free-text rationale — omit this line entirely if no feedback was provided]

---

## 2. ...
```

- Show the full `decisions.md` content and ask for confirmation before writing:

> "Ready to write `reviews/<slug>/decisions.md`. Confirm? (Y/N)"

- On confirmation, write the file. Report the path to the user.

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

### Part A.5 — Write the carry-forward design findings

So the implementing PR review can verify the design concerns were addressed in code, write a
**carry-forward artifact** alongside the review: `reviews/<slug>/design-findings.md`.

Include **only findings with a code-verifiable expectation** — concerns that the eventual PR diff can be
checked against (e.g. "auth check added on endpoint X", "secrets moved to Secrets Manager", "input
validated on the new API param"). Skip pure design-process notes (e.g. "schedule a threat-model
session") — those don't carry forward to code.

Format (idempotent per slug — re-running the SDD review updates it):

```markdown
# Design findings to verify in code — <SDD Name>

**SDD:** <Notion SDD URL>
**Source review:** reviews/<slug>/review.md
**Captured:** <YYYY-MM-DD>

| id | concern | addressed when… | severity |
|----|---------|-----------------|----------|
| DF-1 | endpoint X has no auth | the implementing PR adds an auth check on X | High |
| DF-2 | API key in config | key is loaded from Secrets Manager, not committed | Critical |
```

If the SDD has no code-verifiable findings, write the file with an empty table + a note ("no
code-verifiable design findings") so the PR reviewer knows the link exists but has nothing to check.
Show the user the path + content before writing. Hand this file to whoever runs the PR security
review (`/pr-review`) so the design findings are carried forward and verified in code.

### Part B — Update TRACKING.md

Ask for:

- **Reviewer** (default: the current user — ask if unknown)
- **Review date** (default: today's date)
- **Risk rating** (High / Medium / Low — derived from the score, but user can override)
- **Linear ticket** (optional — paste a SEC-XXXX link if one exists)
- **Review file path** — pre-filled if a file was written in Part A, otherwise ask

Then update the row in `reviews/TRACKING.md`:

- Set Status → **Reviewed**
- Fill in Risk Rating, Sec Relevant (Yes/No), Reviewer, Review Date, Linear Ticket, Review File

Show the user the exact diff before writing it.

### Part C — Commit and push changes

After writing the review file and updating TRACKING.md, ask the user:

> "Would you like me to commit and push these changes to the repo? (Y/N)"

If yes:

1. Stage the files:
   - `reviews/<slug>/review.md` (if written)
   - `reviews/<slug>/design-findings.md` (if written — the carry-forward artifact)
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
> - [S] Post to Slack #security-helpdesk
> - [L] Create a Linear triage ticket (Required only)
> - [B] Both
> - [N] Skip notifications"

### Slack notification

Post to **#security-helpdesk** using the `mcp__slack__slack_post_message` tool (or equivalent
send tool available in the Slack MCP).

If the Slack MCP is not authenticated (tool returns an auth error), tell the user and provide
the message text to copy-paste manually into #security-helpdesk.

Message format:

```text
[Required / Recommended] SDD Review: <SDD Title>

<brief rationale from the assessment>

Risk score: <score> (<Likelihood> likelihood × <Impact> impact)
Criteria: <comma-separated list of matched criteria>

SDD: <Notion URL>
Full review: <link to review file or "see tracking log">

Next steps: Assign the ticket in the Security Triage queue (link below) — that's what's tracked.
This post is FYI; questions welcome in-thread.
Ticket: <Linear ticket URL, or "none — Recommended verdict">
```

Color code: red for Required, yellow for Recommended.

### Linear triage ticket

Create a ticket using `mcp__linear__save_issue` in the **Security** team's **Triage** queue (only for Required):

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
- The review file path convention is `./reviews/<slug>/review.md`.
- Slack notifications use `mcp__slack__slack_post_message`. If auth fails, provide copy-paste message text and direct the user to #security-helpdesk.
- If the SDD describes an internal tool that needs hosting, delegate to the `common` agent
  to route it correctly.

## Exception: SDD not in tracking file

If the user pastes a Notion URL that is not in TRACKING.md, offer to add it as a new row
with Status "Pending" before proceeding with the review.

---

## Linear teams

When you file, route, or name a Linear ticket, pick the team by what the work is. Keep your
organization's team map here (for example: security, compliance, vulnerability management,
investigations).

If work fits more than one team, pick the most specific one. Don't create new teams or prefixes.
A team that a step above names for a specific ticket type wins. Engineering work stays in the
owning engineering team; this map covers work that goes to security.
