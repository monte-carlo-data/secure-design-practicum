#!/bin/bash

# Install global npm packages
set -euo pipefail

if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found. Install Node.js first (run .setup/install.sh)."
    exit 1
fi

npm install -g @anthropic-ai/claude-code
npm install -g @cloud-copilot/iam-collect
npm install -g npm
