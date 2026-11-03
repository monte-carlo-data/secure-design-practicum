# Making a GitHub Repo Public

Read this before changing any repository in your organization from private to public. Once a repo is public it is permanently indexed and cached by outsiders — so check it first.

## What to expect

1. **Run the pre-flight review** (below) — it does the heavy lifting and tells you what to fix.
2. **Fix anything it flags as a Blocker.** Recommended items are optional hardening.
3. **Get sign-offs** if they apply — see *Who gets pulled in*.
4. **Flip the repo** and do the after-going-public steps.

## Who gets pulled in

You don't run this alone. Loop in these people when their item comes up:

- **Legal** — if the repo uses or bundles open-source code under **GPL / LGPL / AGPL**, or if you change any wording inside the `LICENSE` file. (See *OSS Compliance*.)
- **Security** (`#security-helpdesk`) — only if the review comes back with **open Blockers** you aren't remediating, or it flags something it couldn't classify. A clean run (zero Blockers) **is** the security sign-off — you don't need to post anywhere, including for infrastructure code, data connectors, or security tooling.
- **The owning team** — confirms they understand the repo goes permanently public, and records the approval.

> **The pre-flight review is the source of truth.** This page is a short orientation; the review runs the full checklist below. Run it and follow what it reports.

---

## Running the Review

There are two ways to run the pre-flight review — choose whichever fits your workflow:

### Option A — Automated pipeline (recommended)

If your organization has a reusable "public repo review" workflow, call it from the repo you want to open, or trigger it from the security repo against that repo. It runs the secret scans (gitleaks + trufflehog) and the full checklist automatically. Results appear in the run **Summary** tab as a shareable URL, and can optionally be posted as a comment on a Linear ticket.

### Option B — Interactive review

Walk the checklist below with an AI assistant (for example a Claude Code skill that takes `<organization>/my-repo` as its argument) or by hand. Run the secret scans yourself (see *Secrets & Credentials*).

---

## Pre-Flight Checklist

Complete all items before changing visibility.

### Secrets & Credentials

- [ ] Scan the full git history for secrets, tokens, API keys, and credentials
  - **Pipeline:** runs automatically (see Option A above)
  - **Manual:** use `gitleaks` and `trufflehog` — three passes:
    1. **gitleaks** — full git history, deep encoding detection, archive traversal
    2. **gitleaks plain** — working tree scan for untracked files
    3. **trufflehog** — detector-based scan with live credential verification against 700+ APIs
  - If anything is found, rotate the credential immediately and rewrite history with [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) before proceeding
- [ ] Confirm `.gitignore` excludes all secret/config files
- [ ] Confirm no internal hostnames, IPs, or environment-specific config is embedded in code or comments
- [ ] Confirm no internal documentation, architecture details, or customer data is present

### Code Review

- [ ] Review all open issues and PRs — internal-only context should be removed or redacted
- [ ] Review commit messages for sensitive references (customer names, internal system names, vulnerability details)
- [ ] Confirm no third-party proprietary code is included that cannot be publicly distributed
- [ ] Audit for third-party copyleft code (e.g., GPL, LGPL, AGPL) — copyleft licenses impose obligations on the repo's own license; flag any findings to legal before proceeding

### OSS Compliance (only if you ship a Docker image, package, or Helm chart)

**Plain version:** if you publish an artifact, you're handing other people's open-source code along with your own. That carries legal obligations — so a couple of items here go to **legal**, not security.

- [ ] **Copyleft licenses (GPL / LGPL / AGPL) anywhere in the bundled code** → flag to legal first. Shipping the artifact redistributes every bundled library, so these obligations apply even if none of your own code is copyleft.
- [ ] **Include a `NOTICE` file** — bundled MIT / Apache-2.0 / BSD code requires you to carry its copyright and license text. Add a top-level `NOTICE` (or `THIRD_PARTY_LICENSES`) listing the bundled dependencies. *(Source-only repos that don't ship an artifact can skip this.)*
- [ ] **Changing wording inside the `LICENSE` file → legal sign-off.** Updating the copyright line to the current company name is fine. Changing actual license terms — e.g. the named **Licensor** — is a contract change and needs legal/owner approval first, even for the rename.

### Repository Configuration

- [ ] Add or verify `README.md` describes the project purpose and how to use it
- [ ] Add `LICENSE` file — permissive (Apache 2.0 or MIT) or restrictive/proprietary are both acceptable. Copyleft licenses (GPL, LGPL, AGPL) must be flagged to legal before proceeding
- [ ] Copyright notice uses the correct company name **and a year** (e.g. `Copyright 2026 Your Organization, Inc.`). The exact wording depends on when the repo was created — use the legal entity name that applies, and confirm with legal if the company has been renamed
- [ ] Add `SECURITY.md` with instructions for responsible disclosure
- [ ] Add `CONTRIBUTING.md` if external contributions are expected
- [ ] Enable **Private vulnerability reporting** in repo Settings → Security
- [ ] Enable **Dependabot alerts** (free for public repos)
- [ ] Enable **Secret scanning** (free for public repos)
- [ ] Enable **Code scanning** (free for public repos)
- [ ] Verify branch protection rules are in place for `main` (require PRs, no force pushes)

### GitHub Actions

- [ ] Review all workflow files — logs for public repos are publicly visible
- [ ] Confirm no secrets are printed to logs
- [ ] Confirm workflows do not expose internal infrastructure details
- [ ] Set `permissions` to least-privilege in all workflows

### Access & Ownership

- [ ] Confirm the repo is owned by the correct GitHub org
- [ ] Review who has write/admin access — remove anyone who shouldn't retain it post-publication
- [ ] Disable forking in org settings if the repo should not be forkable (note: this limits open source utility)

---

## Risk Assessment (NIST 800-30 Aligned)

Before proceeding, assess the risk of public exposure using the threat framework from [NIST SP 800-30 Rev. 1](https://csrc.nist.gov/pubs/sp/800/30/r1/final):

| Threat | Likelihood | Impact | Notes |
|---|---|---|---|
| Leaked credentials in history | Medium | High | Covered by history scan above |
| Exposure of internal architecture | Low-Medium | Medium | Review commits and comments |
| Supply chain attack via public package | Low | High | Review if the repo publishes a package |
| Reputational harm from low-quality code | Low | Medium | Review code quality before release |
| Forked repo used to distribute malware | Low | Medium | Consider disabling forks if not needed |

If any threat rates **High likelihood** or **High impact with no mitigating control**, escalate to the security team before proceeding.

---

## Approval

- [ ] Confirm with the owning team that they understand the repo will be permanently indexed and cached externally
- [ ] If the review left **open Blockers** (or flagged something it couldn't classify) — get explicit sign-off from the security team in `#security-helpdesk`. A zero-Blocker review needs no post; it is the sign-off.
- [ ] Document the decision (ticket or design doc) with: repo name, date, approver, and rationale

---

## Making the Change

1. Navigate to the repo **Settings → Danger Zone → Change visibility**
2. Select **Public**
3. Confirm you have read and understood the effects
4. Click **Make this repository public**

> Note: Visibility changes are logged in GitHub's org audit log, and your security team may alert on them. This is expected — you do not need to suppress or pre-approve the alert, but be prepared to confirm the change was intentional if asked.

---

## After Going Public

- [ ] Verify GitHub Pages (if used) is still configured as intended
- [ ] Monitor secret scanning alerts for the first 48 hours
- [ ] Confirm Dependabot is running and any alerts are triaged
- [ ] Update any internal documentation to reflect the repo is now public
