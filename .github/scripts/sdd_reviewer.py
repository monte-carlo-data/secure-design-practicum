#!/usr/bin/env python3
"""
SDD Security Review Script

Reads a System Design Document from Notion along with optional context
(source code, specs, diagrams, security concerns, platform context,
team questions) and generates a security review including:
  - 1-10 security questions
  - Data classification table
  - Compliance considerations
  - Incident response scenarios
  - Responses to team-specific questions
  - Architecture diagram (draw.io XML for interactive viewing)
  - Architecture diagram (ASCII for PR comments and terminal output)

Enhancements over a basic review:
  1. Deep code fetch - reads actual file contents from repos, not just directory listings
  2. Platform context - loads a standing doc describing MC architecture patterns
  3. Team questions - accepts specific concerns the team wants addressed
  4. Expanded analysis - data classification, compliance, and incident response
"""

import os
import json
import re
import sys
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
import ai_config

import anthropic
import requests


# File extensions we consider useful source code context
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".rb", ".tf", ".hcl", ".yml", ".yaml", ".json", ".toml",
    ".sql", ".graphql", ".gql", ".proto", ".sh",
}

# Files/dirs to always skip when crawling repos
SKIP_PATHS = {
    "node_modules", "vendor", "dist", "build", "__pycache__",
    ".git", ".tox", ".mypy_cache", ".pytest_cache", "venv",
    "egg-info", ".eggs", "coverage", "htmlcov",
}

# Per-file content cap (chars) to avoid blowing up the prompt
MAX_FILE_CONTENT = 4000

# Total source context cap
MAX_SOURCE_CONTEXT = 30000


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
        """Extract page ID from a Notion URL."""
        url = url.strip().rstrip("/")

        # Extract from the last path segment only (before query string) to avoid
        # matching hex chars from the page title portion of the URL slug.
        parts = url.split("/")
        last = parts[-1].split("?")[0]
        last_no_dash = last.replace("-", "")
        match = re.search(r"([a-f0-9]{32})$", last_no_dash)
        if match:
            raw_id = match.group(1)
            return f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"

        raise ValueError(f"Could not extract Notion page ID from: {url}")

    def get_page_title(self, page_id: str) -> str:
        """Get the title of a Notion page."""
        resp = requests.get(
            f"{self.base_url}/pages/{page_id}",
            headers=self.headers,
        )
        if resp.status_code == 404:
            print(f"Error: Notion page not found (404). Make sure the page exists and the integration has been added as a connection.")
            print(f"  Page ID: {page_id}")
            print(f"  To fix: Open the page in Notion > click '...' > Connections > add your integration")
            sys.exit(1)
        if resp.status_code == 401:
            print(f"Error: Notion token is invalid or expired (401). Check the NOTION_TOKEN secret.")
            sys.exit(1)
        resp.raise_for_status()
        data = resp.json()

        for prop in data.get("properties", {}).values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)
        return "Untitled"

    def get_page_content(self, page_id: str) -> str:
        """Recursively retrieve all block content from a Notion page as plain text."""
        blocks = self._get_blocks(page_id)
        return self._blocks_to_text(blocks)

    def _get_blocks(self, block_id: str) -> List[Dict]:
        """Fetch all child blocks of a given block/page, handling pagination."""
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

            results = data.get("results", [])
            all_blocks.extend(results)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        for block in all_blocks:
            if block.get("has_children"):
                block["_children"] = self._get_blocks(block["id"])

        return all_blocks

    def _rich_text_to_str(self, rich_text_list: List[Dict]) -> str:
        """Convert Notion rich_text array to plain string."""
        return "".join(rt.get("plain_text", "") for rt in rich_text_list)

    def _blocks_to_text(self, blocks: List[Dict], indent: int = 0) -> str:
        """Convert Notion blocks to readable plain text."""
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
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lines.append(f"\n{prefix}# {text}")

            elif btype == "heading_2":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lines.append(f"\n{prefix}## {text}")

            elif btype == "heading_3":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lines.append(f"\n{prefix}### {text}")

            elif btype == "bulleted_list_item":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lines.append(f"{prefix}- {text}")

            elif btype == "numbered_list_item":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lines.append(f"{prefix}1. {text}")

            elif btype == "to_do":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                checked = "x" if bdata.get("checked") else " "
                lines.append(f"{prefix}- [{checked}] {text}")

            elif btype == "toggle":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lines.append(f"{prefix}> {text}")

            elif btype == "code":
                text = self._rich_text_to_str(bdata.get("rich_text", []))
                lang = bdata.get("language", "")
                lines.append(f"{prefix}```{lang}")
                lines.append(text)
                lines.append(f"{prefix}```")

            elif btype == "divider":
                lines.append(f"{prefix}---")

            elif btype == "table":
                children = block.get("_children", [])
                for row_block in children:
                    if row_block.get("type") == "table_row":
                        cells = row_block.get("table_row", {}).get("cells", [])
                        row_text = " | ".join(
                            self._rich_text_to_str(cell) for cell in cells
                        )
                        lines.append(f"{prefix}| {row_text} |")

            children = block.get("_children", [])
            if children:
                lines.append(self._blocks_to_text(children, indent + 1))

        return "\n".join(lines)


