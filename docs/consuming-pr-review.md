# Consuming the PR security review from another repo

`.github/workflows/pr-review-reusable.yml` is called by repos across the org. This is the
contract it offers, and the ways callers have gotten it wrong.

## Pass the secrets the reusable needs

The reusable runs on **your** runner but checks its review scripts out of the **private
security** repo. Your repo's `GITHUB_TOKEN` cannot read that repo, so the reusable mints its
own short-lived token from a GitHub App installed on the org (`SECURITY_GITHUB_APP_ID` /
`SECURITY_GITHUB_APP_PRIVATE_KEY`, org secrets visible to every repo). You must let those secrets reach
the reusable. The simplest correct call is:

```yaml
jobs:
  review:
    uses: <organization>/security/.github/workflows/pr-review-reusable.yml@main
    with:
      pr-review-url: ${{ github.event.pull_request.html_url }}
    secrets: inherit          # ← passes SECURITY_GITHUB_APP_ID/KEY + ANTHROPIC_API_KEY, etc.
```

`secrets: inherit` forwards every secret the caller can see. If you prefer to be explicit, pass at
least these:

```yaml
    secrets:
      ANTHROPIC_API_KEY:          ${{ secrets.ANTHROPIC_API_KEY }}
      SECURITY_GITHUB_APP_ID:           ${{ secrets.SECURITY_GITHUB_APP_ID }}
      SECURITY_GITHUB_APP_PRIVATE_KEY:  ${{ secrets.SECURITY_GITHUB_APP_PRIVATE_KEY }}
      SDD_SLACK_WEBHOOK_URL:      ${{ secrets.SDD_SLACK_WEBHOOK_URL }}
      LINEAR_API_KEY:             ${{ secrets.LINEAR_API_KEY }}
      OPENAI_API_KEY:             ${{ secrets.OPENAI_API_KEY }}   # odd PRs are reviewed by OpenAI
```

Two traps that break callers:

- **`SOURCE_REPO_TOKEN: ${{ secrets.GITHUB_TOKEN }}` does nothing useful.** It just renames your own
  ephemeral token, which still can't read the security repo → the script checkout 404s → no verdict →
  the run fails closed to `Required`. Don't pass `GITHUB_TOKEN` as `SOURCE_REPO_TOKEN`. The App
  token handles the security-repo checkout; `SOURCE_REPO_TOKEN` is only for reading *your* private
  `CONTEXT_REPOS`, and defaults to `github.token` when omitted.
- **`ANTHROPIC_API_KEY` may not be an org secret.** Even with the checkout fixed, the reviewer aborts
  with "Missing required env var: ANTHROPIC_API_KEY" unless the key reaches your repo. Provision it
  as a repo secret, or as an org secret scoped to the repos that call the reusable.

## Pin by SHA, and pass the same SHA as `security-ref`

`@main` runs whatever is on the security repo's main with your secrets. Pinning `uses:` to a commit
SHA pins only the workflow file; the reviewer scripts come from a separate checkout of the security
repo. Pass the same SHA as `security-ref` so both match:

```yaml
    uses: <organization>/security/.github/workflows/pr-review-reusable.yml@<sha> # security main @ YYYY-MM-DD
    with:
      pr-review-url: ${{ github.event.pull_request.html_url }}
      security-ref: <sha>
```

`security-ref` defaults to `main`, so callers that don't pass it behave as before.
Every reusable that fetches code from the security repo takes the same input: `sdd-review`,
`deploy-notion` and `deploy-lucidchart`.

## Gate on the outputs, not the comment

The reusable emits the verdict as workflow outputs:

| Output | Values | Use |
|---|---|---|
| `recommendation` | `Required` \| `Recommended` \| `Not Required` | The verdict |
| `review-required` | `true` \| `false` | The single boolean a merge gate should key on |
| `risk-score` | `0`–`25`, or empty | Likelihood x impact, for reporting |
| `review-status` | `success` \| `failure` | Whether the review ran at all |

