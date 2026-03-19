#!/usr/bin/env python3
"""
PR Security Review Script

Fetches a GitHub PR diff and generates a structured security review focused on
what new risk the code changes introduce. Optionally accepts a Notion SDD URL
as design context.

Outputs:
  pr_review_output.json        — structured review JSON
  pr_review_questions.md       — formatted markdown review
  pr_review_architecture.drawio — draw.io diagram (if generated)

Env vars:
  ANTHROPIC_API_KEY    — required
  GITHUB_TOKEN         — required (for fetching PR diff)
  PR_REVIEW_URL        — required (https://github.com/org/repo/pull/N)
  NOTION_SDD_URL       — optional; if set, NOTION_TOKEN is also required
  NOTION_TOKEN         — required only when NOTION_SDD_URL is set
  REPO_FULL_NAME       — set by GitHub Actions for PR comment posting
  PR_NUMBER            — set by GitHub Actions for PR comment posting
  RISK_REGISTER_REPO   — optional; override default your-org/risk-register
"""

import os
import re
import sys
import json
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic
import requests


# Security-relevant file path keywords (higher score = more important to include)
SECURITY_KEYWORDS = [
    "auth", "authn", "authz", "permission", "policy", "privilege",
    "security", "credential", "secret", "token", "key", "iam",
    "rbac", "acl", "encrypt", "decrypt", "crypto", "hash", "sign",
    "middleware", "guard", "interceptor", "validator", "sanitiz",
    "inject", "xss", "csrf", "cors",
    "config", "settings", "env",
    "terraform", "tf", "cloudformation", "cdk", "helm",
    "dockerfile", "docker-compose",
    "migration", "schema",
    "sql", "query", "database",
    "network", "firewall", "vpc", "sg", "ingress", "egress",
    "role", "policy", "trust",
]

# Extensions we care about for security review
SECURITY_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".rb", ".tf", ".hcl", ".yml", ".yaml", ".json", ".toml",
    ".sql", ".graphql", ".gql", ".proto", ".sh",
    "dockerfile",
}

# Total diff context budget (chars)
MAX_DIFF_CONTEXT = 30_000

# Per-file diff cap (chars)
MAX_FILE_DIFF = 6_000


def parse_pr_url(url: str):
    """Parse a GitHub PR URL and return (repo_full_name, pr_number)."""
    url = url.strip().rstrip("/")
    match = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
    if not match:
        print(f"Error: Could not parse GitHub PR URL: {url}")
        print("  Expected format: https://github.com/org/repo/pull/N")
        sys.exit(1)
    return match.group(1), int(match.group(2))


def github_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def fetch_pr_metadata(repo: str, pr_number: int, token: str) -> Dict[str, Any]:
    """Fetch PR title, description, author, base/head branches."""
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
        headers=github_headers(token),
        timeout=30,
    )
    if resp.status_code == 404:
        print(f"Error: PR not found: {repo}#{pr_number}")
        print("  Check the PR URL and ensure GITHUB_TOKEN has access to this repo.")
        sys.exit(1)
    if resp.status_code == 401:
        print("Error: GitHub token is invalid or lacks access to this repo (401).")
        sys.exit(1)
    if resp.status_code != 200:
        print(f"Error: Could not fetch PR metadata: HTTP {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        sys.exit(1)
    return resp.json()


def fetch_pr_files(repo: str, pr_number: int, token: str) -> List[Dict[str, Any]]:
    """Fetch all changed files for a PR (handles pagination)."""
    files = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files",
            headers=github_headers(token),
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"Warning: Could not fetch PR files page {page}: HTTP {resp.status_code}")
            break
        batch = resp.json()
        if not batch:
            break
        files.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return files