class SourceCodeFetcher:
    """Fetches actual source code files from GitHub repos, not just directory listings."""

    def __init__(self, github_token: str):
        self.github_token = github_token
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def fetch_repo_context(
        self,
        repo: str,
        file_patterns: Optional[List[str]] = None,
        max_depth: int = 3,
    ) -> str:
        """Fetch repository structure and key file contents.

        If file_patterns is provided (e.g. ["src/auth/", "models.py"]),
        only files matching those paths/patterns are fetched.
        Otherwise we use heuristics to pick security-relevant files.
        """
        repo = repo.strip()
        parts = []

        tree = self._get_repo_tree(repo)
        if not tree:
            return ""

        structure = self._format_tree(repo, tree)
        parts.append(structure)

        if file_patterns:
            target_files = self._match_patterns(tree, file_patterns)
        else:
            target_files = self._pick_interesting_files(tree, max_depth)

        total_chars = len(structure)
        for file_path in target_files:
            if total_chars >= MAX_SOURCE_CONTEXT:
                break
            content = self._fetch_file(repo, file_path)
            if content:
                truncated = content[:MAX_FILE_CONTENT]
                if len(content) > MAX_FILE_CONTENT:
                    truncated += f"\n... (truncated, {len(content)} total chars)"
                file_block = f"\n### {repo}/{file_path}\n```\n{truncated}\n```"
                parts.append(file_block)
                total_chars += len(file_block)

        return "\n".join(parts)

    def _get_repo_tree(self, repo: str) -> Optional[List[Dict]]:
        """Fetch the full git tree for a repo (recursive)."""
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1",
                headers=self.headers,
            )
            if resp.status_code != 200:
                print(f"Warning: Could not fetch tree for {repo}: {resp.status_code}")
                return None
            return resp.json().get("tree", [])
        except Exception as e:
            print(f"Warning: Error fetching tree for {repo}: {e}")
            return None

    def _format_tree(self, repo: str, tree: List[Dict]) -> str:
        """Format a git tree into a readable directory listing."""
        dirs = set()
        files = []
        for item in tree:
            path = item["path"]
            if any(skip in path.split("/") for skip in SKIP_PATHS):
                continue
            if item["type"] == "tree":
                depth = path.count("/")
                if depth < 3:
                    dirs.add(path)
            elif item["type"] == "blob":
                depth = path.count("/")
                if depth < 2:
                    files.append(path)

        lines = [f"Repository: {repo}", ""]
        for d in sorted(dirs):
            lines.append(f"  [dir]  {d}/")
        for f in sorted(files):
            lines.append(f"  [file] {f}")
        return "\n".join(lines)

    def _match_patterns(self, tree: List[Dict], patterns: List[str]) -> List[str]:
        """Match tree paths against user-supplied patterns."""
        matched = []
        for item in tree:
            if item["type"] != "blob":
                continue
            path = item["path"]
            ext = Path(path).suffix.lower()
            if ext not in CODE_EXTENSIONS:
                continue
            for pattern in patterns:
                pattern = pattern.strip()
                if pattern in path:
                    matched.append(path)
                    break
        return matched[:30]

    def _pick_interesting_files(self, tree: List[Dict], max_depth: int) -> List[str]:
        """Heuristically pick security-relevant files from a repo tree."""
        priority_keywords = [
            "auth", "permission", "policy", "security", "credential",
            "secret", "token", "iam", "rbac", "acl", "encrypt",
            "middleware", "guard", "interceptor", "validator",
            "model", "schema", "migration",
            "dockerfile", "docker-compose", "terraform", "cloudformation",
            "config", "settings",
        ]
        interesting_names = [
            "requirements.txt", "package.json", "go.mod", "cargo.toml",
            "pyproject.toml", "setup.py", "setup.cfg",
        ]

        scored: List[tuple] = []
        for item in tree:
            if item["type"] != "blob":
                continue
            path = item["path"]
            if any(skip in path.split("/") for skip in SKIP_PATHS):
                continue
            depth = path.count("/")
            if depth > max_depth:
                continue
            ext = Path(path).suffix.lower()
            name = Path(path).name.lower()

            if ext not in CODE_EXTENSIONS and name not in interesting_names:
                continue

            score = 0
            path_lower = path.lower()
            for kw in priority_keywords:
                if kw in path_lower:
                    score += 10
            if name in interesting_names:
                score += 5
            score -= depth

            scored.append((score, path))

        scored.sort(key=lambda x: -x[0])
        return [path for _, path in scored[:20]]

    def _fetch_file(self, repo: str, file_path: str) -> Optional[str]:
        """Fetch a single file's contents from GitHub."""
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/contents/{file_path}",
                headers=self.headers,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            if data.get("encoding") == "base64" and data.get("content"):
                return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
            return None
        except Exception:
            return None


