#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
#  MARS Language Installer  (Linux / macOS)
# ─────────────────────────────────────────────

VENV_DIR=".venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "  MARS Language Installer"
echo "  ─────────────────────────────────────"
echo ""
echo "  Select installation mode:"
echo ""
echo "    1) User      – Install Mars as a standalone tool (stable, no link to source)"
echo "    2) Developer – Editable install linked to this source tree"
echo ""

read -rp "  Enter choice [1/2]: " choice
echo ""

case "$choice" in
    1) MODE="user" ;;
    2) MODE="dev"  ;;
    *)
        echo "  Invalid choice. Exiting."
        exit 1
        ;;
esac

# ── Create virtual environment ───────────────
if [ ! -d "$SCRIPT_DIR/$VENV_DIR" ]; then
    echo "  Creating virtual environment in $VENV_DIR ..."
    python3 -m venv "$SCRIPT_DIR/$VENV_DIR"
else
    echo "  Virtual environment already exists at $VENV_DIR"
fi

# ── Activate and install ─────────────────────
source "$SCRIPT_DIR/$VENV_DIR/bin/activate"

echo "  Upgrading pip ..."
pip install --upgrade pip --quiet

if [ "$MODE" = "user" ]; then
    echo "  Installing Mars (user mode) ..."
    pip install "$SCRIPT_DIR" --quiet
else
    echo "  Installing Mars (developer mode with dev extras) ..."
    pip install -e "$SCRIPT_DIR[dev]" --quiet
fi

echo ""
echo "  ─────────────────────────────────────"
echo "  Installation complete!"
echo ""

# ── PATH instructions ────────────────────────
MARS_BIN="$SCRIPT_DIR/$VENV_DIR/bin"

echo "  To use the 'mars' command, activate the virtual environment:"
echo ""
echo "    source $MARS_BIN/../bin/activate"
echo ""
echo "  Or add the following to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
echo ""
echo "    export PATH=\"$MARS_BIN:\$PATH\""
echo ""

if [ "$MODE" = "dev" ]; then
    echo "  Developer mode: edits to source files take effect immediately."
    echo "  Dev tools installed: pytest, ruff"
    echo ""
fi

echo "  Verify installation:  mars --version"
echo ""
