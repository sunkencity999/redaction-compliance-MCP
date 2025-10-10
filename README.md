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

## Quickstart
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn mcp_redaction.server:app --reload --port 8019
# In another shell:
python mcp_redaction/demo_client.py
```

## Endpoints (REST)
- `POST /classify` → classify payload sensitivity
- `POST /redact` → sanitize payload, return token_map_handle
- `POST /detokenize` → reinject allowed tokens (trusted clients only)
- `POST /route` → produce an execution plan (internal/external, redaction steps)
- `POST /audit/query` → simple audit search

See `mcp_redaction/models.py` for request/response schemas.

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
