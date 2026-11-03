#!/bin/bash

# Setup Linear MCP for Codex and Claude Code
# Docs: https://linear.app/docs/mcp
#
# Notes:
#   - Hosted Linear MCP uses OAuth.
#   - Transport: streamable HTTP at https://mcp.linear.app/mcp. The older SSE
#     endpoint (/sse) breaks OAuth with "Protected resource https://mcp.linear.app/mcp
#     does not match expected https://mcp.linear.app/sse" — Linear advertises its
#     protected resource as /mcp, so the configured URL must match.

set -euo pipefail

LINEAR_MCP_URL="https://mcp.linear.app/mcp"

echo "Checking prerequisites..."
if ! command -v codex >/dev/null 2>&1; then
    echo "  codex : not found, skipping Codex setup."
    SKIP_CODEX=true
else
    echo "  codex : $(codex --version 2>/dev/null || echo 'installed')"
    SKIP_CODEX=false
fi

if ! command -v claude >/dev/null 2>&1; then
    echo "  claude: not found, skipping Claude setup."
    SKIP_CLAUDE=true
else
    echo "  claude: $(claude --version 2>/dev/null || echo 'installed')"
    SKIP_CLAUDE=false
fi

if [[ "$SKIP_CODEX" == "true" && "$SKIP_CLAUDE" == "true" ]]; then
    echo "Error: neither codex nor claude CLI is available."
    exit 1
fi

if [[ "$SKIP_CODEX" == "false" ]]; then
    echo ""
    echo "Configuring Linear MCP for Codex..."

    # Remove existing definition to keep config idempotent.
    codex mcp remove linear >/dev/null 2>&1 || true
    codex mcp add linear --url "$LINEAR_MCP_URL"

    echo ""
    echo "Codex MCP status:"
    codex mcp get linear || true
    codex mcp list || true
fi

echo ""
echo "Configuring Linear MCP for Claude Code..."
if [[ "$SKIP_CLAUDE" == "false" ]]; then
    if [[ -n "${CLAUDE_MCP_SCOPE:-}" ]]; then
        SCOPE_CHOICE="${CLAUDE_MCP_SCOPE}"
    elif [[ -t 0 ]]; then
        echo "Choose Claude scope:"
        echo "  1) local   - only this project (default)"
        echo "  2) project - shared with team via .mcp.json"
        echo "  3) user    - available across all your projects"
        read -rp "Choice [1-3]: " SCOPE_CHOICE
    else
        SCOPE_CHOICE="1"
    fi

    case "${SCOPE_CHOICE:-1}" in
        project) SCOPE="project" ;;
        user) SCOPE="user" ;;
        local) SCOPE="local" ;;
        2) SCOPE="project" ;;
        3) SCOPE="user" ;;
        *) SCOPE="local" ;;
    esac

    claude mcp remove linear --scope "$SCOPE" >/dev/null 2>&1 || true
    claude mcp add --transport http --scope "$SCOPE" linear "$LINEAR_MCP_URL"

    echo ""
    echo "Claude MCP status:"
    claude mcp get linear || true
    claude mcp list || true
    echo "Run /mcp inside Claude Code to complete OAuth for Linear."
fi

echo ""
echo "Linear MCP setup complete."
echo "Notes:"
echo "  - Hosted Linear MCP uses OAuth."
echo "  - Your access is limited by your Linear user/workspace permissions."
echo "  - To troubleshoot Codex auth, run: codex mcp logout linear && codex mcp login linear"
echo "  - If Codex fails to connect, enable RMCP in ~/.codex/config.toml (feature name varies by Codex version)."
