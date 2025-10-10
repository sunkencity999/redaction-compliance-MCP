# Redaction & Compliance MCP Server

**Production-Ready Edition** | Version 2.0

This repository contains a **production-grade** implementation of a **Redaction & Compliance Model Context Protocol (MCP)** server.
It provides a **pre-flight / post-flight firewall** for LLM calls with comprehensive detection, classification, policy enforcement,
reversible redaction, selective detokenization, output safety, and immutable audit logging.

## ✨ Features

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

## 📦 Python Client SDK

**Seamless integration with your applications:**

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

## 🌐 API Endpoints (REST)

- `GET /health` → server health check
- `POST /classify` → classify payload sensitivity
- `POST /redact` → sanitize payload, return token_map_handle
- `POST /detokenize` → reinject allowed tokens (trusted clients only)
- `POST /route` → produce an execution plan (internal/external, redaction steps)
- `POST /audit/query` → simple audit search

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
