# Claude Prompting Guide for Architecture Reviews

This guide helps teams use Claude effectively for security architecture reviews and documentation. The goal is to enable self-sufficiency in evaluating and documenting your own work.

## Getting Started

### Setting Context

Always start by giving Claude context about your project. The more context you provide, the better the output.

**Initial Context Prompt:**
```
I'm working on [project name], an internal application that [brief description].

Tech stack:
- Frontend: [e.g., React, Vue]
- Backend: [e.g., Python/FastAPI, Node.js]
- Database: [e.g., PostgreSQL, DynamoDB]
- Infrastructure: [e.g., AWS Lambda, ECS, Kubernetes]
- Authentication: [e.g., Okta SSO, Cognito]

The app is used by [target users] to [primary use case].
```

---

## Architecture Documentation Prompts

### 1. Generate Architecture Overview

```
Based on the following code structure and configuration, help me create an architecture overview document:

[Paste relevant code snippets, config files, or describe components]

Please include:
1. High-level system diagram description
2. Component responsibilities
3. Data flow between components
4. External dependencies and integrations
```

### 2. Document Data Flows

```
Help me document the data flow for [specific feature/process].

Here's what I know:
- Entry point: [where data enters]
- Processing steps: [what happens to the data]
- Storage: [where data is stored]
- Output: [where data goes]

Please create a data flow diagram description and identify:
1. What data is collected at each step
2. Any sensitive data (PII, credentials, etc.)
3. Data transformations
4. Potential security considerations
```

### 3. Create API Documentation

```
I have the following API endpoints:

[Paste API routes, handlers, or OpenAPI spec]

Please help me document:
1. Authentication requirements for each endpoint
2. Input validation being performed
3. Error handling approach
4. Any security headers or controls
```

---

## Security Review Prompts

### 4. Identify Security Gaps

```
Review this code/architecture for security concerns:

[Paste code or architecture description]

Focus on:
1. OWASP Top 10 vulnerabilities
2. Authentication and authorization gaps
3. Data exposure risks
4. Input validation issues
5. Secrets management
```

### 5. Threat Modeling

```
Help me identify potential threats for this feature:

Feature: [description]
Users: [who uses it]
Data handled: [what data is involved]
External integrations: [third-party services]

Please provide:
1. Potential threat actors and their motivations
2. Attack vectors to consider
3. Assets at risk
4. Recommended mitigations
```

### 6. Review Authentication Implementation

```
Review our authentication approach:

[Describe or paste auth implementation]

Questions to answer:
1. Is the authentication mechanism appropriate for our use case?
2. Are there any token handling vulnerabilities?
3. Is session management secure?
4. Are there proper access controls in place?
```

---

## Self-Review Prompts

### 7. Pre-Review Checklist Generation

```
I'm about to submit [feature/project] for security review. Help me create a self-assessment checklist based on:

- Type of application: [internal tool, customer-facing, etc.]
- Data sensitivity: [PII, credentials, business data, etc.]
- Integration points: [list external services]
- User access model: [who can access what]

Generate questions I should answer before the security review.
```

### 8. Documentation Gap Analysis

```
Here's my current documentation for [project]:

[Paste or describe existing docs]

Compare this against security documentation best practices and identify:
1. Missing sections
2. Areas needing more detail
3. Unclear or ambiguous descriptions
4. Security-relevant information that should be added
```

---

## Best Practices for Prompting

### Do's

1. **Be Specific** - Include actual code, configs, and architecture details
2. **Provide Context** - Explain the business purpose and user base
3. **Ask Follow-ups** - Drill down on specific areas of concern
4. **Iterate** - Refine prompts based on initial responses
5. **Verify** - Cross-check Claude's suggestions against your actual implementation

### Don'ts

1. **Don't Share Secrets** - Never paste actual API keys, passwords, or credentials
2. **Don't Assume Completeness** - Claude may miss context-specific issues
3. **Don't Skip Human Review** - Use Claude as a starting point, not final authority
4. **Don't Ignore Red Flags** - If Claude identifies a concern, investigate it

---

## Example Workflow

### Step 1: Initial Assessment
```
I'm building an internal tool called "Transparent Trust" for [purpose].
Here's the basic architecture: [description]
What security considerations should I be thinking about?
```

### Step 2: Deep Dive on Specific Areas
```
Let's focus on the authentication piece. Here's how it works:
[details]
What are the potential vulnerabilities?
```

### Step 3: Generate Documentation
```
Based on our discussion, help me create a security architecture document
following this template: [paste template sections]
```

### Step 4: Review and Refine
```
Here's the draft documentation. What's missing or unclear from a
security reviewer's perspective?
```

---

## Common Pitfalls to Avoid

| Pitfall | Better Approach |
|---------|-----------------|
| "Review my app for security" | "Review this specific authentication flow for vulnerabilities" |
| Pasting entire codebase | Share relevant modules with context |
| Asking yes/no questions | Ask "how" and "what" questions |
| Skipping context | Always explain the business purpose |
| One-shot prompting | Iterative conversation with follow-ups |

---

## Resources

- [Security Architecture Review Template](../security-architecture-review-template.md) - Full template for formal reviews
- [Self-Service Security Checklist](self-service-checklist.md) - Quick validation checklist
- [Architecture Walkthrough Questions](architecture-walkthrough-questions.md) - Questions for review meetings
