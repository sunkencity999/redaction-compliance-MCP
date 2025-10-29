#!/bin/bash
# MCP Redaction Server - Start Script
# Usage: ./start.sh

set -e

echo "🚀 Starting MCP Redaction Server..."

# Check if already running
if launchctl list | grep -q "com.mcp.redaction"; then
    echo "⚠️  Service is already running"
    echo "   Use ./stop.sh first if you want to restart"
    exit 1
fi

# Load the service
launchctl load ~/Library/LaunchAgents/com.mcp.redaction.plist

# Wait a moment for startup
sleep 3

# Check health
echo ""
echo "🔍 Checking service health..."
if curl -s http://localhost:8019/health > /dev/null 2>&1; then
    echo "✅ Service is healthy!"
    echo ""
    curl -s http://localhost:8019/health | python3 -m json.tool
    echo ""
    echo "📊 Service is running at: http://localhost:8019"
    echo "📝 View logs: ./logs.sh"
    echo "🛑 Stop service: ./stop.sh"
else
    echo "❌ Service failed to start"
    echo "📝 Check logs: ./logs.sh"
    exit 1
fi
