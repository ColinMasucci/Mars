#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
#  MARS Language Installer  (Linux / macOS)
# ─────────────────────────────────────────────
#
#  Can be run interactively or driven by flags:
#    ./install.sh                        (interactive)
#    ./install.sh --mode user            (non-interactive)
#    ./install.sh --mode dev --venv-dir ~/.mars
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE=""
VENV_DIR=""

# ── Parse arguments ──────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)     MODE="$2";     shift 2 ;;
        --venv-dir) VENV_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Interactive prompt if no --mode given ────
if [ -z "$MODE" ]; then
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
fi

# ── Resolve venv path ────────────────────────
if [ -z "$VENV_DIR" ]; then
    VENV_DIR="$SCRIPT_DIR/.venv"
fi

# ── Create virtual environment ───────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
else
    echo "  Virtual environment already exists at $VENV_DIR"
fi

# ── Activate and install ─────────────────────
source "$VENV_DIR/bin/activate"

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
MARS_BIN="$VENV_DIR/bin"

echo "  To use the 'mars' command, activate the virtual environment:"
echo ""
echo "    source $VENV_DIR/bin/activate"
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
