# Architecture Walkthrough Questions

Use these questions when conducting an architecture walkthrough with a development team. The goal is to understand the system holistically before diving into specific security concerns.

---

## Opening Questions

Start with context-setting questions to understand the big picture:

1. **What problem does this application solve?**
   - Who requested it and why?
   - What's the business value?

2. **Who are the users?**
   - Internal teams only? Which ones?
   - External users? Customers?
   - What user personas will leverage this?

3. **What's the current state?**
   - Is this greenfield or modifying existing systems?
   - How long has it been in development?
   - Is it in production already?

---

## Architecture & Design

### System Overview

4. **Can you walk me through the architecture at a high level?**
   - What are the main components?
   - How do they interact?
   - Draw it on a whiteboard/diagram if possible

5. **What's the tech stack?**
   - Frontend framework
   - Backend language/framework
   - Database(s)
   - Infrastructure (AWS services, etc.)

6. **Where does this run?**
   - AWS account? Which one?
   - Lambda, ECS, EC2, etc.?
   - How is it deployed?

### Data Flow

7. **Walk me through a typical user workflow**
   - What happens when a user does [primary action]?
   - What data is created/modified/read?
   - Where does that data go?

8. **What data does this application handle?**
   - What types of data are collected?
   - Is any of it sensitive (PII, credentials, financial)?
   - Where does the data come from? Where does it go?

9. **How is data stored?**
   - What databases/storage systems?
   - How long is data retained?
   - Is there any data that should be encrypted at rest?

---

## Authentication & Authorization

### Authentication

10. **How do users authenticate?**
    - SSO (Okta)?
    - API keys?
    - Other mechanisms?

11. **Are there service accounts or machine-to-machine auth?**
    - What authenticates to what?
    - How are those credentials managed?

### Authorization

12. **What can different users do?**
    - Are there different roles or permission levels?
    - How is authorization enforced?
    - Can users access each other's data?

13. **How would you prevent [persona] from doing something they shouldn't?**
    - Example: "How would you prevent a regular user from accessing admin functions?"

---

## Security Controls

### Input/Output

14. **How is user input validated?**
    - Where does validation happen?
    - What happens when validation fails?

15. **How do you prevent common vulnerabilities?**
    - SQL injection?
    - XSS?
    - CSRF?

### Secrets & Configuration

16. **Where are secrets stored?**
    - API keys, database passwords, etc.
    - Are they in code, config files, or a secret manager?

17. **How do you manage configuration across environments?**
    - Dev vs staging vs prod
    - Is production data used in non-production?

### Dependencies

18. **What third-party libraries/services do you use?**
    - How do you track dependencies?
    - How do you handle vulnerability updates?

---

## Integration & External Services

19. **What external services does this integrate with?**
    - Third-party APIs?
    - Internal platform services?
    - How is auth handled for each?

20. **If this calls external APIs, what data is sent?**
    - Is sensitive data shared externally?
    - What happens if the external service is down?

21. **Does anything call into this service?**
    - Webhooks?
    - API consumers?
    - How are incoming requests authenticated?

---

## Operational Concerns

### Logging & Monitoring

22. **What gets logged?**
    - User actions?
    - Errors?
    - Security events (login, access denied, etc.)?

23. **How would you know if something went wrong?**
    - Monitoring in place?
    - Alerting configured?

24. **How would you detect misuse or a security incident?**
    - What would suspicious activity look like?
    - Can you trace who did what?

### Incident Response

25. **What's your plan if there's a security issue?**
    - Who gets notified?
    - How do you roll back changes?
    - Can you revoke access quickly?

---

## Persona-Based Scenarios

These questions help identify security concerns through user stories:

26. **What would a typical user persona do with this?**
    - Typical workflow
    - Data they'd access

27. **What could Eric do that would cause a security concern?**
    - Intentional misuse scenarios
    - Accidental data exposure
    - Access to things they shouldn't have

28. **What if someone got Eric's credentials?**
    - What could an attacker do?
    - How would you detect it?
    - How would you contain it?

---

## Documentation & Compliance

29. **What documentation exists?**
    - Architecture diagrams?
    - API documentation?
    - Runbooks?

30. **Are there compliance requirements?**
    - SOC 2 controls that apply?
    - Data residency requirements?
    - Audit logging needs?

---

## Closing Questions

31. **What are you most concerned about from a security perspective?**
    - Often the team knows where the gaps are

32. **What would you like help with?**
    - Documentation?
    - Specific security review?
    - General guidance?

33. **What's the timeline?**
    - When does this need to be reviewed by?
    - Any hard deadlines?

---

## Post-Walkthrough Actions

After the walkthrough, document:

1. **Key Findings**
   - Architecture summary
   - Data flow understanding
   - Identified risks

2. **Gaps Identified**
   - Missing documentation
   - Security controls needed
   - Open questions

3. **Recommendations**
   - Prioritized list of actions
   - Who's responsible for what
   - Timeline for follow-up

4. **Follow-up Items**
   - Schedule follow-up review if needed
   - Assign action items
   - Set next meeting date

---

## Tips for Effective Walkthroughs

### For the Reviewer

- Listen more than you talk in the first half
- Draw diagrams as you go to confirm understanding
- Ask "how" questions rather than "did you" questions
- Focus on understanding before identifying problems
- Take notes on follow-up items

### For the Team Being Reviewed

- Have someone who knows the architecture present
- Screen share if remote (show code, diagrams, etc.)
- Be honest about known gaps - we're here to help
- Ask questions if you're unsure about security requirements
- Follow up on action items promptly

---

## Related Resources

- [Self-Service Security Checklist](self-service-checklist.md) - Pre-review validation
- [Claude Prompting Guide](claude-prompting-guide.md) - AI-assisted documentation
- [Security Architecture Review Template](../security-architecture-review-template.md) - Full review template
