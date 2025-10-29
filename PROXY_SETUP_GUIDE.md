# 🔐 Transparent Proxy Setup Guide

## The Problem You're Facing

You're right - **if users are chatting directly from their browsers to OpenAI/Claude/Gemini, the MCP proxy is completely bypassed!**

The browser → vendor server connection means:
- ❌ No redaction happening
- ❌ No audit logging
- ❌ No compliance enforcement
- ❌ Your MCP server is just sitting idle

## The Solution: Route Through the Proxy

To actually use the MCP proxy, you need to **intercept and route traffic** through your MCP server BEFORE it reaches the vendor APIs.

---

## 🏗️ Architecture Options

### Option 1: Configure API Clients (Easiest)

For programmatic API usage, configure the base URL to point to your MCP proxy:

#### Python (OpenAI SDK)
```python
from openai import OpenAI

# Instead of connecting directly to OpenAI
client = OpenAI(
    base_url="http://your-mcp-server.com:8019/v1",  # Your MCP proxy
    api_key="your-openai-api-key"  # Still needed for upstream
)

# Your code works unchanged - redaction happens automatically!
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "My SSN is 123-45-6789"}]
)
```

#### JavaScript/TypeScript (OpenAI SDK)
```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://your-mcp-server.com:8019/v1',
  apiKey: process.env.OPENAI_API_KEY,
});

const response = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Hello!' }],
});
```

#### Claude (Anthropic SDK)
```python
import anthropic

client = anthropic.Anthropic(
    base_url="http://your-mcp-server.com:8019",  # Points to your proxy
    api_key="your-claude-api-key"
)

response = client.messages.create(
    model="claude-3-opus-20240229",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=1024
)
```

---

### Option 2: Browser Extension (For Web Apps)

For browser-based chat interfaces like ChatGPT web, Claude web, etc., you need a **browser extension** or **network-level proxy**.

#### A. Custom Browser Extension

Create a Chrome/Firefox extension that:

1. **Intercepts API requests** to `api.openai.com`, `api.anthropic.com`, etc.
2. **Rewrites the URL** to point to your MCP proxy
3. **Forwards the request** through your MCP server
4. **Returns the response** to the web page

Example manifest:
```json
{
  "name": "MCP Compliance Proxy",
  "version": "1.0",
  "manifest_version": 3,
  "permissions": ["webRequest", "webRequestBlocking"],
  "host_permissions": [
    "https://api.openai.com/*",
    "https://api.anthropic.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  }
}
```

Example background.js:
```javascript
chrome.webRequest.onBeforeRequest.addListener(
  function(details) {
    // Intercept OpenAI API calls
    if (details.url.includes('api.openai.com')) {
      return {
        redirectUrl: details.url.replace(
          'https://api.openai.com',
          'http://your-mcp-server.com:8019'
        )
      };
    }
  },
  {urls: ["https://api.openai.com/*"]},
  ["blocking"]
);
```

---

### Option 3: Network-Level Proxy (Enterprise)

For organization-wide enforcement, use a **reverse proxy** or **MITM proxy**:

#### A. Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/mcp-proxy

server {
    listen 443 ssl;
    server_name api.openai.com;  # Intercept OpenAI requests
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        # Route to MCP server
        proxy_pass http://your-mcp-server:8019;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 443 ssl;
    server_name api.anthropic.com;  # Intercept Claude requests
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://your-mcp-server:8019;
        proxy_set_header Host $host;
    }
}
```

Then use DNS to route `api.openai.com` → your Nginx server.

#### B. Corporate Firewall Rules

Configure your firewall to:
1. Block direct access to `api.openai.com`, `api.anthropic.com`
2. Force all traffic through your MCP proxy
3. Enforce proxy usage via network policies

---

### Option 4: VPN + DNS Override (Medium Security)

For teams:

1. **Set up a VPN** with custom DNS
2. **Override DNS entries**:
   ```
   api.openai.com → your-mcp-server-ip
   api.anthropic.com → your-mcp-server-ip
   ```
3. **Users connect to VPN**
4. **All API calls automatically routed** through your MCP proxy

---

## 🔧 Configuration for Each Vendor

### OpenAI

Your MCP server endpoint: `http://your-server:8019/v1/chat/completions`

Configure clients:
```bash
export OPENAI_API_BASE="http://your-server:8019/v1"
```

### Claude (Anthropic)

Your MCP server endpoint: `http://your-server:8019/v1/messages`

