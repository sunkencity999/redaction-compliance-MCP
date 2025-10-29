#!/bin/bash
# MCP Redaction Server - View Logs
# Usage: ./logs.sh [lines]
# Example: ./logs.sh 50  (show last 50 lines)

LINES=${1:-20}
LOG_FILE="/opt/mcp-redaction/logs/stderr.log"

echo "📝 MCP Redaction Server Logs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

# Show last N lines and then follow
echo "Showing last $LINES lines, then following live..."
echo "Press Ctrl+C to exit"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

tail -n "$LINES" -f "$LOG_FILE"
