"""Exceptions for MCP Client SDK."""


class MCPError(Exception):
    """Base exception for MCP client errors."""
    pass


class MCPBlockedError(MCPError):
    """Request was blocked by policy."""
    def __init__(self, message, decision=None):
        super().__init__(message)
        self.decision = decision


class MCPAuthError(MCPError):
    """Authentication/authorization error."""
    pass


class MCPConnectionError(MCPError):
    """Connection to MCP server failed."""
    pass


class MCPValidationError(MCPError):
    """Request validation failed."""
    pass
