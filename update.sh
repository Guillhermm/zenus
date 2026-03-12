#!/bin/bash
set -e

echo "╔════════════════════════════════════╗"
echo "║    Zenus Update Script             ║"
echo "╚════════════════════════════════════╝"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PIP="$VENV_DIR/bin/pip"

if [ ! -f "$PIP" ]; then
    echo "❌ Virtual environment not found. Run: ./install.sh"
    exit 1
fi

echo "Updating Zenus packages..."
echo ""

echo "→ Upgrading pip..."
"$PIP" install --upgrade pip --quiet

echo "→ Updating zenus-core..."
"$PIP" install -e "$PROJECT_DIR/packages/core" --quiet
echo "✓ zenus-core updated"

echo "→ Updating zenus-cli..."
"$PIP" install -e "$PROJECT_DIR/packages/cli" --quiet
echo "✓ zenus-cli updated"

echo "→ Updating zenus-tui..."
"$PIP" install -e "$PROJECT_DIR/packages/tui" --quiet
echo "✓ zenus-tui updated"

echo ""
echo "════════════════════════════════════"
echo "  Update Complete!"
echo "════════════════════════════════════"
echo ""
echo "  zenus              # CLI"
echo "  zenus-tui          # TUI"
echo ""
