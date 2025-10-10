# SIEM Integration Guide

This guide explains how to integrate the MCP Redaction Server with your SIEM (Security Information and Event Management) platform for centralized audit log collection and analysis.

---

## Overview

The MCP server supports real-time audit log shipping to popular SIEM platforms:

- **Splunk** (HTTP Event Collector)
- **Elasticsearch/ELK Stack** (REST API with daily indices)
- **Datadog** (Logs API)
- **Syslog** (RFC 5424 for traditional SIEM systems)

All audit records are **always written to local JSONL files** first (immutable audit trail), then optionally shipped to your SIEM in real-time.

---

## Architecture

```
┌─────────────────────┐
│   MCP Server        │
│   (audit.write())   │
└──────┬──────────────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌─────────────┐      ┌──────────────┐
│ Local JSONL │      │ SIEM Shipper │
│ (immutable) │      │ (buffered)   │
└─────────────┘      └──────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Your SIEM     │
                    │ Platform      │
                    └───────────────┘
```

**Benefits**:
- **Dual-write**: Local file + SIEM (no data loss)
- **Buffered shipping**: Batch mode reduces SIEM API calls
- **Non-blocking**: SIEM failures don't block requests
- **Structured**: JSON format ready for indexing

---

## Quick Start

### 1. Install Dependencies

```bash
pip install httpx  # Already in requirements.txt
```

### 2. Choose Your SIEM

Set the `SIEM_TYPE` environment variable:

```bash
export SIEM_TYPE=splunk        # or elasticsearch, datadog, syslog
```

### 3. Configure SIEM Credentials

See platform-specific sections below for required environment variables.

### 4. Start Server

```bash
uvicorn mcp_redaction.server:app --port 8019
```

Audit logs will now ship to both local JSONL and your SIEM.

---

## Platform-Specific Configuration

### Splunk (HTTP Event Collector)

**Environment Variables**:
```bash
export SIEM_TYPE=splunk
export SPLUNK_HEC_URL="https://splunk.example.com:8088"
export SPLUNK_HEC_TOKEN="your-hec-token-here"

# Optional
export SIEM_BATCH_MODE=true         # Default: true
export SIEM_BATCH_SIZE=100          # Default: 100 records
export SIEM_FLUSH_INTERVAL=5.0      # Default: 5 seconds
```

**Setup Steps**:

1. **Enable HTTP Event Collector** in Splunk:
   - Settings → Data Inputs → HTTP Event Collector
   - Click "New Token"
   - Name: `mcp-redaction`
   - Source type: `_json`
   - Index: `main` (or custom index)
   - Copy the token

2. **Test connection**:
   ```bash
   curl -k https://splunk.example.com:8088/services/collector/event \
     -H "Authorization: Splunk YOUR_TOKEN" \
     -d '{"event": {"test": "message"}}'
   ```

3. **Start MCP server** with Splunk env vars

4. **Query in Splunk**:
   ```spl
   index=main sourcetype=_json source=mcp_redaction
   | table ts action caller categories decision
   | sort -ts
   ```

**Splunk Dashboards**:
```spl
# Secret detection alerts
index=main source=mcp_redaction action=classify 
| search categories{}.type=secret
| stats count by caller, region
| sort -count

# Blocked requests
index=main source=mcp_redaction suggested_action=block
| timechart count by caller

# Detokenization activity
index=main source=mcp_redaction action=detokenize
| stats count by caller, restored_count
```

---

### Elasticsearch/ELK Stack

**Environment Variables**:
```bash
export SIEM_TYPE=elasticsearch      # or 'elk'
export ELASTICSEARCH_URL="https://elasticsearch.example.com:9200"
export ELASTICSEARCH_API_KEY="your-api-key-here"  # Optional, or use basic auth
export ELASTICSEARCH_INDEX="mcp-audit"             # Default: mcp-audit

# Optional
export SIEM_BATCH_MODE=true         # Recommended for performance
export SIEM_BATCH_SIZE=100
export SIEM_FLUSH_INTERVAL=5.0
```

