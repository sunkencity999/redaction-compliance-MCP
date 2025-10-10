"""
Transparent Proxy Mode for LLM Providers
Intercepts API calls to OpenAI, Claude, and Gemini
Automatically redacts requests and detokenizes responses
"""

import httpx
import json
import time
from typing import Dict, Any, List, Optional
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse


class LLMProxy:
    """Base class for LLM provider proxies."""
    
    def __init__(self, mcp_server):
        self.mcp = mcp_server
        self.http_client = httpx.AsyncClient(timeout=120.0)
    
    async def extract_messages(self, body: Dict[str, Any]) -> List[str]:
        """Extract text messages from provider-specific request format."""
        raise NotImplementedError
    
    async def inject_messages(self, body: Dict[str, Any], sanitized_messages: List[str]) -> Dict[str, Any]:
        """Inject sanitized messages back into request format."""
        raise NotImplementedError
    
    async def extract_response_text(self, response_body: Dict[str, Any]) -> str:
        """Extract text from provider-specific response format."""
        raise NotImplementedError
    
    async def inject_response_text(self, response_body: Dict[str, Any], detokenized_text: str) -> Dict[str, Any]:
        """Inject detokenized text back into response format."""
        raise NotImplementedError
    
    async def forward_request(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """Forward request to actual LLM provider."""
        raise NotImplementedError


class OpenAIProxy(LLMProxy):
    """Proxy for OpenAI API (ChatGPT, GPT-4, etc.)."""
    
    async def extract_messages(self, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract messages from OpenAI chat completions request."""
        messages = body.get("messages", [])
        return messages
    
    async def inject_messages(self, body: Dict[str, Any], sanitized_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Inject sanitized messages into OpenAI request."""
        body["messages"] = sanitized_messages
        return body
    
    async def extract_response_text(self, response_body: Dict[str, Any]) -> Optional[str]:
        """Extract text from OpenAI response."""
        try:
            if "choices" in response_body and len(response_body["choices"]) > 0:
                return response_body["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            pass
        return None
    
    async def inject_response_text(self, response_body: Dict[str, Any], detokenized_text: str) -> Dict[str, Any]:
        """Inject detokenized text into OpenAI response."""
        if "choices" in response_body and len(response_body["choices"]) > 0:
            response_body["choices"][0]["message"]["content"] = detokenized_text
        return response_body
    
    async def forward_request(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """Forward to OpenAI API."""
        # Remove hop-by-hop headers
        clean_headers = {k: v for k, v in headers.items() 
                        if k.lower() not in ['host', 'content-length', 'connection']}
        
        response = await self.http_client.post(
            url,
            headers=clean_headers,
            json=body
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"OpenAI API error: {response.text}"
            )
        
        return response.json()


class ClaudeProxy(LLMProxy):
    """Proxy for Anthropic Claude API."""
    
    async def extract_messages(self, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract messages from Claude request."""
        messages = body.get("messages", [])
        return messages
    
    async def inject_messages(self, body: Dict[str, Any], sanitized_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Inject sanitized messages into Claude request."""
        body["messages"] = sanitized_messages
        return body
    
    async def extract_response_text(self, response_body: Dict[str, Any]) -> Optional[str]:
        """Extract text from Claude response."""
        try:
            if "content" in response_body and len(response_body["content"]) > 0:
                return response_body["content"][0]["text"]
        except (KeyError, IndexError):
            pass
        return None
    
    async def inject_response_text(self, response_body: Dict[str, Any], detokenized_text: str) -> Dict[str, Any]:
        """Inject detokenized text into Claude response."""
        if "content" in response_body and len(response_body["content"]) > 0:
            response_body["content"][0]["text"] = detokenized_text
        return response_body
    
    async def forward_request(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """Forward to Anthropic API."""
        clean_headers = {k: v for k, v in headers.items() 
                        if k.lower() not in ['host', 'content-length', 'connection']}
        
        response = await self.http_client.post(
            url,
            headers=clean_headers,
            json=body
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Claude API error: {response.text}"
            )
        
        return response.json()


class GeminiProxy(LLMProxy):
    """Proxy for Google Gemini API."""
    
    async def extract_messages(self, body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract messages from Gemini request."""
        contents = body.get("contents", [])
        return contents
    
    async def inject_messages(self, body: Dict[str, Any], sanitized_contents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Inject sanitized messages into Gemini request."""
        body["contents"] = sanitized_contents
        return body
    
    async def extract_response_text(self, response_body: Dict[str, Any]) -> Optional[str]:
        """Extract text from Gemini response."""
        try:
            if "candidates" in response_body and len(response_body["candidates"]) > 0:
                candidate = response_body["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if len(parts) > 0 and "text" in parts[0]:
                        return parts[0]["text"]
        except (KeyError, IndexError):
            pass
        return None
    
    async def inject_response_text(self, response_body: Dict[str, Any], detokenized_text: str) -> Dict[str, Any]:
        """Inject detokenized text into Gemini response."""
        try:
            if "candidates" in response_body and len(response_body["candidates"]) > 0:
                candidate = response_body["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    candidate["content"]["parts"][0]["text"] = detokenized_text
        except (KeyError, IndexError):
            pass
        return response_body
    
    async def forward_request(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """Forward to Google Gemini API."""
        clean_headers = {k: v for k, v in headers.items() 
                        if k.lower() not in ['host', 'content-length', 'connection']}
        
        response = await self.http_client.post(
            url,
            headers=clean_headers,
            json=body
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Gemini API error: {response.text}"
            )
        
        return response.json()


class TransparentProxyHandler:
    """
    Handles transparent proxying for all LLM providers.
    Automatically redacts requests and detokenizes responses.
    """
    
    def __init__(self, mcp_functions):
        """
        Initialize with MCP server functions.
        mcp_functions should be a dict with: redact_internal, detokenize_internal, tokens
        """
        self.mcp = mcp_functions
        self.openai = OpenAIProxy(mcp_functions)
        self.claude = ClaudeProxy(mcp_functions)
        self.gemini = GeminiProxy(mcp_functions)
    
    async def process_request(
        self,
        provider: str,
        target_url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process request through MCP pipeline:
        1. Extract messages from provider format
        2. Redact sensitive content
        3. Forward to real provider
        4. Detokenize response
        5. Return in original format
        """
        
        # Select appropriate proxy
        proxy = {
            "openai": self.openai,
            "claude": self.claude,
            "gemini": self.gemini
        }.get(provider)
        
        if not proxy:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
        
        # Extract messages
        messages = await proxy.extract_messages(body)
        
        # Redact each message
        sanitized_messages = []
        token_handles = []
        
        for msg in messages:
            # Extract text content based on provider format
            if provider == "gemini":
                text_content = msg.get("parts", [{}])[0].get("text", "") if "parts" in msg else ""
            else:
                text_content = msg.get("content", "")
            
            if not text_content:
                sanitized_messages.append(msg)
                token_handles.append(None)
                continue
            
            # Redact with MCP
            try:
                redact_result = await self._redact_text(text_content, context)
                sanitized_text = redact_result["sanitized"]
                token_handle = redact_result["handle"]
                
                # Update message with sanitized content
                sanitized_msg = msg.copy()
                if provider == "gemini":
                    if "parts" in sanitized_msg:
                        sanitized_msg["parts"][0]["text"] = sanitized_text
                else:
                    sanitized_msg["content"] = sanitized_text
                
                sanitized_messages.append(sanitized_msg)
                token_handles.append(token_handle)
                
            except Exception as e:
                # If blocked, return error immediately
                if "blocked" in str(e).lower():
                    raise HTTPException(
                        status_code=403,
                        detail="Request blocked by security policy: contains sensitive content"
                    )
                raise
        
        # Inject sanitized messages into request
        sanitized_body = await proxy.inject_messages(body, sanitized_messages)
        
        # Forward to real provider
        llm_response = await proxy.forward_request(target_url, headers, sanitized_body)
        
        # Extract response text
        response_text = await proxy.extract_response_text(llm_response)
        
        # Detokenize if we have token handles
        if response_text and any(token_handles):
            # Use the last valid token handle (usually the user's message)
            active_handle = next((h for h in reversed(token_handles) if h), None)
            if active_handle:
                try:
                    detokenized = await self._detokenize_text(
                        response_text,
                        active_handle,
                        context
                    )
                    llm_response = await proxy.inject_response_text(llm_response, detokenized)
                except Exception as e:
                    # Log but don't fail on detokenization errors
                    print(f"Detokenization warning: {e}")
        
        return llm_response
    
    async def _redact_text(self, text: str, context: Dict[str, Any]) -> Dict[str, str]:
        """Call MCP redact function."""
        from .models import RedactRequest, Context
        
        # Build context
        ctx = Context(
            caller=context.get("caller", "proxy"),
            region=context.get("region", "us"),
            env=context.get("env", "prod"),
            conversation_id=context.get("conversation_id", "proxy-session")
        )
        
        # Create request
        req = RedactRequest(payload=text, context=ctx)
        
        # Call redact logic using the passed function
        result = self.mcp["redact_internal"](req)
        
        return {
            "sanitized": result["sanitized_payload"],
            "handle": result["token_map_handle"]
        }
    
    async def _detokenize_text(
        self,
        text: str,
        token_handle: str,
        context: Dict[str, Any]
    ) -> str:
        """Call MCP detokenize function."""
        from .models import DetokenizeRequest, Context
        
        ctx = Context(
            caller=context.get("caller", "proxy"),
            region=context.get("region", "us"),
            env=context.get("env", "prod"),
            conversation_id=context.get("conversation_id", "proxy-session")
        )
        
        req = DetokenizeRequest(
            payload=text,
            token_map_handle=token_handle,
            allow_categories=["pii", "ops_sensitive"],  # Never restore secrets
            context=ctx
        )
        
        # Use skip_auth=True for proxy (already authenticated by proxy endpoint)
        result = self.mcp["detokenize_internal"](req, skip_auth=True)
        return result["restored_payload"]
