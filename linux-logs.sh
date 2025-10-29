#!/bin/bash
# MCP Redaction Server - Linux View Logs
# Usage: ./linux-logs.sh [lines]
# Example: ./linux-logs.sh 50  (show last 50 lines)

LINES=${1:-20}

echo "📝 MCP Redaction Server Logs (Linux)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if service exists
if ! systemctl list-unit-files | grep -q "mcp-redaction.service"; then
    echo "❌ Service not found. Run ./linux-setup.sh first"
    exit 1
fi

echo "Showing last $LINES lines, then following live..."
echo "Press Ctrl+C to exit"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Use journalctl to follow logs
journalctl -u mcp-redaction -n "$LINES" -f