def score_file(filename: str, patch: str) -> int:
    """Score a changed file for security relevance. Higher = more important."""
    score = 0
    lower = filename.lower()
    name = Path(filename).name.lower()
    ext = Path(filename).suffix.lower()

    # Extension relevance
    if ext in SECURITY_EXTENSIONS or name in {"dockerfile", "makefile"}:
        score += 5

    # Keyword matches in path
    for kw in SECURITY_KEYWORDS:
        if kw in lower:
            score += 8
            break  # count once per file

    # Patch content hints
    if patch:
        patch_lower = patch.lower()
        security_patch_terms = [
            "password", "secret", "token", "key", "credential",
            "exec(", "eval(", "subprocess", "os.system", "shell=true",
            "sql", "query", "render(", "innerhtml", "dangerouslysetinnerhtml",
            "pickle", "deserializ", "yaml.load", "unserialize",
            "open(", "os.path",
            "requests.get", "urllib", "fetch(",
            "iam", "role", "policy", "assume", "trust",
        ]
        for term in security_patch_terms:
            if term in patch_lower:
                score += 3

    return score


def build_diff_context(files: List[Dict[str, Any]]):
    """
    Select and format the most security-relevant file diffs.

    Returns (diff_text, list_of_all_filenames).
    """
    if not files:
        return "No changed files found in this PR.", []

    all_filenames = [f["filename"] for f in files]

    # Score and sort files
    scored = []
    for f in files:
        filename = f.get("filename", "")
        status = f.get("status", "")
        patch = f.get("patch", "") or ""
        additions = f.get("additions", 0)
        deletions = f.get("deletions", 0)
        score = score_file(filename, patch)
        scored.append((score, filename, status, patch, additions, deletions))

    scored.sort(key=lambda x: -x[0])

    # Build diff text within budget
    total_chars = 0
    included = []
    omitted = []

    for score, filename, status, patch, additions, deletions in scored:
        if not patch:
            included.append(f"### {filename}\n_Status: {status} | No text diff available_\n")
            continue

        entry_header = f"### {filename}\n_Status: {status} | +{additions} -{deletions} lines_\n\n```diff\n"
        entry_patch = patch[:MAX_FILE_DIFF]
        if len(patch) > MAX_FILE_DIFF:
            entry_patch += f"\n... (patch truncated at {MAX_FILE_DIFF} chars; full diff available in PR)"
        entry = entry_header + entry_patch + "\n```\n"

        if total_chars + len(entry) > MAX_DIFF_CONTEXT and included:
            omitted.append(filename)
        else:
            included.append(entry)
            total_chars += len(entry)

    diff_parts = [f"## Changed Files ({len(files)} total, {len(included)} shown)\n"]
    diff_parts.extend(included)

    if omitted:
        omitted_preview = ", ".join(omitted[:20])
        more = " and more..." if len(omitted) > 20 else ""
        diff_parts.append(
            f"\n_Note: {len(omitted)} additional files were omitted due to context budget. "
            f"Omitted: {omitted_preview}{more}_\n"
        )

    return "\n".join(diff_parts), all_filenames


class RiskRegisterClient:
    """Fetches accepted risks from the risk register repo."""

    DEFAULT_REPO = "your-org/risk-register"
    DEFAULT_PATH = "risk-register.json"

    def __init__(self, github_token: str, repo: Optional[str] = None):
        self.github_token = github_token
        self.repo = repo or self.DEFAULT_REPO
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def fetch_accepted_risks(self) -> List[Dict[str, Any]]:
        """Fetch risks where Risk Treatment is Accept. Returns [] if unavailable."""
        try:
            url = (
                f"https://api.github.com/repos/{self.repo}"
                f"/contents/{self.DEFAULT_PATH}"
            )
            resp = requests.get(url, headers=self.headers, timeout=30)
            if resp.status_code == 404:
                print(f"Risk register not found at {self.repo}/{self.DEFAULT_PATH} — skipping")
                return []
            if resp.status_code == 403:
                print(f"No access to risk register at {self.repo} — skipping")
                return []
            if resp.status_code != 200:
                print(f"Warning: Could not fetch risk register: HTTP {resp.status_code}")
                return []

            data = resp.json()
            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8")
                register = json.loads(content)
                if isinstance(register, dict):
                    risks = register.get("risks", [])
                elif isinstance(register, list):
                    risks = register
                else:
                    print("Warning: Unexpected risk register format — skipping")
                    return []
                accepted = [r for r in risks if r.get("Risk Treatment") == "Accept"]
                print(f"Loaded {len(accepted)} accepted risks from risk register")
                return accepted
            return []
        except json.JSONDecodeError:
            print("Warning: Could not parse risk register JSON — skipping")
            return []
        except Exception as e:
            print(f"Warning: Error fetching risk register: {e}")
            return []

    def format_for_prompt(self, risks: List[Dict[str, Any]]) -> Optional[str]:
        """Format accepted risks for prompt injection. Returns None if empty."""
        if not risks:
            return None
        lines = []
        for risk in risks:
            rid = risk.get("Risk ID", "???")
            scenario = risk.get("Risk Scenario", "Untitled")
            desc = risk.get("Risk Description", "")
            category = risk.get("High Level Risk", "")
            score = risk.get("Residual Risk Score", "")
            approved = risk.get("Approved At", "")
            entry = f"- **{rid}: {scenario}**"
            if category:
                entry += f" [{category}]"
            if desc:
                entry += f"\n  {desc}"
            if score:
                entry += f"\n  Residual risk score: {score}"
            if approved:
                entry += f" | Approved: {approved[:10]}"
            lines.append(entry)
        return "\n".join(lines)