class RiskRegisterClient:
    """Fetches accepted risks from the risk-register repo.

    The risk register is a JSON file in a private GitHub repo that tracks
    risks that have been formally evaluated. Risks with
    "Risk Treatment": "Accept" should not generate new review questions
    during SDD reviews.

    Expected JSON schema (risk-register.json):
    {
        "risks": [
            {
                "Risk ID": "EUACD-1",
                "Risk Scenario": "Bug Bounty Program",
                "Risk Description": "Detailed description...",
                "Category": "External unauthorized access to customer data",
                "High Level Risk": "External unauthorized access to customer data",
                "Risk Treatment": "Mitigate|Transfer|Accept",
                "Treatment Status": "Done|In progress",
                "Residual Risk Score": 15,
                "Risk Owner": "owner@montecarlodata.com",
                "Approved At": "2025-04-24T02:27:52.594Z"
            }
        ],
        "metadata": { "total_risks": 24 }
    }
    """

    DEFAULT_REPO = "<organization>/risk-register"
    DEFAULT_PATH = "risk-register.json"

    def __init__(self, github_token: str, repo: Optional[str] = None):
        self.github_token = github_token
        self.repo = repo or self.DEFAULT_REPO
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def fetch_accepted_risks(self) -> List[Dict[str, Any]]:
        """Fetch accepted risks from the risk register repo.

        Returns a list of risk entries where Risk Treatment is "Accept",
        or an empty list if the register is unavailable.
        """
        try:
            url = (
                f"https://api.github.com/repos/{self.repo}"
                f"/contents/{self.DEFAULT_PATH}"
            )
            resp = requests.get(url, headers=self.headers, timeout=30)
            if resp.status_code == 404:
                print(
                    f"Risk register not found at "
                    f"{self.repo}/{self.DEFAULT_PATH} — skipping"
                )
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

                # Support both {"risks": [...]} and bare [...]
                if isinstance(register, dict):
                    risks = register.get("risks", [])
                elif isinstance(register, list):
                    risks = register
                else:
                    print("Warning: Unexpected risk register format — skipping")
                    return []

                accepted = [
                    r for r in risks
                    if r.get("Risk Treatment") == "Accept"
                ]
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
        """Format accepted risks as context for the review prompt.

        Returns None if there are no accepted risks.
        """
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


