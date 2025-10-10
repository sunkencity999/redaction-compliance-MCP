# Policy Configuration Guide

This guide explains how to configure the `sample_policies/default.yaml` file to customize the MCP server's behavior.

---

## Policy Structure

```yaml
version: 2  # Policy version for tracking

geo_constraints:      # Geographic/regional controls
caller_rules:         # Caller-based permissions
routes:               # Category-based routing rules
```

---

## 1. Geo Constraints

### Restricted Regions

Define regions subject to export control or compliance restrictions:

```yaml
geo_constraints:
  restricted_regions:
    - cn  # China
    - ru  # Russia
    - ir  # Iran
    - kp  # North Korea
    - sy  # Syria
```

Requests from these regions automatically route to internal-only models.

### Region Routing

Configure preferred models and settings per region:

```yaml
geo_constraints:
  region_routing:
    us:  # United States
      allow_external: true
      preferred_models:
        - "external:azure_openai:gpt-4o-mini"
        - "external:openai:gpt-4o-mini"
      internal_fallback:
        - "internal:llama3-70b"
    
    eu:  # European Union (GDPR)
      allow_external: true
      data_residency: eu  # Flag for compliance
      preferred_models:
        - "external:azure_openai_eu:gpt-4o-mini"
      internal_fallback:
        - "internal:llama3-70b-eu"
    
    apac:  # Asia-Pacific
      allow_external: true
      preferred_models:
        - "external:azure_openai_apac:gpt-4o-mini"
      internal_fallback:
        - "internal:llama3-70b"
    
    restricted:  # For restricted_regions
      allow_external: false
      preferred_models:
        - "internal:llama3-70b"
```

**Fields**:
- `allow_external`: Whether external models are permitted
- `preferred_models`: Priority-ordered list of models
- `internal_fallback`: Internal models if external unavailable
- `data_residency`: Compliance flag (e.g., `eu`, `us`)

---

## 2. Caller Rules

### Trusted Callers

Define callers allowed to detokenize:

```yaml
caller_rules:
  trusted_callers:
    - incident-mgr
    - runbook-executor
    - ops-dashboard
    - security-audit
```

**Note**: Callers not in this list get 403 Forbidden on `/detokenize`.

### Caller-Specific Routing

Configure per-caller permissions:

```yaml
caller_rules:
  caller_routing:
    incident-mgr:
      allow_categories: ["pii", "ops_sensitive"]  # Can detokenize these
      max_detokenize: true
    
    runbook-executor:
      allow_categories: ["ops_sensitive"]  # Only ops_sensitive
      max_detokenize: true
    
    external-analyst:
      allow_categories: []  # Cannot detokenize anything
      max_detokenize: false
      force_redact: true  # Always redact, even if not sensitive
```

**Fields**:
- `allow_categories`: Categories this caller can detokenize
- `max_detokenize`: Whether caller has full detokenize permissions
- `force_redact`: Force redaction for all requests from this caller

---

## 3. Routes

Routes are evaluated **in order**. First matching route wins.

### Route Structure

```yaml
routes:
  - name: route_name
    match:
      category: secret  # Category to match
    action: block  # Action: block|redact|internal_only|allow
    applies_to:
      regions: ["*"]  # Which regions this route applies to
      callers: ["*"]  # Which callers this route applies to
    allow_models: ["model-id"]  # Target models
    allow_categories: ["pii"]  # Categories allowed for detokenize
    redact:  # Redaction configuration
      strategy: token
      allow_detokenize: true
```

### Actions

**block**: Stop request completely
```yaml
- name: secrets_block
  match: {category: secret}
  action: block
  applies_to: {regions: ["*"], callers: ["*"]}
```

**internal_only**: Route to internal models only
```yaml
- name: export_control_internal
  match: {category: export_control}
  action: internal_only
  allow_models: ["internal:llama3-70b"]
  applies_to: {regions: ["*"], callers: ["*"]}
```

