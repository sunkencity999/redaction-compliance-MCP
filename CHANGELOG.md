# Changelog

All notable changes to the Redaction & Compliance MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-10

### Added - Production-Ready Release

#### Detection & Classification
- **20+ credential detectors**: AWS (AKID, secrets), Azure (Storage Keys, SAS, Connection Strings), GCP (API keys, OAuth)
- **OAuth & Bearer tokens**: JWT detection, OAuth access tokens
- **Crypto keys**: PEM (RSA, DSA, EC), PKCS#12, Kubernetes config/tokens
- **PII validation**: Credit cards with Luhn checksum, SSN format validation (rejects invalid area codes)
- **Internal infrastructure**: Joby Aviation domains (`*.na.joby.aero`, `*.az.joby.aero`), IP addresses, hostnames
- **Export control classifier**: 30+ aviation keywords (eVTOL, ITAR, FAA, flight control, propulsion)

#### Policy Engine
- **Geo/region constraints**: US, EU, APAC, restricted regions (CN, RU, IR, KP, SY)
- **Caller-based routing**: Trusted caller lists, per-caller detokenization permissions
- **Data residency**: EU GDPR compliance flags, region-specific model routing
- **Policy version tracking**: Version embedded in all decisions
- **4 action types**: `block`, `redact`, `internal_only`, `allow`

#### Token Storage
- **Redis with AES-256-GCM encryption**: Production-grade token storage
- **PBKDF2 key derivation**: 100k iterations, SHA-256
- **Automatic TTL management**: Redis-native expiration
- **Deterministic placeholders**: `«token:TYPE:HASH4»` stable within conversation scope
- **In-memory fallback**: For development/testing

#### Output Safety
- **50+ dangerous command patterns**: Across 10 categories
  - Filesystem destruction (rm -rf, mkfs, dd)
  - System control (shutdown, reboot, init)
  - Kubernetes (kubectl delete --all, drain)
  - Docker (system prune, container deletion)
  - Databases (DROP, TRUNCATE, DELETE)
  - Cloud infrastructure (AWS, Azure, GCP resource deletion)
  - Network/firewall (iptables, ufw)
  - Permissions (chmod 777, userdel)
  - Services (systemctl stop, service disable)
  - Resource exhaustion (fork bombs)
- **External config support**: JSON-based custom pattern loading
- **3 operating modes**: warning, block, silent

#### SIEM Integration
- **Splunk**: HTTP Event Collector integration
- **Elasticsearch/ELK**: REST API with daily indices, bulk API support
- **Datadog**: Logs API integration with tagging
- **Syslog**: RFC 5424 for traditional SIEM systems
- **Buffered shipping**: Batch mode with <5% performance overhead
- **Non-blocking**: SIEM failures don't block requests
- **Dual-write**: Local JSONL always preserved

#### Testing & Quality
- **186+ test cases** across 6 test modules
- **~88% code coverage** (exceeds 85% target)
- Integration tests with E2E workflows
- Performance benchmarks (<100ms P95 for 50KB payloads)
- Authorization and security verification tests

#### Documentation
- **README.md**: Feature overview and quick start
- **IMPLEMENTATION.md**: Complete architecture guide (850+ lines)
- **QUICKSTART.md**: 10-minute setup guide
- **POLICY_GUIDE.md**: Policy configuration reference
- **SIEM_INTEGRATION.md**: Complete SIEM setup for all platforms
- **SIEM_QUICKSTART.md**: 5-minute SIEM integration
- **ACCEPTANCE_VERIFICATION.md**: Requirements verification
- **PROJECT_COMPLETE.md**: Executive summary
- Inline docstrings for all public functions

#### Security
- Zero secret exfiltration guarantee (secrets never detokenized)
- Deterministic placeholders per conversation
- Selective detokenization with caller authorization
- Immutable audit trail (append-only JSONL)
- AES-256-GCM encryption for Redis storage
- HMAC-SHA256 for token placeholders

#### Performance
- <100ms P95 latency for 50KB payloads (target: <60ms)
- Compiled regex patterns for efficiency
- O(1) token store lookups
- First-match policy routing with early exit
- Buffered SIEM shipping for minimal overhead

### Changed
- Updated policy YAML to version 2 with full geo/region and caller constraints
- Enhanced demo client with 7 showcase scenarios

### Fixed
- Credit card detection now validates Luhn checksum (prevents false positives)
- SSN detection rejects invalid area codes (000, 666, 900-999)
- Overlap resolution in span detection (prioritizes secrets > PII > ops_sensitive)

### Security
- No known vulnerabilities
- All dependencies up to date (as of 2025-10-10)
- Secrets never logged or shipped to SIEM

---

## [1.0.0] - Initial Scaffold

### Added
- Basic FastAPI server with REST endpoints
- Simple credential detection (AWS keys, basic patterns)
- In-memory token store
- Policy engine skeleton
- Basic audit logging to JSONL
- Test suite foundation

---

## Upgrade Guide

### From 1.0 to 2.0

**Breaking Changes**: None (API contracts maintained)

**New Environment Variables**:
```bash
# Token storage (optional)
export TOKEN_BACKEND=redis
export REDIS_URL="redis://localhost:6379/0"
export MCP_ENCRYPTION_KEY="your-encryption-key"

# SIEM integration (optional)
export SIEM_TYPE=splunk  # or elasticsearch, datadog, syslog
export SPLUNK_HEC_URL="https://splunk:8088"
export SPLUNK_HEC_TOKEN="your-token"

# Safety filter (optional)
export SAFETY_CONFIG_PATH="/path/to/custom-patterns.json"
```

**Migration Steps**:
1. Update `requirements.txt`: `pip install -r requirements.txt`
2. Review and update `sample_policies/default.yaml` (now version 2)
3. Configure SIEM integration if desired (optional)
4. Run tests: `./run_tests.sh`
5. Deploy with new environment variables

**New Features Available**:
- Export control classification (aviation/ITAR keywords)
- Geo-fencing with region-based routing
- Redis token storage with encryption
- SIEM real-time log shipping
- Enhanced safety filter with 50+ patterns

---

## Roadmap

### v2.1.0 (Planned)
- [ ] Hot-reload policy without server restart
- [ ] Prometheus metrics endpoint
- [ ] Rate limiting per caller
- [ ] Batch processing API

### v2.2.0 (Planned)
- [ ] OCR for image attachments
- [ ] NER-based entity detection
- [ ] Cost tracking per request
- [ ] Multi-tenancy support

### v3.0.0 (Future)
- [ ] ML-based sensitive content classification
- [ ] Real-time SIEM integration improvements
- [ ] Horizontal auto-scaling
- [ ] GraphQL API

---

**Repository**: https://github.com/sunkencity999/redaction-compliance-MCP  
**License**: MIT  
**Maintainer**: Joby Aviation
