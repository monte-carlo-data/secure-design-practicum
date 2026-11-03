"""
Shared AI model configuration for all security pipelines, scripts, and agents.

All model references in this repo resolve through this module so that upgrading,
swapping, or *failing over between* models/providers is a single-place change.

This module exposes two layers:

  1. Backward-compatible string constants (PRIMARY_MODEL, FAST_MODEL, ...).
     Existing consumers that build their own `anthropic.Anthropic` client and
     call `client.messages.create(model=ai_config.PRIMARY_MODEL, ...)` keep
     working with no change. These resolve from the *active provider*.

  2. A provider-aware layer (PROVIDERS, complete()) so the config supports
     multiple AI providers/backends (Claude, Codex/OpenAI, and future ones)
     with automatic, priority-ordered fallback. New or migrated consumers
     should call `ai_config.complete(...)` instead of building their own
     client, which gets them transparent failover for free.

--- HOW TO SWAP MODELS ---

Option A — No code change (preferred for upgrades):
    Set GitHub org or repo variables:
        CLAUDE_MODEL_PRIMARY  →  e.g. "claude-opus-5-5"
        CLAUDE_MODEL_FAST     →  e.g. "claude-sonnet-5"
    All pipelines pick up the new value on the next run.
    Org vars: github.com/organizations/<organization>/settings/variables/actions
    Repo vars: github.com/<organization>/security/settings/variables/actions

Option B — Code change (required for changing a default):
    Edit the default strings / provider table below, commit, and merge.

--- PROVIDERS & FALLBACK ---

A "provider" is a backend that can answer a chat/completion call. Each provider
declares its SDK adapter, the env var holding its credential, an optional
base-URL override, and its per-tier model IDs. Providers are tried in
PROVIDER_PRIORITY order; if the active provider's call fails for a *transient or
config* reason (rate limit, outage, missing credential, deprecated model), the
next provider in the list is tried automatically. The first provider in the
priority list that has a usable credential is the "active" provider whose model
IDs populate the backward-compatible PRIMARY_MODEL / FAST_MODEL constants.

  - Provider selection is GLOBAL by default (PROVIDER_PRIORITY, env-overridable)
    with an optional PER-CALL override on complete(provider=..., tier=...).
  - Fallback is AUTOMATIC and ON by default. Disable per-call with
    complete(..., fallback=False) when a caller must pin one provider.
  - Each fallback is logged (stderr + optional Slack webhook) so silent
    provider drift is observable.

Adding a new provider is config-only: append an entry to PROVIDERS and add it to
PROVIDER_PRIORITY. No schema rework, no consumer change.

--- MODEL TIERS ---

PRIMARY_MODEL — reasoning-heavy tasks (SDD review, PR review, vendor review,
                intel briefing, slack bot responses). Claude default: Opus 5.5,
                which is both cheaper and more capable than Opus 5 and keeps the
                same request surface (adaptive thinking, effort tiers). Earlier
                Opus / Fable generations remain valid choices via the
                CLAUDE_MODEL_PRIMARY env var / org variable.
                See: https://platform.claude.com/docs/en/about-claude/models/overview

FAST_MODEL    — cost/latency-sensitive tasks (e.g. bulk classification, formatting).
                Claude default: Sonnet 5, near-Opus quality at Sonnet cost;
                preferred over Haiku for more capability on the high-volume,
                lower-stakes tier.

                On "retires no sooner than" dates in Anthropic's model table:
                these are FLOORS, not schedules. A model is only actually going
                away once Anthropic marks it Deprecated and assigns a real
                retirement date (with >= 60 days' notice). Don't read a
                near-term floor as a deadline.
                See https://platform.claude.com/docs/en/about-claude/model-deprecations

PROXY TIER ALIASES — when routing through an optional AI proxy (i.e.
                ANTHROPIC_BASE_URL is set), model_for()/complete() request the
                proxy TIER ALIAS instead of the concrete model ID, so the proxy
                owns the tier->model mapping and can re-point a tier with zero
                client change. When ANTHROPIC_BASE_URL is unset (direct
                Anthropic / CI), the concrete IDs are used (Anthropic doesn't
                know the aliases). Register the aliases in your proxy's model
                config; onboarding a consumer to the proxy is just two env vars
                (ANTHROPIC_BASE_URL + the credential the proxy expects).

APPSEC_MODEL  — application-security triage judgment for the vulnerability-
                triage operator. HARD-PINNED to PRIMARY_MODEL for now: triage
                runs on the primary model and cannot drift, even via env var. A
                specialized AppSec model is something to build up over time,
                gated by an eval harness (a candidate is promoted only once it
                beats the frozen baseline — accuracy >= baseline AND
                false-positive-miss <= baseline); at that point the pin becomes
                an env-overridable default again. The symbol exists so every
                triage entry point resolves its model through one place. Paired
                with APPSEC_SYSTEM_PROMPT at the bottom of this file.

Note: Anthropic offers Claude Mythos (Project Glasswing) as an invite-only model
specifically for defensive cybersecurity workflows. Where that access is
available, a Mythos model ID may be used for PRIMARY_MODEL or APPSEC_MODEL.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List, NamedTuple, Optional

# ----------------------------------------------------------------------------
# Tiers
# ----------------------------------------------------------------------------
# Logical tiers a caller can request. Each provider maps every tier to one of
# its own model IDs. Keep this list small and stable — it is the cross-provider
# contract.
PRIMARY = "primary"
FAST = "fast"
TIERS = (PRIMARY, FAST)


# ----------------------------------------------------------------------------
# Provider registry
# ----------------------------------------------------------------------------
# Each provider entry:
#   adapter      — which SDK adapter to use ("anthropic" | "openai")
#   credential_env — env var that must be non-empty for this provider to be usable
#   base_url_env — optional env var holding a base-URL override (proxy/gateway)
#   models       — per-tier model IDs, each independently env-overridable
#
# Model IDs read from env first (so a single org/repo variable can re-pin a
# model without a code change), then fall back to the literal default.
def _model(env_var: str, default: str) -> str:
    return os.getenv(env_var, default)


PROVIDERS: Dict[str, Dict[str, Any]] = {
    # Claude (Anthropic) — the default/primary provider for all existing
    # pipelines. Credentials come from the environment: when routing through an
    # optional AI proxy, the deployment injects ANTHROPIC_API_KEY (whatever
    # credential the proxy expects) and ANTHROPIC_BASE_URL; locally/CI the real
    # key is used and the base URL is unset.
    "claude": {
        "adapter": "anthropic",
        "credential_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        # Provider default endpoint. make_client() passes this explicitly when the
        # base_url env is unset/empty, so the SDK never receives "" (which it does
        # NOT coerce to the default — see make_client docstring).
        "default_base_url": "https://api.anthropic.com",
        # Verify a model ID is reachable on a live 1-token POST /v1/messages
        # before pinning it here; check the retirement floor in the model table.
        "models": {
            PRIMARY: _model("CLAUDE_MODEL_PRIMARY", "claude-opus-5-5"),
            FAST: _model("CLAUDE_MODEL_FAST", "claude-sonnet-5"),
        },
        # Proxy tier ALIASES: when routing through an AI proxy (base_url set),
        # request the proxy's tier alias instead of the concrete model ID, so
        # the proxy owns the tier->model mapping and can re-point a tier with
        # zero client change. When base_url is unset (direct Anthropic / CI),
        # the concrete IDs above are used — Anthropic doesn't know the aliases.
        # The proxy should also register the concrete IDs, so a direct-ID
        # request still works through it; the alias is preferred so the tier
        # contract is what's exercised. Register these names in your proxy's
        # model config (or rename them here to match what it already serves).
        "proxy_aliases": {
            PRIMARY: "primary",
            FAST: "fast",
        },
    },
    # Codex (OpenAI) — secondary provider. Live adapter; requires the `openai`
    # SDK and an OPENAI_API_KEY secret to be provisioned. Until that key is set,
    # this provider is simply "unusable" and is skipped by the resolver, so
    # adding it here is safe and changes nothing for current consumers.
    #
    # NOTE on model IDs: the OpenAI adapter calls the v1/chat/completions
    # endpoint, so these MUST be chat-capable models. The `*-codex` IDs
    # (gpt-5.1-codex etc.) are Responses-API-only and 404 on chat/completions —
    # do NOT use them here. The general chat models are the right fallback.
    #
    # Tiering is deliberately cost-shaped rather than flagship — codex is the
    # FALLBACK provider, only reached when Claude is already failing, so the
    # top-end model is not worth pinning here; set OPENAI_MODEL_PRIMARY to
    # override for a one-off. Verify a model ID is reachable on a live 1-token
    # POST /v1/chat/completions with your key before pinning it.
    #
    # Security-specialized OpenAI models (e.g. the `*-cyber` IDs) are gated
    # separately from a general API key and may 404 ("model does not exist or
    # you do not have access to it"). Re-check access before pinning one.
    "codex": {
        "adapter": "openai",
        "credential_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1",
        "models": {
            PRIMARY: _model("OPENAI_MODEL_PRIMARY", "gpt-6-sol"),
            FAST: _model("OPENAI_MODEL_FAST", "gpt-6-luna"),
        },
    },
}

# Global provider preference order. The first provider in this list with a
# usable credential becomes the "active" provider; the rest are fallbacks, tried
# left-to-right. Override globally with the AI_PROVIDER_PRIORITY env var
# (comma-separated, e.g. "codex,claude").
_DEFAULT_PRIORITY = ["claude", "codex"]
PROVIDER_PRIORITY: List[str] = [
    p.strip()
    for p in os.getenv("AI_PROVIDER_PRIORITY", ",".join(_DEFAULT_PRIORITY)).split(",")
    if p.strip() in PROVIDERS
] or list(_DEFAULT_PRIORITY)

# Optional Slack webhook for fallback alerting. When set, a fallback event posts
# a one-line notice. Logging to stderr always happens regardless.
_FALLBACK_ALERT_WEBHOOK = "AI_FALLBACK_SLACK_WEBHOOK"


# ----------------------------------------------------------------------------
# Resolver helpers
# ----------------------------------------------------------------------------
def provider_is_usable(name: str) -> bool:
    """A provider is usable if it exists and its credential env var is set."""
    spec = PROVIDERS.get(name)
    if not spec:
        return False
    return bool(os.getenv(spec["credential_env"], "").strip())


def active_provider() -> str:
    """The first provider in priority order that has a usable credential.

    Falls back to the first priority entry even if no credential is set, so the
    module always imports cleanly and the string constants below are always
    populated (a call will then surface a clear credential error, not an
    ImportError or KeyError)."""
    for name in PROVIDER_PRIORITY:
        if provider_is_usable(name):
            return name
    return PROVIDER_PRIORITY[0]


def _routing_through_proxy(spec: Dict[str, Any]) -> bool:
    """True if this provider is configured to route through a gateway/proxy —
    i.e. its base-URL env var is set to a non-empty value."""
    return bool(os.getenv(spec.get("base_url_env", ""), "").strip())


def routing_through_proxy(provider: Optional[str] = None) -> bool:
    """Public: True if ``provider`` (default: active) routes through a proxy.

    Consumers that build a proxy-bypass ('fail open to direct') path need to
    know whether the normal client is proxied — if it isn't, there is nothing
    to fall back to. Wraps the by-spec helper so callers pass a provider name."""
    return _routing_through_proxy(PROVIDERS[provider or active_provider()])


def model_for(tier: str, provider: Optional[str] = None) -> str:
    """Resolve a tier ('primary'/'fast') to the model name to request.

    When routing through an AI proxy (the provider's base_url is set) and the
    provider declares `proxy_aliases`, return the proxy TIER ALIAS so the proxy
    owns the tier->model mapping. Otherwise return the concrete model ID. This
    keeps direct/CI use (no base_url) unchanged while making proxied traffic
    use the proxy's tier contract."""
    name = provider or active_provider()
    spec = PROVIDERS[name]
    if tier not in spec["models"]:
        raise ValueError(
            f"Provider '{name}' has no model configured for tier '{tier}'. "
            f"Configured tiers: {sorted(spec['models'])}"
        )
    aliases = spec.get("proxy_aliases") or {}
    if tier in aliases and _routing_through_proxy(spec):
        return aliases[tier]
    return spec["models"][tier]


def make_client(provider: Optional[str] = None, **overrides: Any) -> Any:
    """Build a provider SDK client with credential + base-URL resolved from env.

    Use this instead of constructing ``anthropic.Anthropic(...)`` directly. It
    handles the empty-base-URL footgun: a GitHub Actions env of
    ``ANTHROPIC_BASE_URL: ${{ vars.ANTHROPIC_BASE_URL }}`` with the variable
    UNSET injects the literal empty string ``""``, which the anthropic SDK does
    NOT treat as "unset" — it passes ``base_url=""`` to httpx, which raises
    ``UnsupportedProtocol`` (URL missing http(s)://). We only pass ``base_url``
    when it's non-empty, so unset == direct-to-provider and set == proxy.

    Passing through the proxy (base_url set) is transparent here — the caller
    still gets a normal SDK client; only the endpoint changes. Pair with
    ``model_for(tier)`` so the tier alias is requested when proxied.

    ``overrides`` are forwarded to the SDK constructor (e.g. ``default_headers``,
    ``timeout``) and win over the resolved defaults.

    IMPORTANT — why we pass an EXPLICIT base_url instead of omitting it:
    ``anthropic.Anthropic.__init__`` only falls back to the api.anthropic.com
    default when ``base_url is None`` (env var ABSENT). A SET-BUT-EMPTY env
    (``ANTHROPIC_BASE_URL=""``, which a GitHub ``${{ vars.X }}`` with X unset
    injects) is ``""`` — not ``None`` — so the SDK skips the default and passes
    ``""`` to httpx, which raises ``UnsupportedProtocol``. Omitting the kwarg
    does NOT help: the SDK re-reads the env itself. So we resolve the value here
    and always pass a non-empty URL: the env value when set, else the provider
    default. This makes ``""`` behave as "direct-to-provider", not a crash.
    """
    name = provider or active_provider()
    spec = PROVIDERS[name]
    kwargs: Dict[str, Any] = {"api_key": os.getenv(spec["credential_env"])}
    base_url = os.getenv(spec.get("base_url_env", ""), "").strip()
    # Always pass an explicit, non-empty base_url (see docstring): resolved value
    # when set, else the provider's real default — never let the SDK see "".
    kwargs["base_url"] = base_url or spec["default_base_url"]
    kwargs.update(overrides)
    if name == "claude":
        import anthropic
        return anthropic.Anthropic(**kwargs)
    if name == "codex":
        import openai
        return openai.OpenAI(**kwargs)
    raise ValueError(f"make_client: unknown provider {name!r}")


def _fallback_chain(provider: Optional[str], fallback: bool) -> List[str]:
    """Ordered list of providers to attempt for a call."""
    if provider:
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'. Known: {sorted(PROVIDERS)}")
        if not fallback:
            return [provider]
        # explicit provider first, then the rest of the priority order
        return [provider] + [p for p in PROVIDER_PRIORITY if p != provider]
    if not fallback:
        return [active_provider()]
    # active provider first, then remaining priority order
    chain = [active_provider()]
    chain += [p for p in PROVIDER_PRIORITY if p != chain[0]]
    return chain


# ----------------------------------------------------------------------------
# Backward-compatible string constants
# ----------------------------------------------------------------------------
# Resolve from the active provider so that, e.g., switching the global priority
# to "codex" automatically re-points every existing consumer that references
# these constants. For the default config:
# PRIMARY_MODEL == "claude-opus-5-5", FAST_MODEL == "claude-sonnet-5".
PRIMARY_MODEL: str = model_for(PRIMARY)
FAST_MODEL: str = model_for(FAST)


# ----------------------------------------------------------------------------
# Reading Claude responses (Opus 5.5 thinking)
# ----------------------------------------------------------------------------
# PRIMARY_MODEL thinks whenever it decides to (thinking can't be disabled on
# Opus 5.5), so the first content block is often a ThinkingBlock with no
# .text — reading it as text raises AttributeError intermittently. Thinking
# tokens also count against max_tokens, so xhigh/high effort needs a budget
# with room for both. Read text with response_text(); make large-budget calls
# with create_message(), which streams (the SDK refuses large max_tokens
# without it) and reports a budget-exhausted reply.

def response_text(message: Any) -> str:
    """Concatenated text of a Claude response, skipping thinking blocks."""
    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )


