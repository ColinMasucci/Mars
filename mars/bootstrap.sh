#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
#  MARS Language Bootstrap Installer
# ─────────────────────────────────────────────
#
#  One-liner install (use this exact form):
#
#    bash -c "$(curl -fsSL https://raw.githubusercontent.com/reillydesai/Mars-test/venv-fix/mars/bootstrap.sh)"
#
#  NOTE: Do NOT use "curl ... | bash" -- that breaks interactive prompts
#        because stdin is consumed by the pipe. The bash -c "$(...)" form
#        downloads the entire script first, then runs it with stdin free.
#

REPO_URL="https://github.com/ColinMasucci/Mars.git"
BRANCH="main"
MARS_HOME="$HOME/.mars"
REPO_SUBDIR="mars"   # the package lives inside the mars/ subdirectory of the repo

# ── Guard: detect piped stdin ────────────────
if [ ! -t 0 ]; then
    echo ""
    echo "  Error: This installer requires an interactive terminal."
    echo ""
    echo "  It looks like you ran:  curl ... | bash"
    echo "  Please use this form instead:"
    echo ""
    echo "    bash -c \"\$(curl -fsSL https://github.com/ColinMasucci/Mars/mars/bootstrap.sh)\""
    echo ""
    exit 1
fi

echo ""
echo "  ========================================="
echo "    MARS Language Bootstrap Installer"
echo "  ========================================="
echo ""

# ── Check prerequisites ──────────────────────
for cmd in git python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  Error: '$cmd' is required but not found. Please install it first."
        exit 1
    fi
done

# ── Select mode ──────────────────────────────
echo "  Select installation mode:"
echo ""
echo "    1) User      - Install Mars as a standalone tool"
echo "                   Installs to ~/.mars, no source code kept"
echo ""
echo "    2) Developer - Clone the repo and create an editable install"
echo "                   Source stays in ./Mars-test, edits take effect immediately"
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

# ══════════════════════════════════════════════
#  USER MODE
# ══════════════════════════════════════════════
if [ "$MODE" = "user" ]; then

    echo "  Cloning Mars repository (this may take a moment) ..."
    TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR"' EXIT

    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMPDIR/Mars-test" --quiet

    SOURCE_DIR="$TMPDIR/Mars-test/$REPO_SUBDIR"

    # Run install.sh in non-interactive mode, venv at ~/.mars
    bash "$SOURCE_DIR/install.sh" --mode user --venv-dir "$MARS_HOME"

    echo "  Source checkout cleaned up."
    echo ""
    echo "  Mars is installed at: $MARS_HOME"
    echo ""

# ══════════════════════════════════════════════
#  DEVELOPER MODE
# ══════════════════════════════════════════════
else

    CLONE_DIR="$(pwd)/Mars-test"

    if [ -d "$CLONE_DIR" ]; then
        echo "  Directory ./Mars-test already exists."
        read -rp "  Use existing checkout? [y/N]: " use_existing
        if [[ ! "$use_existing" =~ ^[Yy]$ ]]; then
            echo "  Exiting. Remove or rename the directory and try again."
            exit 1
        fi
    else
        echo "  Cloning Mars repository ..."
        git clone --branch "$BRANCH" "$REPO_URL" "$CLONE_DIR" --quiet
    fi

    SOURCE_DIR="$CLONE_DIR/$REPO_SUBDIR"

    # Run install.sh in non-interactive mode, venv inside the repo
    bash "$SOURCE_DIR/install.sh" --mode dev

    echo ""
    echo "  Source code is at: $SOURCE_DIR"

fi
