#!/bin/bash
# MCP Redaction Server - Uninstall Script (macOS)
# Usage: ./uninstall.sh

set -e

echo "🗑️  MCP Redaction Server - Uninstall (macOS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  WARNING: This will completely remove the MCP Redaction Server"
echo "   - Service will be stopped and removed"
echo "   - Installation directory (/opt/mcp-redaction) will be deleted"
echo "   - Configuration files will be removed"
echo "   - User data (.mcp-install-state.conf, .mcp-secrets) will be removed"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Uninstall cancelled"
    exit 0
fi

INSTALL_DIR="/opt/mcp-redaction"
PLIST_FILE="$HOME/Library/LaunchAgents/com.mcp.redaction.plist"
STATE_FILE="$HOME/.mcp-install-state.conf"
SECRETS_FILE="$HOME/.mcp-secrets"

echo "🛑 Step 1/5: Stopping service..."
if [ -f "$PLIST_FILE" ]; then
    if launchctl list | grep -q "com.mcp.redaction"; then
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        echo "   ✅ Service stopped"
    else
        echo "   ℹ️  Service not running"
    fi
else
    echo "   ℹ️  Service not found"
fi

echo ""
echo "🗂️  Step 2/5: Removing service configuration..."
if [ -f "$PLIST_FILE" ]; then
    rm -f "$PLIST_FILE"
    echo "   ✅ Removed: $PLIST_FILE"
else
    echo "   ℹ️  No service file to remove"
fi

echo ""
echo "📁 Step 3/5: Removing installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    echo "   Removing: $INSTALL_DIR"
    sudo rm -rf "$INSTALL_DIR"
    echo "   ✅ Installation directory removed"
else
    echo "   ℹ️  Installation directory not found"
fi

echo ""
echo "📝 Step 4/5: Removing user configuration files..."
removed_count=0

if [ -f "$STATE_FILE" ]; then
    rm -f "$STATE_FILE"
    echo "   ✅ Removed: $STATE_FILE"
    ((removed_count++))
fi

if [ -f "$SECRETS_FILE" ]; then
    rm -f "$SECRETS_FILE"
    echo "   ✅ Removed: $SECRETS_FILE"
    ((removed_count++))
fi

if [ $removed_count -eq 0 ]; then
    echo "   ℹ️  No user configuration files found"
fi

echo ""
echo "🧹 Step 5/5: Cleaning up installation logs..."
# Remove any installation log files in the current directory
rm -f "$HOME"/mcp-install-*.log 2>/dev/null || true
rm -f "$HOME"/mcp-install-*.txt 2>/dev/null || true
echo "   ✅ Logs cleaned up"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Uninstall complete!"
echo ""
echo "📋 What was removed:"
echo "   • Service: com.mcp.redaction"
echo "   • Installation: $INSTALL_DIR"
echo "   • Configuration: $STATE_FILE"
echo "   • Secrets: $SECRETS_FILE"
echo ""
echo "📦 Optional: To reinstall later, run:"
echo "   ./install_enhanced.sh"
echo ""
echo "🙏 Thank you for using MCP Redaction Server!"
