# MCP Redaction Server - Troubleshooting Guide

## 🐛 Common Issues

### Requests Hanging / Stuck Processing

**Symptoms:**
- Chat requests show "Just a sec..." but never complete
- No response returned from proxy endpoints
- Requests timeout after 30-120 seconds

**Root Cause:**
The proxy is trying to forward requests to real LLM providers (OpenAI, Claude, Gemini) but:
1. No API key is configured in the request headers
2. Or the upstream API rejects the request due to authentication failure
3. The proxy then hangs waiting for a response that never comes

**Solutions:**

#### Option 1: Configure API Keys (Recommended for Production)

If you want to actually use the proxy to forward to real LLM providers:

```bash
# Add your API keys to the environment
export OPENAI_API_KEY="sk-your-key-here"
export ANTHROPIC_API_KEY="your-claude-key"
export GOOGLE_API_KEY="your-gemini-key"

# Then make requests with proper authorization
curl -X POST http://localhost:8019/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

#### Option 2: Use Direct API Endpoints (Recommended for Testing)

Instead of using the transparent proxy mode, use the direct MCP endpoints:

```bash
# Tokenize text (redact PII)
curl -X POST http://localhost:8019/tokenize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My name is John Smith and my SSN is 123-45-6789",
    "policy": "standard"
  }'

# Response:
# {
#   "sanitized_payload": "My name is «token:PII:a1b2» and my SSN is «token:PII:c3d4»",
#   "token_map_handle": "tm_1730234567890",
#   "blocked": false
# }

# Detokenize (restore original values)
curl -X POST http://localhost:8019/detokenize \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "My name is «token:PII:a1b2» and my SSN is «token:PII:c3d4»",
    "token_map_handle": "tm_1730234567890",
    "allow_categories": ["pii"]
  }'
```

#### Option 3: Disable Proxy Mode

If you're not using the transparent proxy feature:

```bash
# Edit /opt/mcp-redaction/.env
PROXY_MODE_ENABLED=false

# Restart service
./stop.sh && ./start.sh
```

---

## 📊 Monitoring Live Requests

### View All Logs
```bash
./logs.sh
```

### Monitor Specific Events
```bash
# Watch for HTTP requests
tail -f /opt/mcp-redaction/logs/stderr.log | grep "POST\|GET\|/v1/"

# Watch for errors
tail -f /opt/mcp-redaction/logs/stderr.log | grep -i "error\|exception"

# Use the monitor script
./monitor.sh
```

---

## 🔍 Diagnostic Commands

### Check Service Status
```bash
./status.sh
```

### Test Health Endpoint
```bash
curl http://localhost:8019/health | python3 -m json.tool
```

### Check Configuration
```bash
# View environment variables
grep -v "^#" /opt/mcp-redaction/.env | grep -v "^$"

# Check if proxy mode is enabled
curl -s http://localhost:8019/health | grep proxy_mode_enabled
```

### Test Redaction
```bash
# Simple test
curl -X POST http://localhost:8019/tokenize \
  -H "Content-Type: application/json" \
  -d '{"text":"My email is test@example.com","policy":"standard"}' \
  | python3 -m json.tool
```

---

## 🚨 Error Messages

### "Cannot connect to OpenAI API"
- **Cause:** Network issue or wrong upstream URL
- **Fix:** Check `OPENAI_UPSTREAM_URL` in `.env`

### "OpenAI API error: 401 Unauthorized"
- **Cause:** Missing or invalid API key
- **Fix:** Add valid `Authorization: Bearer YOUR_KEY` header to requests

### "Request timed out"
- **Cause:** Upstream API not responding
- **Fix:** Check network, API key, and upstream URL configuration

### "Health check failed"
- **Cause:** Service not running or crashed
- **Fix:** Check logs with `./logs.sh`, restart with `./stop.sh && ./start.sh`

---

## 💡 Tips

1. **Start Simple:** Test direct endpoints first before trying proxy mode
2. **Check Logs:** Always check `./logs.sh` when something doesn't work
3. **Verify Config:** Use `./status.sh` to see current configuration
4. **Monitor Live:** Use `./monitor.sh` during testing to see real-time activity
5. **Test Health:** `curl http://localhost:8019/health` should always return JSON

---

## 🆘 Getting Help

If you're still stuck:

1. Check the logs: `./logs.sh`
2. Check service status: `./status.sh`
3. Verify configuration: `cat /opt/mcp-redaction/.env`
4. Test health endpoint: `curl http://localhost:8019/health`
5. Review this guide and the main README.md