class NotionReader:
    """Reads content from Notion pages."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        self.base_url = "https://api.notion.com/v1"

    def extract_page_id(self, url: str) -> str:
        url = url.strip().rstrip("/")
        parts = url.split("/")
        last = parts[-1].split("?")[0]
        last_no_dash = last.replace("-", "")
        match = re.search(r"([a-f0-9]{32})$", last_no_dash)
        if match:
            raw_id = match.group(1)
            return f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
        raise ValueError(f"Could not extract Notion page ID from: {url}")

    def get_page_title(self, page_id: str) -> str:
        resp = requests.get(f"{self.base_url}/pages/{page_id}", headers=self.headers)
        if resp.status_code == 404:
            print("Error: Notion page not found (404). Check the page exists and the integration has access.")
            sys.exit(1)
        if resp.status_code == 401:
            print("Error: Notion token is invalid or expired (401). Check NOTION_TOKEN.")
            sys.exit(1)
        resp.raise_for_status()
        data = resp.json()
        for prop in data.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in prop.get("title", []))
        return "Untitled"

    def get_page_content(self, page_id: str) -> str:
        blocks = self._get_blocks(page_id)
        return self._blocks_to_text(blocks)

    def _get_blocks(self, block_id: str) -> List[Dict]:
        all_blocks = []
        cursor = None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = requests.get(
                f"{self.base_url}/blocks/{block_id}/children",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            all_blocks.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        for block in all_blocks:
            if block.get("has_children"):
                block["_children"] = self._get_blocks(block["id"])
        return all_blocks

    def _rich_text_to_str(self, rich_text_list: List[Dict]) -> str:
        return "".join(rt.get("plain_text", "") for rt in rich_text_list)

    def _blocks_to_text(self, blocks: List[Dict], indent: int = 0) -> str:
        lines = []
        prefix = "  " * indent
        for block in blocks:
            btype = block.get("type", "")
            bdata = block.get(btype, {})
            if btype in ("paragraph", "quote", "callout"):
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                if text:
                    lines.append(f"{prefix}{text}")
            elif btype == "heading_1":
                lines.append(f"\n{prefix}# {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "heading_2":
                lines.append(f"\n{prefix}## {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "heading_3":
                lines.append(f"\n{prefix}### {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "bulleted_list_item":
                lines.append(f"{prefix}- {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "numbered_list_item":
                lines.append(f"{prefix}1. {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "to_do":
                checked = "x" if bdata.get("checked") else " "
                lines.append(f"{prefix}- [{checked}] {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "toggle":
                lines.append(f"{prefix}> {self._rich_text_to_str(bdata.get('rich_text', []))}")
            elif btype == "code":
                lang = bdata.get("language", "")
                lines.append(f"{prefix}```{lang}")
                lines.append(self._rich_text_to_str(bdata.get("rich_text", [])))
                lines.append(f"{prefix}```")
            elif btype == "divider":
                lines.append(f"{prefix}---")
            elif btype == "table":
                for row_block in block.get("_children", []):
                    if row_block.get("type") == "table_row":
                        cells = row_block.get("table_row", {}).get("cells", [])
                        row_text = " | ".join(self._rich_text_to_str(cell) for cell in cells)
                        lines.append(f"{prefix}| {row_text} |")
            children = block.get("_children", [])
            if children:
                lines.append(self._blocks_to_text(children, indent + 1))
        return "\n".join(lines)


def build_prompt(
    pr_metadata: Dict[str, Any],
    diff_context: str,
    pr_url: str,
    sdd_title: Optional[str] = None,
    sdd_content: Optional[str] = None,
    accepted_risks: Optional[str] = None,
) -> str:
    """Build the Claude prompt for PR security review."""

    pr_title = pr_metadata.get("title", "Unknown PR")
    pr_body = pr_metadata.get("body") or ""
    pr_author = pr_metadata.get("user", {}).get("login", "unknown")
    base_branch = pr_metadata.get("base", {}).get("ref", "unknown")
    head_branch = pr_metadata.get("head", {}).get("ref", "unknown")
    pr_state = pr_metadata.get("state", "unknown")
    changed_files = pr_metadata.get("changed_files", 0)
    additions = pr_metadata.get("additions", 0)
    deletions = pr_metadata.get("deletions", 0)

    prompt = f"""You are a senior security engineer performing a code-level security review of a GitHub pull request. Your goal is to identify what NEW security risk the code changes introduce — focus on what is different, not on re-auditing the entire codebase.