**redact**: Redact sensitive data before sending
```yaml
- name: pii_to_external_us
  match: {category: pii}
  action: redact
  redact:
    strategy: token
    scope: {persist: conversation}
    allow_detokenize: true
  allow_models: ["external:openai:gpt-4o-mini"]
  allow_categories: ["pii", "ops_sensitive"]
  applies_to:
    regions: ["us", "apac"]
    callers: ["*"]
```

**allow**: No restrictions
```yaml
- name: default_allow
  match: {category: null}  # null matches non-sensitive
  action: allow
  allow_models: ["external:openai:gpt-4o-mini"]
  applies_to: {regions: ["*"], callers: ["*"]}
```

---

## 4. Complete Example

### Use Case: Healthcare Company

```yaml
version: 2

geo_constraints:
  restricted_regions: [cn, ru, ir]
  
  region_routing:
    us:
      allow_external: true
      preferred_models: ["external:azure_openai:gpt-4"]
    
    eu:
      allow_external: true
      data_residency: eu
      preferred_models: ["external:azure_openai_eu:gpt-4"]

caller_rules:
  trusted_callers:
    - doctor-assistant
    - billing-system
    - admin-portal
  
  caller_routing:
    doctor-assistant:
      allow_categories: ["pii"]  # Can see patient names
      max_detokenize: true
    
    billing-system:
      allow_categories: ["pii"]
      max_detokenize: true
    
    external-researcher:
      allow_categories: []  # Cannot see any PII
      force_redact: true

routes:
  # PHI/Medical records - internal only
  - name: phi_internal
    match: {category: phi}
    action: internal_only
    allow_models: ["internal:healthcare-llm"]
    applies_to: {regions: ["*"], callers: ["*"]}
  
  # PII - redact for external, allow detokenize by doctors
  - name: pii_redact
    match: {category: pii}
    action: redact
    redact: {allow_detokenize: true}
    allow_models: ["external:azure_openai:gpt-4"]
    allow_categories: ["pii"]
    applies_to:
      regions: ["us", "eu"]
      callers: ["*"]
  
  # Billing info - strict redaction
  - name: financial_redact
    match: {category: financial}
    action: redact
    redact: {allow_detokenize: false}
    allow_models: ["internal:billing-processor"]
    applies_to: {regions: ["*"], callers: ["*"]}
```

---

## 5. Best Practices

### Security

1. **Always block secrets**: Never route credentials externally
```yaml
- name: secrets_block
  match: {category: secret}
  action: block
```

2. **Limit detokenization**: Only trusted callers, specific categories
```yaml
caller_rules:
  trusted_callers: [incident-mgr]  # Minimal list
  caller_routing:
    incident-mgr:
      allow_categories: [ops_sensitive]  # Not PII or secrets
```

3. **Geo-fence sensitive data**: Internal-only for restricted regions
```yaml
geo_constraints:
  restricted_regions: [cn, ru, ir, kp, sy]
```

### Performance

1. **Order routes by frequency**: Most common matches first
```yaml
routes:
  - name: secrets_block  # Fast fail
  - name: common_pii     # High volume
  - name: rare_category  # Low volume
```

2. **Use wildcards carefully**: `["*"]` matches everything
```yaml
applies_to:
  regions: ["*"]  # All regions
  callers: ["*"]  # All callers
```

### Compliance

1. **Document policy versions**: Increment on changes
```yaml
version: 3  # Updated 2025-10-04: Added GDPR rules
```

2. **Set data residency flags**: For audit trail
```yaml
eu:
  data_residency: eu  # Logged in audit records
```

3. **Enforce internal-only for export control**:
```yaml
- name: itar_internal
  match: {category: export_control}
  action: internal_only
```

---

## 6. Testing Your Policy

### Test Different Scenarios

