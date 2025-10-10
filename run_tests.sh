#!/bin/bash
# Test runner script for MCP Redaction Server

set -e

echo "=================================="
echo "MCP Redaction Server - Test Suite"
echo "=================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Setting up..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    echo "✓ Virtual environment created"
else
    source .venv/bin/activate
fi

# Set required environment variables
export MCP_TOKEN_SALT="test-salt-for-testing"
export TOKEN_BACKEND="memory"

# Run tests
echo ""
echo "Running test suite..."
echo ""

python -m pytest tests/ -v --tb=short --cov=mcp_redaction --cov-report=term-missing 2>/dev/null || \
python -m pytest tests/ -v --tb=short

echo ""
echo "✓ Tests completed"
