# Redaction & Compliance MCP Server

**Production-Ready Edition** | Version 2.0

This repository contains a **production-grade** implementation of a **Redaction & Compliance Model Context Protocol (MCP)** server.
It provides a **pre-flight / post-flight firewall** for LLM calls with comprehensive detection, classification, policy enforcement,
reversible redaction, selective detokenization, output safety, and immutable audit logging.

## ✨ Features

### 🎯 Core Capabilities
- **🔄 Streaming Support**: Real-time streaming for OpenAI, Claude, and Gemini with chunk-by-chunk detokenization
- **🛡️ Claim Verification**: Research-based hallucination detection with inline warnings (supports local models)
- **🚀 Transparent Proxy**: Zero-code integration - just change your API base URL
- **📊 Production-Grade**: NGINX, HTTPS, SIEM integration, Redis backend, systemd service

### 🔍 Advanced Detection
- **Multi-cloud credentials**: AWS (AKID, secrets), Azure (Storage Keys, SAS tokens, Connection Strings), GCP (API keys, OAuth)
- **OAuth & Bearer tokens**: JWT detection, OAuth access tokens
- **Crypto keys**: PEM (RSA, DSA, EC), PKCS#12, Kubernetes config/tokens
- **PII with validation**: 
  - Credit cards with **Luhn checksum validation**
  - SSN with **format validation** (rejects invalid area codes 000, 666, 900-999)
  - Email addresses and phone numbers
- **Internal infrastructure**: Joby Aviation domains (`*.na.joby.aero`, `*.az.joby.aero`), IP addresses, hostnames
- **Export control**: Aviation keywords (eVTOL, ITAR, FAA certification, flight control systems, propulsion)

### 🛡️ Policy Engine
- **Geo/region constraints**: US, EU, APAC, restricted regions (CN, RU, IR, KP, SY)
- **Caller-based routing**: Trusted caller lists, per-caller detokenization permissions
- **Data residency**: EU GDPR compliance, region-specific model routing
- **Category actions**: `block`, `redact`, `internal_only`, `allow`
- **Version tracking**: Policy version embedded in all decisions

### 🔐 Token Store
- **In-memory**: Fast, stateless, for dev/test
- **Redis with AES-GCM**: Production-grade with encryption at rest
  - AES-256-GCM encryption
  - PBKDF2 key derivation
  - Automatic TTL management
- **Deterministic placeholders**: `«token:TYPE:HASH4»` stable within conversation scope

### ⚠️ Output Safety
- **50+ dangerous command patterns**: Filesystem destruction, system control, K8s/Docker, databases, cloud infra, network/firewall
- **External config support**: JSON-based custom pattern loading
- **3 modes**: `warning` (annotate), `block` (redact), `silent` (pass-through)

### 📊 Audit & Compliance
- **Append-only JSONL**: Immutable audit trail
- **Full context capture**: Caller, region, categories, decisions, redaction counts
- **Query API**: Search and retrieve audit records
- **SIEM integration**: Real-time shipping to Splunk, Elasticsearch, Datadog, Syslog
- **Buffered shipping**: <5% overhead, batch mode for production

## 🚀 Production Installation (5 Minutes)

**Automated installer with NGINX, HTTPS, and Client SDK:**

```bash
# On your Linux server (Ubuntu 20.04+ or RHEL 8+)
wget https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install.sh
chmod +x install.sh
sudo ./install.sh
```

