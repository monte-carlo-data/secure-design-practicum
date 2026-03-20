#!/bin/bash

# Install Cursor editor integrations.

set -euo pipefail

CURSOR_CMD="cursor"
ZSHRC="${HOME}/.zshrc"
OLD_PATH_MARKER_START="# >>> codex-path-setup-cursor >>>"
OLD_PATH_MARKER_END="# <<< codex-path-setup-cursor <<<"
EXTENSIONS=(
  "anthropic.claude-code"
  "github.copilot"
  "github.copilot-chat"
)

echo "Configuring Cursor setup..."

if ! command -v "${CURSOR_CMD}" >/dev/null 2>&1; then
    if [[ -x "/Applications/Cursor.app/Contents/Resources/app/bin/cursor" ]]; then
        CURSOR_CMD="/Applications/Cursor.app/Contents/Resources/app/bin/cursor"
    else
        echo "Cursor CLI 'cursor' not found."
        echo "Install Cursor and enable the shell command, then re-run this script."
        exit 1
    fi
fi

echo "Installing Cursor extensions..."
for extension in "${EXTENSIONS[@]}"; do
    if ! "${CURSOR_CMD}" --install-extension "${extension}"; then
        echo "Warning: failed to install ${extension}; continuing."
    fi
done

if [[ -f "${ZSHRC}" ]]; then
    # Remove legacy Codex PATH block from prior cursor-codex script.
    TMP_FILE="$(mktemp)"
    awk -v start="${OLD_PATH_MARKER_START}" -v end="${OLD_PATH_MARKER_END}" '
        $0 == start {skip=1; next}
        $0 == end {skip=0; next}
        !skip {print}
    ' "${ZSHRC}" > "${TMP_FILE}"
    mv "${TMP_FILE}" "${ZSHRC}"
fi

echo ""
echo "Cursor setup complete."
echo "  cursor binary: ${CURSOR_CMD}"
echo ""
echo "Next steps:"
echo "  1) Restart Cursor if it is already open"
echo "  2) Sign in to extension providers as needed (Claude/Copilot)"
