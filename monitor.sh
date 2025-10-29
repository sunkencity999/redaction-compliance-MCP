#!/bin/bash
# MCP Redaction Server - Live Transaction Monitor
# Usage: ./monitor.sh

echo "📡 MCP Redaction Server - Live Transaction Monitor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Monitoring: /opt/mcp-redaction/logs/stderr.log"
echo "Press Ctrl+C to exit"
echo ""
echo "Showing INFO, WARNING, and ERROR messages..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Filter for actual requests/responses, not startup messages
tail -f /opt/mcp-redaction/logs/stderr.log | grep --line-buffered -E "INFO:.*HTTP|POST|GET|ERROR|Exception|Traceback|WARNING|Streaming|Redact|Detokenize|proxy|/v1/"
