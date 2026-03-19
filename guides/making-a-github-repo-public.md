# Making a GitHub Repository Public

Use this guide when considering making a private GitHub repository public (e.g., for open source releases).

## When to Use This Guide

This process applies any time a private repository is being changed to public visibility. This ensures the change is intentional and safe.

---

## Pre-Flight Checklist

Complete all items before changing visibility.

### Secrets & Credentials

- [ ] Scan the full git history for secrets, tokens, API keys, and credentials
  - Use tools like `gitleaks` and `trufflehog`:
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

### Repository Configuration

- [ ] Add or verify `README.md` describes the project purpose and how to use it
- [ ] Add `LICENSE` file — confirm with legal if unsure which license to use
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
- [ ] If the repo contains infrastructure-as-code, data connectors, or security tooling — get explicit sign-off from your security team
- [ ] Document the decision (ticket or design doc) with: repo name, date, approver, and rationale

---

## Making the Change

1. Navigate to the repo **Settings → Danger Zone → Change visibility**
2. Select **Public**
3. Confirm you have read and understood the effects
4. Click **Make this repository public**

> Note: Visibility changes are logged in GitHub's org audit log. Notify your security team so they know the change was intentional.

---

## After Going Public

- [ ] Verify GitHub Pages (if used) is still configured as intended
- [ ] Monitor secret scanning alerts for the first 48 hours
- [ ] Confirm Dependabot is running and any alerts are triaged
- [ ] Update any internal documentation to reflect the repo is now public
