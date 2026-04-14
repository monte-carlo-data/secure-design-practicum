# Example Security Review: Extensible Connector Framework

> **Note:** This is an example review showing the format and depth of analysis produced by the SDD Review workflow. Org-specific details have been generalized. Use this as a reference when reviewing your own SDDs.

**SDD:** Extensible Connector Framework — Partner Extension Model

**Tech Stack:** Python, Jinja2, Docker, PostgreSQL, AWS (S3, SQS, Lambda, ECS), GraphQL

**Scope:** Architecture/design review of the SDD, supplemented with code review of relevant backend repos.

**Risk Rating: High**

Customer-authored code (Jinja2 templates) executes on the platform's backend infrastructure. The trust model for connector runtimes shifts from platform-authored to customer-authored. New ingestion paths (manifests, templates) flow from untrusted sources into core platform components. Any one of these would warrant a High rating individually; together they represent a significant trust boundary change.

---

## Overall Assessment

This is a well-considered extension of an existing connector architecture. The team made sound foundational choices — using Jinja2 over arbitrary code, storing templates in object storage rather than the database, reusing an existing hybrid deployment model, and leveraging existing guardrails for runtime communication. The team's own questions during the review (around template injection risk, credential handling, and runtime trust) show the right security instincts are already present.

The concerns in this review are not about the pattern itself — they are about hardening an inherently higher-risk pattern so it can ship safely. Allowing partners to extend the platform is the right product direction. The security work outlined below is about ensuring the implementation matches the ambition.

---

## Data Classification

| Data Type | Flow Direction | Classification | Notes |
| --- | --- | --- | --- |
| Jinja2 templates | Customer → Platform (via object storage) | **Critical** | Untrusted code that executes on platform infrastructure. Equivalent to customer-submitted code artifacts. |
| Connector manifest JSON | Customer → Platform (via message queue) | **High** | Defines capabilities and storage locations. Controls how the backend interacts with the custom integration. Malformed manifests can alter platform behavior. |
| Connector capabilities | Customer → Platform (stored in DB) | **High** | Determines which platform features are enabled. Incorrect capabilities could enable code paths the runtime doesn't support. |
| SQL query strings | Platform → Customer (via connector runtime) | **Medium** | Generated from customer templates. Contains schema and table names from configured data sources. Customer data remains in the customer's environment, but the platform is the sender of record. |
| Query results / metadata | Customer → Platform (via connector runtime) | **Medium** | Table names, column names, row counts, and schema structures. Subject to existing response size limits. |
| Health check responses | Customer → Platform | **Medium** | Version, build, platform info. Written directly to runtime status fields. Can influence feature gating. |
| Credential references | Customer → Platform (stored in DB) | **Low** | Env var names or Secrets Manager ARNs — not the credentials themselves. Only resolvable from customer's network. |

**Key observation:** The existing ingestion pipeline handles Medium-classified data (query results, metadata). This design introduces Critical and High classifications (templates, manifests) that did not exist in the prior trust model. The security controls must scale accordingly.

---

## Security Questions

### 1. How are customer-supplied Jinja2 templates sandboxed during rendering?

**Area:** Input Validation / Code Injection

**Why it matters:** Jinja2's default `Environment` allows arbitrary Python expressions. Even with only primitive values in the render context, a template can traverse Python's object hierarchy via `__class__.__mro__.__subclasses__()` to reach `os`, `subprocess`, or `builtins`. The choice of Jinja2 over arbitrary Python is correct; sandboxing is the missing piece.

**Recommendation:** Switch to `jinja2.SandboxedEnvironment`, which blocks access to unsafe attributes like `__class__`, `__mro__`, and `__subclasses__()`. Also add a blocklist validation step during manifest ingestion that rejects templates containing suspicious patterns. Consider rendering templates in an isolated subprocess or container as defense in depth.

---

### 2. What authorization gates the manifest refresh API?

**Area:** Authorization

**Why it matters:** The API that triggers re-ingestion of a custom connector runtime's manifest should be restricted to users with admin-level access to that specific deployment. Without proper authorization, any authenticated user could trigger manifest refreshes for any deployment, potentially disrupting other integrations.

**Recommendation:** Confirm that deployment-level authorization is enforced on the manifest refresh mutation. Add an integration test covering this boundary.

---

### 3. How is object storage access controlled for the template bucket?

**Area:** Secrets Management / Infrastructure

**Why it matters:** Templates are loaded from object storage at runtime with no checksum or signature validation. If a template is modified in storage — by a compromised service or a misconfiguration — the backend will render the tampered template. Indefinite process-lifetime caching means a tampered template persists until process restart.

**Recommendation:** Create a dedicated storage bucket for custom templates. Restrict write access to the manifest ingestion service's IAM role only. Store a SHA-256 hash of each template and validate it on load. Use a TTL-based cache (e.g., 1 hour) instead of indefinite caching so template updates can propagate without restarts. Enable versioning and access logging on the bucket.

---

### 4. How is multi-tenancy enforced for custom connector definitions?

**Area:** Data Isolation / Multi-Tenancy

**Why it matters:** If the ORM layer that resolves custom connector definitions is not tenant-scoped, it could return another account's custom definitions. This is particularly subtle in async/Lambda code paths where the tenant context may not be automatically set by HTTP middleware.

