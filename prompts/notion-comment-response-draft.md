# SDD Notion Comment Pull + Response Draft

Copy/paste everything below into Codex or Claude, then fill the placeholders.

---

Using Notion MCP, pull review-relevant comments from this SDD page.

Inputs:
- SDD URL: `<PASTE_NOTION_SDD_URL>`
- Target reviewer name: `<PASTE_NAME>` (optional; example: `Steven Carlson`)
- Review report URL: `<PASTE_REVIEW_MD_URL>`

Tasks:
1. Fetch all page discussions/comments, including resolved and inline comments.
2. If target reviewer name is provided, include only comments that mention that person.
   - Match both plain-text mentions and `mention-user` tags.
3. Resolve user IDs to display names where possible.
4. Return markdown only using this structure:

```md
# <SDD Title>
- Source link: <canonical notion page URL>
- Target reviewer: <name or N/A>
- Total matching comments: <count>

## Matching comments
- <UTC timestamp> | Author: <name> | Context: <discussion text-context>
  URL: <comment URL>
  Comment: <full comment text with @Name mentions resolved when possible>

## Draft responses (local only, not posted to Notion)
### Response for `<context 1>`
`<professional response grounded in the review findings>`

### Response for `<context 2>`
`<professional response grounded in the review findings>`
```

5. Add a professional reference to the full report in each draft response, for example:
   - `For full details and evidence, please see: <PASTE_REVIEW_MD_URL>`

Constraints:
- Do NOT post, edit, or reply to comments in Notion.
- Do NOT modify Notion content.
- Keep exact comment URLs and UTC timestamps.
- Output markdown only.
