#!/bin/bash
# MCP Redaction Server - Linux Start Script
# Usage: ./linux-start.sh

echo "🚀 Starting MCP Redaction Server (Linux)..."

# Check if service exists
if ! systemctl list-unit-files | grep -q "mcp-redaction.service"; then
    echo "❌ Service not found. Run ./linux-setup.sh first"
    exit 1
fi

# Check if already running
if systemctl is-active --quiet mcp-redaction; then
    echo "⚠️  Service is already running"
    echo "   Use ./linux-stop.sh first if you want to restart"
    exit 0
fi

# Start the service
sudo systemctl start mcp-redaction

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
    echo "📝 View logs: ./linux-logs.sh"
    echo "🛑 Stop service: ./linux-stop.sh"
else
    echo "❌ Service failed to start"
    echo "📝 Check logs: ./linux-logs.sh"
    exit 1
fi