## PR Details

- **Title:** {pr_title}
- **PR URL:** {pr_url}
- **Author:** {pr_author}
- **State:** {pr_state}
- **Base branch:** {base_branch} <- **Head branch:** {head_branch}
- **Changed files:** {changed_files} | **+{additions} / -{deletions} lines**

"""

    if pr_body:
        prompt += f"""## PR Description

{pr_body[:3000]}

"""

    if sdd_title and sdd_content:
        prompt += f"""## Design Context (SDD: {sdd_title})

The team provided a System Design Document as background. Use this to understand the intended design and cross-reference implementation against design intent.

{sdd_content[:8000]}

"""

    if accepted_risks:
        prompt += f"""## Accepted Risks

The following risks have been formally evaluated and accepted by the business. Do NOT generate security questions, findings, or recommendations that overlap with these accepted risks. They have already been reviewed and the residual risk has been explicitly accepted. Focus your review on risks NOT covered below:

{accepted_risks[:5000]}

"""

    prompt += f"""## Code Changes (Diff)

The following shows the most security-relevant changed files. Files are prioritized by security relevance. Binary files and files outside the context budget are noted but not shown.

{diff_context}

## Security Team Involvement Assessment

As part of your review, determine whether the Security team should be directly involved.

Uses a NIST 800-30 based risk model. Risk = Likelihood x Impact, scored 1-5 each:
- **High risk** (score 15-25): Severe or catastrophic adverse effect on operations, customers, or data
- **Medium risk** (score 5-14): Serious adverse effect; primary functions degraded but not lost
- **Low risk** (score 1-4): Limited adverse effect; minimal damage or financial loss

**Required** - Security team must be consulted before this PR merges. Apply if ANY of:
- New external API surface introduced (endpoints, webhooks, OAuth flows, customer-facing APIs)
- Data classification includes Critical items (credentials, encryption keys, customer PII, auth tokens)
- Authentication or authorization model is being changed or extended
- Customer-supplied code or queries execute on your infrastructure
- Cross-tenant data flows or changes to multi-tenancy isolation
- New third-party integrations that receive, transmit, or store customer data
- New encryption schemes, key management, or cryptographic primitives
- Significant changes to IAM roles, policies, or cross-account access
- High estimated risk score (15-25)

**Recommended** - Security team should review but is not blocking. Apply if ANY of:
- Net-new service or significant architectural change with moderate risk surface
- New data stores that expand SOC 2 scope
- New internal APIs crossing trust boundaries
- Changes to audit logging, monitoring, or alerting for security-relevant events
- Dependency on a new open-source library in a security-sensitive area (auth, crypto, serialization)
- Medium estimated risk score (5-14)

**Not Required** - Apply if ALL of:
- Internal tooling or developer-facing workflows with no customer data
- All data Low or Medium sensitivity with existing, well-understood controls
- No new trust boundaries, external integrations, or authentication changes
- Purely additive change with no infrastructure changes
- Low estimated risk score (1-4)

