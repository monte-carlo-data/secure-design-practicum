"""Tests for ai_config.response_text / create_message / stream_json_reply.

The primary model always may think: whenever it does, response.content[0] is
a ThinkingBlock with no .text, so `response.content[0].text` raises
AttributeError — intermittently, depending on whether the model chose to
think. Thinking tokens also count against max_tokens, so a small budget can
come back with no text at all. These helpers are the one place callers read
text and make large-budget calls; the static guard below keeps the old
pattern out.

No network.  Run:  python -m pytest tests/test_ai_config_message_helpers.py -q
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_fakes as fakes  # noqa: E402

anthropic = fakes.install_anthropic_stub()

_spec = importlib.util.spec_from_file_location("ai_config", REPO_ROOT / "shared" / "ai_config.py")
ai = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ai)


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(ai.time, "sleep", lambda *_a, **_k: None)


def _block(kind: str, text: str = ""):
    if kind == "text":
        return types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(type=kind, thinking="")  # no .text, like the SDK's ThinkingBlock


def _message(blocks, stop_reason="end_turn"):
    return types.SimpleNamespace(content=blocks, stop_reason=stop_reason)


class _FakeStream:
    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._msg


class _FakeClient:
    def __init__(self, msg):
        self.kwargs = None
        self.messages = types.SimpleNamespace(stream=self._stream)
        self._msg = msg

    def _stream(self, **kwargs):
        self.kwargs = kwargs
        return _FakeStream(self._msg)


# --- response_text -----------------------------------------------------------

def test_response_text_skips_a_leading_thinking_block():
    msg = _message([_block("thinking"), _block("text", "SECURITY")])
    assert ai.response_text(msg) == "SECURITY"


def test_response_text_joins_every_text_block_in_order():
    msg = _message([_block("text", "a"), _block("thinking"), _block("text", "b")])
    assert ai.response_text(msg) == "ab"


def test_response_text_of_a_thinking_only_reply_is_empty():
    assert ai.response_text(_message([_block("thinking")])) == ""


# --- create_message ----------------------------------------------------------

def test_create_message_streams_and_passes_kwargs_through():
    final = _message([_block("text", "ok")])
    client = _FakeClient(final)
    out = ai.create_message(client, model="m", max_tokens=64000, messages=[])
    assert out is final
    assert client.kwargs == {"model": "m", "max_tokens": 64000, "messages": []}


def test_create_message_warns_when_the_output_budget_ran_out(capsys):
    ai.create_message(_FakeClient(_message([_block("thinking")], "max_tokens")),
                      model="m", max_tokens=10, messages=[])
    assert "max_tokens" in capsys.readouterr().err


# --- stream_json_reply: one JSON-object request with retries ----------------

GOOD = '{"verdict": "ok", "note": "Run:\\n```bash\\nls\\n```"}'
FENCED = "Review:\n```json\n" + GOOD + "\n```\n"


def _run(script, **kw):
    client = fakes.FakeClient(script)
    return ai.stream_json_reply(client, model="m", max_tokens=1, messages=[], **kw), client


def test_parses_a_fenced_object_keeping_a_fence_inside_a_string():
    r, c = _run([fakes.reply("end_turn", FENCED)])
    assert r.data == {"verdict": "ok", "note": "Run:\n```bash\nls\n```"}
    assert len(c.calls) == 1


def test_budget_exhausted_attempt_is_retried():
    r, c = _run([fakes.reply("max_tokens", ""), fakes.reply("end_turn", FENCED)])
    assert r.data is not None and len(c.calls) == 2


def test_truncated_json_is_retried_never_half_parsed():
    r, c = _run([fakes.reply("max_tokens", FENCED[: len(FENCED) // 2]), fakes.reply("end_turn", FENCED)])
    assert r.data is not None and len(c.calls) == 2


def test_persistently_unparseable_returns_data_none_after_every_attempt():
    r, c = _run([fakes.reply("end_turn", "nope")] * 3)
    assert r.data is None and r.stop_reason == "end_turn" and r.text == "nope"
    assert len(c.calls) == 3


def test_attempts_is_configurable_and_the_last_stop_reason_is_returned():
    r, c = _run([fakes.reply("max_tokens", "")] * 2, attempts=2)
    assert r.data is None and r.stop_reason == "max_tokens" and len(c.calls) == 2


def test_after_a_budget_overrun_the_retry_steps_effort_down():
    # Retrying an overrun at the same effort just overruns again: a review that
    # thinks its way to the ceiling once usually does so on the retry too.
    # After a max_tokens attempt, later attempts drop to budget_retry_effort.
    _, c = _run([fakes.reply("max_tokens", ""), fakes.reply("end_turn", FENCED)],
                output_config={"effort": "xhigh"}, budget_retry_effort="high")
    assert [call["output_config"]["effort"] for call in c.calls] == ["xhigh", "high"]


def test_a_transient_error_retry_keeps_the_original_effort():
    _, c = _run([fakes.raise_(anthropic.APIConnectionError("x")), fakes.reply("end_turn", FENCED)],
                output_config={"effort": "xhigh"}, budget_retry_effort="high")
    assert [call["output_config"]["effort"] for call in c.calls] == ["xhigh", "xhigh"]


def test_without_budget_retry_effort_the_request_is_unchanged():
    _, c = _run([fakes.reply("max_tokens", ""), fakes.reply("end_turn", FENCED)],
                output_config={"effort": "xhigh", "task_budget": 5})
    assert [call["output_config"] for call in c.calls] == [{"effort": "xhigh", "task_budget": 5}] * 2


@pytest.mark.parametrize("name", ["connection drop", "overloaded (529)", "rate limit", "mid-stream error event"])
def test_transient_errors_are_retried(name):
    exc = {
        "connection drop": lambda: anthropic.APIConnectionError("reset"),
        "overloaded (529)": lambda: anthropic.OverloadedError("o", 529),
        "rate limit": lambda: anthropic.RateLimitError("r", 429),
        "mid-stream error event": lambda: anthropic.APIStatusError("overloaded_error", 200),
    }[name]()
    r, c = _run([fakes.raise_(exc), fakes.reply("end_turn", FENCED)])
    assert r.data is not None and len(c.calls) == 2


def test_refusal_returns_at_once_unretried():
    r, c = _run([fakes.reply("refusal", "")])
    assert r.data is None and r.stop_reason == "refusal" and len(c.calls) == 1


def test_non_transient_api_error_propagates():
    with pytest.raises(anthropic.BadRequestError):
        _run([fakes.raise_(anthropic.BadRequestError("bad", 400))])


def test_transient_error_on_the_last_attempt_propagates():
    with pytest.raises(anthropic.APIConnectionError):
        _run([fakes.raise_(anthropic.APIConnectionError("x"))] * 3)


def test_betas_route_the_request_to_the_beta_endpoint():
    _, c = _run([fakes.reply("end_turn", FENCED)], betas=["b"], fallbacks="default")
    assert c.endpoints == ["beta"]


def test_no_betas_uses_the_standard_endpoint():
    _, c = _run([fakes.reply("end_turn", FENCED)])
    assert c.endpoints == ["messages"]


# --- static guard ------------------------------------------------------------

def test_no_script_reads_content0_text():
    # Nothing outside the tests reads content[0].text; use ai_config.response_text.
    pattern = re.compile(r"\.content\[0\]\.text")
    offenders = []
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in rel for part in ("archive/", "node_modules/", "venv/", "/.venv/")) \
                or path.name.startswith("test_"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{rel}:{n}")
    assert not offenders, ", ".join(offenders)
