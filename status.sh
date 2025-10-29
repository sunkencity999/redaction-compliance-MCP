#!/bin/bash
# MCP Redaction Server - Status Check
# Usage: ./status.sh

echo "🔍 MCP Redaction Server Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if service is loaded
if launchctl list | grep -q "com.mcp.redaction"; then
    echo "✅ Service: RUNNING"
    
    # Get PID
    PID=$(launchctl list | grep com.mcp.redaction | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "   PID: $PID"
    fi
else
    echo "❌ Service: NOT RUNNING"
    echo ""
    echo "Start with: ./start.sh"
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
    echo "   Check logs: ./logs.sh"
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
echo "   View logs: ./logs.sh"
echo "   Stop: ./stop.sh"
echo "   Restart: ./stop.sh && ./start.sh"
