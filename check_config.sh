#!/bin/bash
echo "╔════════════════════════════════════╗"
echo "║   Zenus Configuration Check        ║"
echo "╚════════════════════════════════════╝"
echo ""

CONFIG_DIR="$HOME/.zenus"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
SECRETS_FILE="$CONFIG_DIR/.env"

echo "Checking configuration..."
echo ""

# Check directory
if [ -d "$CONFIG_DIR" ]; then
    echo "✓ Config directory exists: $CONFIG_DIR"
else
    echo "❌ Config directory missing: $CONFIG_DIR"
    exit 1
fi

# Check config.yaml
if [ -f "$CONFIG_FILE" ]; then
    size=$(stat -c%s "$CONFIG_FILE")
    perms=$(stat -c%a "$CONFIG_FILE")
    echo "✓ Config file exists: $CONFIG_FILE"
    echo "  Size: $size bytes"
    echo "  Permissions: $perms"
    echo ""
    echo "  Provider: $(grep 'provider:' "$CONFIG_FILE" | head -1 | awk '{print $2}')"
    echo "  Model: $(grep 'model:' "$CONFIG_FILE" | head -1 | awk '{print $2}')"
else
    echo "❌ Config file missing: $CONFIG_FILE"
fi

echo ""

# Check .env
if [ -f "$SECRETS_FILE" ]; then
    size=$(stat -c%s "$SECRETS_FILE")
    perms=$(stat -c%a "$SECRETS_FILE")
    echo "✓ Secrets file exists: $SECRETS_FILE"
    echo "  Size: $size bytes"
    echo "  Permissions: $perms"
    
    if [ "$perms" != "600" ]; then
        echo "  ⚠️  WARNING: Permissions should be 600, run: chmod 600 $SECRETS_FILE"
    fi
    
    echo ""
    echo "  API Keys configured:"
    grep -E "API_KEY=" "$SECRETS_FILE" | sed 's/=.*/=***/' || echo "  (none)"
else
    echo "❌ Secrets file missing: $SECRETS_FILE"
fi

echo ""
echo "════════════════════════════════════"
echo ""

if [ -f "$CONFIG_FILE" ] && [ -f "$SECRETS_FILE" ]; then
    echo "✓ Configuration is complete!"
    echo ""
    echo "You can edit these files:"
    echo "  nano $CONFIG_FILE"
    echo "  nano $SECRETS_FILE"
else
    echo "❌ Configuration incomplete. Run: ./install.sh"
fi

echo ""