## Instructions

Focus your review on what the **diff introduces** - new code paths, new dependencies, changed authorization logic, new data flows. Do not audit existing code that is unchanged.

If the PR diff is empty or has no meaningful changes, note that and produce a minimal review.

Produce a security review with these sections:

### 1. Security Questions (1-10)
Each question must be specific to these code changes - not generic advice. Prioritize by impact.

For each question include:
- `exploit_scenario`: A concrete, specific description of how an attacker would exploit this — what payload, path, preconditions, and outcome. Not theoretical; describe the actual attack.
- `confidence`: A float 0.0–1.0 reflecting how confident you are this is a real, exploitable issue in this specific code:
  - 0.9–1.0: Certain exploit path identified
  - 0.8–0.9: Clear vulnerability pattern with known exploitation method
  - 0.7–0.8: Suspicious pattern requiring specific conditions
  - Below 0.7: Do not include — too speculative
- `affected_file`: The specific file path this question applies to, or null if cross-cutting
- `affected_line`: The approximate line number in the diff this question applies to, or null if not line-specific

### 2. Data Classification
Classify data this PR touches or introduces. Sensitivity tiers:
- **Critical**: Credentials, encryption keys, customer PII, authentication tokens
- **High**: Customer business data, configuration affecting security posture
- **Medium**: Operational metadata, logs, metrics
- **Low**: Public documentation, non-sensitive configuration

### 3. Compliance Considerations
SOC 2 scope changes, DPA impacts, data residency concerns, audit logging requirements. If none, state that explicitly.

### 4. Incident Response Considerations
Specific failure/incident scenarios introduced by these changes: what could go wrong, how to detect it, blast radius, rollback options.

### 5. Architecture Diagrams

**a) draw.io XML diagram:**
- Valid draw.io XML, complete `<mxfile>` document
- Show only components/flows relevant to these changes
- Color: red = critical trust boundaries, orange = high-risk data flows, blue = standard components, green = security controls
- Label connections with protocol/mechanism

**b) ASCII diagram:**
- Text-based, max 120 chars wide