**Setup Steps**:

1. **Create API Key** (recommended):
   ```bash
   curl -X POST "https://elasticsearch.example.com:9200/_security/api_key" \
     -H "Content-Type: application/json" \
     -u elastic:password \
     -d '{
       "name": "mcp-redaction",
       "role_descriptors": {
         "mcp-writer": {
           "cluster": ["monitor"],
           "indices": [
             {
               "names": ["mcp-audit-*"],
               "privileges": ["write", "create_index", "auto_configure"]
             }
           ]
         }
       }
     }'
   ```
   Save the returned API key.

2. **Create Index Template** (optional but recommended):
   ```bash
   curl -X PUT "https://elasticsearch.example.com:9200/_index_template/mcp-audit" \
     -H "Content-Type: application/json" \
     -H "Authorization: ApiKey YOUR_API_KEY" \
     -d '{
       "index_patterns": ["mcp-audit-*"],
       "template": {
         "settings": {
           "number_of_shards": 1,
           "number_of_replicas": 1
         },
         "mappings": {
           "properties": {
             "@timestamp": {"type": "date"},
             "ts": {"type": "keyword"},
             "action": {"type": "keyword"},
             "caller": {"type": "keyword"},
             "region": {"type": "keyword"},
             "env": {"type": "keyword"},
             "categories": {
               "type": "nested",
               "properties": {
                 "type": {"type": "keyword"},
                 "confidence": {"type": "float"}
               }
             },
             "decision": {
               "properties": {
                 "action": {"type": "keyword"},
                 "policy_version": {"type": "integer"}
               }
             }
           }
         }
       }
     }'
   ```

3. **Start MCP server** with Elasticsearch env vars

4. **Query in Kibana**:
   - Navigate to Discover
   - Index pattern: `mcp-audit-*`
   - Filter by `action`, `caller`, `categories.type`

**Kibana Visualizations**:
- **Line chart**: Count of requests over time, split by `action`
- **Pie chart**: Distribution of `categories.type`
- **Data table**: Recent blocks (`decision.action:block`)
- **Metric**: Total secrets detected (`categories.type:secret`)

---

### Datadog Logs

**Environment Variables**:
```bash
export SIEM_TYPE=datadog
export DATADOG_API_KEY="your-datadog-api-key"
export DATADOG_SITE="datadoghq.com"         # or datadoghq.eu, us3.datadoghq.com, etc.
export DATADOG_SERVICE="mcp-redaction"      # Service name in Datadog

# Optional
export SIEM_BATCH_MODE=true
export SIEM_BATCH_SIZE=100
export SIEM_FLUSH_INTERVAL=5.0
```

**Setup Steps**:

1. **Get API Key**:
   - Datadog → Organization Settings → API Keys
   - Create new key: `mcp-redaction`
   - Copy the key

2. **Test connection**:
   ```bash
   curl -X POST "https://http-intake.logs.datadoghq.com/api/v2/logs" \
     -H "DD-API-KEY: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '[{"ddsource":"test","message":"test message"}]'
   ```

3. **Start MCP server** with Datadog env vars

4. **Query in Datadog**:
   - Navigate to Logs
   - Filter: `source:mcp-redaction`
   - Facets: `@action`, `@caller`, `@env`, `@region`

**Datadog Log Pipeline** (recommended):

Create a processing pipeline in Datadog:
1. Logs → Configuration → Pipelines → New Pipeline
2. Filter: `source:mcp-redaction`
3. Add processors:
   - **Grok Parser**: Extract JSON from message field
   - **Date Remapper**: Map `ts` → `@timestamp`
   - **Category Processor**: Tag by `action`, `env`, `caller`

