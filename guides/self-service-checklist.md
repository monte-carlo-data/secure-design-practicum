# Self-Service Security Checklist

Use this checklist to validate your application before requesting a formal security review. This helps identify common issues early and makes the review process more efficient.

---

## Pre-Review Information Gathering

Before starting, gather the following information about your application:

- [ ] Application name and purpose
- [ ] Target users (internal teams, customers, etc.)
- [ ] Tech stack (frontend, backend, database, infrastructure)
- [ ] Data types handled (what data does the app process?)
- [ ] External integrations (third-party APIs, services)
- [ ] Repository location(s)

---

## 1. Authentication & Access Control

### Authentication
- [ ] Users authenticate via approved method (Okta SSO, etc.)
- [ ] No hardcoded credentials in code
- [ ] Service accounts use API keys/tokens (not user credentials)
- [ ] Session tokens have appropriate expiration

### Authorization
- [ ] Users can only access data they're authorized to see
- [ ] Admin functions are restricted to appropriate roles
- [ ] API endpoints check authorization before processing
- [ ] No privilege escalation paths exist

### Questions to Answer
- How do users authenticate?
- What roles/permissions exist?
- How is authorization enforced?

---

## 2. Data Security

### Data Classification
- [ ] I know what data types the application handles
- [ ] Sensitive data (PII, credentials, etc.) is identified
- [ ] Data retention requirements are defined

### Data Protection
- [ ] Sensitive data is encrypted at rest
- [ ] All data in transit uses TLS/HTTPS
- [ ] Database connections are encrypted
- [ ] Logs don't contain sensitive data (passwords, tokens, PII)

### Data Flow
- [ ] I can describe how data flows through the system
- [ ] Data flow diagram exists or can be created
- [ ] External data sharing is documented

### Questions to Answer
- What sensitive data does the app handle?
- Where is data stored?
- Who/what can access the data?

---

## 3. Application Security

### Input Validation
- [ ] All user input is validated before processing
- [ ] SQL queries use parameterized statements (no string concatenation)
- [ ] File uploads are validated and restricted
- [ ] API inputs are validated against expected types/formats

### Output Encoding
- [ ] User-supplied data is encoded before display (XSS prevention)
- [ ] API responses don't leak sensitive information
- [ ] Error messages don't expose internal details

### Dependencies
- [ ] Dependencies are tracked (package.json, requirements.txt, etc.)
- [ ] No known vulnerable dependencies (check with `npm audit`, etc.)
- [ ] Dependencies are from trusted sources

### Questions to Answer
- How is user input validated?
- What happens when validation fails?
- When were dependencies last updated?

---

## 4. Infrastructure & Configuration

### Environment Security
- [ ] Production, staging, and development are separated
- [ ] Production data isn't used in non-production environments
- [ ] Environment-specific configs are properly managed

### Secrets Management
- [ ] Secrets stored in approved secret manager (not in code/config files)
- [ ] Secrets are not logged or exposed in error messages
- [ ] Secret rotation process exists

### Network Security
- [ ] Only necessary ports/endpoints are exposed
- [ ] Internal services are not publicly accessible
- [ ] API endpoints use authentication

### Questions to Answer
- Where are secrets stored?
- What's publicly accessible?
- How are environments separated?

---

## 5. Logging & Monitoring

### Logging
- [ ] Security-relevant events are logged (login, access, changes)
- [ ] Logs don't contain sensitive data
- [ ] Logs are sent to centralized logging system
- [ ] Log retention meets requirements

### Monitoring & Alerting
- [ ] Errors and exceptions are monitored
- [ ] Unusual activity can be detected
- [ ] On-call/alerting is configured for critical issues

### Questions to Answer
- What events are logged?
- How long are logs retained?
- How would you detect a security incident?

---

## 6. Third-Party Integrations

### Vendor Security
- [ ] Third-party services have been evaluated for security
- [ ] Data sharing with third parties is documented
- [ ] Third-party access is limited to minimum necessary

### API Security
- [ ] Third-party API keys are stored securely
- [ ] Webhook endpoints validate incoming requests
- [ ] Rate limiting is implemented where appropriate

### Questions to Answer
- What third-party services does the app use?
- What data is shared with them?
- How are their credentials managed?

---

## 7. Documentation

### Required Documentation
- [ ] Architecture overview exists
- [ ] Data flow is documented
- [ ] API endpoints are documented
- [ ] Deployment process is documented

### Security-Specific
- [ ] Security controls are documented
- [ ] Access control model is documented
- [ ] Incident response process is defined

---

## Risk Assessment Summary

After completing the checklist, assess your application's risk level:

| Risk Factor | Low | Medium | High |
|-------------|-----|--------|------|
| Data Sensitivity | Public data only | Internal business data | PII, credentials, financial |
| User Base | Internal team only | All employees | Customers/external |
| External Integrations | None | Read-only access | Write access to external systems |
| Internet Exposure | Internal only | VPN required | Publicly accessible |

---

## Next Steps

### If you checked all boxes:
Run the [SDD Review Action](../automation/sdd-review.md) on your Notion SDD. The output includes a **Security Team Involvement** recommendation based on a NIST 800-30 risk model:

- **Required** — Post the SDD link in your security team channel before starting implementation
- **Recommended** — Consider posting in your security team channel for a lightweight async review
- **Not Required** — Proceed with implementation; address the security questions during code review

### If you have unchecked items:
1. Address the gaps you can fix independently
2. Document items that need discussion or guidance
3. Post in your security team channel to discuss remaining concerns

### Questions or need help?
- Review the [Claude Prompting Guide](claude-prompting-guide.md) for self-service assistance
- Post in your security team channel for a walkthrough
- Check the [full Security Architecture Review template](../security-architecture-review-template.md) for comprehensive requirements