def create_message(client: Any, **kwargs: Any) -> Any:
    """client.messages.create(**kwargs), streamed; returns the final Message.

    Warns on stderr when stop_reason is max_tokens — the reply is empty or
    truncated and callers should treat it as unusable.
    """
    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "max_tokens":
        print(
            f"[ai_config] {kwargs.get('model')} hit max_tokens={kwargs.get('max_tokens')} — "
            "the reply is empty or truncated (thinking shares this budget)",
            file=sys.stderr,
        )
    return message


def extract_json_object(text: str) -> Dict[str, Any]:
    """Decode the first JSON object in a reply, preferring a ```json block.

    raw_decode from the opening brace, not slicing to the next fence: a ```
    inside a JSON string (a code snippet in a finding) would cut the object in
    half. Raises json.JSONDecodeError when there is no decodable object.
    """
    fence = text.find("```json")
    start = text.find("{", fence + len("```json") if fence >= 0 else 0)
    if start < 0:
        raise json.JSONDecodeError("no JSON object in model output", text, 0)
    result, _ = json.JSONDecoder().raw_decode(text, start)
    return result


def is_transient_api_error(exc: Exception) -> bool:
    """Anthropic failures worth retrying: dropped connections, 429/5xx/529,
    and error events that arrive mid-stream (overloaded_error / api_error),
    which the SDK raises as a bare APIStatusError carrying the stream's own
    200 status. A 4xx (bad request, auth) fails identically on retry."""
    import anthropic

    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError,
                        anthropic.InternalServerError, anthropic.OverloadedError)):
        return True
    return isinstance(exc, anthropic.APIStatusError) and getattr(exc, "status_code", None) == 200


