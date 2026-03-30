---
name: decision
description: >
  Interactive decision capture workflow for security reviews. Use this
  skill whenever a security engineer wants to record or update decisions for security
  questions in an existing review — even if phrased casually (e.g. "record decisions
  for evalabilly", "update decisions on this review", "/decision evalabilly").
  Accepts a review slug or path as input.
---

# Decision Capture Workflow

This skill loads an existing `decisions.md` from a review directory, presents undecided
questions for disposition, and writes the updated file. It is the primary way to record
or update decisions after a review has been completed.

Decisions live at `reviews/<slug>/decisions.md`. They are separate from
the review narrative (`review.md` or `pr-review.md`) so they can be updated independently
as engineers work through findings.

---

## Step 0 — Identify the review

Check whether the user provided a slug or path at invocation
(e.g. `/decision evalabilly` or `/decision reviews/evalabilly`).

**If a slug or path was provided:** resolve it to a review directory and proceed to Step 1.

- If the input is a bare slug (no `/`), look for `reviews/<slug>/`.
- If the input is a path, use it directly.

**If nothing was provided:** prompt:

> "Which review would you like to record decisions for?
> Provide a slug (e.g. `evalabilly`) or a path (e.g. `reviews/evalabilly`)."

Wait for input before proceeding.

---

## Step 1 — Load the review directory

Check that the directory exists. If it does not:

> "No review found at `reviews/<slug>/`. Check the slug and try again,
> or provide the full path."

Stop and wait for corrected input.

If the directory exists, load the review state as follows:

**1. Find the review file** — look for any of these in the directory (accept typos and variants):

- `review.md`, `reivew.md` — SDD review
- `pr-review.md` — PR review

Read whichever exists. If multiple exist, read all of them. Extract questions from the
**`## Follow-Up Questions`** section only — these are the open questions that require
decisions from the engineering team. Do not pull from `## Concerns`, `## Questions`, or
other sections; those are review findings and commentary, not decision points.

If no `## Follow-Up Questions` section exists in the review file, tell the user and stop:

> "No `## Follow-Up Questions` section found in `<slug>/`. Only follow-up questions
> are tracked in `decisions.md`. If the review doesn't have a follow-up questions
> section yet, add one before recording decisions."

**2. Find or initialize `decisions.md`** — check whether `decisions.md` exists and has content:

- **If `decisions.md` exists and has entries:** load it. Parse each entry's title, full text,
  current decision, and feedback. Cross-reference with the question set from the review file —
  any questions in the review file not yet in `decisions.md` should be added as new
  `Not recorded` entries.
- **If `decisions.md` does not exist or is empty:** build the initial entry list from the
  question set extracted in step 1. All entries start as `Not recorded`.

Announce the state to the user:

> "Found N question(s) in `<slug>` (X undecided, Y decided). Working through undecided ones first."

If no questions could be found in any file, tell the user:

> "No questions found in `reviews/<slug>/`. Paste the questions you'd
> like to record decisions for, or run `/sdd-review` or `/pr-review` first."

---

## Step 2 — Present questions for decision

### If undecided questions exist

Tell the user:

> "Found N undecided question(s) in `<slug>/decisions.md`. Working through them now.
> You can update already-decided entries after."

Present each undecided question in order:

```text
## [N of total]. [Question title]

[Full question text]

Options:
  [1] Resolved
  [2] Accepted Risk  (feedback required)
  [3] Deferred       (feedback required)
  [4] Requires Fix
  [S] Skip (leave as "Not recorded")
```

After the user selects:

- **Accepted Risk** or **Deferred** — prompt: `Feedback (required):` and re-prompt if the
  response is empty. Do not proceed until feedback is provided.
- **Resolved** or **Requires Fix** — prompt: `Feedback (optional, press Enter to skip):`
- **Skip** — move to next question with no change.

### After all undecided questions are handled

If any questions remain undecided (user skipped some), note:

> "N question(s) still undecided. You can run `/decision <slug>` again to come back to them."

Then offer to update already-decided entries:

> "Would you like to update any already-decided entries? (Y/N)
> If yes, I'll list them by number."

If yes, display a numbered list of all decided entries with their current decision, and
ask which number(s) to update. For each selected entry, repeat the disposition prompt.

### If all questions are already decided

> "All questions in `<slug>/decisions.md` are decided. Would you like to update any entry? (Y/N)"

If yes, display the full numbered list and accept a number to update.

---

## Step 3 — Write the updated file

Assemble the full updated `decisions.md`. Before showing it, ask:

> "Who is recording these decisions? (your name or handle)"

Wait for a response — do not proceed with "Not recorded" as the reviewer.

Also extract the source link from the review file header (look for a `**Repo:**`, `**Notion:**`,
`**PR:**`, or similar field). If none is found, omit the `**Source:**` line rather than
leaving it blank or guessing.

Show the full content and ask for confirmation:

> "Ready to write `reviews/<slug>/decisions.md`. Confirm? (Y/N)"

On confirmation, write the file using this format:

```markdown
# Decisions: <Review Title>

**Source:** <link extracted from review header — omit line if none found>
**Date:** <today's date>
**Reviewer:** <name provided by user>

---

## 1. [Follow-up question title]

[Full question text copied from ## Follow-Up Questions in the review]

**Sources:** <PR URL(s) — only present when merged from multiple PRs>
**Decision:** [Resolved / Accepted Risk / Deferred / Requires Fix / Not recorded]
**Feedback:** [free-text rationale — omit this line entirely if no feedback was provided]

---

## 2. ...
```

Report the file path after writing.

---

## Notes

- Valid decisions: `Resolved`, `Accepted Risk`, `Deferred`, `Requires Fix`. No other values.
- `Accepted Risk` and `Deferred` always require non-empty feedback — enforce at prompt time.
- Never silently overwrite the file — always show the full content and confirm first.
- If the user provides a Notion SDD URL or GitHub PR URL instead of a slug, extract the
  page/PR title and derive a slug from it (lowercase, spaces to underscores, strip special
  chars), then check whether that directory exists.
- This skill does not re-run the security review. For a new review, use `/sdd-review` or
  `/pr-review`.
