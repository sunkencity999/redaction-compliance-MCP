# Transparent Proxy Mode

**Zero-code integration for existing applications**

The MCP Redaction Server can act as a transparent proxy for OpenAI, Claude, and Gemini APIs, automatically redacting sensitive data in requests and detokenizing responses.

---

## 🎯 Use Case

You have existing applications calling OpenAI/Claude/Gemini APIs and want to add MCP protection **without changing any application code**.

**Before:**
```
Your App → OpenAI API
```

**After:**
```
Your App → MCP Server → OpenAI API
           (redacts)     (detokenizes)
```

---

## 🚀 Quick Start

### Step 1: Enable Proxy Mode

Add to `/opt/mcp-redaction/.env`:

```bash
# Enable transparent proxy
PROXY_MODE_ENABLED=true

# Upstream API endpoints (defaults shown)
OPENAI_UPSTREAM_URL=https://api.openai.com/v1/chat/completions
CLAUDE_UPSTREAM_URL=https://api.anthropic.com/v1/messages
GEMINI_UPSTREAM_URL=https://generativelanguage.googleapis.com

# Add proxy as trusted caller for detokenization
DETOKENIZE_TRUSTED_CALLERS=demo_client,openai-proxy,claude-proxy,gemini-proxy
```

### Step 2: Restart Service

```bash
sudo systemctl restart mcp-redaction
```

### Step 3: Update Your Application

**OpenAI:**
```python
import openai

# Just change the base URL!
openai.api_base = "https://mcp.yourcompany.com/v1"
openai.api_key = "your-openai-key"  # Still your real OpenAI key

# Your existing code works unchanged
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "My AWS key is AKIA..."}]
)
# Sensitive data automatically redacted before OpenAI sees it!
```

**Claude:**
```python
from anthropic import Anthropic

client = Anthropic(
    api_key="your-claude-key",
    base_url="https://mcp.yourcompany.com/v1/messages"
)

response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "My password is secret123"}]
)
# Protected automatically!
```

**Gemini:**
```python
import google.generativeai as genai

genai.configure(
    api_key="your-gemini-key",
    transport="rest",
    client_options={"api_endpoint": "https://mcp.yourcompany.com/v1"}
)

model = genai.GenerativeModel('gemini-pro')
response = model.generate_content("My SSN is 123-45-6789")
# Redacted before Gemini sees it!
```

---

## 🔧 How It Works

### Request Flow

1. **Your app** makes standard API call to MCP server
2. **MCP extracts** messages from provider-specific format
3. **MCP classifies** content for sensitive data
4. **MCP redacts** secrets, PII, credentials
5. **MCP forwards** sanitized request to real provider (OpenAI/Claude/Gemini)
6. **Provider responds** with generated content
7. **MCP detokenizes** response (restores non-secrets)
8. **Your app** receives response in original format

### What Gets Redacted

- ✅ **Secrets**: AWS keys, API tokens, passwords, crypto keys
- ✅ **PII**: Credit cards, SSNs, emails, phone numbers  
- ✅ **Credentials**: OAuth tokens, connection strings
- ✅ **Infrastructure**: Internal IPs, hostnames, domains

### What Gets Restored

- ✅ **PII**: Credit cards, emails (if policy allows)
- ✅ **Ops Data**: IPs, hostnames (if needed)
- ❌ **Secrets**: NEVER restored (stay tokenized forever)

---

## 📡 Supported Endpoints

### OpenAI

| Endpoint | Path | Status |
|----------|------|--------|
| Chat Completions | `POST /v1/chat/completions` | ✅ Supported |

**Client Libraries:**
- `openai` (Python)
- `openai-node` (Node.js)
- Any HTTP client pointing to `/v1`

### Claude (Anthropic)

| Endpoint | Path | Status |
|----------|------|--------|
| Messages | `POST /v1/messages` | ✅ Supported |

**Client Libraries:**
- `anthropic` (Python)
- `@anthropic-ai/sdk` (Node.js)

### Gemini (Google)

| Endpoint | Path | Status |
|----------|------|--------|
| Generate Content | `POST /v1/models/{model}:generateContent` | ✅ Supported |
| Generate Content (Beta) | `POST /v1beta/models/{model}:generateContent` | ✅ Supported |

**Client Libraries:**
- `google-generativeai` (Python)
- `@google/generative-ai` (Node.js)

---

## 🌐 Network-Level Integration

### Option 1: DNS Override

Modify `/etc/hosts` on client machines:

```
# /etc/hosts
# Redirect OpenAI API to MCP server
23.45.67.89  api.openai.com
```

