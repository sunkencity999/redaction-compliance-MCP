from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Any, Dict, List, Tuple
from .models import *
from .config import settings
from .detectors import find_spans
from .token_store import create_token_store, token_placeholder
from .policy import PolicyEngine
from .safety import output_safety
from .audit import (
    AuditLogger,
    SplunkHECShipper,
    ElasticsearchShipper,
    DatadogShipper,
    SyslogShipper,
    BufferedSIEMShipper,
)
from .classifier import classify_export_control, should_enforce_internal_only
import os, json, hmac, hashlib, time

def create_siem_shipper():
    """Create SIEM shipper based on environment configuration."""
    siem_type = os.getenv("SIEM_TYPE", "").lower()
    
    if siem_type == "splunk":
        hec_url = os.getenv("SPLUNK_HEC_URL")
        hec_token = os.getenv("SPLUNK_HEC_TOKEN")
        if not hec_url or not hec_token:
            raise ValueError("SPLUNK_HEC_URL and SPLUNK_HEC_TOKEN required for Splunk")
        shipper = SplunkHECShipper(hec_url, hec_token)
    
    elif siem_type == "elasticsearch" or siem_type == "elk":
        es_url = os.getenv("ELASTICSEARCH_URL")
        if not es_url:
            raise ValueError("ELASTICSEARCH_URL required for Elasticsearch")
        api_key = os.getenv("ELASTICSEARCH_API_KEY")
        index = os.getenv("ELASTICSEARCH_INDEX", "mcp-audit")
        shipper = ElasticsearchShipper(es_url, index, api_key)
    
    elif siem_type == "datadog":
        api_key = os.getenv("DATADOG_API_KEY")
        if not api_key:
            raise ValueError("DATADOG_API_KEY required for Datadog")
        site = os.getenv("DATADOG_SITE", "datadoghq.com")
        service = os.getenv("DATADOG_SERVICE", "mcp-redaction")
        shipper = DatadogShipper(api_key, site, service)
    
    elif siem_type == "syslog":
        host = os.getenv("SYSLOG_HOST")
        if not host:
            raise ValueError("SYSLOG_HOST required for Syslog")
        port = int(os.getenv("SYSLOG_PORT", "514"))
        facility = int(os.getenv("SYSLOG_FACILITY", "16"))
        shipper = SyslogShipper(host, port, facility)
    
    elif siem_type:
        raise ValueError(f"Unknown SIEM_TYPE: {siem_type}")
    
    else:
        return None  # No SIEM configured
    
    # Wrap in buffered shipper if batch mode enabled
    if os.getenv("SIEM_BATCH_MODE", "true").lower() == "true":
        batch_size = int(os.getenv("SIEM_BATCH_SIZE", "100"))
        flush_interval = float(os.getenv("SIEM_FLUSH_INTERVAL", "5.0"))
        shipper = BufferedSIEMShipper(shipper, batch_size, flush_interval)
    
    return shipper

app = FastAPI(title=settings.app_name)

# Configure CORS for browser-based applications
# Customize allowed_origins in production to restrict to your domains
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # In production: ["https://yourapp.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
    max_age=3600,
)

audit = AuditLogger(settings.audit_path, siem_shipper=create_siem_shipper())
tokens = create_token_store(backend=settings.token_backend, redis_url=settings.redis_url)
policy = PolicyEngine(settings.policy_path)

def get_salt(context: Context) -> bytes:
    env_name = settings.token_salt_env
    raw = os.getenv(env_name)
    if not raw:
        raise RuntimeError(f"Missing HMAC salt in env var {env_name}")
    scope = (context.conversation_id or "default").encode("utf-8")
    return hmac.new(raw.encode("utf-8"), scope, hashlib.sha256).digest()

def classify_text(text: str) -> List[Category]:
    spans = find_spans(text)
    cats = []
    seen = set()
    for cat, _ in spans:
        if cat not in seen:
            seen.add(cat)
            conf = 0.95 if cat == "secret" else 0.85 if cat == "pii" else 0.7
            cats.append(Category(type=cat, confidence=conf))
    
    # Check for export control content
    ec_result = classify_export_control(text)
    if ec_result["is_export_controlled"] and "export_control" not in seen:
        cats.append(Category(type="export_control", confidence=ec_result["confidence"]))
    
    return cats