```bash
# Test US region, trusted caller
curl -X POST http://localhost:8019/route \
  -H "Content-Type: application/json" \
  -d '{
    "model_request": {"text": "Email: test@example.com"},
    "context": {"caller": "incident-mgr", "region": "us"}
  }'

# Test restricted region
curl -X POST http://localhost:8019/route \
  -H "Content-Type: application/json" \
  -d '{
    "model_request": {"text": "Email: test@example.com"},
    "context": {"caller": "user", "region": "cn"}
  }'

# Test untrusted caller
curl -X POST http://localhost:8019/route \
  -H "Content-Type: application/json" \
  -d '{
    "model_request": {"text": "Email: test@example.com"},
    "context": {"caller": "external-analyst", "region": "us"}
  }'
```

### Verify Expected Behavior

1. **Secrets always blocked**: Check `action: block`
2. **Region routing works**: Verify `target` model matches region
3. **Caller constraints applied**: Check `allowed_categories` intersection
4. **Policy version tracked**: Verify `policy_version` in response

---

## 7. Reloading Policy

Policy changes require server restart:

```bash
# Edit policy
vim mcp_redaction/sample_policies/default.yaml

# Restart server
# Kill existing server (Ctrl+C)
uvicorn mcp_redaction.server:app --reload --port 8019
```

**Hot reload** (future enhancement):
```python
# In server.py (not implemented yet)
@app.post("/admin/reload-policy")
def reload_policy():
    policy.reload()
    return {"ok": True, "version": policy.doc.get("version")}
```

---

## 8. Validation

### Common Errors

**Invalid YAML syntax**:
```
yaml.scanner.ScannerError: while scanning...
```
Fix: Check indentation, quotes, brackets

**Missing required fields**:
```
KeyError: 'routes'
```
Fix: Ensure all required sections present

**Invalid region code**:
```
# Policy still loads, but won't match
applies_to:
  regions: ["USA"]  # Should be "us"
```

### Validation Script

```python
import yaml

with open("mcp_redaction/sample_policies/default.yaml") as f:
    policy = yaml.safe_load(f)

# Check required sections
assert "version" in policy
assert "routes" in policy
assert len(policy["routes"]) > 0

# Check route structure
for route in policy["routes"]:
    assert "name" in route
    assert "match" in route
    assert "action" in route
    assert route["action"] in ["block", "redact", "internal_only", "allow"]

print(f"✓ Policy valid: {len(policy['routes'])} routes")
```

---

## 9. Advanced Patterns

### Multi-Region Fallback

```yaml
us:
  preferred_models:
    - "external:azure_openai_us:gpt-4o"
    - "external:openai:gpt-4o"
    - "external:anthropic:claude-3"
  internal_fallback:
    - "internal:llama3-70b"
    - "internal:mistral-7b"
```

### Time-Based Routing (Future)

```yaml
# Not yet implemented
caller_routing:
  on_call_engineer:
    allow_categories: ["pii", "ops_sensitive"]
    schedule:
      weekdays: "09:00-17:00"
      weekends: "none"
```

### Cost-Based Routing (Future)

```yaml
# Not yet implemented
us:
  preferred_models:
    - model: "external:openai:gpt-4o"
      max_cost_per_request: 0.05
    - model: "external:openai:gpt-3.5"
      max_cost_per_request: 0.01
```

---

## 10. Troubleshooting

### "Policy file not found"
```bash
export POLICY_PATH=/absolute/path/to/policy.yaml
```

### Routes not matching
- Check route order (first match wins)
- Verify `applies_to` filters
- Test with wildcard: `regions: ["*"]`

### Detokenize always forbidden
- Check caller in `trusted_callers` list
- Verify `allow_categories` includes the category
- Check caller has `max_detokenize: true`

### Wrong model selected
- Check region routing configuration
- Verify `preferred_models` for region
- Ensure route has `allow_models` set

---

For more details, see:
- `README.md`: Feature overview
- `IMPLEMENTATION.md`: Architecture details
- `QUICKSTART.md`: Setup guide