**Pros:** Works for all applications  
**Cons:** Requires root, affects entire machine

### Option 2: Network Proxy

Configure firewall/router to redirect:

```bash
# iptables example
iptables -t nat -A OUTPUT -p tcp --dport 443 \
  -d api.openai.com -j DNAT \
  --to-destination mcp.yourcompany.com:443
```

**Pros:** Centralized, transparent  
**Cons:** Requires network access

### Option 3: Environment Variables

Set base URLs via environment (recommended):

```bash
export OPENAI_API_BASE=https://mcp.yourcompany.com/v1
export ANTHROPIC_BASE_URL=https://mcp.yourcompany.com/v1/messages
```

**Pros:** No code changes, easy rollback  
**Cons:** Requires env var support

---

## 🔐 Authentication

### API Keys

Your **original provider API keys** still work! The MCP server forwards them to the upstream provider.

```python
# Your real OpenAI key
openai.api_key = "sk-proj-abc123..."

# MCP server forwards this to OpenAI
# OpenAI validates it normally
```

### Custom Headers (Optional)

Add metadata for better audit trails:

```python
import openai

openai.api_base = "https://mcp.yourcompany.com/v1"
openai.api_key = "sk-proj-..."

# Optional: Identify your application
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[...],
    headers={
        "X-MCP-Caller": "my-chatbot-app",
        "X-MCP-Region": "us",
        "X-MCP-Conversation-ID": "session-123"
    }
)
```

These headers appear in audit logs for better tracking.

---

## 📊 Monitoring & Audit

### Check Health

```bash
curl https://mcp.yourcompany.com/health
```

Response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "proxy_mode_enabled": true,
  "token_backend": "redis",
  "siem_enabled": true
}
```

### Audit Logs

All proxied requests are logged:

```json
{
  "ts": "2024-01-15T14:30:00Z",
  "caller": "openai-proxy",
  "action": "redact",
  "categories": ["secret", "pii"],
  "redaction_counts": {"secret": 1, "pii": 2},
  "decision": {"action": "redact"}
}
```

### SIEM Integration

Audit logs automatically ship to your configured SIEM:
- Splunk HEC
- Elasticsearch
- Datadog
- Syslog

See `SIEM_INTEGRATION.md` for details.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROXY_MODE_ENABLED` | Enable transparent proxy | `false` |
| `OPENAI_UPSTREAM_URL` | Real OpenAI endpoint | `https://api.openai.com/v1/chat/completions` |
| `CLAUDE_UPSTREAM_URL` | Real Claude endpoint | `https://api.anthropic.com/v1/messages` |
| `GEMINI_UPSTREAM_URL` | Real Gemini endpoint | `https://generativelanguage.googleapis.com` |
| `DETOKENIZE_TRUSTED_CALLERS` | Callers allowed to detokenize | `demo_client` |

### Policy Configuration

Edit `/opt/mcp-redaction/mcp_redaction/sample_policies/default.yaml`:

```yaml
callers:
  openai-proxy:
    action: redact  # Always redact for proxy
    detokenize: ["pii", "ops_sensitive"]  # Restore these categories
    
  claude-proxy:
    action: redact
    detokenize: ["pii"]
    
  gemini-proxy:
    action: block  # Block if too sensitive
    detokenize: []
```

---

## 🧪 Testing

### Test OpenAI Proxy

```python
import openai

openai.api_base = "http://localhost:8019/v1"  # Local testing
openai.api_key = "your-real-key"

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "My AWS key is AKIAIOSFODNN7EXAMPLE"}
    ]
)

print(response.choices[0].message.content)
# AWS key was redacted before reaching OpenAI!
```

### Test Claude Proxy

```python
from anthropic import Anthropic

client = Anthropic(
    api_key="your-real-key",
    base_url="http://localhost:8019/v1/messages"
)

response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "My credit card is 4111-1111-1111-1111"}
    ]
)

print(response.content[0].text)
# Credit card was redacted!
```

### Test Gemini Proxy

```python
import google.generativeai as genai

genai.configure(
    api_key="your-real-key",
    transport="rest",
    client_options={"api_endpoint": "http://localhost:8019/v1"}
)

model = genai.GenerativeModel('gemini-pro')
response = model.generate_content(
    "Help me debug this: my password is SuperSecret123"
)

print(response.text)
# Password was redacted!
```

---

## 🚨 Troubleshooting

### Proxy Mode Not Working

**Check if enabled:**
```bash
curl http://localhost:8019/health | jq '.proxy_mode_enabled'
# Should return: true
```

**If false:**
```bash
echo "PROXY_MODE_ENABLED=true" >> /opt/mcp-redaction/.env
sudo systemctl restart mcp-redaction
```