class SDDReviewer:
    """Reviews an SDD and generates security questions."""

    def __init__(self):
        self.anthropic_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.repo_name = os.getenv("REPO_FULL_NAME", "")
        self.pr_number = os.getenv("PR_NUMBER", "")

    def read_local_file(self, path: str) -> Optional[str]:
        """Read a local file and return its contents."""
        try:
            filepath = Path(path)
            if not filepath.exists():
                print(f"Warning: File not found: {path}")
                return None

            if filepath.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".svg"):
                return f"[Architecture diagram file: {filepath.name} ({filepath.suffix})]"

            if filepath.suffix.lower() == ".drawio":
                return filepath.read_text(encoding="utf-8", errors="ignore")

            return filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"Warning: Could not read {path}: {e}")
            return None

    def build_prompt(
        self,
        sdd_content: str,
        sdd_title: str,
        source_context: Optional[str] = None,
        spec_content: Optional[str] = None,
        diagram_content: Optional[str] = None,
        security_concerns: Optional[str] = None,
        platform_context: Optional[str] = None,
        team_questions: Optional[str] = None,
        accepted_risks: Optional[str] = None,
    ) -> str:
        """Build the Claude prompt for SDD review."""

        prompt = """You are a senior security engineer at Organization reviewing a System Design Document (SDD) before engineering begins building. Your goal is to produce a thorough security analysis that helps the engineering team build securely from day one.

"""
        if platform_context:
            prompt += f"""## Organization Platform Context

This is how our platform works. Use this as baseline knowledge when evaluating the SDD -- it describes our multi-tenancy model, IAM patterns, data pipeline architecture, and existing security controls. Reference specific platform patterns when they are relevant to the design.

{platform_context[:10000]}

"""

        prompt += f"""## SDD: {sdd_title}

{sdd_content}

"""
        if source_context:
            prompt += f"""## Source Code Context

The following shows repository structure and actual source code from the repos involved. Use this to understand existing patterns, security controls already in place, authentication/authorization models, and how the codebase is structured. When the SDD references components, cross-reference them against this code.

{source_context[:MAX_SOURCE_CONTEXT]}

"""

        if spec_content:
            prompt += f"""## Specification Document

{spec_content[:6000]}

"""

        if diagram_content:
            prompt += f"""## Architecture Diagram Description

{diagram_content[:3000]}

"""

        if security_concerns:
            prompt += f"""## Known Security Concerns

The team has already identified these security considerations. Dig deeper into these areas rather than restating them, and identify anything the team may have missed:

{security_concerns[:4000]}

"""

        if team_questions:
            prompt += f"""## Team Questions

The engineering team specifically wants these questions addressed in the review. Provide direct, actionable answers or flag what additional information is needed:

{team_questions[:3000]}

"""

        if accepted_risks:
            prompt += f"""## Accepted Risks

The following risks have been formally evaluated and accepted by the business. Do NOT generate security questions, findings, or recommendations that overlap with these accepted risks. They have already been reviewed and the residual risk has been explicitly accepted. Focus your review on risks NOT covered below:

{accepted_risks[:5000]}

"""

        prompt += """## Security Team Involvement Assessment

As part of your review, determine whether the Security team should be directly involved in reviewing this design.

Organization uses a NIST 800-30 based risk model. Risk = Likelihood × Impact, scored 1–5 each:
- **High risk** (score 15–25): Severe or catastrophic adverse effect on operations, customers, or data
- **Medium risk** (score 5–14): Serious adverse effect; primary functions degraded but not lost
- **Low risk** (score 1–4): Limited adverse effect; minimal damage or financial loss

Use this risk framing alongside the criteria below to determine involvement level.

**Required** — Security team must be consulted before implementation proceeds. Apply if ANY of:
- New external API surface is introduced (new public endpoints, webhooks, OAuth flows, customer-facing APIs)
- Data classification includes Critical items (credentials, encryption keys, customer PII, authentication tokens)
- Authentication or authorization model is being changed or extended
- Customer-supplied code or queries execute on Organization infrastructure (templates, scripts, custom agents, etc.)
- Cross-tenant data flows or changes to the multi-tenancy isolation model
- New third-party integrations that receive, transmit, or store customer data
- New encryption schemes, key management, or cryptographic primitives
- Significant changes to IAM roles, policies, or cross-account access patterns
- Estimated risk score is High (15–25) based on likelihood × impact assessment

**Recommended** — Security team should review but is not blocking. Apply if ANY of:
- Net-new service or significant architectural change with no Critical data but moderate risk surface
- New data stores that expand SOC 2 scope (even if data is Medium sensitivity)
- New internal APIs between services that cross trust boundaries
- Changes to audit logging, monitoring, or alerting for security-relevant events
- Dependency on a new open-source library in a security-sensitive area (auth, crypto, serialization)
- The design acknowledges security tradeoffs but defers decisions to implementation
- Estimated risk score is Medium (5–14) based on likelihood × impact assessment

**Not Required** — Security team does not need to be involved. Apply if ALL of:
- Design is limited to internal tooling or developer-facing workflows with no customer data
- All data items are Low or Medium sensitivity with existing, well-understood controls
- No new trust boundaries, external integrations, or authentication changes
- Purely additive change (new UI, new metric, new dashboard) with no infrastructure changes
- Estimated risk score is Low (1–4) based on likelihood × impact assessment

Include a brief likelihood (1–5) and impact (1–5) estimate with your recommendation to explain the risk score.

Use your judgment when a design sits between categories — err toward the higher involvement level when uncertain.

## Instructions

Produce a security review with the following sections:

### 1. Security Questions (1-10)

Generate between 1 and 10 security-focused questions. Each question should:
- Be specific to this particular design (not generic security advice)
- Identify a concrete risk, gap, or area that needs clarification
- Be actionable -- the team should be able to answer it or take action
- Cover areas like: authentication, authorization, data protection, input validation, secrets management, logging/monitoring, error handling, dependency risks, multi-tenancy isolation, and deployment safety

Prioritize by impact. If the SDD is thorough and low-risk, fewer questions is fine.

### 2. Data Classification

Classify the data this design handles into sensitivity tiers:
- **Critical**: Credentials, encryption keys, customer PII, authentication tokens
- **High**: Customer business data, configuration that affects security posture
- **Medium**: Operational metadata, logs, metrics
- **Low**: Public documentation, non-sensitive configuration

For each data item, note where it is stored, transmitted, and who has access.

### 3. Compliance Considerations

Identify any compliance implications:
- SOC 2 scope changes (new data stores, processing pipelines, third-party integrations)
- DPA / data processing agreement impacts (new data flows, sub-processors)
- Data residency concerns (where data lands geographically)
- Audit logging requirements for the new components

If the design has no compliance impact, state that explicitly.

### 4. Incident Response Considerations

Identify specific failure/incident scenarios introduced by this design:
- What could go wrong and how would the team detect it?
- What runbooks or monitoring should be created?
- What is the blast radius if a component is compromised?
- Can the feature be disabled or rolled back quickly?

### 5. Team Question Responses (if team questions were provided)

For each team question, provide a direct assessment with specific recommendations.

### 6. Architecture Diagrams

Generate two representations of the system architecture described in the SDD:

**a) draw.io XML diagram:**
- Produce valid draw.io (diagrams.net) XML that can be opened directly in draw.io
- Show system components, data flows, trust boundaries, and external integrations
- Use different colors to indicate sensitivity: red for critical trust boundaries, orange for high-risk data flows, blue for standard components, green for security controls
- Label all connections with the protocol/mechanism (e.g. "TLS", "JWT", "IAM role", "Kinesis")
- Group components by trust zone (e.g. "Customer VPC", "MC Platform", "External Services")
- The XML must be a complete, self-contained draw.io file (wrapped in <mxfile> tags)

**b) ASCII architecture diagram:**
- Produce a text-based diagram of the same architecture using box-drawing characters
- Show the same components, data flows, and trust boundaries as the draw.io version
- Use labels on arrows to indicate protocols and data sensitivity
- Keep it readable at 120 characters wide maximum
- This is for quick reference in PR comments, terminal output, and code reviews

Format your entire response as JSON:
```json
{
  "sdd_title": "title of the SDD",
  "risk_summary": "2-3 sentence overall risk assessment",
  "security_involvement": {
    "recommendation": "Required|Recommended|Not Required",
    "rationale": "1-2 sentence explanation of why this level was chosen",
    "trigger_criteria": ["list of specific criteria from the rubric that applied"],
    "likelihood": 3,
    "impact": 4,
    "risk_score": 12,
    "intake_note": "What the team should do next — informational only, not a blocker (e.g. post in #team-security with the SDD link, or proceed without security review)"
  },
  "questions": [
    {
      "number": 1,
      "question": "The specific question",
      "why_it_matters": "Brief explanation of the risk",
      "security_area": "Category (e.g. Authentication, Data Protection)"
    }
  ],
  "data_classification": [
    {
      "data_item": "Name of data element",
      "sensitivity": "Critical|High|Medium|Low",
      "storage": "Where it is stored",
      "in_transit": "How it moves between systems",
      "access": "Who/what has access"
    }
  ],
  "compliance_considerations": [
    {
      "area": "SOC 2|DPA|Data Residency|Audit Logging",
      "impact": "Description of the compliance impact",
      "recommendation": "What to do about it"
    }
  ],
  "incident_scenarios": [
    {
      "scenario": "What could go wrong",
      "detection": "How you would know",
      "blast_radius": "What is affected",
      "mitigation": "How to respond or prevent"
    }
  ],
  "team_question_responses": [
    {
      "question": "The original team question",
      "assessment": "Direct answer with recommendations"
    }
  ],
  "architecture_diagram_drawio": "<mxfile>...complete draw.io XML...</mxfile>",
  "architecture_diagram_ascii": "ASCII text diagram with box-drawing characters"
}
```
"""
        return prompt

    def call_anthropic(self, prompt: str) -> Dict[str, Any]:
        """Send prompt to Claude and parse the response."""
        try:
            response = self.anthropic_client.messages.create(
                model=ai_config.PRIMARY_MODEL,
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
                "sdd_title": "Unknown",
                "risk_summary": "Could not parse AI response",
                "questions": [
                    {
                        "number": 1,
                        "question": "Manual review required - automated analysis could not parse results",
                        "why_it_matters": "The automated review encountered an issue",
                        "security_area": "General",
                    }
                ],
                "data_classification": [],
                "compliance_considerations": [],
                "incident_scenarios": [],
                "team_question_responses": [],
            }
        except Exception as e:
            print(f"Error calling Anthropic API: {e}")
            sys.exit(1)

    def format_markdown(self, result: Dict[str, Any]) -> str:
        """Format review results as markdown."""
        title = result.get("sdd_title", "SDD")
        risk_summary = result.get("risk_summary", "")
        questions = result.get("questions", [])
        data_class = result.get("data_classification", [])
        compliance = result.get("compliance_considerations", [])
        incidents = result.get("incident_scenarios", [])
        team_responses = result.get("team_question_responses", [])
        ascii_diagram = result.get("architecture_diagram_ascii", "")
        involvement = result.get("security_involvement", {})

        involvement_banners = {
            "Required": "> **SECURITY REVIEW: REQUIRED** — Post this SDD in #team-security before implementation proceeds.",
            "Recommended": "> **SECURITY REVIEW: RECOMMENDED** — Consider posting this SDD in #team-security for a lightweight review.",
            "Not Required": "> **SECURITY REVIEW: NOT REQUIRED** — This design does not meet the criteria for Security team involvement.",
        }

        md = f"""## Security Review: {title}

**Risk Summary:** {risk_summary}

"""
        rec = involvement.get("recommendation", "")
        if rec and rec in involvement_banners:
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
                md += f">\n> **Risk score:** {risk_score}/25 (Likelihood {likelihood}/5 × Impact {impact}/5)\n"
            if criteria:
                md += ">\n> **Criteria met:**\n"
                for c in criteria:
                    md += f"> - {c}\n"
            if intake_note:
                md += f">\n> {intake_note}\n"
            md += "\n"

        md += """---

### Security Questions ({count})

""".format(count=len(questions))

        for q in questions:
            num = q.get("number", "")
            question = q.get("question", "")
            why = q.get("why_it_matters", "")
            area = q.get("security_area", "")

            md += f"""#### {num}. {question}

**Area:** {area}
**Why it matters:** {why}

"""

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
                area = item.get("area", "")
                impact = item.get("impact", "")
                rec = item.get("recommendation", "")
                md += f"**{area}:** {impact}\n- *Recommendation:* {rec}\n\n"

        if incidents:
            md += """---

### Incident Response Scenarios

"""
            for item in incidents:
                scenario = item.get("scenario", "")
                detection = item.get("detection", "")
                blast = item.get("blast_radius", "")
                mitigation = item.get("mitigation", "")
                md += f"""**Scenario:** {scenario}
- **Detection:** {detection}
- **Blast radius:** {blast}
- **Mitigation:** {mitigation}

"""

        if team_responses:
            md += """---

### Team Question Responses

"""
            for item in team_responses:
                q = item.get("question", "")
                a = item.get("assessment", "")
                md += f"""**Q:** {q}
**A:** {a}

"""

        if ascii_diagram:
            md += """---

### Architecture Diagram

"""
            md += f"""```
{ascii_diagram}
```

> A draw.io version of this diagram is available in the build artifacts (`sdd_review_architecture.drawio`).
> Open it at [app.diagrams.net](https://app.diagrams.net/) for an interactive, color-coded view with
> trust boundaries and data flow annotations.

"""

        md += "\n---\n*Generated by SDD Security Review Action*"
        return md

    def post_pr_comment(self, markdown: str) -> None:
        """Post results as a PR comment if running in PR context."""
        if not self.github_token or not self.repo_name or not self.pr_number:
            print("No PR context - skipping PR comment")
            return

        url = f"https://api.github.com/repos/{self.repo_name}/issues/{self.pr_number}/comments"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            resp = requests.post(url, headers=headers, json={"body": markdown})
            resp.raise_for_status()
            print("Posted review as PR comment")
        except Exception as e:
            print(f"Warning: Could not post PR comment: {e}")

    def post_summary(self, markdown: str) -> None:
        """Post results to GitHub Actions job summary."""
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file:
            with open(summary_file, "a") as f:
                f.write(markdown)
            print("Posted review to job summary")


