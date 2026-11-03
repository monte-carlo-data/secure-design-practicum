"""Offline fakes for Anthropic SDK calls, shared by the reviewer tests.

`install_anthropic_stub()` puts a minimal `anthropic` module (just the
exception hierarchy the code under test classifies errors by) into
sys.modules, so code under test runs with no SDK and no network. It is
idempotent: every test module in one pytest process shares the same stub, so
an exception raised by one module's fake client is still caught by the
`except anthropic.APIError` in the shared config. `FakeClient` scripts one
outcome per model attempt: `reply(stop_reason, text)` or `raise_(exc)`.
"""

from __future__ import annotations

import sys
import types

_STUB_MARKER = "__reviewer_test_stub__"


def install_anthropic_stub() -> types.ModuleType:
    existing = sys.modules.get("anthropic")
    if existing is not None and getattr(existing, _STUB_MARKER, False):
        return existing

    mod = types.ModuleType("anthropic")
    setattr(mod, _STUB_MARKER, True)

    class APIError(Exception):
        pass

    class APIStatusError(APIError):
        def __init__(self, message: str, status_code: int):
            super().__init__(message)
            self.status_code = status_code

    class APIConnectionError(APIError):
        pass

    mod.APIError = APIError
    mod.APIStatusError = APIStatusError
    mod.APIConnectionError = APIConnectionError
    for name in ("RateLimitError", "InternalServerError", "OverloadedError", "BadRequestError"):
        setattr(mod, name, type(name, (APIStatusError,), {}))
    sys.modules["anthropic"] = mod
    return mod


def reply(stop_reason: str, text: str = ""):
    """One model attempt: what it streamed and why it stopped."""
    return ("reply", stop_reason, text)


def raise_(exc: BaseException):
    """One model attempt that blows up (connection drop, mid-stream error...)."""
    return ("raise", exc, None)


class _FakeStream:
    def __init__(self, stop_reason: str, text: str):
        self._stop, self._text = stop_reason, text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        # Chunked like a real stream, so callers must accumulate.
        return iter([self._text[i:i + 40] for i in range(0, len(self._text), 40)])

    def get_final_message(self):
        usage = types.SimpleNamespace(
            output_tokens=1000, output_tokens_details=types.SimpleNamespace(thinking_tokens=900)
        )
        content = [types.SimpleNamespace(type="text", text=self._text)]
        return types.SimpleNamespace(stop_reason=self._stop, usage=usage, content=content)


class FakeClient:
    """Records each request and which endpoint (`messages` / `beta`) it hit."""

    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []
        self.endpoints: list[str] = []
        self.messages = types.SimpleNamespace(stream=lambda **kw: self._stream("messages", kw))
        self.beta = types.SimpleNamespace(
            messages=types.SimpleNamespace(stream=lambda **kw: self._stream("beta", kw))
        )

    def _stream(self, endpoint: str, kwargs: dict):
        self.calls.append(kwargs)
        self.endpoints.append(endpoint)
        kind, a, b = self._script.pop(0)
        if kind == "raise":
            raise a
        return _FakeStream(a, b)