**Datadog Monitors**:
```
# Alert on secret detection
source:mcp-redaction @action:classify @categories.type:secret
threshold: > 10 in 5 minutes

# Alert on blocked requests
source:mcp-redaction @suggested_action:block
threshold: > 50 in 1 hour

# Alert on failed SIEM shipping
source:mcp-redaction "SIEM shipping failed"
threshold: > 5 in 5 minutes
```

---

### Syslog (Traditional SIEM)

**Environment Variables**:
```bash
export SIEM_TYPE=syslog
export SYSLOG_HOST="syslog.example.com"
export SYSLOG_PORT=514                  # Default: 514 (UDP)
export SYSLOG_FACILITY=16               # Default: 16 (local0)

# Buffering not recommended for syslog (UDP)
export SIEM_BATCH_MODE=false
```

**Setup Steps**:

1. **Configure syslog server** to accept UDP on port 514

2. **Test connection**:
   ```bash
   echo "<134>1 $(date -u +"%Y-%m-%dT%H:%M:%SZ") mcp-server mcp-redaction - - - {\"test\":\"message\"}" | nc -u syslog.example.com 514
   ```

3. **Start MCP server** with syslog env vars

4. **Query logs** on your syslog server

**Syslog Format** (RFC 5424):
```
<Priority>Version Timestamp Hostname AppName ProcID MsgID StructuredData Message
<134>1 2025-10-08T22:45:00Z mcp-server mcp-redaction - - - {"ts":"2025-10-08T22:45:00Z","action":"classify",...}
```

**Priority Calculation**:
- Facility: `16` (local0) * 8 = 128
- Severity: `6` (INFO) = 6
- Priority: 128 + 6 = 134

---

## Advanced Configuration

### Buffered Shipping (Recommended for Production)

Buffering reduces SIEM API calls and improves performance:

```bash
export SIEM_BATCH_MODE=true       # Enable batching
export SIEM_BATCH_SIZE=100        # Batch size (records)
export SIEM_FLUSH_INTERVAL=5.0    # Flush interval (seconds)
```

**How it works**:
1. Records accumulate in an in-memory buffer (max 1000)
2. Flush triggers when:
   - Buffer reaches `SIEM_BATCH_SIZE`, OR
   - `SIEM_FLUSH_INTERVAL` seconds elapsed
3. Batch sent via `ship_batch()` method

**Trade-offs**:
- ✅ **Pro**: Fewer API calls, better throughput
- ❌ **Con**: Up to 5-second delay before records appear in SIEM
- ❌ **Con**: Records in buffer lost on server crash (rare)

**Recommendation**: Use buffering for Splunk, Elasticsearch, Datadog. Disable for syslog (UDP).

### Error Handling

SIEM shipping failures are **non-blocking** and **logged**:

```python
# mcp_redaction/audit.py
def write(self, record: Dict[str, Any]):
    # Always write to local file first
    line = json.dumps(record)
    with open(self.path, "a") as f:
        f.write(line + "\n")
    
    # Ship to SIEM (non-blocking)
    if self.siem_shipper:
        try:
            self.siem_shipper.ship(record)
        except Exception as e:
            logger.error(f"SIEM shipping failed: {e}")
            # Request continues normally
```

**Monitoring**:
- Check server logs for "SIEM shipping failed" errors
- Set up alerts on repeated failures
- Audit logs always preserved in local JSONL

### Custom SIEM Integration

Implement the `SIEMShipper` protocol:

```python
from typing import Dict, Any, List

class CustomSIEMShipper:
    """Custom SIEM integration."""
    
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
    
    def ship(self, record: Dict[str, Any]) -> None:
        """Ship single record to custom SIEM."""
        # Your implementation here
        pass
    
    def ship_batch(self, records: List[Dict[str, Any]]) -> None:
        """Ship batch of records to custom SIEM."""
        # Your implementation here
        pass
```

