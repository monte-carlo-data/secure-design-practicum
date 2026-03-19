# Platform Architecture Context (Template)

Copy this file to your repository as `docs/platform_context.md` and fill in the details for your platform. This file is passed to the SDD Security Review action as the `platform_context_path` input. Providing accurate platform context significantly improves review quality — the reviewer uses it to flag design decisions that conflict with your established patterns rather than giving generic advice.

---

## Multi-Tenancy Model

Describe how your platform isolates customer/tenant data:

- How is tenant data scoped? (e.g., tenant ID on every record, separate databases, row-level security)
- What is the base model or pattern that enforces tenant isolation?
- How are API requests scoped to a single tenant?

Example:
```
- All customer data is scoped by a TenantID field on every database record
- API requests are authenticated and the tenant is derived from the JWT claims
- Database queries are automatically filtered by tenant via a base ORM mixin
- Cross-tenant data access must be flagged as a critical risk in any design
```

---

## IAM & Authentication

Describe how your platform handles identity and access:

- How do users authenticate? (SSO, API keys, OAuth, etc.)
- How do services authenticate to each other? (service accounts, signed tokens, mTLS, etc.)
- How is cross-account or cross-environment access managed?

Example:
```
- Users authenticate via Okta SSO (SAML/OIDC)
- Service-to-service calls use signed JWT tokens with short expiry
- Cross-account AWS access uses IAM role assumption with external IDs
- Secrets are stored in AWS Secrets Manager — never in code or config files
```

---

## Data Pipeline

Describe how data moves through your platform:

- What are the major data movement mechanisms? (message queues, streams, ETL, etc.)
- Where is data stored at rest? (databases, object storage, caches)
- What processing happens between ingestion and storage?

Example:
```
- Event streams use Kafka topics for async processing
- S3 is used for artifact and export storage (encrypted at rest)
- Lambda functions process events from the queue
```

---

## Existing Security Controls

Describe the security controls already in place so the reviewer knows what's covered:

- API authentication and authorization patterns
- Secret storage (e.g., AWS Secrets Manager, HashiCorp Vault)
- Monitoring and alerting tools
- Any existing WAF, rate limiting, or API gateway controls

Example:
```
- All API endpoints require a valid session token
- Authorization is enforced at the resolver/controller level on every query
- Secrets are stored in AWS Secrets Manager; no secrets in environment variables or config files
- DataDog is used for metrics and alerting; PagerDuty for on-call
```

---

## Key Repositories

List the main repositories and what they contain:

```
- your-org/backend: Main application server (Python/Django)
- your-org/frontend: Web application (React/TypeScript)
- your-org/infrastructure: Terraform modules for AWS
- your-org/data-pipeline: Event processing workers
```

---

## How to Use This in a Review

When analyzing an SDD, cross-reference the design against these patterns:

- Does it scope all data access through the tenant isolation layer? If not, flag cross-tenant risk.
- Does it introduce new external API surface? If so, flag auth and rate limiting.
- Does it store credentials outside the approved secret manager? Flag secrets management gap.
- Does it add a new data stream or queue? Verify tenant isolation is enforced at the consumer.
- Does it run user-supplied code or queries on your infrastructure? Flag injection risk.
- Does it introduce new IAM roles or cross-account access? Flag for IAM review.
- Does it change or extend the authentication model? Flag as Required involvement.

---

## Known Accepted Risks (Optional)

Optionally list any risks that have been formally accepted so the reviewer doesn't re-raise them:

```
- Rate limiting on public APIs uses a best-effort approach; DDoS mitigation is handled at the CDN layer
- Internal admin endpoints do not enforce MFA (mitigated by VPN requirement)
```