Configure clients:
```bash
export ANTHROPIC_BASE_URL="http://your-server:8019"
```

### Gemini (Google)

Your MCP server endpoint: `http://your-server:8019/v1/models/{model}:generateContent`

Configure clients:
```python
import google.generativeai as genai

genai.configure(
    api_key="your-api-key",
    transport="rest",
    client_options={"api_endpoint": "http://your-server:8019"}
)
```

---

## 🔐 API Key Handling

### The Flow:

```
User App → MCP Proxy → Vendor API
           ↓
      [Redaction]
      [Audit Log]
      [Policy Check]
```

### Where API Keys Go:

1. **User provides their API key** in the request (`Authorization` header)
2. **MCP proxy intercepts** the request
3. **MCP redacts sensitive data** from the request
4. **MCP forwards** the sanitized request to the vendor API **with the original API key**
5. **Vendor processes** the request
6. **MCP detokenizes** the response before returning to user

### Example:

```bash
# User makes request to YOUR proxy (not directly to OpenAI)
curl -X POST http://your-mcp-server:8019/v1/chat/completions \
  -H "Authorization: Bearer sk-user-openai-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "My SSN is 123-45-6789"}]
  }'

# MCP proxy:
# 1. Receives request
# 2. Redacts: "My SSN is «token:PII:a1b2»"
# 3. Forwards to api.openai.com with user's API key
# 4. Gets response from OpenAI
# 5. Detokenizes any tokens in response
# 6. Returns to user
```

---

## 🚀 Quick Start for Testing

### 1. Start Your MCP Server
```bash
./start.sh  # macOS
./linux-start.sh  # Linux
```

### 2. Test with curl
```bash
curl -X POST http://localhost:8019/v1/chat/completions \
  -H "Authorization: Bearer YOUR_OPENAI_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "My email is john@secret.com"}
    ]
  }'
```

### 3. Watch the Logs
```bash
./monitor.sh  # See redaction in action
```

---

## 📊 Deployment Patterns

### Pattern 1: Development/Testing
- Developers configure their local API clients
- Use `http://localhost:8019` as base URL
- Each developer runs MCP locally

### Pattern 2: Team Server
- Deploy MCP on internal server (e.g., `mcp.internal.company.com`)
- Team members configure clients to use team server
- Centralized audit logs

### Pattern 3: Production/Enterprise
- Deploy MCP behind load balancer
- Use network-level routing (DNS/firewall)
- Enforce proxy usage via corporate policies
- High availability setup

---

## 🔒 Security Considerations

### SSL/TLS
For production, run behind HTTPS:
```bash
# Use Nginx or Caddy as HTTPS termination
# Then proxy to MCP server on localhost:8019
```

### Authentication
Add authentication to your MCP proxy:
```python
# In server.py, add middleware for API key validation
# Or use OAuth/JWT for user authentication
```

### Network Isolation
- Run MCP in private network
- Only expose via VPN or internal network
- Use firewall rules to restrict access

---

## 💡 Best Practices

1. **Start small**: Test with API clients first before browser extensions
2. **Monitor logs**: Use `./monitor.sh` to see what's being redacted
3. **Test thoroughly**: Verify redaction works for your use cases
4. **Document for users**: Provide clear setup instructions
5. **Plan for scale**: Use load balancing for production

---

## 🆘 Troubleshooting

### "My requests still go directly to OpenAI"
- ✅ Check: Is your client configured with the correct base URL?
- ✅ Check: Are you using the MCP proxy port (8019)?
- ✅ Check: Monitor with `./monitor.sh` to see if requests arrive

### "API returns 401 Unauthorized"
- ✅ Check: Are you passing the vendor API key in headers?
- ✅ Check: Is the API key valid?
- ✅ Check: Are headers being forwarded correctly?

### "Responses are empty or garbled"
- ✅ Check: Is detokenization enabled?
- ✅ Check: Are the right token categories allowed?
- ✅ Check: View logs for detokenization errors

---

## 📚 Next Steps

1. **Read**: `TRANSPARENT_PROXY.md` for architecture details
2. **Configure**: Your first API client to use the proxy
3. **Test**: With sample requests containing PII
4. **Deploy**: Choose deployment pattern for your organization
5. **Monitor**: Use audit logs to verify compliance

---

**Remember**: The proxy only works if traffic actually goes THROUGH it. Configuration is key! 🔑
