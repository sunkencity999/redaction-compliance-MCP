#!/bin/bash
# MCP Redaction Server - Linux Stop Script
# Usage: ./linux-stop.sh

echo "🛑 Stopping MCP Redaction Server (Linux)..."

# Check if service exists
if ! systemctl list-unit-files | grep -q "mcp-redaction.service"; then
    echo "❌ Service not found"
    exit 1
fi

# Check if running
if ! systemctl is-active --quiet mcp-redaction; then
    echo "⚠️  Service is not running"
    exit 0
fi

# Stop the service
sudo systemctl stop mcp-redaction

# Wait a moment
sleep 2

# Verify it stopped
if systemctl is-active --quiet mcp-redaction; then
    echo "❌ Failed to stop service"
    echo "   Try: sudo systemctl kill mcp-redaction"
    exit 1
else
    echo "✅ Service stopped successfully"
fi