def main():
    # Validate required env vars
    required = ["ANTHROPIC_API_KEY", "NOTION_TOKEN", "NOTION_SDD_URL"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    notion_url = os.getenv("NOTION_SDD_URL", "")
    source_repos = os.getenv("SOURCE_REPOS", "")
    source_file_patterns = os.getenv("SOURCE_FILE_PATTERNS", "")
    spec_path = os.getenv("SPEC_MARKDOWN_PATH", "")
    diagram_path = os.getenv("ARCHITECTURE_DIAGRAM_PATH", "")
    security_path = os.getenv("SECURITY_CONCERNS_PATH", "")
    platform_context_path = os.getenv("PLATFORM_CONTEXT_PATH", "")
    team_questions_path = os.getenv("TEAM_QUESTIONS_PATH", "")
    risk_register_repo = os.getenv("RISK_REGISTER_REPO", "")

    # Initialize components
    notion = NotionReader(os.getenv("NOTION_TOKEN", ""))
    reviewer = SDDReviewer()
    github_token = os.getenv("GITHUB_TOKEN", "")

    # 1. Read SDD from Notion
    print(f"Reading SDD from Notion: {notion_url}")
    page_id = notion.extract_page_id(notion_url)
    sdd_title = notion.get_page_title(page_id)
    sdd_content = notion.get_page_content(page_id)

    if not sdd_content.strip():
        print("Error: SDD page appears to be empty")
        sys.exit(1)

    print(f"SDD Title: {sdd_title}")
    print(f"SDD Content length: {len(sdd_content)} chars")

    # 2. Gather optional context

    # Source code (deep fetch)
    source_context = None
    if source_repos and github_token:
        print(f"Fetching source code from: {source_repos}")
        fetcher = SourceCodeFetcher(github_token)
        patterns = (
            [p.strip() for p in source_file_patterns.split(",") if p.strip()]
            if source_file_patterns
            else None
        )
        parts = []
        for repo in source_repos.split(","):
            repo = repo.strip()
            if repo:
                ctx = fetcher.fetch_repo_context(repo, file_patterns=patterns)
                if ctx:
                    parts.append(ctx)
                    print(f"  {repo}: {len(ctx)} chars of context")
        if parts:
            source_context = "\n\n".join(parts)

    # Spec
    spec_content = None
    if spec_path:
        print(f"Reading specification: {spec_path}")
        spec_content = reviewer.read_local_file(spec_path)

    # Diagram
    diagram_content = None
    if diagram_path:
        print(f"Reading architecture diagram: {diagram_path}")
        diagram_content = reviewer.read_local_file(diagram_path)

    # Security concerns
    security_concerns = None
    if security_path:
        print(f"Reading security concerns: {security_path}")
        security_concerns = reviewer.read_local_file(security_path)

    # Platform context
    platform_context = None
    if platform_context_path:
        print(f"Reading platform context: {platform_context_path}")
        platform_context = reviewer.read_local_file(platform_context_path)

    # Team questions
    team_questions = None
    if team_questions_path:
        print(f"Reading team questions: {team_questions_path}")
        team_questions = reviewer.read_local_file(team_questions_path)

    # Accepted risks (from external risk register repo)
    accepted_risks_text = None
    if github_token:
        risk_client = RiskRegisterClient(
            github_token,
            repo=risk_register_repo or None,
        )
        accepted_risks = risk_client.fetch_accepted_risks()
        accepted_risks_text = risk_client.format_for_prompt(accepted_risks)

    # 3. Build prompt and call Claude
    print("Generating security review...")
    prompt = reviewer.build_prompt(
        sdd_content=sdd_content,
        sdd_title=sdd_title,
        source_context=source_context,
        spec_content=spec_content,
        diagram_content=diagram_content,
        security_concerns=security_concerns,
        platform_context=platform_context,
        team_questions=team_questions,
        accepted_risks=accepted_risks_text,
    )

    print(f"Prompt size: {len(prompt)} chars")
    result = reviewer.call_anthropic(prompt)

    # 4. Format and output results
    markdown = reviewer.format_markdown(result)

    # Save outputs
    with open("sdd_review_output.json", "w") as f:
        json.dump(result, f, indent=2)
    with open("sdd_review_questions.md", "w") as f:
        f.write(markdown)

    # Save draw.io diagram as a separate file for easy import
    drawio_xml = result.get("architecture_diagram_drawio", "")
    if drawio_xml:
        with open("sdd_review_architecture.drawio", "w") as f:
            f.write(drawio_xml)
        print("Saved architecture diagram to sdd_review_architecture.drawio")

    print("Saved results to sdd_review_output.json and sdd_review_questions.md")

    # Post to PR if in PR context
    reviewer.post_pr_comment(markdown)

    # Post to job summary
    reviewer.post_summary(markdown)

    # Print to stdout
    print("\n" + "=" * 60)
    print(markdown)
    print("=" * 60)

    num_questions = len(result.get("questions", []))
    num_data = len(result.get("data_classification", []))
    num_compliance = len(result.get("compliance_considerations", []))
    num_incidents = len(result.get("incident_scenarios", []))
    print(f"\nGenerated: {num_questions} questions, {num_data} data classifications, "
          f"{num_compliance} compliance items, {num_incidents} incident scenarios")


if __name__ == "__main__":
    main()
