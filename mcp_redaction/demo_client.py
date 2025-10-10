#!/usr/bin/env python3
"""
Demo client for Redaction & Compliance MCP Server.
Showcases all key features: detection, classification, redaction, and detokenization.
"""

import os, requests, json, sys

BASE = os.environ.get("MCP_REDACTION_BASE", "http://127.0.0.1:8019")
os.environ.setdefault("MCP_TOKEN_SALT", "change-me-please-in-prod")

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def demo_multi_credential():
    """Demonstrate detection of various credential types."""
    print_section("1. Multi-Credential Detection (AWS, Azure, GCP)")
    
    payload = """
    Production credentials:
    - AWS: AKIAIOSFODNN7EXAMPLE
    - Azure Storage: AccountKey=abc123xyz789ABC123XYZ789abc123xyz789ABC123XYZ789abc123xyz789abcd==
    - GCP API: AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe
    - Bearer Token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature
    """
    
    ctx = {"purpose": "security-audit", "env": "prod", "conversation_id": "DEMO-001", 
           "caller": "incident-mgr", "region": "us"}
    
    r = requests.post(f"{BASE}/classify", json={"payload": payload, "context": ctx})
    result = r.json()
    
    print(f"Categories detected: {[c['type'] for c in result.get('categories', [])]}")
    print(f"Suggested action: {result.get('suggested_action')}")
    print(f"Policy version: {result.get('decision', {}).get('policy_version')}")


def demo_pii_validation():
    """Demonstrate PII detection with validation (Luhn for cards, SSN format)."""
    print_section("2. PII Detection with Validation")
    
    payload = """
    Customer info:
    - Email: john.doe@joby.aero
    - Phone: +1-650-555-1234
    - Credit Card: 4532015112830366 (valid Luhn)
    - Invalid Card: 4532015112830367 (invalid Luhn - should NOT detect)
    - SSN: 123-45-6789 (valid)
    - Invalid SSN: 666-45-6789 (invalid - should NOT detect)
    """
    
    ctx = {"purpose": "data-review", "env": "dev", "conversation_id": "DEMO-002",
           "caller": "incident-mgr", "region": "us"}
    
    r = requests.post(f"{BASE}/classify", json={"payload": payload, "context": ctx})
    result = r.json()
    
    print(f"Categories: {[c['type'] for c in result.get('categories', [])]}")
    
    # Redact
    r = requests.post(f"{BASE}/redact", json={"payload": payload, "context": ctx})
    red = r.json()
    print(f"\nRedactions count: {len(red['redactions'])}")
    print(f"Sanitized preview: {red['sanitized_payload'][:200]}...")


def demo_export_control():
    """Demonstrate export control classification for aviation content."""
    print_section("3. Export Control Classification")
    
    payload = """
    Project Update: Our eVTOL aircraft design has completed FAA Part 23 certification phase.
    The flight control system uses advanced avionics with autopilot capabilities.
    Propulsion system utilizes electric motors with battery management (BMS).
    This document is subject to ITAR export control regulations.
    """
    
    ctx = {"purpose": "engineering-doc", "env": "prod", "conversation_id": "DEMO-003",
           "caller": "engineer", "region": "us"}
    
    r = requests.post(f"{BASE}/classify", json={"payload": payload, "context": ctx})
    result = r.json()
    
    print(f"Categories: {[c['type'] for c in result.get('categories', [])]}")
    print(f"Export control detected: {'export_control' in [c['type'] for c in result.get('categories', [])]}")
    print(f"Suggested action: {result.get('suggested_action')}")


def demo_internal_domains():
    """Demonstrate detection of internal Joby domains."""
    print_section("4. Internal Domain Detection")
    
    payload = """
    Infrastructure:
    - Database: db01.na.joby.aero
    - App Server: app-server.az.joby.aero
    - Internal API: api.internal
    - IP: 10.50.100.25
    """
    
    ctx = {"purpose": "ops-review", "env": "prod", "conversation_id": "DEMO-004",
           "caller": "incident-mgr", "region": "us"}
    
    r = requests.post(f"{BASE}/classify", json={"payload": payload, "context": ctx})
    result = r.json()
    
    print(f"Categories: {[c['type'] for c in result.get('categories', [])]}")
    
    # Redact and detokenize
    r = requests.post(f"{BASE}/redact", json={"payload": payload, "context": ctx})
    red = r.json()
    handle = red["token_map_handle"]
    print(f"\nSanitized: {red['sanitized_payload']}")
    
    # Detokenize ops_sensitive
    r = requests.post(f"{BASE}/detokenize", json={
        "payload": red["sanitized_payload"],
        "token_map_handle": handle,
        "allow_categories": ["ops_sensitive"],
        "context": ctx
    })
    det = r.json()
    print(f"\nRestored (ops_sensitive): {det['restored_payload']}")


