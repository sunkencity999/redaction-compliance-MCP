# SIEM Integration - Quick Start

## 5-Minute Setup

### For Splunk

```bash
# 1. Set environment
export SIEM_TYPE=splunk
export SPLUNK_HEC_URL="https://your-splunk:8088"
export SPLUNK_HEC_TOKEN="your-hec-token"

# 2. Start server
uvicorn mcp_redaction.server:app --port 8019

# 3. Verify in Splunk
# Search: index=main source=mcp_redaction
```

### For Elasticsearch

```bash
# 1. Set environment
export SIEM_TYPE=elasticsearch
export ELASTICSEARCH_URL="https://your-elasticsearch:9200"
export ELASTICSEARCH_API_KEY="your-api-key"

# 2. Start server
uvicorn mcp_redaction.server:app --port 8019

# 3. Verify in Kibana
# Index: mcp-audit-YYYY.MM.DD
```

### For Datadog

```bash
# 1. Set environment
export SIEM_TYPE=datadog
export DATADOG_API_KEY="your-api-key"
export DATADOG_SITE="datadoghq.com"

# 2. Start server
uvicorn mcp_redaction.server:app --port 8019

# 3. Verify in Datadog
# Logs → Filter: source:mcp-redaction
```

### For Syslog

```bash
# 1. Set environment
export SIEM_TYPE=syslog
export SYSLOG_HOST="syslog.example.com"
export SYSLOG_PORT=514

# 2. Start server
uvicorn mcp_redaction.server:app --port 8019

# 3. Verify on syslog server
# tail -f /var/log/messages | grep mcp-redaction
```

## Test SIEM Integration

```bash
# Make a test request
curl -X POST http://localhost:8019/classify \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "Email: test@example.com",
    "context": {"caller": "test-user", "region": "us"}
  }'

# Check local logs (always works)
tail -1 audit/audit.jsonl

# Check SIEM platform
# Should see the same record appear within 5 seconds
```

## Troubleshooting

**Logs not appearing in SIEM?**

1. Check server logs:
   ```bash
   # Look for "SIEM shipping failed" errors
   grep "SIEM" logs/server.log
   ```

2. Verify local JSONL (ground truth):
   ```bash
   tail -f audit/audit.jsonl
   ```

3. Test SIEM connectivity:
   ```bash
   # Splunk
   curl -k $SPLUNK_HEC_URL/services/collector/health
   
   # Elasticsearch
   curl -k $ELASTICSEARCH_URL/_cluster/health
   
   # Datadog
   curl https://http-intake.logs.$DATADOG_SITE/api/v2/logs
   ```

## What's Shipped

Every audit record contains:
- Timestamp (UTC)
- Action (classify, redact, detokenize, route)
- Caller identity
- Region & environment
- Categories detected (secret, pii, ops_sensitive, export_control)
- Policy decision (block, redact, internal_only, allow)
- Redaction/restoration counts

**Important**: Actual payload content is **NEVER** shipped to SIEM (privacy/security).

## Next Steps

For complete documentation, see:
- **SIEM_INTEGRATION.md** - Full configuration guide for all platforms
- **config/siem-examples.env** - Copy-paste configuration templates

---

**Setup Time**: <5 minutes  
**Performance Impact**: <5% with buffering enabled  
**Supported Platforms**: Splunk, Elasticsearch, Datadog, Syslog
