#!/bin/bash

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -e .

echo "MARS installed"
echo "Activate with: source .venv/bin/activate"
echo "Run with: mars run file.mars"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VSIX_PATH="$SCRIPT_DIR/mars-extension-1.0.3.vsix"

#Check for VSCode
CODE_PATH=""

if command -v code &>/dev/null; then
    CODE_PATH="code"
elif [ -f "/usr/bin/code" ]; then
    CODE_PATH="/usr/bin/code"
elif [ -f "/usr/local/bin/code" ]; then
    CODE_PATH="/usr/local/bin/code"
elif [ -f "$HOME/.local/bin/code" ]; then
    CODE_PATH="$HOME/.local/bin/code"
else
    echo "Error: Visual Studio Code was not found. Please install VSCode and re-run this installer." >&2
    exit 1
fi

#Check for .vsix
if [ ! -f "$VSIX_PATH" ]; then
    echo "Error: Extension file not found: $VSIX_PATH" >&2
    exit 1
fi

#Install the extension
echo "Installing VSCode extension..."
"$CODE_PATH" --install-extension "$VSIX_PATH" --force

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "Extension installed successfully."
else
    echo "Error: Extension installation failed with exit code $EXIT_CODE." >&2
    exit 1
fi