@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    text = req.payload if isinstance(req.payload, str) else json.dumps(req.payload, ensure_ascii=False)
    cats = classify_text(text)
    decision = policy.decide([c.dict() for c in cats], (req.context or Context()).dict())
    audit.write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "caller": (req.context.caller if req.context else None),
        "context": (req.context.dict() if req.context else None),
        "action": "classify",
        "categories": [c.dict() for c in cats],
        "decision": decision,
        "policy_version": decision.get("policy_version")
    })
    return ClassifyResponse(ok=True, categories=cats, suggested_action=decision.get("action"))

@app.post("/redact", response_model=RedactResponse)
def redact(req: RedactRequest):
    text = req.payload if isinstance(req.payload, str) else json.dumps(req.payload, ensure_ascii=False)
    if len(text.encode("utf-8")) > settings.max_payload_kb * 1024:
        raise HTTPException(413, "Payload too large")
    ctx = req.context or Context()
    salt = get_salt(ctx)
    spans = find_spans(text)
    redactions: List[RedactionEvent] = []
    # create token map
    handle = tokens.create()
    out = []
    last = 0
    for cat,(s,e) in spans:
        out.append(text[last:s])
        ph = token_placeholder(cat.upper(), text[s:e], salt)
        out.append(ph)
        redactions.append(RedactionEvent(type=cat, placeholder=ph, range=[s,e]))
        tokens.put(handle, ph, text[s:e], meta=cat)
        last = e
    out.append(text[last:])
    sanitized = "".join(out)
    audit.write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "caller": (ctx.caller if ctx else None),
        "context": (ctx.dict() if ctx else None),
        "action": "redact",
        "categories": [{"type":r.type,"confidence":1.0} for r in redactions],
        "decision": {"action":"redact"},
        "redaction_counts": {r.type: sum(1 for x in redactions if x.type==r.type) for r in redactions}
    })
    return RedactResponse(ok=True, sanitized_payload=sanitized, token_map_handle=handle, redactions=redactions)

@app.post("/detokenize", response_model=DetokenizeResponse)
def detokenize(req: DetokenizeRequest):
    ctx = req.context or Context()
    trusted = [x.strip() for x in settings.detokenize_trusted_callers.split(",") if x.strip()]
    if ctx.caller not in trusted:
        raise HTTPException(403, "Caller not trusted to detokenize")
    text = req.payload if isinstance(req.payload, str) else json.dumps(req.payload, ensure_ascii=False)
    kv, meta = tokens.all(req.token_map_handle)
    def replace(match):
        ph = match.group(0)
        cat = meta.get(ph, "unknown")
        if cat not in req.allow_categories:
            return ph
        return kv.get(ph, ph)
    import re
    restored = re.sub(r"«token:[A-Z_]+:[0-9a-f]{4}»", replace, text)
    audit.write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "caller": (ctx.caller if ctx else None),
        "context": (ctx.dict() if ctx else None),
        "action": "detokenize",
        "categories": [{"type":c,"confidence":1.0} for c in set(meta.values())],
        "decision": {"allow_categories": req.allow_categories}
    })
    return DetokenizeResponse(ok=True, restored_payload=restored)

@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest):
    text = req.model_request.get("text","")
    cats = classify_text(text)
    decision = policy.decide([c.dict() for c in cats], (req.context or Context()).dict())
    if decision.get("action") == "block":
        return RouteResponse(ok=False, errors=["Blocked by policy"], decision=decision)
    pre = []
    post = []
    if decision.get("requires_redaction"):
        pre.append(ExecutionStep(tool="redact", args={"policy": req.policy}))
        if decision.get("allow_detokenize"):
            post.append(ExecutionStep(tool="detokenize", args={"allow_categories": decision.get("allowed_categories",[])}))
    post.append(ExecutionStep(tool="output_safety", args={}))
    plan = ExecutionPlan(target=decision.get("target","internal:default"), pre=pre, post=post)
    audit.write({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "caller": (req.context.caller if req.context else None),
        "context": (req.context.dict() if req.context else None),
        "action": "route",
        "categories": [c.dict() for c in cats],
        "decision": decision,
        "target": plan.target
    })
    return RouteResponse(ok=True, plan=plan, decision=decision)

@app.post("/audit/query")
def audit_query(req: AuditQueryRequest):
    return JSONResponse(content={"records": audit.query(req.q, req.limit)})

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring and installation verification."""
    try:
        # Check Redis connection if using Redis backend
        if settings.token_backend == "redis":
            tokens.redis.ping()
        
        return JSONResponse(content={
            "status": "healthy",
            "version": "2.0.0",
            "token_backend": settings.token_backend,
            "policy_version": policy.policy.get("version", 1),
            "siem_enabled": bool(audit.siem_shipper)
        })
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )
