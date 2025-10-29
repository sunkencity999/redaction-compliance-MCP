#!/bin/bash
# MCP Redaction Server - Uninstall Script (Linux)
# Usage: ./linux-uninstall.sh

set -e

echo "🗑️  MCP Redaction Server - Uninstall (Linux)"
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
SERVICE_FILE="/etc/systemd/system/mcp-redaction.service"
STATE_FILE="$HOME/.mcp-install-state.conf"
SECRETS_FILE="$HOME/.mcp-secrets"

echo "🛑 Step 1/6: Stopping service..."
if systemctl list-unit-files | grep -q "mcp-redaction.service"; then
    if systemctl is-active --quiet mcp-redaction; then
        sudo systemctl stop mcp-redaction
        echo "   ✅ Service stopped"
    else
        echo "   ℹ️  Service not running"
    fi
    
    # Disable service
    if systemctl is-enabled --quiet mcp-redaction 2>/dev/null; then
        sudo systemctl disable mcp-redaction
        echo "   ✅ Service disabled"
    fi
else
    echo "   ℹ️  Service not found"
fi

echo ""
echo "🗂️  Step 2/6: Removing service configuration..."
if [ -f "$SERVICE_FILE" ]; then
    sudo rm -f "$SERVICE_FILE"
    echo "   ✅ Removed: $SERVICE_FILE"
    
    # Reload systemd
    sudo systemctl daemon-reload
    echo "   ✅ Systemd reloaded"
else
    echo "   ℹ️  No service file to remove"
fi

echo ""
echo "📁 Step 3/6: Removing installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    echo "   Removing: $INSTALL_DIR"
    sudo rm -rf "$INSTALL_DIR"
    echo "   ✅ Installation directory removed"
else
    echo "   ℹ️  Installation directory not found"
fi

echo ""
echo "📝 Step 4/6: Removing user configuration files..."
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
echo "🧹 Step 5/6: Cleaning up installation logs..."
# Remove any installation log files
rm -f "$HOME"/mcp-install-*.log 2>/dev/null || true
rm -f "$HOME"/mcp-install-*.txt 2>/dev/null || true
rm -f /tmp/mcp-install-*.txt 2>/dev/null || true
echo "   ✅ Logs cleaned up"

echo ""
echo "🔄 Step 6/6: Resetting systemd..."
sudo systemctl reset-failed 2>/dev/null || true
echo "   ✅ Systemd reset complete"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Uninstall complete!"
echo ""
echo "📋 What was removed:"
echo "   • Service: mcp-redaction.service"
echo "   • Installation: $INSTALL_DIR"
echo "   • Configuration: $STATE_FILE"
echo "   • Secrets: $SECRETS_FILE"
echo ""
echo "📦 Optional: To reinstall later, run:"
echo "   ./install_enhanced.sh && ./linux-setup.sh"
echo ""
echo "🙏 Thank you for using MCP Redaction Server!"