Then in `server.py`:
```python
from .audit import AuditLogger
from my_custom_siem import CustomSIEMShipper

shipper = CustomSIEMShipper(
    endpoint=os.getenv("CUSTOM_SIEM_ENDPOINT"),
    api_key=os.getenv("CUSTOM_SIEM_API_KEY")
)
audit = AuditLogger(settings.audit_path, siem_shipper=shipper)
```

---

## Audit Record Schema

All platforms receive the same JSON structure:

```json
{
  "ts": "2025-10-08T22:45:00Z",
  "action": "classify",
  "caller": "incident-mgr",
  "region": "us",
  "env": "prod",
  "conversation_id": "INC-12345",
  "categories": [
    {"type": "pii", "confidence": 0.85},
    {"type": "ops_sensitive", "confidence": 0.7}
  ],
  "decision": {
    "action": "redact",
    "target": "external:openai:gpt-4",
    "policy_version": 2,
    "requires_redaction": true,
    "allowed_categories": ["pii", "ops_sensitive"]
  },
  "suggested_action": "redact",
  "redaction_count": 3,
  "payload_size_bytes": 2048
}
```

**Key Fields**:
- `ts`: ISO 8601 timestamp (UTC)
- `action`: `classify`, `redact`, `detokenize`, `route`
- `caller`: Identity of request originator
- `region`: Geographic region (for geo-fencing)
- `env`: Environment (prod, dev, staging)
- `categories`: List of detected sensitivity types
- `decision`: Policy engine decision with routing
- `redaction_count`: Number of spans redacted
- `restored_count`: Number of tokens restored (detokenize)

---

## SIEM Queries & Alerts

### Common Queries

**Splunk**:
```spl
# Secret detection rate over time
index=main source=mcp_redaction action=classify categories{}.type=secret
| timechart span=1h count

# Top callers by blocked requests
index=main source=mcp_redaction suggested_action=block
| stats count by caller | sort -count

# Detokenization by category
index=main source=mcp_redaction action=detokenize
| rex field=_raw "\"type\":\"(?<category>[^\"]+)\""
| stats sum(restored_count) by category
```

**Elasticsearch (Kibana Query Language)**:
```
# Secrets detected
action:classify AND categories.type:secret

# Requests from restricted regions
region:(cn OR ru OR ir) AND action:classify

# High-confidence PII
categories.type:pii AND categories.confidence:>=0.9

# Export control content
categories.type:export_control AND decision.action:internal_only
```

**Datadog**:
```
# Secret leakage attempts (should be 0)
source:mcp-redaction @action:detokenize @categories.type:secret

# Failed policy enforcement
source:mcp-redaction @decision.action:block status:error

# Regional routing compliance
source:mcp-redaction @region:eu @decision.target:external:azure_openai_eu:*
```

### Recommended Alerts

1. **Secret Detection Spike**
   - Threshold: >20 secrets detected in 5 minutes
   - Action: Page security team
   - Priority: P1 (critical)

2. **Unauthorized Detokenization Attempts**
   - Threshold: >5 403 Forbidden on `/detokenize` in 1 hour
   - Action: Email security team
   - Priority: P2 (high)

3. **Policy Violations**
   - Threshold: Any `export_control` routed to external model
   - Action: Page compliance team
   - Priority: P1 (critical)

4. **SIEM Shipping Failures**
   - Threshold: >10 "SIEM shipping failed" in 5 minutes
   - Action: Page ops team
   - Priority: P3 (medium)

---

## Performance Impact

### Benchmarks

**Without SIEM** (baseline):
- Classify + Redact: ~40-80ms P95 for 50KB

**With SIEM** (buffered):
- Classify + Redact: ~42-85ms P95 for 50KB
- Overhead: ~2-5ms (<5%)

**With SIEM** (unbuffered):
- Classify + Redact: ~100-200ms P95 for 50KB
- Overhead: ~60-120ms (not recommended for prod)

**Recommendation**: Always use buffered mode (`SIEM_BATCH_MODE=true`) in production.