Format your entire response as JSON:
```json
{{
  "pr_title": "title of the PR",
  "pr_review_mode": true,
  "risk_summary": "2-3 sentence overall risk assessment of these specific changes",
  "security_involvement": {{
    "recommendation": "Required|Recommended|Not Required",
    "rationale": "1-2 sentence explanation tied to the specific changes in this PR",
    "trigger_criteria": ["list of specific criteria that applied"],
    "likelihood": 3,
    "impact": 4,
    "risk_score": 12,
    "intake_note": "What the team should do next"
  }},
  "questions": [
    {{
      "number": 1,
      "question": "The specific question about these code changes",
      "why_it_matters": "Brief explanation of the risk",
      "security_area": "Category (e.g. Authentication, Data Protection, Input Validation)",
      "exploit_scenario": "Concrete description of how an attacker would exploit this — what payload, what path, what outcome",
      "confidence": 0.85,
      "affected_file": "path/to/file.py or null if cross-cutting",
      "affected_line": 42
    }}
  ],
  "data_classification": [
    {{
      "data_item": "Name of data element",
      "sensitivity": "Critical|High|Medium|Low",
      "storage": "Where it is stored",
      "in_transit": "How it moves",
      "access": "Who/what has access"
    }}
  ],
  "compliance_considerations": [
    {{
      "area": "SOC 2|DPA|Data Residency|Audit Logging",
      "impact": "Description",
      "recommendation": "What to do"
    }}
  ],
  "incident_scenarios": [
    {{
      "scenario": "What could go wrong",
      "detection": "How you would know",
      "blast_radius": "What is affected",
      "mitigation": "How to respond or prevent"
    }}
  ],
  "architecture_diagram_drawio": "<mxfile>...complete draw.io XML...</mxfile>",
  "architecture_diagram_ascii": "ASCII text diagram"
}}
```
"""
    return prompt


def call_anthropic(prompt: str) -> Dict[str, Any]:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    # Ensure prompt is safe for the HTTP transport layer
    prompt = prompt.encode("utf-8", errors="replace").decode("utf-8")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text

        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            json_str = content[json_start:json_end].strip()
        else:
            json_match = re.search(r"\{[\s\S]*\}", content)
            json_str = json_match.group(0) if json_match else content

        return json.loads(json_str)

    except json.JSONDecodeError:
        return {
            "pr_title": "Unknown PR",
            "pr_review_mode": True,
            "risk_summary": "Could not parse AI response — manual review required.",
            "security_involvement": {
                "recommendation": "Recommended",
                "rationale": "Automated analysis failed; defaulting to Recommended out of caution.",
                "trigger_criteria": [],
                "likelihood": None,
                "impact": None,
                "risk_score": None,
                "intake_note": "",
            },
            "questions": [{
                "number": 1,
                "question": "Manual review required — automated analysis could not parse results.",
                "why_it_matters": "The automated review encountered a parsing issue.",
                "security_area": "General",
                "exploit_scenario": None,
                "confidence": 1.0,
                "affected_file": None,
                "affected_line": None,
            }],
            "data_classification": [],
            "compliance_considerations": [],
            "incident_scenarios": [],
        }
    except Exception as e:
        print(f"Error calling Anthropic API: {e}")
        sys.exit(1)


def format_markdown(result: Dict[str, Any], pr_url: str) -> str:
    """Format PR review results as markdown."""
    pr_title = result.get("pr_title", "PR")
    risk_summary = result.get("risk_summary", "")
    questions = result.get("questions", [])
    data_class = result.get("data_classification", [])
    compliance = result.get("compliance_considerations", [])
    incidents = result.get("incident_scenarios", [])
    ascii_diagram = result.get("architecture_diagram_ascii", "")
    involvement = result.get("security_involvement", {})

    involvement_banners = {
        "Required": "> **SECURITY REVIEW: REQUIRED** — Contact your security team before merging.",
        "Recommended": "> **SECURITY REVIEW: RECOMMENDED** — Consider a lightweight async review with your security team.",
        "Not Required": "> **SECURITY REVIEW: NOT REQUIRED** — This PR does not meet the criteria for Security team involvement.",
    }

    md = f"""## Security Review: {pr_title}

**PR:** {pr_url}
**Risk Summary:** {risk_summary}

"""

    rec = involvement.get("recommendation", "")
    if rec in involvement_banners:
        rationale = involvement.get("rationale", "")
        criteria = involvement.get("trigger_criteria", [])
        intake_note = involvement.get("intake_note", "")
        likelihood = involvement.get("likelihood")
        impact = involvement.get("impact")
        risk_score = involvement.get("risk_score")

        md += involvement_banners[rec] + "\n"
        if rationale:
            md += f">\n> {rationale}\n"
        if likelihood is not None and impact is not None and risk_score is not None:
            md += f">\n> **Risk score:** {risk_score}/25 (Likelihood {likelihood}/5 x Impact {impact}/5)\n"
        if criteria:
            md += ">\n> **Criteria met:**\n"
            for c in criteria:
                md += f"> - {c}\n"
        if intake_note:
            md += f">\n> {intake_note}\n"
        md += "\n"

    # Filter out low-confidence questions (below 0.7) for the PR comment
    CONFIDENCE_THRESHOLD = 0.7
    visible_questions = [q for q in questions if q.get("confidence", 1.0) >= CONFIDENCE_THRESHOLD]
    suppressed_count = len(questions) - len(visible_questions)

    md += f"""---

### Security Questions ({len(visible_questions)})

"""

    for q in visible_questions:
        confidence = q.get("confidence")
        confidence_str = f" _(confidence: {confidence:.0%})_" if confidence is not None else ""
        md += f"""#### {q.get('number', '')}. {q.get('question', '')}{confidence_str}

**Area:** {q.get('security_area', '')}
**Why it matters:** {q.get('why_it_matters', '')}
"""
        exploit = q.get("exploit_scenario")
        if exploit:
            md += f"**Exploit scenario:** {exploit}\n"
        md += "\n"

    if suppressed_count:
        md += f"_{suppressed_count} lower-confidence question(s) suppressed (confidence < {CONFIDENCE_THRESHOLD:.0%})._\n\n"

    if data_class:
        md += """---

