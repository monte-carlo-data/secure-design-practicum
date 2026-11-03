"""Fail-closed verdict tests for pr_reviewer.py's model-declined path.

A model refusal, an empty body, or an unparseable response on a PR security
review must escalate to *Required* (mandatory human review), NOT silently
downgrade to the softest verdict (Recommended). The diffs that trigger a refusal
are disproportionately the most security-sensitive ones (security tooling,
exploit-shaped code), so a soft default there is exactly backwards.

This is a regression guard for that behavior. It also guards the recovery
path: a transient failure (output budget exhausted, a truncated or unparseable
body, a dropped connection, a mid-stream overload) is retried before the review
fails closed, so a recoverable blip yields a real verdict. No network — the
model is a scripted fake client.

Run:  python -m pytest tests/test_pr_reviewer_failclosed.py -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / ".github" / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_fakes as fakes  # noqa: E402


def _load_pr_reviewer():
    # pr_reviewer.py imports ai_config and anthropic at module top; make the
    # scripts dir importable and stub out the heavy deps so this stays offline.
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
def anthropic():
    return fakes.install_anthropic_stub()


def _run(pr, monkeypatch, script):
    """Run the Claude (even-PR) review against a scripted client; returns (result, client)."""
    client = fakes.FakeClient(script)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.setattr(pr.ai_config, "make_client", lambda *_a, **_k: client)
    monkeypatch.setattr(pr.ai_config.time, "sleep", lambda *_a, **_k: None)  # no real backoff
    result, _provider, _model = pr.call_reviewer("prompt", 2)
    return result, client


def _rec(result):
    return result["security_involvement"]["recommendation"]


VALID = {
    "pr_title": "Real PR",
    "risk_summary": "Fine.",
    "security_involvement": {"recommendation": "Not Required", "risk_score": 2},
    "questions": [],
}
VALID_FENCED = "Here is the review.\n```json\n" + json.dumps(VALID) + "\n```\n"


def test_refusal_escalates_to_required(pr):
    r = pr._model_declined_result("refusal", "")
    assert _rec(r) == "Required"
    assert _rec(r) != "Recommended"
    assert "declined" in r["risk_summary"].lower()


def test_empty_response_escalates_to_required(pr):
    r = pr._model_declined_result(None, "")
    assert _rec(r) == "Required"
    assert "empty" in r["risk_summary"].lower()


def test_unparseable_response_escalates_to_required(pr):
    r = pr._model_declined_result("unparseable", "not json at all { oops")
    assert _rec(r) == "Required"
    # Shape contract: the fallback still returns the keys downstream expects.
    for key in ("pr_title", "risk_summary", "security_involvement", "questions"):
        assert key in r
    assert len(r["questions"]) >= 1


def test_budget_exhausted_attempt_is_retried(pr, monkeypatch):
    # Thinking ate the whole output budget (no text, stop_reason=max_tokens).
    # Retried, and the retry's real verdict wins.
    r, c = _run(pr, monkeypatch, [fakes.reply("max_tokens", ""), fakes.reply("end_turn", VALID_FENCED)])
    assert _rec(r) == "Not Required"
    assert len(c.calls) == 2
    efforts = [call["output_config"]["effort"] for call in c.calls]
    assert efforts == ["xhigh", "high"], "the overrun retry steps xhigh down to high"


def test_truncated_json_is_retried(pr, monkeypatch):
    # Truncated mid-JSON (the "could not be parsed" shape) is retried too.
    truncated = VALID_FENCED[: len(VALID_FENCED) // 2]
    r, c = _run(pr, monkeypatch, [fakes.reply("max_tokens", truncated), fakes.reply("end_turn", VALID_FENCED)])
    assert _rec(r) == "Not Required"
    assert len(c.calls) == 2


def test_persistent_budget_exhaustion_fails_closed(pr, monkeypatch):
    script = [fakes.reply("max_tokens", "")] * pr.REVIEW_ATTEMPTS
    r, c = _run(pr, monkeypatch, script)
    assert _rec(r) == "Required"
    assert len(c.calls) == pr.REVIEW_ATTEMPTS, "persistent failure uses every attempt"
    assert "max_tokens" in r["risk_summary"], "the summary names the cause"


def test_persistently_unparseable_output_fails_closed(pr, monkeypatch):
    r, _ = _run(pr, monkeypatch, [fakes.reply("end_turn", "no json here")] * pr.REVIEW_ATTEMPTS)
    assert _rec(r) == "Required"
    assert "could not be parsed" in r["risk_summary"]


@pytest.mark.parametrize("name", ["connection drop", "overloaded (529)", "mid-stream error event"])
def test_transient_errors_are_retried(pr, monkeypatch, anthropic, name):
    exc = {
        "connection drop": lambda: anthropic.APIConnectionError("reset"),
        "overloaded (529)": lambda: anthropic.OverloadedError("overloaded", 529),
        "mid-stream error event": lambda: anthropic.APIStatusError("overloaded_error", 200),
    }[name]()
    r, c = _run(pr, monkeypatch, [fakes.raise_(exc), fakes.reply("end_turn", VALID_FENCED)])
    assert _rec(r) == "Not Required"
    assert len(c.calls) == 2


def test_non_transient_api_error_exits_non_zero(pr, monkeypatch, anthropic):
    # A bad request is not retried; it still exits non-zero so the workflow
    # fails closed and the run goes red.
    with pytest.raises(SystemExit) as exc_info:
        _run(pr, monkeypatch, [fakes.raise_(anthropic.BadRequestError("bad", 400))])
    assert exc_info.value.code not in (0, None)


def test_refusal_fails_closed_without_retrying(pr, monkeypatch):
    # A refusal is a decision, not a blip: no retry, Required immediately.
    r, c = _run(pr, monkeypatch, [fakes.reply("refusal", "")])
    assert _rec(r) == "Required"
    assert len(c.calls) == 1


def test_output_budget_leaves_room_for_thinking_and_json(pr, monkeypatch):
    # The review goes through ai_config.complete, so there is no Anthropic-only
    # server-side refusal fallback here; the budget must be well above the 32k
    # that thinking alone can exhaust.
    _, c = _run(pr, monkeypatch, [fakes.reply("end_turn", VALID_FENCED)])
    req = c.calls[0]
    assert req.get("max_tokens", 0) >= 64000


def test_code_fence_inside_json_string_still_parses(pr, monkeypatch):
    # A ``` inside a JSON string (code in a question) must not truncate the
    # extraction — a naive find-next-fence cut the object in half.
    tricky = dict(VALID, risk_summary="Run:\n```bash\nrm -rf /tmp/x\n```\nthen check.")
    r, _ = _run(pr, monkeypatch, [fakes.reply("end_turn", "```json\n" + json.dumps(tricky) + "\n```")])
    assert _rec(r) == "Not Required"
    assert "rm -rf" in r["risk_summary"]


def test_required_banner_matches_the_ticket_rule(pr):
    # The Required banner must match what sdd_notify actually does: a ticket is
    # filed only for Critical findings. Telling the author "a ticket has been
    # filed" below the threshold sends them to track a ticket that does not exist.
    def banner(score):
        res = dict(VALID, security_involvement={"recommendation": "Required", "risk_score": score,
                                                "likelihood": 2, "impact": 4})
        return pr.format_markdown(res, "https://github.com/example-org/example-repo/pull/1")

    md = banner(8)
    assert "has been filed" not in md and "ticket above" not in md
    assert "no Security ticket" in md
    assert "has been filed" in banner(15)
    assert "has been filed" in pr.format_markdown(pr._model_declined_result(None, ""), "u")


def test_prompt_states_the_critical_threshold_rule(pr):
    # The model writes intake_note itself, so the prompt must tell it the same
    # threshold rule instead of "for Required a ticket is filed".
    prompt = pr.build_prompt(pr_metadata={"title": "t"}, diff_context="d", pr_url="u")
    assert f"risk_score >= {pr.CRITICAL_RISK_THRESHOLD}" in prompt
    assert "for Required a ticket is filed automatically" not in prompt