### Authentication Errors

The MCP server **forwards your original API keys** to the upstream provider. If you get auth errors:

1. Verify your API key works directly: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
2. Check MCP server logs: `journalctl -u mcp-redaction -f`
3. Ensure headers are being forwarded correctly

### Detokenization Not Working

**Error:** "Caller not trusted to detokenize"

**Fix:**
```bash
# Add proxy callers to trusted list
echo "DETOKENIZE_TRUSTED_CALLERS=demo_client,openai-proxy,claude-proxy,gemini-proxy" \
  >> /opt/mcp-redaction/.env

sudo systemctl restart mcp-redaction
```

### Slow Response Times

Proxy adds ~100-200ms latency for redaction/detokenization.

**Optimize:**
- Use Redis backend (not in-memory)
- Enable SIEM batching
- Increase MCP server resources
- Deploy MCP server close to upstream APIs

---

## 📈 Performance

### Latency

| Component | Latency |
|-----------|---------|
| Redaction | 20-50ms |
| Detokenization | 10-30ms |
| Network (proxy → upstream) | 50-100ms |
| **Total Overhead** | **~100-200ms** |

### Throughput

- **Requests/sec**: 500-1000 (single instance)
- **Concurrent connections**: 1000+
- **Scales horizontally**: Yes (Redis backend required)

---

## 🔒 Security Considerations

### SSL/TLS

**CRITICAL:** Always use HTTPS in production!

```bash
# MCP server must have valid SSL cert
https://mcp.yourcompany.com  # ✅ Good
http://mcp.yourcompany.com   # ❌ Insecure!
```

### API Key Security

- API keys are **forwarded** to upstream providers (not stored)
- MCP server **never logs** API keys
- Use TLS to protect keys in transit

### Network Security

```
[Your App] --HTTPS--> [MCP Server] --HTTPS--> [OpenAI/Claude/Gemini]
            encrypted              encrypted
```

Both hops must use HTTPS!

---

## 🎓 Best Practices

### 1. Test in Development First

```python
# Development
openai.api_base = "http://localhost:8019/v1"

# Production
openai.api_base = "https://mcp.yourcompany.com/v1"
```

### 2. Use Environment Variables

```bash
# .env
OPENAI_API_BASE=https://mcp.yourcompany.com/v1
OPENAI_API_KEY=sk-proj-...
```

```python
import os
import openai

openai.api_base = os.getenv("OPENAI_API_BASE")
openai.api_key = os.getenv("OPENAI_API_KEY")
```

### 3. Add Custom Headers for Audit

```python
headers = {
    "X-MCP-Caller": "production-chatbot",
    "X-MCP-Conversation-ID": f"user-{user_id}"
}
```

### 4. Monitor SIEM Logs

Set up alerts for:
- High redaction counts
- Blocked requests
- Unusual patterns

### 5. Gradual Rollout

1. Enable proxy for 1% of traffic
2. Monitor metrics
3. Increase to 10%, 50%, 100%

---

## 📚 Related Documentation

- **Direct API Integration**: See `README.md` for SDK usage
- **SIEM Integration**: See `SIEM_INTEGRATION.md`
- **Deployment**: See `DEPLOYMENT.md`
- **Policy Configuration**: See `mcp_redaction/sample_policies/default.yaml`

---

## ❓ FAQ

**Q: Do I need to change my application code?**  
A: No! Just change the base URL.

**Q: Will my API keys still work?**  
A: Yes, they're forwarded to the real provider.

**Q: What's the performance impact?**  
A: ~100-200ms latency added for redaction/detokenization.

**Q: Can I use this with SDKs?**  
A: Yes! Works with official OpenAI, Anthropic, and Google SDKs.

**Q: Does it work with streaming?**  
A: Not yet. Streaming support coming in v2.1.

**Q: Can I proxy other providers (Cohere, etc.)?**  
A: Not yet, but easy to add. Contact us or submit a PR!

---

## 🛠️ Implementation Details

The proxy mode uses provider-specific adapters:

- **OpenAIProxy**: Handles `/v1/chat/completions` format
- **ClaudeProxy**: Handles `/v1/messages` format  
- **GeminiProxy**: Handles `/v1/models/{model}:generateContent` format

Each adapter:
1. Extracts messages from provider format
2. Redacts each message
3. Injects sanitized messages
4. Forwards to upstream
5. Extracts response text
6. Detokenizes
7. Returns in original format

See `mcp_redaction/proxy.py` for implementation.

---

**Transparent proxy mode enables zero-code integration with existing applications while providing full MCP protection!**