### Network Requirements

**Bandwidth** (buffered, 1000 req/min):
- Record size: ~500 bytes
- Batch: 100 records = 50 KB
- Flush: every 5 seconds
- Rate: 10 KB/sec = ~80 Kbps

**Outbound connections**:
- Splunk HEC: HTTPS (port 8088)
- Elasticsearch: HTTPS (port 9200)
- Datadog: HTTPS (port 443)
- Syslog: UDP (port 514)

---

## Troubleshooting

### SIEM not receiving logs

1. **Check server logs**:
   ```bash
   tail -f /var/log/mcp-redaction.log | grep "SIEM"
   ```

2. **Verify environment variables**:
   ```bash
   env | grep SIEM
   env | grep SPLUNK
   env | grep ELASTICSEARCH
   env | grep DATADOG
   env | grep SYSLOG
   ```

3. **Test connectivity**:
   ```bash
   # Splunk
   curl -k $SPLUNK_HEC_URL/services/collector/event

   # Elasticsearch
   curl -k $ELASTICSEARCH_URL/_cluster/health

   # Datadog
   curl https://http-intake.logs.$DATADOG_SITE/api/v2/logs

   # Syslog
   nc -vz $SYSLOG_HOST $SYSLOG_PORT
   ```

4. **Check local JSONL** (always works):
   ```bash
   tail -f audit/audit.jsonl
   ```

### High latency

- Enable buffering: `export SIEM_BATCH_MODE=true`
- Increase flush interval: `export SIEM_FLUSH_INTERVAL=10.0`
- Check SIEM endpoint response time
- Consider deploying SIEM collector closer to MCP server

### Records missing in SIEM

- Check buffer overflow (max 1000 records)
- Verify SIEM index/source configuration
- Check SIEM ingestion lag (Elasticsearch can take 30-60s)
- Review local JSONL for ground truth

### Authentication errors

- **Splunk**: Verify HEC token, check firewall
- **Elasticsearch**: Verify API key, check cluster permissions
- **Datadog**: Verify API key, check site (US vs EU)
- **Syslog**: Check firewall, UDP port 514 open

---

## Security Considerations

1. **API Keys**: Store in environment variables, **never** hardcode
2. **TLS/HTTPS**: Always use HTTPS for Splunk, Elasticsearch, Datadog
3. **Network**: SIEM shipping goes over outbound connections only
4. **Credentials**: Rotate API keys quarterly
5. **Audit**: SIEM logs contain sensitive metadata (caller, categories)
   - Do NOT ship payload content (already redacted in local file)
6. **Firewall**: Allow outbound to SIEM endpoints only

---

## Production Checklist

- [ ] SIEM_TYPE configured
- [ ] SIEM credentials in secure env vars
- [ ] Buffered mode enabled (`SIEM_BATCH_MODE=true`)
- [ ] TLS/HTTPS enabled for SIEM endpoint
- [ ] Test connection to SIEM successful
- [ ] SIEM index/source created
- [ ] Alerts configured for secret detection
- [ ] Alerts configured for policy violations
- [ ] Alerts configured for SIEM shipping failures
- [ ] Network firewall rules allow outbound to SIEM
- [ ] Local JSONL backup verified working
- [ ] Log rotation configured for local JSONL
- [ ] SIEM retention policy set (90+ days recommended)

---

## Support

**SIEM Integration Issues**:
1. Check local JSONL logs (always work)
2. Review server logs for "SIEM shipping failed"
3. Test SIEM endpoint connectivity
4. Verify credentials and permissions

**Documentation**:
- `README.md` - Feature overview
- `IMPLEMENTATION.md` - Architecture details
- `QUICKSTART.md` - Setup guide
- `SIEM_INTEGRATION.md` - This guide

---

**Version**: 2.0  
**Last Updated**: 2025-10-08  
**Status**: Production Ready
