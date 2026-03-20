#!/bin/bash

# Setup Notion MCP for Codex and Claude Code
# Docs: https://developers.notion.com/docs/get-started-with-mcp
#
# Notes:
#   - Hosted Notion MCP uses OAuth; NOTION_TOKEN is not used for this flow.
#   - URL: https://mcp.notion.com/mcp

set -euo pipefail

NOTION_MCP_URL="https://mcp.notion.com/mcp"

echo "Configuring Notion MCP for Codex..."
if ! command -v codex >/dev/null 2>&1; then
    echo "  codex CLI not found, skipping. Run .setup/vscode-codex.sh first to enable Codex support."
else
    echo "  codex: $(codex --version 2>/dev/null || echo 'installed')"

    # Remove existing definition to keep config idempotent.
    codex mcp remove notion >/dev/null 2>&1 || true
    codex mcp add notion --url "$NOTION_MCP_URL"

    echo ""
    echo "Codex MCP status:"
    codex mcp get notion || true
    codex mcp list || true
fi

echo ""
echo "Configuring Notion MCP for Claude Code..."
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

    claude mcp remove notion --scope "$SCOPE" >/dev/null 2>&1 || true
    claude mcp add --transport http --scope "$SCOPE" notion "$NOTION_MCP_URL"

    echo ""
    echo "Claude MCP status:"
    claude mcp get notion || true
    claude mcp list || true
    echo "Run /mcp inside Claude Code to complete OAuth for Notion."
fi

echo ""
echo "Notion MCP setup complete."
echo "Notes:"
echo "  - Hosted Notion MCP uses OAuth and does not use NOTION_TOKEN."
echo "  - Your access is limited by your Notion user/workspace permissions."
echo "  - To troubleshoot, run: codex mcp logout notion && codex mcp login notion"