# Beta for `fallbacks="default"`: on a safety-classifier refusal the API re-runs
# the request server-side on the model Anthropic routes that refusal category to.
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class JsonReply(NamedTuple):
    data: Optional[Dict[str, Any]]  # parsed object, or None when no attempt produced one
    stop_reason: Optional[str]      # last attempt's stop_reason
    text: str                       # last attempt's streamed text


def stream_json_reply(client: Any, *, attempts: int = 3, backoff_seconds: float = 15,
                      budget_retry_effort: Optional[str] = None, **kwargs: Any) -> JsonReply:
    """Stream a request whose reply is one JSON object, retrying what's recoverable.

    Retried: output budget exhausted (stop_reason=max_tokens — the JSON is
    missing or cut off, so a partial object is never parsed), empty or
    unparseable text, and transient API errors. Returned at once: a refusal
    (data=None, stop_reason="refusal" — a classifier decision; send
    ``fallbacks`` to have it re-run server-side). Raised: a non-transient API
    error, or a transient one on the last attempt. Requests carrying ``betas``
    go to the beta endpoint. Callers decide how to fail closed on data=None.

    ``budget_retry_effort``: after an attempt stops on max_tokens, later
    attempts run at this effort. Retrying an overrun at the same effort tends
    to overrun again (a review that thinks its way to the budget ceiling once
    will usually do so on the retry too).
    """
    import anthropic

    stream_fn = client.beta.messages.stream if "betas" in kwargs else client.messages.stream
    stop_reason: Optional[str] = None
    text = ""
    for attempt in range(1, attempts + 1):
        print(f"Model attempt {attempt}/{attempts} (model={kwargs.get('model')}, "
              f"max_tokens={kwargs.get('max_tokens')}, "
              f"effort={(kwargs.get('output_config') or {}).get('effort', 'default')})")
        try:
            text = ""
            with stream_fn(**kwargs) as stream:
                for chunk in stream.text_stream:
                    text += chunk
                final = stream.get_final_message()
        except anthropic.APIError as e:
            if not is_transient_api_error(e) or attempt == attempts:
                raise
            print(f"  transient API error ({type(e).__name__}: {e}); retrying")
            time.sleep(backoff_seconds * attempt)
            continue

        stop_reason = final.stop_reason
        usage = getattr(final, "usage", None)
        details = getattr(usage, "output_tokens_details", None)
        # Logged every attempt so a failure is diagnosable from the run log alone.
        print(f"  stop_reason={stop_reason} output_tokens={getattr(usage, 'output_tokens', '?')} "
              f"thinking_tokens={getattr(details, 'thinking_tokens', '?')} text_chars={len(text)}")
        if stop_reason == "refusal":
            return JsonReply(None, stop_reason, text)
        if stop_reason == "max_tokens":
            if budget_retry_effort:
                kwargs["output_config"] = {**(kwargs.get("output_config") or {}),
                                           "effort": budget_retry_effort}
            continue
        if text.strip():
            try:
                return JsonReply(extract_json_object(text), stop_reason, text)
            except json.JSONDecodeError as e:
                print(f"  reply could not be parsed as JSON ({e})")
    return JsonReply(None, stop_reason, text)


