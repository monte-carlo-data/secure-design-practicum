# Linear Executive Summary Prompt

Replace `{TICKET_ID}` with the Linear ticket identifier (e.g., SEC-844).

---

Using the Linear MCP tools, provide an executive summary for Linear issue **{TICKET_ID}**:

1. Parent ticket: title, status, priority, assignee, expected completion date
2. Subtask metrics: total, completed (count + %), in progress, todo, canceled
3. Completed subtasks grouped by category (Infrastructure, Security Tooling, Access Control, Configuration, Integration)
4. Outstanding work: list incomplete subtasks with ticket ID, title, assignee, status
5. Recent activity: subtasks completed in last 7 days
6. Key highlights: major milestones, critical items completed, risks/concerns
7. Next steps: immediate priorities, estimated timeline

Format as Slack-ready output:

```
📊 Executive Summary: {TICKET_TITLE}
Status: {STATUS} | Priority: {PRIORITY} | Assignee: {ASSIGNEE}
Expected: {DATE}

Progress: {X}/{TOTAL} subtasks ({PERCENTAGE}%)

✅ Completed ({COUNT})
[grouped by category with ticket IDs]

🔄 In Progress ({COUNT})
[list with assignees]

📋 Todo ({COUNT})
[list with assignees]

⚠️ Blockers: [if any]

📈 Recent Wins (7d): [list]

🎯 Next Steps: [list]

*Updated: {TIMESTAMP}*
```
