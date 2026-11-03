"""SDD reviewer: retries recoverable model failures, fails closed, honest banner.

Parity with the PR reviewer:
  * Extended thinking shares max_tokens with the JSON body, so an exhausted or
    truncated reply is retried rather than turned into a soft "could not parse"
    result.
  * When no usable review comes back (or the model refuses), the result fails
    CLOSED to Required — an earlier fallback carried no verdict at all.
  * The Required banner and the prompt's intake_note rule only promise a
    Security ticket when sdd_notify actually files one.

No network — the model is a scripted fake client.
Run:  python -m pytest tests/test_sdd_reviewer.py -q
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


def _load():
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(REPO_ROOT / "shared"))
    fakes.install_anthropic_stub()
    sys.modules.setdefault("requests", types.ModuleType("requests"))
    spec = importlib.util.spec_from_file_location("sdd_reviewer", SCRIPTS / "sdd_reviewer.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sdd():
    return _load()


@pytest.fixture
def anthropic():
    return fakes.install_anthropic_stub()


@pytest.fixture
def run(sdd, monkeypatch):
    monkeypatch.setattr(sdd.ai_config.time, "sleep", lambda *_a, **_k: None)  # no real backoff

    def _run(script):
        client = fakes.FakeClient(script)
        monkeypatch.setattr(sdd.ai_config, "make_client", lambda *_a, **_k: client)
        return sdd.SDDReviewer().call_anthropic("prompt"), client

    return _run


@pytest.fixture
def reviewer(sdd, monkeypatch):
    monkeypatch.setattr(sdd.ai_config, "make_client", lambda *_a, **_k: fakes.FakeClient([]))
    return sdd.SDDReviewer()


def _rec(r):
    return r.get("security_involvement", {}).get("recommendation")


VALID = {
    "sdd_title": "Real SDD",
    "risk_summary": "Fine.",
    "security_involvement": {"recommendation": "Not Required", "risk_score": 2},
    "questions": [],
}
VALID_FENCED = "```json\n" + json.dumps(VALID) + "\n```"


def test_budget_exhausted_attempt_is_retried_into_a_real_verdict(run):
    r, c = run([fakes.reply("max_tokens", ""), fakes.reply("end_turn", VALID_FENCED)])
    assert _rec(r) == "Not Required"
    assert len(c.calls) == 2


def test_transient_api_error_is_retried_into_a_real_verdict(run, anthropic):
    r, c = run([fakes.raise_(anthropic.APIConnectionError("reset")), fakes.reply("end_turn", VALID_FENCED)])
    assert _rec(r) == "Not Required"
    assert len(c.calls) == 2


def test_request_shape(run):
    # Room for thinking + JSON, high (not xhigh) effort, and a refusal fallback.
    # At xhigh the SDD prompt can spend the whole budget thinking and never
    # finish the JSON; high finishes with room to spare.
    _, c = run([fakes.reply("end_turn", VALID_FENCED)])
    req = c.calls[-1]
    assert req.get("max_tokens", 0) >= 64000
    assert req["output_config"]["effort"] == "high"
    assert req.get("fallbacks") == "default"
    assert "server-side-fallback-2026-07-01" in req.get("betas", [])


def test_budget_overrun_retries_at_lower_effort(run):
    _, c = run([fakes.reply("max_tokens", ""), fakes.reply("end_turn", VALID_FENCED)])
    efforts = [call["output_config"]["effort"] for call in c.calls]
    assert efforts == ["high", "medium"]


def test_persistently_unparseable_reply_fails_closed(sdd, run):
    # No usable reply → fail CLOSED to Required (an earlier fallback had no verdict).
    r, c = run([fakes.reply("end_turn", "not json")] * sdd.REVIEW_ATTEMPTS)
    assert _rec(r) == "Required"
    assert len(c.calls) == sdd.REVIEW_ATTEMPTS
    # No risk score, so sdd_notify treats it as Critical and files a ticket.
    assert r["security_involvement"].get("risk_score") is None
    for key in ("sdd_title", "risk_summary", "questions", "team_question_responses"):
        assert key in r, f"fail-closed result keeps the '{key}' key downstream reads"


def test_budget_exhaustion_on_every_attempt_names_the_cause(sdd, run):
    r, _ = run([fakes.reply("max_tokens", "")] * sdd.REVIEW_ATTEMPTS)
    assert _rec(r) == "Required"
    assert "max_tokens" in r["risk_summary"]


def test_refusal_fails_closed_at_once(run):
    r, c = run([fakes.reply("refusal", "")])
    assert _rec(r) == "Required"
    assert "declined" in r["risk_summary"].lower()
    assert len(c.calls) == 1


def test_non_transient_api_error_exits_non_zero(run, anthropic):
    with pytest.raises(SystemExit) as exc_info:
        run([fakes.raise_(anthropic.BadRequestError("bad", 400))])
    assert exc_info.value.code not in (0, None)


def test_required_banner_matches_the_ticket_rule(sdd, reviewer):
    # Banner honesty: a ticket is promised only at the Critical threshold.
    def banner(score):
        return reviewer.format_markdown(dict(VALID, security_involvement={
            "recommendation": "Required", "risk_score": score, "likelihood": 2, "impact": 4}))

    md = banner(8)
    assert "has been filed" not in md and "reference the ticket" not in md
    assert "no Security ticket" in md
    assert "has been filed" in banner(15)
    assert "has been filed" in reviewer.format_markdown(sdd._model_declined_result(None, ""))


def test_prompt_states_the_critical_threshold_rule(sdd, reviewer):
    prompt = reviewer.build_prompt(sdd_content="c", sdd_title="t")
    assert f"risk_score >= {sdd.CRITICAL_RISK_THRESHOLD}" in prompt
    assert "for Required a ticket is filed automatically" not in prompt
    assert "{CRITICAL_RISK_THRESHOLD}" not in prompt
