#!/bin/bash

# Bootstrap a macOS dev machine for the security review practicum.
# Installs Homebrew, core tools, and AI assistants needed to run
# the SDD and PR review workflows.

set -euo pipefail

# Download-inspect-run helper. Replaces blind `bash -c "$(curl …)"` pipe-to-shell —
# the policy is "download the script first, inspect it, then run it". Fetches to a
# temp file, prints its sha256 and a head preview so the operator can eyeball it,
# prompts (default: no), then runs it. Pinning a fixed hash is deliberately avoided:
# the Homebrew installer updates upstream continuously, so a pinned digest would
# break on every upstream change; the gate here is human inspection, not a brittle pin.
fetch_inspect_run() {  # usage: fetch_inspect_run <url> [interpreter]
  local url="$1" interp="${2:-bash}" tmp ans
  tmp="$(mktemp)"
  echo "Fetching installer: $url"
  curl -fsSL "$url" -o "$tmp" || { echo "  download failed: $url" >&2; rm -f "$tmp"; return 1; }
  echo "  sha256: $(shasum -a 256 "$tmp" | awk '{print $1}')"
  echo "  --- first 20 lines ---"; head -20 "$tmp"; echo "  --- (review the full file: $tmp) ---"
  if [[ -t 0 ]]; then
    read -r -p "Run this installer with $interp? [y/N] " ans
  else
    ans="N"   # non-interactive: skip (the inspection gate needs a TTY)
  fi
  if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    "$interp" "$tmp"
  else
    echo "  skipped: $url"
  fi
  rm -f "$tmp"
}

# Install Homebrew (download → inspect → confirm → run)
fetch_inspect_run "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh" bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
eval "$(/opt/homebrew/bin/brew shellenv)"

# Rosetta (Apple Silicon)
sudo softwareupdate --install-rosetta --agree-to-license

# Core CLI tools
brew install git
brew install gh
brew install jq
brew install node
brew install python@3.11
brew install python@3.13
brew install wget

# VS Code and AI tools
brew install --cask visual-studio-code
brew install --cask claude
brew install --cask cursor
brew install --cask drawio

# Install VS Code extensions and npm packages
bash "$(dirname "$0")/vsc.sh"
bash "$(dirname "$0")/npm.sh"

# Python deps for .github/scripts/
pip install anthropic requests notion-client PyYAML

# Upgrade and cleanup
brew upgrade
brew cleanup

# MCP server setup
# Each mcp-*.sh in this directory configures one MCP server for Codex/Claude Code.
# Discovery is by glob, so dropping in a new mcp-<name>.sh wires it up with no edit
# to install.sh.
#
# Each installer is run as its own process so one aborted/failed connector does not
# halt the rest. Most prompt for a token, so this is opt-in per script and
# interactive. Set SKIP_MCP_SETUP=1 to skip the whole section (e.g. unattended runs).
SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${SKIP_MCP_SETUP:-0}" == "1" ]]; then
    echo "SKIP_MCP_SETUP=1 — skipping MCP server setup."
else
    echo ""
    echo "=== MCP server setup ==="
    echo "Configures MCP connectors for Codex / Claude Code. Each is optional and may"
    echo "prompt for an API token. Press 'n' to skip any you don't need."
    for mcp_script in "${SETUP_DIR}"/mcp-*.sh; do
        [[ -e "$mcp_script" ]] || continue   # no matches → glob stays literal
        name="$(basename "$mcp_script" .sh)"; name="${name#mcp-}"
        echo ""
        if [[ -t 0 ]]; then
            read -rp "Configure ${name} MCP? [y/N]: " RUN_MCP
        else
            RUN_MCP="N"   # non-interactive: skip (installers need a TTY for token prompts)
        fi
        case "${RUN_MCP:-N}" in
            y|Y|yes|YES)
                echo "--- ${name} ---"
                bash "$mcp_script" || echo "  ${name} MCP setup failed or was aborted — continuing."
                ;;
            *)
                echo "  skipped ${name}."
                ;;
        esac
    done
    echo ""
    echo "MCP server setup complete. Re-run any individual installer with:"
    echo "  bash ${SETUP_DIR}/mcp-<name>.sh"
fi

echo ""
echo "Setup complete. Next steps:"
echo "  1. Run .setup/vscode-claude.sh  — configure Claude Code"
echo "  2. Run .setup/vscode-codex.sh   — configure Codex"
echo "  3. Run .setup/vscode-cursor.sh  — configure Cursor"
echo "  4. Add secrets to your repo (ANTHROPIC_API_KEY, NOTION_TOKEN)"
echo "     See automation/sdd-review.md for full setup instructions."