```yaml
jobs:
  review:
    uses: <organization>/security/.github/workflows/pr-review-reusable.yml@main
    with:
      pr-review-url: ${{ github.event.pull_request.html_url }}
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      SOURCE_REPO_TOKEN: ${{ secrets.SOURCE_REPO_TOKEN }}

  gate:
    needs: [review]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - if: needs.review.outputs.review-required == 'true'
        run: |
          echo "Security review required — see the Architect's comment on the PR." >&2
          exit 1
```

**Do not** parse the review comment:

```bash
# DON'T — the banner is prose for humans, and it gets reworded.
grep -q "SECURITY REVIEW: REQUIRED" <<< "$body"
```

That string is not an API. It has been reworded before — when the intake path moved from a Slack
post to a Linear ticket, the `SECURITY REVIEW: <VERDICT>` prefix survived by luck, not by contract.
A caller grepping it would have failed closed on every PR with no signal pointing back here. Two
further traps if you grep anyway: `NOT REQUIRED` contains `REQUIRED` as a substring, and low-
confidence questions are filtered out of the comment but present in `pr_review_output.json`.

`review-required` is fail-closed: a missing file, unparseable JSON, or an unrecognized
recommendation all yield `Required`/`true`, matching `pr_reviewer.py`'s own posture — a model
refusal on a security-sensitive diff must never read as an all-clear.

Before it fails closed, the reviewer retries recoverable failures, up to 3 attempts.
These count as recoverable: the model running out of output budget (`stop_reason=max_tokens`), an
empty or unparseable reply, a dropped connection, and 429/5xx/overloaded errors, including ones
that arrive mid-stream. A safety-classifier refusal is re-run server-side on a fallback model
instead of being retried. So a `Required` caused by "the automated reviewer produced no usable
verdict" means every attempt failed. The run log shows `stop_reason` and token usage for each
attempt.

## A bypass label is not a Security sign-off

If you make the verdict a required check, you need an unblock path for `Required`. A label that any
repo writer can apply is not it.

A common anti-pattern: a `security-gate` check where a `security-approved` label short-circuits the
check green, described as "Security signed off — bypasses the security-gate check." Everyone with
write on the repo — including a PR's own author — can self-clear a check that carries Security's
name. In practice an author reads the workflow's unblock instructions, asks Security for the label,
and waits on a gate Security doesn't control and can't grant.

If you own a gate like this:

- **Restrict who can clear it.** Key the bypass on Security team membership, or on the linked
  Security ticket's state — not on a label any writer can add.
- **Don't name it after Security** unless Security can actually grant it. A check called
  `security-gate` that Security cannot pass or fail is a check that misattributes its own outcome.
- **Say what it means when red.** Point at the Linear ticket, not at a label. The reviewer's banner
  tells authors that no label clears the verdict; a gate that contradicts that puts the author in
  the middle of two conflicting instructions.
- **Know whether it blocks.** A check that isn't in the branch's required contexts — or on an
  unprotected branch — is advisory. That's a fine choice, but make it deliberately: a red X that
  blocks nothing while training people to reach for a bypass is the worst of both.

## What the verdict does and doesn't mean

`Required` means the Architect found criteria that warrant a human security look. When the finding
is **Critical** — risk score ≥ 14/25, or no score because the review failed closed — a ticket is
filed in the Security Triage queue. Below that threshold the review still lands as a PR
comment and Slack post, but no ticket is created; open one manually if you want Security involved.
Either way, `Required` does **not** mean Security has blocked the merge: Security does not sign off
on PRs, and the reviewing team owns the merge decision with the findings in hand. When a ticket
exists, closing the verdict out means working it.

Authors should answer the Architect's questions **on the PR** — that's what a reviewer reads. An
answer only in Slack doesn't reach the reviewer or change the verdict.
