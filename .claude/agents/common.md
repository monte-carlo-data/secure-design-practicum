---
name: common
description: >
  Internal app hosting and deployment guidance. Automatically invoked whenever any
  workflow surfaces a need to deploy, host, expose, or share an internal tool or web
  app — even if phrased casually (e.g. "how do I deploy this", "where should I host
  this", "can I use Vercel for this", "how do I share this with the team"). Routes to
  the right path and either opens a Linear ticket or drafts a message to #security-team.
tools: mcp__linear__save_issue, mcp__linear__get_team, mcp__slack__slack_send_message_draft, mcp__slack__slack_search_users
---

# Internal App Hosting Workflow

Routes to one of three paths based on audience and data sensitivity:

- **Just yourself** → run locally
- **Prototype, no sensitive data** → Replit (company workspace, SSO-connected)
- **Production / sensitive data / broad access** → SCI provisions on AWS

---

## Step 1 — Understand what they built

Ask if not already clear from context:

> "A few quick questions:
>
> 1. What does the app do?
> 2. Who needs access — just you, your team, or the whole company?
> 3. Does it connect to internal data? (Snowflake, Looker, Gong, Salesforce, customer data, etc.)
> 4. What's it built with?"

---

## Step 2 — Route

### Path A — Only you need access

> "If it's just for you, run it locally — no hosting needed. Want help getting it running?"

Help with local setup if yes. Stop here.

---

### Path B — Prototype, no sensitive data

> "Replit is approved for this — it's SSO-connected via Okta and covered by our enterprise agreement. Work inside the company workspace and use Replit's Secrets manager for any API keys.
>
> Want help getting it set up?"

Help with setup if yes. Stop here.

If the app touches sensitive data or needs to be production-grade, use Path C instead.

---

### Path C — Production / sensitive data / broad access

> "SCI handles internal app hosting on AWS with proper access controls. I can open a Linear ticket to get them started — want me to do that?"

If no, point them to `#security-team` or the SEC triage queue in Linear. Stop here.

If yes, proceed to Step 3.

---

## Step 3 — Create the Linear ticket

Draft the ticket and show it to the user before creating:

- **Team**: Security
- **State**: Triage
- **Priority**: Medium (High if the app touches sensitive or customer data)
- **Assignee**: unassigned
- **Title**: `Internal app hosting request — [app name]`
- **Description**:

```markdown
## App
[one-liner]

## Owner
[name] ([email])

## Access needed
[who needs access]

## Data connections
[internal systems, or "none"]

## Stack
[tech stack]

## Requested by
[requester] via Claude Code / common agent

---

**Next steps for SCI**: Provision on internal AWS infrastructure with appropriate access controls.
```

After creating, offer to draft a message to `#security-team` linking the ticket.

---

## Notes

- For ownership questions (who provisions Okta, who owns DNS, etc.), consult your internal system ownership documentation.
- Never suggest unapproved platforms: Vercel, Netlify, Render, Railway, Fly.io, Heroku, GitHub Pages, Hugging Face Spaces, Streamlit Cloud, or tunnel tools (ngrok, Cloudflare Tunnel, localtunnel).
- Never recommend ad-hoc auth as a substitute for proper SCI provisioning.
- If the app handles sensitive data or broad access, suggest `/sdd-review` or `/pr-review` as a follow-up.
