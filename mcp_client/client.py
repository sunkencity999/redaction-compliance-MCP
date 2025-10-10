"""MCP Client SDK for seamless LLM integration."""

import os
import requests
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .exceptions import MCPError, MCPBlockedError, MCPAuthError, MCPConnectionError


@dataclass
class MCPConfig:
    """Configuration for MCP Client."""
    server_url: str
    caller: str
    region: str = "us"
    env: str = "prod"
    timeout: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables."""
        return cls(
            server_url=os.getenv("MCP_SERVER_URL", "https://mcp.yourcompany.com"),
            caller=os.getenv("MCP_CALLER", "unknown-app"),
            region=os.getenv("MCP_REGION", "us"),
            env=os.getenv("MCP_ENV", "prod"),
            timeout=int(os.getenv("MCP_TIMEOUT", "30")),
            verify_ssl=os.getenv("MCP_VERIFY_SSL", "true").lower() == "true"
        )


class MCPClient:
    """
    MCP Redaction Client - Seamless integration for LLM applications.
    
    Usage:
        from mcp_client import MCPClient, MCPConfig
        
        # Configure once
        config = MCPConfig(
            server_url="https://mcp.company.com",
            caller="my-app"
        )
        mcp = MCPClient(config)
        
        # Before calling LLM
        sanitized, handle = mcp.redact(user_input)
        
        # Call your LLM
        llm_response = call_openai(sanitized)
        
        # After LLM response
        final = mcp.detokenize(llm_response, handle)
    """
    
    def __init__(self, config: MCPConfig):
        """Initialize MCP client with configuration."""
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
    
    def _context(self) -> Dict[str, str]:
        """Build context dict for requests."""
        return {
            "caller": self.config.caller,
            "region": self.config.region,
            "env": self.config.env
        }
    
    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to MCP server."""
        url = f"{self.config.server_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.config.timeout
            )
            
            if response.status_code == 403:
                raise MCPAuthError(
                    f"Authorization failed: {response.json().get('detail', 'Forbidden')}"
                )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            raise MCPConnectionError(f"Request to {url} timed out after {self.config.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MCPConnectionError(f"Failed to connect to MCP server: {e}")
        except requests.exceptions.HTTPError as e:
            raise MCPError(f"HTTP error from MCP server: {e}")
    
    def classify(self, payload: str) -> Dict[str, Any]:
        """
        Classify payload to detect sensitive content.
        
        Args:
            payload: Text to classify
            
        Returns:
            Classification result with categories and policy decision
            
        Raises:
            MCPError: On server error
        """
        response = self._post("/classify", {
            "payload": payload,
            "context": self._context()
        })
        return response
    
    def redact(self, payload: str) -> tuple[str, str]:
        """
        Redact sensitive content from payload.
        
        Args:
            payload: Text to redact
            
        Returns:
            Tuple of (sanitized_payload, token_map_handle)
            
        Raises:
            MCPBlockedError: If policy blocks the request
            MCPError: On server error
            
        Example:
            sanitized, handle = mcp.redact("My AWS key is AKIA...")
            # sanitized: "My AWS key is «token:SECRET:a3f9»..."
            # handle: "conv-123-abc"
        """
        # First classify to check policy
        classify_result = self.classify(payload)
        
        if classify_result.get("suggested_action") == "block":
            raise MCPBlockedError(
                "Request blocked by policy",
                decision=classify_result.get("decision")
            )
        
        # Redact
        response = self._post("/redact", {
            "payload": payload,
            "context": self._context()
        })
        
        return response["sanitized_payload"], response["token_map_handle"]
    
    def detokenize(
        self,
        payload: str,
        token_map_handle: str,
        allow_categories: Optional[List[str]] = None
    ) -> str:
        """
        Restore tokens from payload (selective).
        
        Args:
            payload: Text with tokens to restore
            token_map_handle: Handle from redact()
            allow_categories: Categories to restore (default: ["pii", "ops_sensitive"])
            
        Returns:
            Text with allowed tokens restored
            
        Raises:
            MCPAuthError: If caller not authorized to detokenize
            MCPError: On server error
            
        Note:
            Secrets are NEVER detokenized, even if requested.
        """
        if allow_categories is None:
            allow_categories = ["pii", "ops_sensitive"]
        
        response = self._post("/detokenize", {
            "payload": payload,
            "token_map_handle": token_map_handle,
            "allow_categories": allow_categories,
            "context": self._context()
        })
        
        return response["restored_payload"]
    
    def safe_llm_call(
        self,
        payload: str,
        llm_callable,
        detokenize: bool = True,
        allow_categories: Optional[List[str]] = None
    ) -> str:
        """
        Safely call an LLM with automatic redaction/detokenization.
        
        Args:
            payload: User input to send to LLM
            llm_callable: Function that takes sanitized text and returns LLM response
            detokenize: Whether to detokenize the response (default: True)
            allow_categories: Categories to restore (default: ["pii", "ops_sensitive"])
            
        Returns:
            Final response (detokenized if requested)
            
        Raises:
            MCPBlockedError: If policy blocks the request
            MCPAuthError: If not authorized
            MCPError: On server error
            
        Example:
            def call_openai(text):
                return openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": text}]
                ).choices[0].message.content
            
            response = mcp.safe_llm_call(
                "My AWS key is AKIA..., help me debug",
                call_openai
            )
            # MCP automatically redacts, calls OpenAI, and restores tokens
        """
        # Redact
        sanitized, handle = self.redact(payload)
        
        # Call LLM
        llm_response = llm_callable(sanitized)
        
        # Detokenize if requested
        if detokenize:
            return self.detokenize(llm_response, handle, allow_categories)
        else:
            return llm_response
    
    def check_safe(self, payload: str) -> bool:
        """
        Quick check if payload is safe to send to external LLM.
        
        Args:
            payload: Text to check
            
        Returns:
            True if safe, False if blocked
        """
        try:
            result = self.classify(payload)
            return result.get("suggested_action") != "block"
        except MCPError:
            # On error, assume unsafe
            return False
    
    def health(self) -> Dict[str, Any]:
        """
        Check MCP server health.
        
        Returns:
            Health status dict
            
        Raises:
            MCPConnectionError: If server is unreachable
        """
        url = f"{self.config.server_url.rstrip('/')}/health"
        try:
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise MCPConnectionError(f"Health check failed: {e}")
