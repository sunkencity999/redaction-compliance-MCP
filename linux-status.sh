#!/bin/bash
# MCP Redaction Server - Linux Status Check
# Usage: ./linux-status.sh

echo "🔍 MCP Redaction Server Status (Linux)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if service exists
if ! systemctl list-unit-files | grep -q "mcp-redaction.service"; then
    echo "❌ Service not found. Run ./linux-setup.sh first"
    exit 1
fi

# Check if service is active
if systemctl is-active --quiet mcp-redaction; then
    echo "✅ Service: RUNNING"
    
    # Get PID
    PID=$(systemctl show -p MainPID --value mcp-redaction)
    if [ "$PID" != "0" ]; then
        echo "   PID: $PID"
    fi
else
    echo "❌ Service: NOT RUNNING"
    echo ""
    echo "Start with: ./linux-start.sh"
    exit 1
fi

echo ""

# Check health endpoint
echo "🏥 Health Check:"
if curl -s http://localhost:8019/health > /dev/null 2>&1; then
    echo "✅ API: HEALTHY"
    echo ""
    curl -s http://localhost:8019/health | python3 -m json.tool
else
    echo "❌ API: UNREACHABLE"
    echo "   The service is loaded but not responding"
    echo "   Check logs: ./linux-logs.sh"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Endpoints:"
echo "   Health: http://localhost:8019/health"
echo "   OpenAI Proxy: http://localhost:8019/v1/chat/completions"
echo "   Claude Proxy: http://localhost:8019/v1/messages"
echo "   Gemini Proxy: http://localhost:8019/v1/models/{model}:generateContent"
echo ""
echo "🔧 Management:"
echo "   View logs: ./linux-logs.sh"
echo "   Stop: ./linux-stop.sh"
echo "   Restart: ./linux-stop.sh && ./linux-start.sh"
echo "   Enable on boot: sudo systemctl enable mcp-redaction"
