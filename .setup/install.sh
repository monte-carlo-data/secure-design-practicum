#!/bin/bash

# Bootstrap a macOS dev machine for the security review practicum.
# Installs Homebrew, core tools, and AI assistants needed to run
# the SDD and PR review workflows.

set -euo pipefail

# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
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

echo ""
echo "Setup complete. Next steps:"
echo "  1. Run .setup/vscode-claude.sh  — configure Claude Code"
echo "  2. Run .setup/vscode-codex.sh   — configure Codex"
echo "  3. Run .setup/vscode-cursor.sh  — configure Cursor"
echo "  4. Add secrets to your repo (ANTHROPIC_API_KEY, NOTION_TOKEN)"
echo "     See automation/sdd-review.md for full setup instructions."
