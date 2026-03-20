#!/bin/bash

# Install VS Code extensions for the security review practicum.
set -euo pipefail

if ! command -v code >/dev/null 2>&1; then
    echo "VS Code CLI 'code' not found."
    echo "Open VS Code and run: Shell Command: Install 'code' command in PATH"
    exit 1
fi

EXTENSIONS=(
    # AI assistants
    "anthropic.claude-code"
    "andrepimenta.claude-code-chat"
    "openai.chatgpt"
    "github.copilot"
    "github.copilot-chat"

    # Python (for .github/scripts/)
    "ms-python.python"
    "ms-python.vscode-pylance"
    "ms-python.pylint"
    "ms-python.isort"
    "ms-python.debugpy"

    # GitHub Actions / YAML
    "github.vscode-github-actions"
    "github.vscode-pull-request-github"
    "redhat.vscode-yaml"

    # Markdown
    "davidanson.vscode-markdownlint"
    "bierner.markdown-mermaid"

    # Diagrams
    "hediet.vscode-drawio"

    # General
    "eamodio.gitlens"
    "editorconfig.editorconfig"
    "streetsidesoftware.code-spell-checker"
    "esbenp.prettier-vscode"
)

echo "Installing VS Code extensions..."
for extension in "${EXTENSIONS[@]}"; do
    code --install-extension "${extension}"
done

echo "Done."
