#!/bin/bash

# Install Claude Code extensions for Visual Studio Code
echo "Installing Claude Code extensions..."
code --install-extension anthropic.claude-code
code --install-extension andrepimenta.claude-code-chat

# Install Claude Code CLI
echo "Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code

echo "Claude Code extensions and CLI installed successfully!"
echo ""
echo "Setup Authentication:"
echo "1. Get your API key from https://console.anthropic.com/"
echo "2. In VSCode, open Command Palette (Cmd+Shift+P)"
echo "3. Type 'Claude Code: Set API Key' and select it"
echo "4. Enter your API key when prompted"
echo ""
echo "Alternative: Set environment variable ANTHROPIC_API_KEY"
echo "export ANTHROPIC_API_KEY=your_api_key_here"
echo ""
echo "Getting Started:"
echo "• Open Command Palette (Cmd+Shift+P) and type 'Claude Code' to see all commands"
echo "• Use Cmd+I to start inline editing with Claude"
echo "• Use Cmd+Shift+I to open Claude Code chat panel"
echo "• Highlight code and ask Claude questions or request changes"
echo "• Claude can read your entire project context automatically"
echo ""
echo "Tips:"
echo "• Claude works best when you describe what you want to achieve"
echo "• You can ask Claude to explain code, fix bugs, or add new features"
echo "• Use specific file paths when referencing files in your requests"
echo ""
echo "Restart VSCode to complete setup."