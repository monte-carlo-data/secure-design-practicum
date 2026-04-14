"""
Shared AI model configuration for all security pipelines, scripts, and agents.

All model references in this repo resolve through this module so that upgrading
or swapping models is a single-place change.

--- HOW TO SWAP MODELS ---

Option A — No code change (preferred for upgrades):
    Set GitHub org or repo variables:
        CLAUDE_MODEL_PRIMARY  →  e.g. "claude-opus-4-6"
        CLAUDE_MODEL_FAST     →  e.g. "claude-haiku-4-5-20251001"
    All pipelines pick up the new value on the next run.
    Org vars: github.com/organizations/<organization>/settings/variables/actions
    Repo vars: github.com/<organization>/security/settings/variables/actions

Option B — Code change (required for changing the fallback default):
    Edit the default strings below, commit, and merge.
    Use this when you want the default to change for local development
    or when env vars are not set.

--- MODEL TIERS ---

PRIMARY_MODEL — reasoning-heavy tasks (SDD review, PR review, vendor review,
                intel briefing, slack bot responses).
                Anthropic recommends Opus 4.6 for complex reasoning and coding tasks.
                See: https://docs.anthropic.com/en/docs/about-claude/models/overview

FAST_MODEL    — cost/latency-sensitive tasks (e.g. bulk classification, formatting).
                Haiku 4.5 is the fastest model with near-frontier intelligence.
                Not currently used — reserved for future high-volume, low-stakes tasks.

Note: Anthropic offers Claude Mythos (Project Glasswing) as an invite-only model
specifically for defensive cybersecurity workflows. If access is granted, update
PRIMARY_MODEL to the Mythos model ID.
"""

import os

PRIMARY_MODEL: str = os.getenv("CLAUDE_MODEL_PRIMARY", "claude-opus-4-6")
FAST_MODEL: str = os.getenv("CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001")