**What it does:**
- ✅ Installs all dependencies (Python 3.11, Redis, NGINX)
- ✅ Generates cryptographic secrets (you backup them)
- ✅ Configures SIEM integration (Splunk/Elasticsearch/Datadog)
- ✅ Sets up NGINX reverse proxy with HTTPS (Let's Encrypt or self-signed)
- ✅ Creates systemd service (auto-start on boot)
- ✅ Installs Python Client SDK
- ✅ Creates integration examples
- ✅ Runs full test suite (186+ tests)

**Manual installation:** See `QUICKSTART.md`

---

## 📦 Client SDKs

### Python SDK

**Seamless integration for Python/backend applications:**

```bash
# Install SDK (included in automated installer)
pip install -e .
```

**Usage:**

```python
from mcp_client import MCPClient, MCPConfig

# Configure once
mcp = MCPClient(MCPConfig(
    server_url="https://mcp.yourcompany.com",
    caller="your-app-name"
))

# Protect LLM calls automatically
user_input = "My AWS key is AKIAIOSFODNN7EXAMPLE, help me debug"

# Redact before sending to LLM
sanitized, handle = mcp.redact(user_input)
# sanitized: "My AWS key is «token:SECRET:a3f9», help me debug"

# Send sanitized version to OpenAI/Claude/etc
llm_response = your_llm_function(sanitized)

# Restore non-secret tokens
final = mcp.detokenize(llm_response, handle)

# Secrets stay tokenized, PII/ops_sensitive restored!
```

**Or use the convenience wrapper:**

```python
from mcp_client import MCPClient, MCPConfig

mcp = MCPClient(MCPConfig.from_env())

# One-line protection
response = mcp.safe_llm_call(
    user_input,
    lambda text: openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": text}]
    ).choices[0].message.content
)
```

**Examples:** See `examples/` directory after installation

---

### JavaScript/Browser SDK

**For web applications, React, Vue, Angular:**

```html
<!-- Include SDK -->
<script src="mcp_client_js/mcp-client.js"></script>

<script>
// Initialize client
const mcp = new MCPClient({
    serverUrl: 'https://mcp.yourcompany.com',
    caller: 'web-app'
});

// Protect browser-based LLM calls
async function safeChatCompletion(userInput) {
    const response = await mcp.safeLLMCall(
        userInput,
        async (sanitized) => {
            // Call OpenAI/Claude from browser
            return await callYourLLM(sanitized);
        }
    );
    return response;
}
</script>
```

**React Example:**

```jsx
import { MCPClient } from './mcp-client.js';

const mcp = new MCPClient({
    serverUrl: process.env.REACT_APP_MCP_SERVER,
    caller: 'react-app'
});

function ChatComponent() {
    const handleSubmit = async (input) => {
        try {
            const response = await mcp.safeLLMCall(input, callOpenAI);
            setMessages(prev => [...prev, response]);
        } catch (error) {
            if (error instanceof MCPBlockedError) {
                alert('Request blocked: contains sensitive data');
            }
        }
    };
    // ... rest of component
}
```

**TypeScript supported:** See `mcp_client_js/mcp-client.d.ts`

**Examples:** See `mcp_client_js/examples/` for browser and React demos

---

## 🔄 Transparent Proxy Mode (NEW!)

**Zero-code integration for existing OpenAI/Claude/Gemini apps:**

Just change your API base URL and MCP automatically protects all calls!

```python
import openai

# Change this one line:
openai.api_base = "https://mcp.yourcompany.com/v1"

# Your existing code works unchanged!
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "My AWS key is AKIA..."}]
)
# MCP automatically redacts before OpenAI sees it!
```

**Supported Providers:**
- ✅ **OpenAI** (`/v1/chat/completions`) - Streaming supported
- ✅ **Claude** (`/v1/messages`) - Streaming supported
- ✅ **Gemini** (`/v1/models/{model}:generateContent`) - Streaming supported

**Features:**
- ✅ Real-time streaming with chunk-by-chunk detokenization
- ✅ Optional claim verification (hallucination detection)
- ✅ Local model support (vLLM, Ollama, FastAPI)
- ✅ Automatic redaction + detokenization
- ✅ Full audit trail in SIEM

**Setup:**
```bash
# In .env file
PROXY_MODE_ENABLED=true
CLAIM_VERIFICATION_ENABLED=false  # Optional
DETOKENIZE_TRUSTED_CALLERS=openai-proxy,claude-proxy,gemini-proxy
```

**Full Guides:** 
- `TRANSPARENT_PROXY.md` - Proxy mode documentation
- `CLAIM_VERIFICATION.md` - Hallucination detection guide

---

## 🛡️ Claim Verification (Hallucination Detection)

**Optional post-processing layer to verify factual accuracy of LLM responses:**

Using a research-based approach, this feature analyzes LLM responses through a 4-stage pipeline to detect and flag potential hallucinations and false claims.

```python
# Enable in .env
CLAIM_VERIFICATION_ENABLED=true
CLAIM_VERIFICATION_MODEL=gpt-4o-mini  # Or local model

# Use any LLM normally via transparent proxy
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What was Argentina's inflation in 2023?"}]
)

# If LLM hallucinates a wrong number, you'll see:
print(response.choices[0].message.content)
# "Argentina's inflation reached 300% in 2023."
# ⚠️ **[CLAIM FLAGGED - HIGH CONFIDENCE]**: This claim is likely false. 
# Evidence suggests Argentina's inflation was approximately 211% in 2023.
```

**4-Stage Verification Pipeline:**
1. **Sentence Splitting** - Break response into sentences with context
2. **Selection** - Filter to verifiable factual claims
3. **Disambiguation** - Resolve or flag ambiguous statements
4. **Decomposition** - Extract atomic, standalone claims
5. **Verification** - Fact-check each claim with confidence scores

**Output Modes:**
- **Inline Warnings**: 🚨 High, ⚠️ Medium, ℹ️ Low confidence flags added to text
- **Metadata**: Full verification details in `mcp_verification` response field
- **No Blocking**: Users always see full response + warnings (inform, don't censor)

**Local Model Support:**
```bash
# Use vLLM, Ollama, or FastAPI locally (no API fees, full privacy)
CLAIM_VERIFICATION_BASE_URL=http://localhost:8000/v1
CLAIM_VERIFICATION_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
CLAIM_VERIFICATION_REQUIRE_AUTH=false  # No authentication needed
```

**Use Cases:**
- ✅ **Technical/Engineering** - Verify calculations, formulas, specifications
- ✅ **Scientific** - Fact-check research claims, data, constants
- ✅ **Financial** - Validate statistics, market data, economic claims
- ✅ **Medical** - Verify dosages, symptoms, treatments (strict mode)

**Performance:**
- Latency: ~500-1000ms per response (cloud) or ~300ms (local)
- Cost: ~$0.0003/response with gpt-4o-mini, $0 with local models
- Caching: ~80% hit rate reduces both latency and cost

**Full Guide:** See `CLAIM_VERIFICATION.md` for complete setup, configuration, and examples.

---

## 🌐 API Endpoints (REST)

**Core MCP Endpoints:**
- `GET /health` → server health check
- `POST /classify` → classify payload sensitivity
- `POST /redact` → sanitize payload, return token_map_handle
- `POST /detokenize` → reinject allowed tokens (trusted clients only)
- `POST /route` → produce an execution plan (internal/external, redaction steps)
- `POST /audit/query` → simple audit search

**Transparent Proxy Endpoints** (when `PROXY_MODE_ENABLED=true`):
- `POST /v1/chat/completions` → OpenAI-compatible proxy
- `POST /v1/messages` → Claude-compatible proxy
- `POST /v1/models/{model}:generateContent` → Gemini-compatible proxy

**Full API documentation:** See `mcp_redaction/models.py` for request/response schemas.

## Policy
Edit `mcp_redaction/sample_policies/default.yaml`. Hot-reload on change is supported (watcher optional).

## Stdio / JSON-RPC (MCP) Adapter
See `mcp_redaction/stdio_adapter.py` for a minimal adapter skeleton you can mount under an agent runtime.

## Testing
```bash
pytest -q
```

## Production Hardening
- Run behind mTLS and identity-aware proxy
- Use Redis (or KV with envelope encryption) for token maps
- Ship audit logs to SIEM (Splunk/ELK); rotate JSONL files
- Add OPA/Gatekeeper check on **detokenize** categories
- Extend detectors (NER, export-control classifier), add OCR for attachments
- Enforce geo-routing and model-allow lists in `policy.yaml`
