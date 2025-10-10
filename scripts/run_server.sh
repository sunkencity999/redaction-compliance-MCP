#!/usr/bin/env bash
set -euo pipefail
export MCP_TOKEN_SALT=${MCP_TOKEN_SALT:-change-me}
uvicorn mcp_redaction.server:app --host 0.0.0.0 --port 8019
