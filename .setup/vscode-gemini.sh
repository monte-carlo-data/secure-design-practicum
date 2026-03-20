#!/bin/bash

# Install Gemini Code Assist extensions for Visual Studio Code
echo "Installing Gemini Code Assist extensions..."
code --install-extension google.geminicodeassist

# Install Gemini CLI
echo "Installing Gemini CLI..."
npm install -g @google/gemini-cli

echo "Gemini Code Assist extension and CLI installed successfully!"
echo ""
echo "Setup Authentication:"
echo "1. Get your API key from https://aistudio.google.com/apikey"
echo "2. In VSCode, open Command Palette (Cmd+Shift+P)"
echo "3. Type 'Gemini Code Assist: Sign In' and select it"
echo "4. Follow the prompts to authenticate with your Google account"
echo ""
echo "Alternative: Set environment variable GEMINI_API_KEY"
echo "export GEMINI_API_KEY=your_api_key_here"
echo ""
echo "Getting Started:"
echo "• Open Command Palette (Cmd+Shift+P) and type 'Gemini' to see all commands"
echo "• Use the Gemini chat panel in the sidebar to ask questions"
echo "• Highlight code and use right-click to access Gemini Code Assist options"
echo "• Gemini can read your project context and suggest completions inline"
echo ""
echo "Tips:"
echo "• Gemini works best when you describe what you want to achieve"
echo "• You can ask Gemini to explain code, fix bugs, or add new features"
echo "• Use specific file paths when referencing files in your requests"
echo ""
echo "Restart VSCode to complete setup."
