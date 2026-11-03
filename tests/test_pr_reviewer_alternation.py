"""pr_reviewer.py alternates the reviewing vendor by PR number.

Even PRs are reviewed by Claude, odd PRs by OpenAI (codex), so a second
automated checker on the same PR can always be routed to the opposite vendor.
The OpenAI leg has two transports: through an AI proxy when ANTHROPIC_BASE_URL
is set (a Responses API POST to {ANTHROPIC_BASE_URL}/v1/responses with
ANTHROPIC_API_KEY as the bearer, OPENAI_API_KEY never read), else direct to
OpenAI with OPENAI_API_KEY. With neither available it exits non-zero naming
both instead of silently using Claude.

Whichever vendor writes it, the verdict and risk-score lines a comment-reading
gate parses must come out byte-identical. No network.

Run:  python -m pytest tests/test_pr_reviewer_alternation.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / ".github" / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_fakes as fakes  # noqa: E402


def _load_pr_reviewer():
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(REPO_ROOT / "shared"))
    fakes.install_anthropic_stub()
    sys.modules.setdefault("requests", types.ModuleType("requests"))
    spec = importlib.util.spec_from_file_location("pr_reviewer", SCRIPTS / "pr_reviewer.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pr():
    return _load_pr_reviewer()


@pytest.fixture
def ai(pr, monkeypatch):
    monkeypatch.setattr(pr.ai_config.time, "sleep", lambda *_a, **_k: None)
    return pr.ai_config


# A Required finding with a risk score: exercises both lines a gate reads.
REVIEW = {
    "pr_title": "Add token exchange",
    "risk_summary": "New credential path.",
    "security_involvement": {
        "recommendation": "Required",
        "rationale": "Touches auth.",
        "trigger_criteria": ["Authentication change"],
        "likelihood": 3,
        "impact": 4,
        "risk_score": 12,
        "intake_note": "",
    },
    "questions": [],
}
REVIEW_TEXT = "```json\n" + json.dumps(REVIEW) + "\n```"
VERDICT_LINE = "> **SECURITY REVIEW: REQUIRED**"
RISK_LINE = "> **Risk score:** 12/25 (Likelihood 3/5 x Impact 4/5)"
PR_URL = "https://github.com/example-org/example-repo/pull/1"


def gate_lines(md: str) -> list[str]:
    """The lines a comment-reading gate keys on: the verdict banner and risk score."""
    return [ln for ln in md.splitlines()
            if ln.startswith("> **SECURITY REVIEW:") or ln.startswith("> **Risk score:**")]


class _Resp:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class _SpyEnviron(dict):
    """os.environ stand-in that records every key looked up."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.reads: list[str] = []

    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.reads.append(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self.reads.append(key)
        return super().__contains__(key)


def test_parity_rule(pr):
    assert pr.reviewer_provider(2) == "claude"
    assert pr.reviewer_provider("3") == "codex"


def test_both_providers_produce_identical_gate_lines(pr, ai, monkeypatch):
    # Both providers go through ai_config.complete with the spec'd kwargs and
    # produce byte-identical gate lines.
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.test")
    comments = {}
    for pr_num, provider, raw in (
        (2, "claude", types.SimpleNamespace(stop_reason="end_turn")),
        (3, "codex", {"status": "completed", "output": []}),
    ):
        calls: list[dict] = []

        def fake_complete(prompt, **kw):
            calls.append(kw)
            return ai.AIResult(text=REVIEW_TEXT, provider=kw["provider"],
                               model=f"{kw['provider']}-model", raw=raw)

        monkeypatch.setattr(ai, "complete", fake_complete)
        result, used, model = pr.call_reviewer("prompt", pr_num)
        assert len(calls) == 1
        kw = calls[0]
        assert kw.get("provider") == provider
        # The vendor is pinned: no fallback, primary tier, the review budget.
        assert kw.get("fallback") is False
        assert kw.get("tier") == "primary"
        assert kw.get("max_tokens") == pr.REVIEW_MAX_TOKENS
        assert "budget_retry_effort" not in kw, "no Anthropic-only kwarg on a vendor-neutral call"
        reviewer = f"{provider} ({model})"
        md = pr.format_markdown(result, PR_URL, reviewer=reviewer)
        comments[provider] = md
        assert f"Reviewed by {reviewer}" in md.splitlines()[-1]
        lines = gate_lines(md)
        assert len(lines) == 2 and lines[0].startswith(VERDICT_LINE) and lines[1] == RISK_LINE, lines
        assert result["security_involvement"]["recommendation"] == "Required"
        assert result["security_involvement"]["risk_score"] == 12
    assert gate_lines(comments["claude"]) == gate_lines(comments["codex"])


def test_codex_leg_posts_to_the_proxy_and_never_reads_openai_key(pr, ai, monkeypatch):
    posted: list = []

    def fake_urlopen(req, timeout=None):
        posted.append(req)
        return _Resp({"status": "completed", "output": [
            {"type": "message", "content": [{"type": "output_text", "text": REVIEW_TEXT}]}]})

    spy = _SpyEnviron({k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"})
    spy.update(ANTHROPIC_BASE_URL="https://proxy.test/", ANTHROPIC_API_KEY="proxy-token")
    monkeypatch.setattr(ai.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(os, "environ", spy)
    result, used, model = pr.call_reviewer("prompt", 3)

    assert len(posted) == 1
    req = posted[0]
    assert req.full_url == "https://proxy.test/v1/responses"
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer proxy-token"
    body = json.loads(req.data)
    assert body.get("input") == "prompt"
    assert body.get("max_output_tokens") == pr.REVIEW_MAX_TOKENS
    assert body.get("model") == ai.model_for(ai.PRIMARY, provider="codex")
    assert "OPENAI_API_KEY" not in spy.reads
    assert used == "codex"
    assert result["security_involvement"]["risk_score"] == 12


def test_codex_truncation_is_retried_then_fails_closed(pr, ai, monkeypatch):
    incomplete = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                  "output": []}
    posted: list = []
    monkeypatch.setattr(ai.urllib.request, "urlopen",
                        lambda req, timeout=None: (posted.append(req), _Resp(incomplete))[1])
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "proxy-token")
    result, _, _ = pr.call_reviewer("prompt", 5)
    assert len(posted) == pr.REVIEW_ATTEMPTS, "budget exhaustion retries every attempt"
    assert result["security_involvement"]["recommendation"] == "Required"
    assert "max_tokens" in result["risk_summary"]


def test_odd_pr_without_the_proxy_goes_direct_to_openai(pr, ai, monkeypatch, capsys):
    # ANTHROPIC_BASE_URL unset but OPENAI_API_KEY set: OpenAI DIRECT
    # (chat/completions via ai_config's codex adapter), never Claude. Supporting
    # both transports matters: if the proxy variable disappears from a caller
    # repo, every odd PR would otherwise fail.
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-direct")
    direct_calls: list[dict] = []

    def fake_direct(prompt, **kw):
        direct_calls.append(kw)
        return ai.AIResult(text=REVIEW_TEXT, provider="codex", model="codex-model",
                           raw=types.SimpleNamespace(choices=[types.SimpleNamespace(finish_reason="stop")]))

    monkeypatch.setattr(ai, "complete", fake_direct)
    result, used, model = pr.call_reviewer("prompt", 3)
    assert len(direct_calls) == 1
    kw = direct_calls[0]
    assert kw.get("provider") == "codex"
    assert kw.get("transport") != ai.TRANSPORT_ANTHROPIC_PROXY, "direct transport, not the proxy"
    assert used == "codex"
    assert result["security_involvement"]["risk_score"] == 12
    assert "direct" in capsys.readouterr().out.lower(), "the log says OpenAI is reached directly"


def test_stop_reasons_normalize_for_both_codex_transports(pr, ai):
    def codex_result(raw):
        return ai.AIResult(text="", provider="codex", model="m", raw=raw)

    def chat(reason):
        return types.SimpleNamespace(choices=[types.SimpleNamespace(finish_reason=reason)])

    # Direct chat/completions object.
    assert pr._stop_reason(codex_result(chat("length"))) == "max_tokens"
    assert pr._stop_reason(codex_result(chat("content_filter"))) == "refusal"
    assert pr._stop_reason(codex_result(chat("stop"))) == "end_turn"
    # The proxy's Responses dict.
    assert pr._stop_reason(codex_result({"status": "incomplete",
                                         "incomplete_details": {"reason": "max_output_tokens"},
                                         "output": []})) == "max_tokens"
    assert pr._stop_reason(codex_result({"status": "completed", "output": []})) == "end_turn"


def test_odd_pr_with_neither_proxy_nor_key_exits_non_zero(pr, ai, monkeypatch, capsys):
    # No cross-vendor fallback: it exits naming both variables and never
    # quietly becomes a Claude review.
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    called: list = []
    monkeypatch.setattr(ai, "complete", lambda *a, **k: called.append(k))
    with pytest.raises(SystemExit) as exc_info:
        pr.call_reviewer("prompt", 3)
    assert exc_info.value.code not in (0, None)
    out = capsys.readouterr().out
    assert "ANTHROPIC_BASE_URL" in out and "OPENAI_API_KEY" in out
    assert called == [], "no silent fallback to the other vendor"
