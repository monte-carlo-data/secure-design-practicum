# OWASP Guidance for Security Reviews

This document covers OWASP frameworks that go beyond the standard Top 10 and apply to specific feature types. Reference it during SDD and PR reviews when your feature matches the trigger criteria below.

---

## OWASP Top 10 for Agentic Applications

**Reference:** [genai.owasp.org/initiatives/agentic-security-initiative/](https://genai.owasp.org/initiatives/agentic-security-initiative/)

### When to apply

Apply this framework when your feature involves any of the following:

- AI agents that take autonomous actions (Claude, GPT, etc.)
- MCP servers or MCP client integrations
- Tool-use patterns where an LLM calls external functions or APIs
- Orchestrator/sub-agent architectures
- Features that allow an AI model to act on behalf of a user

### What to look for

| Risk | What it means for your organization |
| --- | --- |
| **Prompt injection** | Untrusted content (user data, external API responses, file contents) reaching an agent's context and hijacking its instructions |
| **Excessive agency** | An agent with more permissions, tools, or autonomy than the task requires — can amplify blast radius of a mistake or compromise |
| **Tool misuse** | An agent calling tools in unintended ways, or tools lacking input validation that an LLM might exploit |
| **Insecure tool design** | Tools that trust agent-supplied arguments without validation, or that expose dangerous operations without guardrails |
| **Uncontrolled recursion / loops** | Agent orchestration that can spin up unbounded sub-agents, retries, or tool calls |
| **Sensitive data in context** | Customer data, credentials, or PII flowing through an agent's context window and potentially into logs or external APIs |
| **Inadequate human oversight** | Autonomous actions with no human-in-the-loop checkpoint for high-impact operations |

### Questions to answer

- What tools can this agent call, and what is the minimum set needed?
- Can untrusted input (customer data, external content) reach the agent's system prompt or tool arguments?
- What is the worst-case action this agent could take if its instructions were hijacked?
- Is there a human approval step before irreversible actions (deletes, sends, writes)?
- Are agent actions logged with enough detail to reconstruct what happened?

---

## OWASP Non-Human Identities Top 10

**Reference:** [owasp.org/www-project-non-human-identities-top-10/](https://owasp.org/www-project-non-human-identities-top-10/)

> **NHI = service accounts, API keys, OAuth clients, MCP server tokens, CI/CD bot credentials.** This is not about your identity provider or human logins — it is about the machine identities that authenticate on behalf of services.

### When to apply

Apply this framework when your feature involves any of the following:

- Creating or consuming API keys, service account tokens, or OAuth clients
- MCP server authentication (any token the MCP server uses to call downstream APIs)
- CI/CD credentials, GitHub Actions secrets, or automation bot accounts
- Cross-service authentication within your platform
- Third-party integrations where your organization holds a credential on the customer's behalf

### What to look for

| Risk | What it means for your organization |
| --- | --- |
| **Long-lived credentials** | API keys or tokens with no expiry — a leaked key stays valid indefinitely |
| **Overprivileged identities** | Service accounts with broader permissions than the service needs to function |
| **Secret leakage** | Credentials logged, committed to git, exposed in CI artifacts, or passed through URLs |
| **Improper offboarding** | Credentials that survive past the service, employee, or integration they were created for |
| **Vulnerable third-party integrations** | External services that hold your organization's credentials and may not have strong security controls |
| **Lack of rotation** | No rotation process means a compromised credential stays compromised until manually revoked |
| **No inventory** | Credentials that nobody knows exist, so they are never rotated or revoked |

### Questions to answer

- What credentials does this feature create, consume, or store?
- What is the minimum permission scope needed for each credential?
- How are credentials rotated, and what is the rotation period?
- Where are credentials stored — are they in a secret manager (AWS Secrets Manager, HashiCorp Vault), or somewhere else?
- What happens to the credential when the integration is removed or the feature is deprecated?
- Are credentials logged anywhere (including debug logs, error messages, or CI job summaries)?

---

## Adding more OWASP frameworks

To add a new OWASP framework to this guide, append a new `##` section following the same structure:

1. Reference URL
2. "When to apply" trigger criteria
3. "What to look for" table
4. "Questions to answer" list

No changes to the SDD review, PR review, or Security Review Guide docs are needed — they all link here.
