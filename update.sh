#!/bin/bash
set -e

echo "╔════════════════════════════════════╗"
echo "║   Zenus Update Script           ║"
echo "╚════════════════════════════════════╝"
echo ""

# Get absolute path to project
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Updating Zenus packages..."
echo ""

# Update core package
echo "→ Updating zenus-core..."
cd "$PROJECT_DIR/packages/core"
poetry install --no-interaction
echo "✓ zenus-core updated"
echo ""

# Update CLI package
echo "→ Updating zenus-cli..."
cd "$PROJECT_DIR/packages/cli"
poetry install --no-interaction
echo "✓ zenus-cli updated"
echo ""

# Update TUI package
echo "→ Updating zenus-tui..."
cd "$PROJECT_DIR/packages/tui"
poetry install --no-interaction
echo "✓ zenus-tui updated"
echo ""

cd "$PROJECT_DIR"

echo "════════════════════════════════════"
echo "  Update Complete!"
echo "════════════════════════════════════"
echo ""
echo "All packages updated with latest dependencies."
echo ""
echo "You can now use:"
echo "  zenus                    # CLI"
echo "  zenus-tui                # TUI"
echo ""
