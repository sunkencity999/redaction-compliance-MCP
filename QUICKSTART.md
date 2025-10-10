# Quick Start Guide

## 1. Installation (2 minutes)

```bash
# Clone and setup
cd /Users/christopher.bradford/redaction-compliance-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Required Configuration

### Set HMAC Salt (REQUIRED)
```bash
export MCP_TOKEN_SALT="$(openssl rand -base64 32)"
# Save this value! You'll need it for every server start
```

### Optional: Enable Redis (Production)
```bash
# Install and start Redis
brew install redis  # macOS
redis-server --daemonize yes

# Configure MCP server
export TOKEN_BACKEND=redis
export REDIS_URL="redis://localhost:6379/0"
export MCP_ENCRYPTION_KEY="$(openssl rand -base64 32)"
```

## 3. Start Server (30 seconds)

```bash
# Development mode
uvicorn mcp_redaction.server:app --reload --port 8019

# Production mode
uvicorn mcp_redaction.server:app --host 0.0.0.0 --port 8019 --workers 4
```

Server will be available at: http://localhost:8019
API Docs: http://localhost:8019/docs

## 4. Run Demo (1 minute)

```bash
# In a new terminal
source .venv/bin/activate
export MCP_TOKEN_SALT="<same-value-as-server>"
python mcp_redaction/demo_client.py
```

Expected output:
- 7 demo scenarios showcasing all features
- Multi-credential detection (AWS, Azure, GCP)
- PII validation (Luhn, SSN)
- Export control classification
- Internal domain detection
- Full workflow (classify → route → redact → detokenize)
- Region-based routing
- Audit query

## 5. Run Tests (2 minutes)

```bash
# Make test script executable
chmod +x run_tests.sh

# Run full test suite
./run_tests.sh

# Or run specific test modules
source .venv/bin/activate
export MCP_TOKEN_SALT="test-salt"

python -m pytest tests/test_detectors.py -v
python -m pytest tests/test_classifier.py -v
python -m pytest tests/test_policy.py -v
python -m pytest tests/test_token_store.py -v
python -m pytest tests/test_safety.py -v
python -m pytest tests/test_integration.py -v
```

## 6. Test API Endpoints

### Classify
```bash
curl -X POST http://localhost:8019/classify \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "Email: test@joby.aero, AWS: AKIAIOSFODNN7EXAMPLE",
    "context": {"caller": "user", "region": "us", "conversation_id": "test"}
  }'
```

### Redact
```bash
curl -X POST http://localhost:8019/redact \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "Contact: alice@example.com, Server: 192.168.1.1",
    "context": {"caller": "incident-mgr", "region": "us", "conversation_id": "test"}
  }'
```

### Route
```bash
curl -X POST http://localhost:8019/route \
  -H "Content-Type: application/json" \
  -d '{
    "model_request": {"text": "eVTOL aircraft with FAA certification"},
    "context": {"caller": "engineer", "region": "us"}
  }'
```

## 7. Key Features to Test

### ✅ Zero Secret Exfiltration
- Send payload with AWS keys → should be BLOCKED
- Verify secrets never detokenized

### ✅ PII Validation
- Valid credit card (4532015112830366) → detected
- Invalid credit card (4532015112830367) → NOT detected
- Valid SSN (123-45-6789) → detected
- Invalid SSN (666-45-6789) → NOT detected

### ✅ Export Control
- Text with "eVTOL aircraft FAA ITAR" → classified as export_control
- Routes to internal-only models

### ✅ Region-Based Routing
- US region → external models allowed
- CN/RU regions → internal-only enforced

### ✅ Selective Detokenization
- Trusted caller + allowed categories → restored
- Untrusted caller → 403 Forbidden
- Secrets category → never restored

## 8. Configuration Files

### Policy Configuration
Edit `mcp_redaction/sample_policies/default.yaml` to customize:
- Geo/region constraints
- Caller-based routing rules
- Category actions (block/redact/internal_only)
- Model preferences per region

### Safety Patterns
Create custom safety config (optional):
```json
{
  "dangerous_patterns": [
    {
      "pattern": "custom-dangerous-cmd",
      "description": "Your custom dangerous pattern"
    }
  ]
}
```

Then set: `export SAFETY_CONFIG_PATH=/path/to/config.json`

## 9. Environment Variables Reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MCP_TOKEN_SALT` | **YES** | - | HMAC salt for tokens |
| `TOKEN_BACKEND` | No | `memory` | `memory` or `redis` |
| `REDIS_URL` | If Redis | - | Redis connection |
| `MCP_ENCRYPTION_KEY` | If Redis | - | AES encryption key |
| `MAX_PAYLOAD_KB` | No | `256` | Max payload size |
| `DETOK_TRUSTED` | No | `incident-mgr,runbook-executor` | Trusted callers |
| `POLICY_PATH` | No | `sample_policies/default.yaml` | Policy file |
| `AUDIT_PATH` | No | `./audit/audit.jsonl` | Audit log path |
| `SAFETY_CONFIG_PATH` | No | - | Custom safety config |

## 10. Troubleshooting

### "Missing HMAC salt in env var MCP_TOKEN_SALT"
```bash
export MCP_TOKEN_SALT="your-secret-salt-here"
```

### "redis package required for RedisTokenStore"
```bash
pip install redis hiredis
```

### "MCP_ENCRYPTION_KEY environment variable required"
```bash
export MCP_ENCRYPTION_KEY="$(openssl rand -base64 32)"
```

### Tests fail with "Cannot connect to server"
Make sure server is running:
```bash
uvicorn mcp_redaction.server:app --port 8019
```

### "403 Forbidden" on detokenize
Check caller is in trusted list:
```bash
export DETOK_TRUSTED="incident-mgr,runbook-executor,your-caller"
```

## 11. Next Steps

1. **Review Policy**: Customize `sample_policies/default.yaml` for your needs
2. **Add Custom Detectors**: Extend patterns in `mcp_redaction/detectors.py`
3. **Configure Safety**: Add organization-specific dangerous patterns
4. **Deploy**: Set up mTLS, identity-aware proxy, SIEM integration
5. **Monitor**: Add Prometheus metrics, alerting on block/redact rates

## 12. Production Checklist

- [ ] Set strong `MCP_TOKEN_SALT` (32+ random bytes)
- [ ] Enable Redis backend with `MCP_ENCRYPTION_KEY`
- [ ] Configure mTLS for API endpoints
- [ ] Set up identity-aware proxy for caller verification
- [ ] Ship audit logs to SIEM (implement `audit.ship()`)
- [ ] Add Prometheus metrics
- [ ] Configure log rotation for audit.jsonl
- [ ] Set up monitoring/alerting
- [ ] Document incident response procedures
- [ ] Schedule policy reviews

---

**Time to Production**: ~10 minutes for basic setup, 1-2 hours for full hardening

**Support**: See `IMPLEMENTATION.md` for architecture details and `README.md` for features