def demo_full_workflow():
    """Demonstrate complete classify → route → redact → detokenize workflow."""
    print_section("5. Full Workflow: Classify → Route → Redact → Detokenize")
    
    payload = {
        "text": "User alice@joby.aero connected to postgres://svc:Pass123@db.na.joby.aero:5432/prod"
    }
    
    ctx = {"purpose": "incident-response", "env": "prod", "conversation_id": "INC-999",
           "caller": "incident-mgr", "region": "us"}
    
    # Step 1: Classify
    print("\n[1] Classify:")
    r = requests.post(f"{BASE}/classify", json={"payload": payload, "context": ctx})
    classify_result = r.json()
    print(f"   Categories: {[c['type'] for c in classify_result.get('categories', [])]}")
    print(f"   Action: {classify_result.get('suggested_action')}")
    
    # Step 2: Route (gets execution plan)
    print("\n[2] Route:")
    r = requests.post(f"{BASE}/route", json={"model_request": payload, "context": ctx})
    route_result = r.json()
    if route_result.get('ok'):
        plan = route_result['plan']
        print(f"   Target: {plan['target']}")
        print(f"   Pre-steps: {[s['tool'] for s in plan['pre']]}")
        print(f"   Post-steps: {[s['tool'] for s in plan['post']]}")
    else:
        print(f"   BLOCKED: {route_result.get('errors')}")
        return
    
    # Step 3: Redact
    print("\n[3] Redact:")
    r = requests.post(f"{BASE}/redact", json={"payload": payload, "context": ctx})
    red = r.json()
    print(f"   Redactions: {len(red['redactions'])}")
    print(f"   Sanitized: {red['sanitized_payload']}")
    
    # Step 4: Detokenize (selective)
    print("\n[4] Detokenize (PII + Ops only, NOT secrets):")
    r = requests.post(f"{BASE}/detokenize", json={
        "payload": red["sanitized_payload"],
        "token_map_handle": red["token_map_handle"],
        "allow_categories": ["pii", "ops_sensitive"],
        "context": ctx
    })
    det = r.json()
    print(f"   Restored: {det['restored_payload']}")
    print(f"   Note: Secrets (postgres password) remain redacted!")


def demo_region_routing():
    """Demonstrate region-based policy routing."""
    print_section("6. Region-Based Routing")
    
    payload = "Email: contact@example.com"
    
    for region in ["us", "eu", "cn"]:
        ctx = {"env": "prod", "caller": "user", "region": region, 
               "conversation_id": f"DEMO-{region}"}
        
        r = requests.post(f"{BASE}/route", json={"model_request": {"text": payload}, "context": ctx})
        result = r.json()
        
        if result.get('ok'):
            target = result['plan']['target']
            print(f"Region {region.upper()}: routes to → {target}")
        else:
            print(f"Region {region.upper()}: BLOCKED")


def demo_audit_query():
    """Query audit logs."""
    print_section("7. Audit Log Query")
    
    r = requests.post(f"{BASE}/audit/query", json={"q": "classify", "limit": 5})
    records = r.json().get('records', [])
    
    print(f"Recent audit records (showing {len(records)}):")
    for rec in records[:3]:
        print(f"  - {rec.get('ts')}: {rec.get('action')} by {rec.get('caller')} - "
              f"cats: {[c['type'] for c in rec.get('categories', [])]}")


def main():
    """Run all demo scenarios."""
    print("""
╔══════════════════════════════════════════════════════════╗
║  Redaction & Compliance MCP Server - Demo Client        ║
║  Showcasing Production-Ready Features                   ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Test server connectivity
        r = requests.get(f"{BASE}/docs", timeout=2)
        print(f"✓ Server running at: {BASE}\n")
    except:
        print(f"✗ Cannot connect to server at: {BASE}")
        print("  Please start the server: uvicorn mcp_redaction.server:app --port 8019")
        sys.exit(1)
    
    # Run demos
    demo_multi_credential()
    demo_pii_validation()
    demo_export_control()
    demo_internal_domains()
    demo_full_workflow()
    demo_region_routing()
    demo_audit_query()
    
    print(f"\n{'='*60}")
    print("✓ Demo completed successfully!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
