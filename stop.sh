#!/bin/bash
# MCP Redaction Server - Stop Script
# Usage: ./stop.sh

echo "🛑 Stopping MCP Redaction Server..."

# Check if running
if ! launchctl list | grep -q "com.mcp.redaction"; then
    echo "⚠️  Service is not running"
    exit 0
fi

# Unload the service
launchctl unload ~/Library/LaunchAgents/com.mcp.redaction.plist

# Wait a moment
sleep 2

# Verify it stopped
if launchctl list | grep -q "com.mcp.redaction"; then
    echo "❌ Failed to stop service"
    echo "   Try: launchctl kill SIGTERM com.mcp.redaction"
    exit 1
else
    echo "✅ Service stopped successfully"
fi