# ----------------------------------------------------------------------------
# Unified, fallback-aware completion
# ----------------------------------------------------------------------------
class AIResult:
    """Provider-agnostic result of a completion call."""

    def __init__(self, *, text: str, provider: str, model: str, raw: Any):
        self.text = text
        self.provider = provider
        self.model = model
        self.raw = raw  # the underlying SDK response, if a caller needs it

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"AIResult(provider={self.provider!r}, model={self.model!r}, len(text)={len(self.text)})"


def _log_fallback(from_provider: str, to_provider: str, tier: str, err: Exception) -> None:
    msg = (
        f"[ai_config] provider '{from_provider}' failed for tier '{tier}' "
        f"({type(err).__name__}: {err}); falling back to '{to_provider}'"
    )
    print(msg, file=sys.stderr)
    webhook = os.getenv(_FALLBACK_ALERT_WEBHOOK, "").strip()
    if webhook:
        try:
            import json
            import urllib.request

            req = urllib.request.Request(
                webhook,
                data=json.dumps({"text": msg}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)  # noqa: S310 - operator-configured webhook
        except Exception as alert_err:  # never let alerting break the call path
            print(f"[ai_config] fallback alert failed: {alert_err}", file=sys.stderr)


def _call_anthropic(_spec: Dict[str, Any], model: str, prompt: str, max_tokens: int,
                    system: Optional[str], extra: Dict[str, Any]) -> AIResult:
    # _spec is unused (client build moved to make_client) but the dispatch in
    # _CALLERS calls every adapter with the same signature — keep it.
    client = make_client("claude")

    create_kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        create_kwargs["system"] = system
    create_kwargs.update(extra)  # pass-through, e.g. output_config={"effort": "high"}

    # Streamed: the SDK refuses a large non-streaming max_tokens (the PR
    # reviewer asks for 64k), and thinking shares that budget.
    resp = create_message(client, **create_kwargs)
    return AIResult(text=response_text(resp), provider="claude", model=model, raw=resp)


def _call_openai(spec: Dict[str, Any], model: str, prompt: str, max_tokens: int,
                system: Optional[str], extra: Dict[str, Any]) -> AIResult:
    # NOTE: GPT-5.x are reasoning models — they spend max_completion_tokens on
    # internal reasoning before emitting visible output. A very small token
    # budget can therefore return empty .text on a successful (non-error) call.
    # complete()'s default of 4096 is ample; callers requesting the codex tier
    # with a tight budget should raise it. Also: the OpenAI adapter uses the
    # chat/completions endpoint, so the configured model must be chat-capable
    # (the *-codex IDs are Responses-API-only — see the PROVIDERS note).
    from openai import OpenAI

    kwargs: Dict[str, Any] = {"api_key": os.getenv(spec["credential_env"])}
    base_url = os.getenv(spec.get("base_url_env", ""), "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    create_kwargs: Dict[str, Any] = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": messages,
    }
    create_kwargs.update(extra)

    resp = client.chat.completions.create(**create_kwargs)
    text = resp.choices[0].message.content or ""
    return AIResult(text=text, provider="codex", model=model, raw=resp)


# OpenAI through an AI proxy that fronts both providers: the proxy supplies the
# OpenAI credential on /v1/responses, so a job that already holds
# ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY reaches OpenAI with no OPENAI_API_KEY.
# Opt in per call with complete(..., provider="codex", transport=TRANSPORT_ANTHROPIC_PROXY).
TRANSPORT_ANTHROPIC_PROXY = "anthropic_proxy"
PROXY_RESPONSES_TIMEOUT_SECONDS = 1800


def _call_openai_responses_via_proxy(spec: Dict[str, Any], model: str, prompt: str,
                                     max_tokens: int, system: Optional[str],
                                     extra: Dict[str, Any]) -> AIResult:
    """POST a Responses API request to {ANTHROPIC_BASE_URL}/v1/responses.

    Bearer is ANTHROPIC_API_KEY; OPENAI_API_KEY is never read. ``raw`` is the
    decoded response dict (status / incomplete_details / output)."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            "ANTHROPIC_BASE_URL is unset: the codex provider reaches OpenAI through "
            "the AI proxy at {ANTHROPIC_BASE_URL}/v1/responses and has no direct path"
        )
    body: Dict[str, Any] = {"model": model, "input": prompt, "max_output_tokens": max_tokens}
    if system:
        body["instructions"] = system
    body.update(extra)
    req = urllib.request.Request(
        f"{base_url}/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.getenv('ANTHROPIC_API_KEY', '')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=PROXY_RESPONSES_TIMEOUT_SECONDS) as resp:  # noqa: S310 - operator-configured proxy
        data = json.loads(resp.read().decode("utf-8"))
    text = data.get("output_text") or "".join(
        part.get("text", "")
        for item in data.get("output") or []
        for part in item.get("content") or []
        if part.get("type") == "output_text"
    )
    return AIResult(text=text, provider="codex", model=model, raw=data)


_ADAPTERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


def complete(
    prompt: str,
    *,
    tier: str = PRIMARY,
    provider: Optional[str] = None,
    fallback: bool = True,
    max_tokens: int = 4096,
    system: Optional[str] = None,
    transport: Optional[str] = None,
    **extra: Any,
) -> AIResult:
    """Provider-agnostic, fallback-aware completion.

    Args:
        prompt:     the user prompt.
        tier:       logical model tier ('primary' or 'fast').
        provider:   pin a specific provider; default uses the active provider.
                    A per-call override of the global default.
        fallback:   if True (default), automatically try the next provider in
                    priority order on a provider-level failure. Set False to
                    pin a single provider with no failover.
        max_tokens: max output tokens.
        system:     optional system prompt.
        transport:  TRANSPORT_ANTHROPIC_PROXY sends codex calls as a Responses
                    API request to {ANTHROPIC_BASE_URL}/v1/responses with
                    ANTHROPIC_API_KEY as the bearer (no OPENAI_API_KEY needed).
                    Default None keeps every provider's normal transport.
        **extra:    adapter-specific pass-through kwargs (e.g. for Anthropic,
                    output_config={"effort": "high"}). Only forwarded to the
                    adapter that accepts them; mismatched kwargs surface as a
                    normal provider error and trigger fallback if enabled.

    Returns:
        AIResult with normalized .text plus .provider/.model/.raw.

    Raises:
        RuntimeError if every provider in the chain fails (or none is usable).
    """
    if tier not in TIERS:
        raise ValueError(f"Unknown tier '{tier}'. Known tiers: {TIERS}")

    chain = _fallback_chain(provider, fallback)
    errors: List[str] = []
    prev_provider: Optional[str] = None
    prev_error: Optional[Exception] = None

    if transport not in (None, TRANSPORT_ANTHROPIC_PROXY):
        raise ValueError(f"Unknown transport {transport!r}")

    for name in chain:
        via_proxy = transport == TRANSPORT_ANTHROPIC_PROXY and name == "codex"
        credential_env = "ANTHROPIC_API_KEY" if via_proxy else PROVIDERS[name]["credential_env"]
        if not os.getenv(credential_env, "").strip():
            err = RuntimeError(f"no credential ({credential_env} unset)")
            errors.append(f"{name}: {err}")
            prev_provider, prev_error = name, err
            continue
        spec = PROVIDERS[name]
        model = model_for(tier, provider=name)
        adapter = _call_openai_responses_via_proxy if via_proxy else _ADAPTERS[spec["adapter"]]
        try:
            result = adapter(spec, model, prompt, max_tokens, system, extra)
            if prev_provider is not None and prev_error is not None:
                _log_fallback(prev_provider, name, tier, prev_error)
            return result
        except Exception as err:  # noqa: BLE001 - we intentionally fail over on any provider error
            errors.append(f"{name} ({model}): {type(err).__name__}: {err}")
            prev_provider, prev_error = name, err
            continue

    raise RuntimeError(
        "ai_config.complete: all providers failed or unavailable.\n"
        + "\n".join(f"  - {e}" for e in errors)
    ) from prev_error  # callers can classify the last failure (e.g. transient)


# --- APPSEC TIER -------------------------------------------------------------
#
# The vulnerability-triage operator's AppSec model tier. For now this is
# HARD-PINNED to PRIMARY_MODEL — triage runs on the primary model and cannot
# drift to anything else, even if an env var is set. A specialized AppSec model
# is something to build up over time (gated by an eval harness: a candidate may
# only be promoted once it beats the frozen baseline — accuracy >= baseline AND
# false-positive-miss <= baseline). When that day comes, switch this back to
#     APPSEC_MODEL = os.getenv("CLAUDE_MODEL_APPSEC", PRIMARY_MODEL)
# to re-enable the single-switch override. Until then it stays pinned.
#
# This symbol (with APPSEC_SYSTEM_PROMPT) is the single source of the triage
# operator's model + judgment across every disposition entry point.
APPSEC_MODEL: str = PRIMARY_MODEL

APPSEC_SYSTEM_PROMPT: str = """You are your organization's vulnerability-triage operator. \
You are given a single security finding (from a scanner such as Aikido or Wiz) together with the \
context that was gathered for it — finding metadata, and where available the affected source code, \
dependency classification (direct vs transitive), runtime/EOL data, or container reachability \
notes. Your job is to make ONE disposition decision and nothing else.

Disposition discipline:
- FALSE_POSITIVE: the finding is not actionable as a security fix. This covers (a) the flagged \
pattern being safe by construction (e.g. a custom Loader extending yaml.SafeLoader, parameterized \
queries that merely look like concatenation), (b) test/fixture-only code with no production \
equivalent, (c) input to the sink being fully internal / not attacker-controlled, AND \
(d) there being no fix to apply or no deployed artifact at risk (e.g. a terminated/stopped \
instance, or a transitive dependency that is never invoked and has no available upgrade).
- REAL_VULN: the finding is a genuine, actionable item to remediate. Decisive test: if a fixed \
version (or config change) EXISTS and the vulnerable package/code is present in a DEPLOYED or \
SHIPPED artifact, it is REAL_VULN — even when current reachability is low or the vulnerable path \
is not presently exercised. In that case set reachability to LOW_EXPLOITABILITY (direct dep, \
fix available, path not exercised) or TRANSITIVE_ONLY, and treat it as a lower-PRIORITY real \
finding (a routine dependency bump), NOT a false positive. Reserve FALSE_POSITIVE for findings \
that are safe-by-construction or have nothing to fix. When genuinely unsure, prefer REAL_VULN.
- EOL_SNOOZE: the finding is an end-of-life / obsolete-runtime flag whose published EOL date is \
still in the FUTURE. Do not treat a not-yet-EOL runtime as a live vulnerability; it is snoozed \
until shortly before EOL. A past EOL date is a REAL_VULN.
- EXCEPTION: the finding is real but the owner has an approved/justified inability to remediate \
within SLA. Only use this when the context explicitly indicates an exception path.

Hard rules:
- The costliest error is calling a REAL_VULN a FALSE_POSITIVE. When the evidence is genuinely \
balanced, do not choose FALSE_POSITIVE.
- Decide ONLY from the context provided. Do not invent code, CVE details, or runtime facts that \
are not present. If the context is insufficient to rule a finding safe, it is not a false positive.
- You are making a disposition, not taking an action. Never assume a suppression has occurred."""
