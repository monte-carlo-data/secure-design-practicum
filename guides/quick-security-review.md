# Quick Security Review

Think like Security Steve. Answer these 10 questions before shipping your feature.

---

## Understanding Security Through Analogies

Before diving into the questions, here are some mental models to help think about security concepts:

| Concept | Analogy | What It Means |
|---------|---------|---------------|
| **Authentication** | Checking IDs at the door | Proving you are who you claim to be |
| **Authorization** | Hotel room key cards | Being authenticated doesn't mean you can access everything - you only get into your room |
| **Secrets Management** | A safe vs. under the doormat | Where you store keys matters - a vault is better than a sticky note |
| **Logging** | Security cameras | You can't investigate what you didn't record |
| **Input Validation** | TSA screening | Don't trust what's coming in - inspect it before it enters your system |
| **Data Isolation** | Apartment walls | Neighbor A shouldn't see Neighbor B's stuff, even though they're in the same building |
| **Least Privilege** | Need-to-know basis | Give people exactly what they need to do their job, nothing more |
| **Defense in Depth** | Castle with moat, walls, AND guards | Multiple layers of protection, not just one |

Use these analogies when answering the questions below. They can help frame your thinking and explain concepts to others.

---

## The 10 Essential Questions

### 1. What does this feature do, and who uses it?

- One sentence description
- Internal users, customers, or both?
- What type of user persona would use this?

---

### 2. What data does it touch?

- What data is read, written, or processed?
- Is any of it sensitive? (PII, credentials, customer data)
- Where does the data come from? Where does it go?

---

### 3. How do users authenticate?

- SSO? API keys? Something else?
- Are there service accounts or machine-to-machine connections?
- How are those credentials stored?

---

### 4. What can different users do?

- Are there different permission levels?
- Can User A see User B's data?
- How would you prevent someone from doing something they shouldn't?

---

### 5. What external services does this integrate with?

- Third-party APIs? Internal services?
- What data is sent to them?
- How are their credentials managed?

---

### 6. Where are secrets stored?

- API keys, database passwords, tokens
- Are they in code, config files, or a secret manager?
- Can they be rotated without a deploy?

---

### 7. What gets logged?

- User actions? Errors? Security events?
- Do logs contain anything sensitive?
- How would you investigate a problem?

---

### 8. What could a malicious user do?

- If someone got valid credentials, what's the worst they could do?
- Could they access other users' data?
- Could they escalate privileges?

---

### 9. How would you know if something went wrong?

- What does suspicious activity look like?
- Would you notice unauthorized access?
- Can you trace who did what?

---

### 10. What are you worried about?

- What keeps you up at night about this feature?
- What would you want a security reviewer to look at?
- What's the riskiest part?

---

## Security Steve Mindset

When answering these questions, think like an adversary:

> "If I wanted to abuse this feature, how would I do it?"

Consider:

- **Accidental exposure** - Could someone accidentally leak data?
- **Intentional misuse** - Could a malicious insider abuse this?
- **Credential compromise** - What happens if someone's account is stolen?
- **Data leakage** - Could sensitive data end up somewhere it shouldn't?

---

## What's Next?

**If you can answer all 10 questions confidently:**
You're ready for a security review. Run the [SDD Review Action](../README.md) on your Notion SDD, or use the [Quick Review Prompt](../prompts/quick-review-prompt.md) to document your answers with Claude's help.

**If you're unsure about some answers:**
That's normal. Note what you don't know and bring those questions to your security review.

**If you found gaps:**
Great - that's the point. Fix what you can, document what needs discussion.

---

## Related Resources

- [Quick Review Prompt](../prompts/quick-review-prompt.md) - AI-assisted documentation
- [Self-Service Security Checklist](self-service-checklist.md) - Detailed validation checklist
- [Architecture Walkthrough Questions](architecture-walkthrough-questions.md) - Full question set for formal reviews
