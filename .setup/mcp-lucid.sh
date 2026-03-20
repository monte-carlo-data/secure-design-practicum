#!/bin/bash

# Setup Lucid MCP for Codex and Claude Code
# Docs: https://help.lucid.co/hc/en-us/articles/42578801807508-Integrate-Lucid-with-AI-tools-using-the-Lucid-MCP-server
#
# Notes:
#   - Lucid MCP uses OAuth and streamable HTTP transport.
#   - URL: https://mcp.lucid.app/mcp

set -euo pipefail

LUCID_MCP_URL="https://mcp.lucid.app/mcp"

echo "Checking prerequisites..."
if ! command -v codex >/dev/null 2>&1; then
    echo "  codex: not found, skipping Codex setup."
    SKIP_CODEX=true
else
    echo "  codex: $(codex --version 2>/dev/null || echo 'installed')"
    SKIP_CODEX=false
fi

if [[ "$SKIP_CODEX" == "false" ]]; then
    echo ""
    echo "Configuring Lucid MCP for Codex..."

    # Remove existing definition to keep config idempotent.
    codex mcp remove lucid >/dev/null 2>&1 || true
    codex mcp add lucid --url "$LUCID_MCP_URL"

    echo ""
    echo "Codex MCP status:"
    codex mcp get lucid || true
    codex mcp list || true
fi

echo ""
echo "Configuring Lucid MCP for Claude Code..."
if ! command -v claude >/dev/null 2>&1; then
    echo "Claude CLI not found, skipping Claude setup."
else
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

    claude mcp remove lucid --scope "$SCOPE" >/dev/null 2>&1 || true
    claude mcp add --transport http --scope "$SCOPE" lucid "$LUCID_MCP_URL"

    echo ""
    echo "Claude MCP status:"
    claude mcp get lucid || true
    claude mcp list || true
    echo "Run /mcp inside Claude Code to complete OAuth for Lucid."
fi

echo ""
echo "Lucid MCP setup complete."
echo "Notes:"
echo "  - Lucid MCP uses OAuth and streamable HTTP transport."
echo "  - Your access is limited by your Lucid user/account permissions."
echo "  - If this account is Team or Enterprise, admin can disable MCP access in Security > Feature controls."
echo "  - If Codex auth fails, run: codex mcp logout lucid && codex mcp login lucid"
echo "  - If your client does not support HTTP transport, use mcp-remote:"
echo "      npx -y mcp-remote https://mcp.lucid.app/mcp"
