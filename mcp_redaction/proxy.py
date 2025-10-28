"""
Transparent Proxy Mode for LLM Providers
Intercepts API calls to OpenAI, Claude, and Gemini
Automatically redacts requests and detokenizes responses
Supports both streaming and non-streaming responses
"""

import httpx
import json
import time
import re
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse


class StreamingDetokenizer:
    """
    Handles real-time detokenization of streaming responses.
    Buffers partial tokens across chunk boundaries.
    """
    
    def __init__(self, token_handle: str, mcp_functions: Dict[str, Any]):
        self.token_handle = token_handle
        self.mcp = mcp_functions
        self.buffer = ""
        self.token_pattern = re.compile(r'«token:[A-Z_]+:[0-9a-f]{4}»')
    
    async def process_chunk(self, chunk_text: str) -> str:
        """
        Process a chunk of text, detokenizing complete tokens.
        Buffers partial tokens for next chunk.
        """
        # Add chunk to buffer
        self.buffer += chunk_text
        
        # Find all complete tokens in buffer
        matches = list(self.token_pattern.finditer(self.buffer))
        
        if not matches:
            # No complete tokens - check if we have a partial token at the end
            if '«token:' in self.buffer:
                # Might be partial token - keep in buffer
                split_pos = self.buffer.rfind('«token:')
                output = self.buffer[:split_pos]
                self.buffer = self.buffer[split_pos:]
                return output
            else:
                # No tokens at all - flush buffer
                output = self.buffer
                self.buffer = ""
                return output
        
        # Process complete tokens
        last_match_end = 0
        output_parts = []
        
        for match in matches:
            # Add text before token
            output_parts.append(self.buffer[last_match_end:match.start()])
            
            # Detokenize the token
            token = match.group(0)
            detokenized = await self._detokenize_single_token(token)
            output_parts.append(detokenized)
            
            last_match_end = match.end()
        
        # Keep any remaining text in buffer (might be partial token)
        remainder = self.buffer[last_match_end:]
        self.buffer = remainder if '«token:' in remainder else ""
        
        output = ''.join(output_parts)
        if not self.buffer:
            output += remainder
        
        return output
    
    async def flush(self) -> str:
        """Flush any remaining buffer content."""
        output = self.buffer
        self.buffer = ""
        return output
    
    async def _detokenize_single_token(self, token_placeholder: str) -> str:
        """Detokenize a single token placeholder."""
        from .models import DetokenizeRequest, Context
        
        try:
            # Create minimal request for detokenization
            req = DetokenizeRequest(
                payload=token_placeholder,
                token_map_handle=self.token_handle,
                allow_categories=["pii", "ops_sensitive"],
                context=Context(caller="streaming-proxy", region="us", env="prod")
            )
            
            result = self.mcp["detokenize_internal"](req, skip_auth=True)
            return result["restored_payload"]
        except Exception:
            # If detokenization fails, return original token
            return token_placeholder


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
        """Forward to OpenAI API (non-streaming)."""
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
    
    async def stream_request(
        self,
        url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        detokenizer: StreamingDetokenizer
    ) -> AsyncIterator[str]:
        """
        Stream request to OpenAI and detokenize chunks in real-time.
        Yields Server-Sent Events format.
        """
        clean_headers = {k: v for k, v in headers.items() 
                        if k.lower() not in ['host', 'content-length', 'connection']}
        
        async with self.http_client.stream('POST', url, headers=clean_headers, json=body) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"OpenAI API error: {error_text.decode()}"
                )
            
            # Process SSE stream
            async for line in response.aiter_lines():
                if not line:
                    yield "\n"
                    continue
                
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    
                    if data == "[DONE]":
                        # Flush any remaining buffer
                        remaining = await detokenizer.flush()
                        if remaining:
                            # Send remaining content as a chunk
                            chunk_data = {
                                "id": "mcp-flush",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": body.get("model", "gpt-4"),
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": remaining},
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                        
                        yield "data: [DONE]\n\n"
                        break
                    
                    try:
                        chunk = json.loads(data)
                        
                        # Extract content from delta
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                content = delta["content"]
                                
                                # Detokenize the content
                                safe_content = await detokenizer.process_chunk(content)
                                
                                if safe_content:
                                    # Update chunk with detokenized content
                                    chunk["choices"][0]["delta"]["content"] = safe_content
                                    yield f"data: {json.dumps(chunk)}\n\n"
                            else:
                                # No content, pass through
                                yield f"{line}\n"
                        else:
                            # No choices, pass through
                            yield f"{line}\n"
                    except json.JSONDecodeError:
                        # Invalid JSON, pass through
                        yield f"{line}\n"
                else:
                    # Non-data line (comments, etc.)
                    yield f"{line}\n"


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
        """Forward to Anthropic API (non-streaming)."""
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
    
    async def stream_request(
        self,
        url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        detokenizer: StreamingDetokenizer
    ) -> AsyncIterator[str]:
        """
        Stream request to Claude and detokenize chunks in real-time.
        Yields Server-Sent Events format.
        """
        clean_headers = {k: v for k, v in headers.items() 
                        if k.lower() not in ['host', 'content-length', 'connection']}
        
        async with self.http_client.stream('POST', url, headers=clean_headers, json=body) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Claude API error: {error_text.decode()}"
                )
            
            # Process SSE stream (Claude format)
            async for line in response.aiter_lines():
                if not line:
                    yield "\n"
                    continue
                
                if line.startswith("event: ") or line.startswith("data: "):
                    if line.startswith("data: "):
                        data = line[6:]
                        
                        try:
                            chunk = json.loads(data)
                            
                            # Claude streams different event types
                            if chunk.get("type") == "content_block_delta":
                                delta = chunk.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    
                                    # Detokenize the text
                                    safe_text = await detokenizer.process_chunk(text)
                                    
                                    if safe_text:
                                        chunk["delta"]["text"] = safe_text
                                        yield f"data: {json.dumps(chunk)}\n\n"
                                else:
                                    yield f"{line}\n"
                            elif chunk.get("type") == "message_stop":
                                # Flush remaining buffer
                                remaining = await detokenizer.flush()
                                if remaining:
                                    flush_chunk = {
                                        "type": "content_block_delta",
                                        "index": 0,
                                        "delta": {"type": "text_delta", "text": remaining}
                                    }
                                    yield f"data: {json.dumps(flush_chunk)}\n\n"
                                yield f"{line}\n"
                            else:
                                # Pass through other event types
                                yield f"{line}\n"
                        except json.JSONDecodeError:
                            yield f"{line}\n"
                    else:
                        # Event type line
                        yield f"{line}\n"
                else:
                    yield f"{line}\n"


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
        """Forward to Google Gemini API (non-streaming)."""
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
    
    async def stream_request(
        self,
        url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        detokenizer: StreamingDetokenizer
    ) -> AsyncIterator[str]:
        """
        Stream request to Gemini and detokenize chunks in real-time.
        Gemini uses JSON streaming (newline-delimited JSON).
        """
        clean_headers = {k: v for k, v in headers.items() 
                        if k.lower() not in ['host', 'content-length', 'connection']}
        
        async with self.http_client.stream('POST', url, headers=clean_headers, json=body) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Gemini API error: {error_text.decode()}"
                )
            
            # Process JSON stream (newline-delimited)
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                
                try:
                    chunk = json.loads(line)
                    
                    # Extract text from Gemini response structure
                    if "candidates" in chunk and len(chunk["candidates"]) > 0:
                        candidate = chunk["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            if len(parts) > 0 and "text" in parts[0]:
                                text = parts[0]["text"]
                                
                                # Detokenize the text
                                safe_text = await detokenizer.process_chunk(text)
                                
                                if safe_text:
                                    chunk["candidates"][0]["content"]["parts"][0]["text"] = safe_text
                                    yield f"{json.dumps(chunk)}\n"
                            else:
                                yield f"{line}\n"
                        else:
                            yield f"{line}\n"
                    else:
                        # Check if this is a final chunk
                        if "candidates" in chunk:
                            # Flush remaining buffer
                            remaining = await detokenizer.flush()
                            if remaining:
                                flush_chunk = {
                                    "candidates": [{
                                        "content": {
                                            "parts": [{"text": remaining}],
                                            "role": "model"
                                        },
                                        "finishReason": "STOP",
                                        "index": 0
                                    }]
                                }
                                yield f"{json.dumps(flush_chunk)}\n"
                        yield f"{line}\n"
                except json.JSONDecodeError:
                    # Not valid JSON, pass through
                    yield f"{line}\n"


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
    
    async def process_streaming_request(
        self,
        provider: str,
        target_url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """
        Process streaming request through MCP pipeline:
        1. Extract messages from provider format
        2. Redact sensitive content
        3. Stream from real provider
        4. Detokenize chunks in real-time
        5. Yield in original format
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
        
        # Get active token handle for detokenization
        active_handle = next((h for h in reversed(token_handles) if h), None)
        
        if not active_handle:
            # No tokens to detokenize - just stream through
            async for chunk in proxy.stream_request(target_url, headers, sanitized_body, None):
                yield chunk
            return
        
        # Create detokenizer and stream with detokenization
        detokenizer = StreamingDetokenizer(active_handle, self.mcp)
        
        try:
            async for chunk in proxy.stream_request(target_url, headers, sanitized_body, detokenizer):
                yield chunk
        except Exception as e:
            print(f"Streaming error: {e}")
            raise
    
    async def process_request(
        self,
        provider: str,
        target_url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process non-streaming request through MCP pipeline:
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
        detokenized_text = response_text
        if response_text and any(token_handles):
            # Use the last valid token handle (usually the user's message)
            active_handle = next((h for h in reversed(token_handles) if h), None)
            if active_handle:
                try:
                    detokenized_text = await self._detokenize_text(
                        response_text,
                        active_handle,
                        context
                    )
                    llm_response = await proxy.inject_response_text(llm_response, detokenized_text)
                except Exception as e:
                    # Log but don't fail on detokenization errors
                    print(f"Detokenization warning: {e}")
        
        # Claim verification (if enabled)
        verification_result = await self._verify_claims_if_enabled(
            detokenized_text or response_text,
            context,
            llm_response
        )
        
        # Add verification metadata to response
        if verification_result:
            llm_response["mcp_verification"] = verification_result.to_dict()
        
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
    
    async def _verify_claims_if_enabled(
        self,
        response_text: str,
        context: Dict[str, Any],
        llm_response: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Verify claims in response if verification is enabled.
        Adds inline warnings and metadata but never blocks responses.
        """
        import os
        
        # Check if claim verification is enabled
        if os.getenv("CLAIM_VERIFICATION_ENABLED", "false").lower() != "true":
            return None
        
        if not response_text or not response_text.strip():
            return None
        
        try:
            from .claim_verification import ClaimVerifier, annotate_response_with_warnings
            
            # Get verification LLM configuration
            # Supports both cloud (OpenAI) and local (vLLM, FastAPI) models
            verification_config = {
                "model": os.getenv("CLAIM_VERIFICATION_MODEL", "gpt-4o-mini"),
                "api_key": os.getenv("CLAIM_VERIFICATION_API_KEY", os.getenv("OPENAI_API_KEY", "")),
                "base_url": os.getenv("CLAIM_VERIFICATION_BASE_URL", os.getenv("OPENAI_UPSTREAM_URL", "https://api.openai.com/v1").replace("/chat/completions", "")),
                "require_auth": os.getenv("CLAIM_VERIFICATION_REQUIRE_AUTH", "true").lower() == "true",
                "supports_json_mode": os.getenv("CLAIM_VERIFICATION_SUPPORTS_JSON", "true").lower() == "true"
            }
            
            # Create verifier with shared HTTP client
            verifier = ClaimVerifier(
                llm_client=self.openai.http_client,
                llm_config=verification_config
            )
            
            # Run verification pipeline
            verification = await verifier.verify_response(
                response_text=response_text,
                context=context,
                verification_level=os.getenv("CLAIM_VERIFICATION_LEVEL", "standard")
            )
            
            # Add inline warnings to response text if enabled
            if os.getenv("CLAIM_VERIFICATION_INLINE", "true").lower() == "true":
                annotated_text = annotate_response_with_warnings(response_text, verification)
                
                # Inject annotated text back into response
                provider = context.get("provider", "openai")
                if provider == "openai":
                    if "choices" in llm_response and len(llm_response["choices"]) > 0:
                        llm_response["choices"][0]["message"]["content"] = annotated_text
                elif provider == "claude":
                    if "content" in llm_response and len(llm_response["content"]) > 0:
                        llm_response["content"][0]["text"] = annotated_text
                elif provider == "gemini":
                    if "candidates" in llm_response and len(llm_response["candidates"]) > 0:
                        candidate = llm_response["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            candidate["content"]["parts"][0]["text"] = annotated_text
            
            return verification
            
        except Exception as e:
            print(f"Claim verification error: {e}")
            # Don't fail the request if verification fails
            return None
