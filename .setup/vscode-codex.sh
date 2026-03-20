#!/bin/bash

# Install Codex tooling for VS Code and shell usage.

set -euo pipefail

OPENAI_EXTENSION="openai.chatgpt"
ZSHRC="${HOME}/.zshrc"
PATH_MARKER_START="# >>> codex-path-setup >>>"
PATH_MARKER_END="# <<< codex-path-setup <<<"

echo "Installing OpenAI VS Code extension (includes Codex CLI binary)..."
if ! command -v code >/dev/null 2>&1; then
    echo "VS Code CLI 'code' not found."
    echo "Open VS Code and run: Shell Command: Install 'code' command in PATH"
    exit 1
fi

code --install-extension "${OPENAI_EXTENSION}"

# Prefer whichever extension version is latest.
CODEX_BIN_DIR="$(ls -d "${HOME}"/.vscode/extensions/openai.chatgpt-*/bin/macos-aarch64 2>/dev/null | sort -V | tail -n 1 || true)"

if [[ -z "${CODEX_BIN_DIR}" ]]; then
    echo "Could not locate Codex binary under ~/.vscode/extensions/${OPENAI_EXTENSION}-*/bin/macos-aarch64"
    exit 1
fi

if [[ ":$PATH:" != *":${CODEX_BIN_DIR}:"* ]]; then
    export PATH="${CODEX_BIN_DIR}:$PATH"
fi

if ! command -v codex >/dev/null 2>&1; then
    echo "Codex binary still not available on PATH."
    exit 1
fi

if [[ ! -f "${ZSHRC}" ]]; then
    touch "${ZSHRC}"
fi

# Replace prior managed block if present.
TMP_FILE="$(mktemp)"
awk -v start="${PATH_MARKER_START}" -v end="${PATH_MARKER_END}" '
    $0 == start {skip=1; next}
    $0 == end {skip=0; next}
    !skip {print}
' "${ZSHRC}" > "${TMP_FILE}"
mv "${TMP_FILE}" "${ZSHRC}"

cat >> "${ZSHRC}" <<'EOF'
# >>> codex-path-setup >>>
if [ -d "$HOME/.vscode/extensions" ]; then
  _codex_bin_dir="$(ls -d "$HOME"/.vscode/extensions/openai.chatgpt-*/bin/macos-aarch64 2>/dev/null | sort -V | tail -n 1)"
  if [ -n "$_codex_bin_dir" ] && [[ ":$PATH:" != *":$_codex_bin_dir:"* ]]; then
    export PATH="$_codex_bin_dir:$PATH"
  fi
  unset _codex_bin_dir
fi
# <<< codex-path-setup <<<
EOF

echo ""
echo "Codex setup complete."
echo "  codex binary : $(command -v codex)"
echo "  codex version: $(codex --version)"
echo ""
echo "Next steps:"
echo "  1) Reload shell: source ~/.zshrc"
echo "  2) Authenticate: codex login"
echo "  3) Verify MCP: codex mcp list"
echo ""
echo "Current Codex MCP servers:"
codex mcp list || true