**Recommendation:** Custom connector definition records must use a tenant-aware ORM manager that filters as `Q(shared=True) | Q(account=current_account)`. All async code paths that query custom definitions must explicitly set the tenant context before any ORM queries. Add integration tests that verify a connector definition from Account A is invisible to Account B.

---

### 5. What prevents supply chain attacks on the public connector runtime repository?

**Area:** Third-Party / Supply Chain

**Why it matters:** Dependencies pinned to mutable Git tags (e.g., `@v0.0.2`) can be silently updated — anyone with write access to the dependency repo can move the tag to a different commit without changing the pin. If the connector runtime repo is published under a copyleft license (e.g., GPL v3) while depending on proprietary-licensed libraries, this creates a license conflict that must be resolved before publishing.

**Recommendation:** Pin all dependencies to immutable commit hashes, not mutable Git tags. Publish internal dependency packages to a private registry. Resolve any license compatibility questions with legal before publishing the repo. Document whether customer forks should remain private when they contain environment-specific configuration.

---

## Incident Response Scenarios

**Scenario:** Template injection via a malicious customer template
- **Detection:** Anomalous process spawning, unexpected network connections, or `SandboxedEnvironment` security exceptions (if sandboxing is implemented)
- **Blast radius:** Monolith infrastructure; potential for credential exposure or data exfiltration
- **Mitigation:** Remove template from object storage, invalidate cache (process restart), disable the connector definition record

**Scenario:** Custom integration causes pipeline throughput incident (ingests millions of unexpected assets)
- **Detection:** Per-connector metrics and queue lag alarms
- **Blast radius:** Shared queue capacity and downstream processing workers
- **Mitigation:** Kill switch API to disable jobs for a specific connector definition ID; rate-limit manifest refresh API

**Scenario:** SSRF via crafted result location URL in agent response
- **Detection:** Backend access logs showing requests to non-cloud-storage domains
- **Blast radius:** Internal platform services accessible from the backend service network
- **Mitigation:** Validate `result_location` URLs against an allowlist of trusted domains before following them; block the offending connector deployment

**Scenario:** Cross-tenant data leak via unscoped connector definition query
- **Detection:** Customer support ticket (no automated alert without per-query tenant logging)
- **Blast radius:** Exposure of another customer's custom integration configuration
- **Mitigation:** Identify and fix the unscoped query; audit access logs; notify affected accounts

---

## Compliance Considerations

**Compliance scope expansion:** New message queues, object storage buckets, Lambda functions, and processing services are new infrastructure components that process customer data. These must be included in compliance audit scope (SOC 2, ISO 27001, etc.) and provisioned via auditable IaC — not manually created.

**Data processing agreements:** Customer-authored templates are stored on your infrastructure and executed on your backend. Some customers may interpret template storage as "hosting customer code," which is a different relationship than "processing customer metadata." The DPA should be reviewed to confirm it covers this flow.

**Data residency:** If the platform operates in multiple regions, the template storage bucket and message queues must be co-located with the rest of the customer's data. Confirm the template bucket is provisioned per-region, not as a single global bucket.

---

## Gaps Summary

- **Jinja2 sandboxing** — switch to `SandboxedEnvironment` before templates can execute in production
- **Manifest content validation** — validate payload size, schema, and S3 bucket/prefix against expected patterns during ingestion
- **Connector response safety** — enforce response size limits server-side; validate `result_location` URLs; add decompression size limits for gzip responses
- **Health check trust** — do not use customer-modified runtime health check responses for version gating; use the capabilities manifest instead
- **Kill switch** — implement a per-connector disable mechanism before launch; needed for effective incident containment
- **Customer documentation** — hardening guide for connector runtime deployment (TLS, non-root containers, secrets injection) and template authoring guidelines must be drafted before partner onboarding
- **License review** — resolve license compatibility before publishing the public connector runtime repository

---

## Team Question Responses

**Q:** What concerns do you have for customer-authored Jinja templates being rendered on the backend?

**A:** Use `SandboxedEnvironment` instead of `Environment`. Store templates in object storage (not the database) to separate rendering from data — this design already does this correctly. Add template size limits and rendering timeouts. Log all template renders with account context for audit. The primitive-only render context is a good practice but is not a security boundary against SSTI on its own.

**Q:** What additional security measures should we take to avoid code injection?

**A:** (1) `SandboxedEnvironment`, (2) blocklist validation on ingestion rejecting `__class__`, `__mro__`, `__subclasses__`, `__globals__`, `__builtins__`, `import`, (3) render in an isolated subprocess with no network access, (4) add a canary check that renders a known-safe template on a schedule and alerts if the output changes.

**Q:** Are there vulnerabilities if customers change how the connector runtime responds to health checks?

**A:** Yes — health check responses are written directly to the runtime DB record with no validation. A modified connector runtime could spoof its version number to bypass feature gates, report false upgrade capability, or return arbitrary data that gets displayed in the UI. Recommendation: do not use health check version numbers for feature gating on customer-modified runtimes. Use the capabilities manifest (already part of this design) for feature gating instead.

---

*Generated by the SDD Security Review workflow. See the [review guides](../../guides/) for methodology.*
