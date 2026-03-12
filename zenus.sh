#!/usr/bin/env bash
# Zenus OS launcher — uses the shared project venv (.venv/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [ ! -f "$VENV/bin/zenus" ]; then
    echo "❌ Zenus not installed. Run: ./install.sh" >&2
    exit 1
fi

cd "$SCRIPT_DIR" || exit 1
exec "$VENV/bin/zenus" "$@"
