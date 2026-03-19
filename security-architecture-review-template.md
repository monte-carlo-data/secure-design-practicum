# Security Architecture Review (Template)

## 1. Executive Summary

- Feature Overview: Briefly describe the new feature, its business purpose, and expected impact.
- AI Usage: Summarize any AI/ML components, including their purpose and data flows.
- Risk Rating: Assign an initial risk level (Low/Medium/High) based on data sensitivity, user impact, and AI involvement.

## 2. Feature Description

- Functionality: What does the feature do? Who are the intended users? What user personas will leverage this feature?
- Integration Points: List all integrations (internal and third-party APIs, data sources, etc.).
- AI Components: Detail any AI models, algorithms, or third-party AI services used.

## 3. Data Security

| **Area** | **Review Questions** | **Notes/Findings** |
| --- | --- | --- |
| Data Types | What data is collected, processed, or generated? Is any of it sensitive (PII, PHI, PCI, etc.)? |  |
| Data Flow | How does data move through the system? Are data flow diagrams available? |  |
| Data Storage | Where is data stored? Is it encrypted at rest? |  |
| Data in Transit | Is all data encrypted in transit (TLS/SSL)? |  |
| Data Retention | What are the retention and deletion policies? |  |
| Data Masking | Is sensitive data masked or anonymized, especially in AI training datasets? |  |

## 4. Access Control & Identity Management

- Authentication: Is SSO/MFA enforced for all users and admins?
- Authorization: Are role-based access controls (RBAC) in place?
- API Security: Are APIs protected with authentication and authorization checks?
- AI Model Access: Who can access, modify, or retrain AI models?
- Secrets Management: Are secrets (API keys, database passwords, certificates) stored securely and rotated regularly? What is the rotation schedule and process?

## 5. Application & AI Security

### Application Security

- Vulnerability Management: Has the feature undergone code review, static/dynamic analysis, and penetration testing?
- OWASP Top 10: Are common vulnerabilities (e.g., injection, XSS) mitigated?
- Configuration: Are security settings, ACLs, and IP allow lists properly configured?
- Open Source: Are all open source components tracked and regularly scanned for vulnerabilities?

### AI-Specific Security

- Model Security: Are models protected from adversarial attacks and tampering?
- Model Explainability: Are explainability and transparency measures in place for AI decisions?
- Model Updates: Is there a process for secure model updates and version control?
- Data Poisoning: Are controls in place to prevent malicious data from corrupting AI training?

## 6. Monitoring, Logging, and Incident Response

- Logging: Are all critical actions and AI model interactions logged?
- Monitoring: Is there real-time monitoring for anomalies, especially in AI outputs?
- Alerting: Are alerts configured for suspicious activities?
- Incident Response: Is there a documented plan for responding to breaches, model tampering, or data leaks?

## 7. Compliance & Regulatory

- Certifications: Does the feature and its infrastructure comply with relevant standards (SOC 2, ISO 27001, etc.)?
- Privacy Laws: Are GDPR, CCPA, HIPAA, or other regulations applicable? Is AI use compliant with these laws?
- AI Governance: Is there an AI policy aligned with recognized frameworks?

## 8. Third-Party & Supply Chain Security

- Vendor Assessment: Are all third-party services (including AI APIs) vetted for security practices?
- Access Control: Is vendor access limited to only what is necessary?
- Ongoing Monitoring: Are third-party security postures regularly reviewed?

## 9. User Education & Awareness

- Training: Are users and staff trained on new security risks, especially those related to AI features?
- Documentation: Is security documentation updated and accessible?

## 10. Continuous Improvement

- Security Audits: Are regular audits scheduled for both application and AI components?
- Feedback Loop: Is there a process for incorporating lessons learned from incidents and user feedback?

## Appendix

- Supporting Diagrams: Data flow, architecture, and AI model lifecycle diagrams.
- Penetration Test Reports: Attach or reference recent test results.
- AI Model Cards: Documentation of AI model purpose, data, and limitations.
