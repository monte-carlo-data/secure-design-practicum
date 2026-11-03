"""Linear tickets are created only for Critical findings.

Opening a triage ticket for every "Required" verdict floods the queue with
medium-risk reviews, most of which are not critical. The gate is: Required AND
(risk_score absent OR risk_score >= CRITICAL_RISK_THRESHOLD). An absent score
means the review failed closed (unparseable/crashed) — that always needs a
human, so it still tickets.

Slack notifications are unaffected — every Required/Recommended review still
posts, so a sub-threshold review stays visible without queue spam.

Run:  python -m pytest tests/test_sdd_notify_critical_gate.py -q
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / ".github/scripts/sdd_notify.py"

sys.modules.setdefault("requests", types.ModuleType("requests"))
spec = importlib.util.spec_from_file_location("sdd_notify", SCRIPT)
sdd_notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdd_notify)


def make_review(rec: str, risk_score) -> dict:
    return {
        "pr_review_mode": True,
        "pr_title": "Test PR",
        "risk_summary": "summary",
        "security_involvement": {
            "recommendation": rec,
            "rationale": "because",
            "risk_score": risk_score,
            "likelihood": 3,
            "impact": 4,
            "trigger_criteria": [],
        },
    }


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    """Run main() with the review JSON and fake notifier credentials; capture calls."""

    def _run(review: dict) -> dict:
        calls = {"linear": [], "slack": []}
        monkeypatch.setattr(sdd_notify, "create_linear_ticket", lambda *a, **k: calls["linear"].append(a))
        monkeypatch.setattr(sdd_notify, "post_slack", lambda *a, **k: calls["slack"].append(a))

        path = tmp_path / "pr_review_output.json"
        path.write_text(json.dumps(review))
        monkeypatch.setenv("LINEAR_API_KEY", "fake-key")
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/fake")
        monkeypatch.setenv("REVIEW_OUTPUT_FILE", str(path))
        monkeypatch.setattr(sdd_notify, "REVIEW_JSON", str(path))
        try:
            sdd_notify.main()
        except SystemExit:
            pass
        return calls

    return _run


@pytest.mark.parametrize("involvement, expected", [
    ({"risk_score": 15}, True),
    ({"risk_score": 14}, True),   # boundary
    ({"risk_score": 13}, False),
    ({"risk_score": 12}, False),
    ({"risk_score": 0}, False),
    ({"risk_score": None}, True),  # absent score fails closed: an unparseable review needs a human
    ({}, True),                    # missing key fails closed
])
def test_is_critical_threshold(involvement, expected):
    assert sdd_notify.is_critical(involvement) is expected


def test_required_critical_creates_ticket_and_posts_slack(run_main):
    calls = run_main(make_review("Required", 15))
    assert len(calls["linear"]) == 1
    assert len(calls["slack"]) == 1


def test_required_below_threshold_posts_slack_but_no_ticket(run_main):
    calls = run_main(make_review("Required", 12))
    assert len(calls["linear"]) == 0
    assert len(calls["slack"]) == 1, "sub-threshold Required still posts for transparency"


def test_required_without_score_fails_closed_to_a_ticket(run_main):
    calls = run_main(make_review("Required", None))
    assert len(calls["linear"]) == 1


def test_recommended_never_tickets_even_at_high_score(run_main):
    calls = run_main(make_review("Recommended", 20))
    assert len(calls["linear"]) == 0


def test_not_required_skips_ticket_and_slack(run_main):
    calls = run_main(make_review("Not Required", 25))
    assert len(calls["linear"]) == 0
    assert len(calls["slack"]) == 0