### Data Classification

| Data Item | Sensitivity | Storage | In Transit | Access |
|-----------|------------|---------|------------|--------|
"""
        for item in data_class:
            md += (
                f"| {item.get('data_item', '')} "
                f"| {item.get('sensitivity', '')} "
                f"| {item.get('storage', '')} "
                f"| {item.get('in_transit', '')} "
                f"| {item.get('access', '')} |\n"
            )
        md += "\n"

    if compliance:
        md += """---

### Compliance Considerations

"""
        for item in compliance:
            md += f"**{item.get('area', '')}:** {item.get('impact', '')}\n- *Recommendation:* {item.get('recommendation', '')}\n\n"

    if incidents:
        md += """---

### Incident Response Scenarios

"""
        for item in incidents:
            md += f"""**Scenario:** {item.get('scenario', '')}
- **Detection:** {item.get('detection', '')}
- **Blast radius:** {item.get('blast_radius', '')}
- **Mitigation:** {item.get('mitigation', '')}

"""

    if ascii_diagram:
        md += """---

### Architecture Diagram

"""
        md += f"""```
{ascii_diagram}
```

> A draw.io version of this diagram is available in the build artifacts (`pr_review_architecture.drawio`).
> Open it at [app.diagrams.net](https://app.diagrams.net/) for an interactive view.

"""

    md += "\n---\n*Generated by PR Security Review Action*"
    return md


def post_pr_comment(markdown: str, repo: str, pr_number: str, token: str) -> None:
    """Post review as a PR comment."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    try:
        resp = requests.post(
            url,
            headers=github_headers(token),
            json={"body": markdown},
            timeout=30,
        )
        resp.raise_for_status()
        print("Posted review as PR comment")
    except Exception as e:
        print(f"Warning: Could not post PR comment: {e}")


def post_inline_comments(
    questions: List[Dict[str, Any]],
    repo: str,
    pr_number: str,
    token: str,
    commit_sha: str,
) -> None:
    """Post inline review comments on specific files/lines for questions that have location info."""
    CONFIDENCE_THRESHOLD = 0.7
    headers = github_headers(token)
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"

    for q in questions:
        if q.get("confidence", 1.0) < CONFIDENCE_THRESHOLD:
            continue
        affected_file = q.get("affected_file")
        affected_line = q.get("affected_line")
        if not affected_file or not affected_line:
            continue

        body = f"**Security Question #{q.get('number', '')} ({q.get('security_area', '')}):** {q.get('question', '')}\n\n"
        body += f"**Why it matters:** {q.get('why_it_matters', '')}\n"
        exploit = q.get("exploit_scenario")
        if exploit:
            body += f"\n**Exploit scenario:** {exploit}\n"
        confidence = q.get("confidence")
        if confidence is not None:
            body += f"\n_Confidence: {confidence:.0%}_"

        try:
            resp = requests.post(
                url,
                headers=headers,
                json={
                    "body": body,
                    "commit_id": commit_sha,
                    "path": affected_file,
                    "line": affected_line,
                    "side": "RIGHT",
                },
                timeout=30,
            )
            if resp.status_code == 422:
                # Line may not be in the diff — silently skip
                pass
            else:
                resp.raise_for_status()
        except Exception as e:
            print(f"Warning: Could not post inline comment for Q{q.get('number', '')}: {e}")


def post_summary(markdown: str) -> None:
    """Post review to GitHub Actions job summary."""
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(markdown)
        print("Posted review to job summary")


def main():
    # Validate required env vars
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: Missing required env var: ANTHROPIC_API_KEY")
        sys.exit(1)

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        print("Error: Missing required env var: GITHUB_TOKEN")
        sys.exit(1)

    pr_review_url = os.getenv("PR_REVIEW_URL", "").strip()
    if not pr_review_url:
        print("Error: Missing required env var: PR_REVIEW_URL")
        sys.exit(1)

    notion_sdd_url = os.getenv("NOTION_SDD_URL", "").strip()
    notion_token = os.getenv("NOTION_TOKEN", "").strip()

    # FR-003: NOTION_TOKEN only required when NOTION_SDD_URL is set
    if notion_sdd_url and not notion_token:
        print("Error: NOTION_TOKEN is required when NOTION_SDD_URL is provided.")
        sys.exit(1)

    # Parse PR URL
    repo, pr_number = parse_pr_url(pr_review_url)
    print(f"Reviewing PR: {repo}#{pr_number}")

    # Fetch PR metadata
    print("Fetching PR metadata...")
    pr_metadata = fetch_pr_metadata(repo, pr_number, github_token)
    pr_title = pr_metadata.get("title", "Unknown PR")
    print(f"PR Title: {pr_title}")
    print(f"Changed files: {pr_metadata.get('changed_files', 0)}")

    # Fetch changed files and build diff context
    print("Fetching PR diff...")
    files = fetch_pr_files(repo, pr_number, github_token)
    if not files:
        print("Warning: No changed files found in this PR.")

    diff_context, all_filenames = build_diff_context(files)
    print(f"Diff context: {len(diff_context)} chars across {len(all_filenames)} files")

    # Optional: fetch Notion SDD as design context
    sdd_title = None
    sdd_content = None
    if notion_sdd_url and notion_token:
        print(f"Fetching Notion SDD: {notion_sdd_url}")
        notion = NotionReader(notion_token)
        page_id = notion.extract_page_id(notion_sdd_url)
        sdd_title = notion.get_page_title(page_id)
        sdd_content = notion.get_page_content(page_id)
        print(f"SDD Title: {sdd_title} ({len(sdd_content)} chars)")

    # Accepted risks (from risk register — FR-011)
    accepted_risks_text = None
    risk_register_repo = os.getenv("RISK_REGISTER_REPO", "")
    risk_client = RiskRegisterClient(github_token, repo=risk_register_repo or None)
    accepted_risks = risk_client.fetch_accepted_risks()
    accepted_risks_text = risk_client.format_for_prompt(accepted_risks)

    # Build prompt and call Claude
    print("Generating security review...")
    prompt = build_prompt(
        pr_metadata=pr_metadata,
        diff_context=diff_context,
        pr_url=pr_review_url,
        sdd_title=sdd_title,
        sdd_content=sdd_content,
        accepted_risks=accepted_risks_text,
    )
    print(f"Prompt size: {len(prompt)} chars")

    result = call_anthropic(prompt)
    result["pr_review_mode"] = True  # ensure flag is always set for sdd_notify.py

    # Format markdown
    markdown = format_markdown(result, pr_review_url)

    # Save outputs (FR-006: pr_review_* naming)
    with open("pr_review_output.json", "w") as f:
        json.dump(result, f, indent=2)
    with open("pr_review_questions.md", "w") as f:
        f.write(markdown)

    drawio_xml = result.get("architecture_diagram_drawio", "")
    if drawio_xml:
        with open("pr_review_architecture.drawio", "w") as f:
            f.write(drawio_xml)
        print("Saved architecture diagram to pr_review_architecture.drawio")

    print("Saved results to pr_review_output.json and pr_review_questions.md")

    # Post PR comment if in PR-triggered context (FR-004)
    github_repo = os.getenv("REPO_FULL_NAME", "")
    github_pr_num = os.getenv("PR_NUMBER", "")
    if github_repo and github_pr_num:
        post_pr_comment(markdown, github_repo, github_pr_num, github_token)
        # Post inline comments for questions that reference specific files/lines
        commit_sha = pr_metadata.get("head", {}).get("sha", "")
        if commit_sha:
            post_inline_comments(
                result.get("questions", []),
                github_repo,
                github_pr_num,
                github_token,
                commit_sha,
            )

    # Post to job summary (FR-005)
    post_summary(markdown)

    # Print to stdout
    print("\n" + "=" * 60)
    print(markdown)
    print("=" * 60)

    num_q = len(result.get("questions", []))
    num_d = len(result.get("data_classification", []))
    num_c = len(result.get("compliance_considerations", []))
    num_i = len(result.get("incident_scenarios", []))
    print(
        f"\nGenerated: {num_q} questions, {num_d} data classifications, "
        f"{num_c} compliance items, {num_i} incident scenarios"
    )


if __name__ == "__main__":
    main()
