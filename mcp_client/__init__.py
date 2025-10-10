"""MCP Redaction Client SDK - Seamless integration with LLM applications."""

from .client import MCPClient, MCPConfig
from .exceptions import MCPError, MCPBlockedError, MCPAuthError

__version__ = "2.0.0"
__all__ = ["MCPClient", "MCPConfig", "MCPError", "MCPBlockedError", "MCPAuthError"]
