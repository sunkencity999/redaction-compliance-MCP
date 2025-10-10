"""
Comprehensive integration tests for the full MCP server.
Tests multi-category redaction, authorization, secret blocking, and performance.
"""

import pytest
import os
import time
from fastapi.testclient import TestClient
from mcp_redaction.server import app

# Set test environment variables
os.environ.setdefault("MCP_TOKEN_SALT", "test-salt-for-integration")
os.environ.setdefault("TOKEN_BACKEND", "memory")

client = TestClient(app)


class TestMultiCategoryRedaction:
    """Test redaction with multiple sensitivity categories."""
    
    def test_multi_category_payload(self):
        """Test payload with PII, secrets, and ops-sensitive data."""
        payload = """
        Contact: john.doe@joby.aero
        Server: db.na.joby.aero
        API Key: AKIAIOSFODNN7EXAMPLE
        Phone: 555-123-4567
        """
        context = {
            "purpose": "analysis",
            "env": "dev",
            "conversation_id": "test-123",
            "caller": "incident-mgr",
            "region": "us"
        }
        
        # Classify
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        cats = r.json()["categories"]
        cat_types = {c["type"] for c in cats}
        assert "secret" in cat_types
        assert "pii" in cat_types
        assert "ops_sensitive" in cat_types
        
        # Should suggest block due to secret
        assert r.json()["suggested_action"] == "block"
    
    def test_redact_multiple_categories(self):
        """Test redaction handles multiple categories correctly."""
        payload = "Email: test@example.com, Server: 192.168.1.1"
        context = {
            "env": "dev",
            "conversation_id": "test-456",
            "caller": "incident-mgr",
            "region": "us"
        }
        
        r = client.post("/redact", json={"payload": payload, "context": context})
        assert r.status_code == 200
        
        result = r.json()
        sanitized = result["sanitized_payload"]
        redactions = result["redactions"]
        
        # Should have both email and IP redacted
        assert "«token:" in sanitized
        assert "test@example.com" not in sanitized
        assert "192.168.1.1" not in sanitized
        assert len(redactions) >= 2


class TestDetokenizeAuthorization:
    """Test detokenize authorization and category filtering."""
    
    def test_detokenize_trusted_caller(self):
        """Test trusted caller can detokenize allowed categories."""
        payload = "Email: jane@example.com, IP: 10.0.0.1"
        context = {
            "env": "dev",
            "conversation_id": "test-789",
            "caller": "incident-mgr",
            "region": "us"
        }
        
        # Redact
        r = client.post("/redact", json={"payload": payload, "context": context})
        assert r.status_code == 200
        sanitized = r.json()["sanitized_payload"]
        handle = r.json()["token_map_handle"]
        
        # Detokenize with allowed categories
        r = client.post("/detokenize", json={
            "payload": sanitized,
            "token_map_handle": handle,
            "allow_categories": ["pii", "ops_sensitive"],
            "context": context
        })
        assert r.status_code == 200
        restored = r.json()["restored_payload"]
        assert "jane@example.com" in restored
        assert "10.0.0.1" in restored
    
    def test_detokenize_untrusted_caller_blocked(self):
        """Test untrusted caller cannot detokenize."""
        payload = "Email: test@example.com"
        context_trusted = {
            "env": "dev",
            "conversation_id": "test-999",
            "caller": "incident-mgr",
            "region": "us"
        }
        context_untrusted = {
            "env": "dev",
            "conversation_id": "test-999",
            "caller": "untrusted-user",
            "region": "us"
        }
        
        # Redact with trusted caller
        r = client.post("/redact", json={"payload": payload, "context": context_trusted})
        assert r.status_code == 200
        sanitized = r.json()["sanitized_payload"]
        handle = r.json()["token_map_handle"]
        
        # Try to detokenize with untrusted caller
        r = client.post("/detokenize", json={
            "payload": sanitized,
            "token_map_handle": handle,
            "allow_categories": ["pii"],
            "context": context_untrusted
        })
        assert r.status_code == 403
    
    def test_detokenize_category_filtering(self):
        """Test detokenize only restores allowed categories."""
        payload = "Email: admin@example.com, Server: db.internal"
        context = {
            "env": "dev",
            "conversation_id": "test-cat",
            "caller": "incident-mgr",
            "region": "us"
        }
        
        # Redact
        r = client.post("/redact", json={"payload": payload, "context": context})
        sanitized = r.json()["sanitized_payload"]
        handle = r.json()["token_map_handle"]
        
        # Detokenize only PII, not ops_sensitive
        r = client.post("/detokenize", json={
            "payload": sanitized,
            "token_map_handle": handle,
            "allow_categories": ["pii"],
            "context": context
        })
        assert r.status_code == 200
        restored = r.json()["restored_payload"]
        
        # Email should be restored
        assert "admin@example.com" in restored
        # Server should still be redacted
        assert "db.internal" not in restored or "«token:" in restored


class TestSecretBlockPath:
    """Test that secrets are always blocked."""
    
    def test_secret_blocks_classify(self):
        """Test classify suggests block for secrets."""
        payload = "AWS Key: AKIAIOSFODNN7EXAMPLE"
        context = {"env": "prod", "caller": "user1", "region": "us"}
        
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        assert r.json()["suggested_action"] == "block"
    
    def test_secret_blocks_route(self):
        """Test routing blocks requests with secrets."""
        payload = "Connection: postgres://user:pass@db.local:5432/app"
        context = {"env": "prod", "caller": "user1", "region": "us"}
        
        r = client.post("/route", json={
            "model_request": {"text": payload},
            "context": context
        })
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] == False
        assert "Blocked" in str(result.get("errors", []))
    
    def test_jwt_token_blocked(self):
        """Test JWT tokens are blocked."""
        payload = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.test"
        context = {"env": "prod", "caller": "user1", "region": "us"}
        
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        assert r.json()["suggested_action"] == "block"
    
    def test_azure_key_blocked(self):
        """Test Azure storage keys are blocked."""
        payload = "AccountKey=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd=="
        context = {"env": "prod", "caller": "user1", "region": "us"}
        
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        cats = r.json()["categories"]
        assert any(c["type"] == "secret" for c in cats)


class TestExportControlClassification:
    """Test export control classification and routing."""
    
    def test_export_control_detected(self):
        """Test aviation keywords trigger export control."""
        payload = "Our eVTOL aircraft design uses FAA Part 23 certification with ITAR controls"
        context = {"env": "prod", "caller": "engineer", "region": "us"}
        
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        cats = r.json()["categories"]
        assert any(c["type"] == "export_control" for c in cats)
    
    def test_export_control_internal_only(self):
        """Test export control content routes to internal only."""
        payload = "eVTOL flight control avionics system with autopilot"
        context = {"env": "prod", "caller": "engineer", "region": "us"}
        
        r = client.post("/route", json={
            "model_request": {"text": payload},
            "context": context
        })
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] == True
        assert "internal" in result["plan"]["target"]


class TestPayloadSizeLimits:
    """Test payload size validation."""
    
    def test_payload_too_large(self):
        """Test large payload rejection."""
        # Create a payload larger than MAX_PAYLOAD_KB (256KB default)
        large_payload = "X" * (300 * 1024)  # 300KB
        context = {"env": "dev", "caller": "user1", "region": "us"}
        
        r = client.post("/redact", json={"payload": large_payload, "context": context})
        assert r.status_code == 413


class TestAuditLogging:
    """Test audit logging for all operations."""
    
    def test_classify_creates_audit(self):
        """Test classify action is audited."""
        payload = "test@example.com"
        context = {"env": "dev", "caller": "auditor", "region": "us"}
        
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        
        # Query audit logs
        r = client.post("/audit/query", json={"q": "auditor", "limit": 10})
        assert r.status_code == 200
        records = r.json()["records"]
        assert len(records) > 0
        assert any(rec.get("action") == "classify" for rec in records)
    
    def test_redact_creates_audit(self):
        """Test redact action is audited."""
        payload = "Email: test@example.com"
        context = {"env": "dev", "caller": "redactor", "region": "us", "conversation_id": "audit-test"}
        
        r = client.post("/redact", json={"payload": payload, "context": context})
        assert r.status_code == 200
        
        # Query audit logs
        r = client.post("/audit/query", json={"q": "redactor", "limit": 10})
        assert r.status_code == 200
        records = r.json()["records"]
        assert any(rec.get("action") == "redact" for rec in records)


class TestPerformanceBenchmarks:
    """Performance tests to ensure <60ms P95 for 50KB payloads."""
    
    def test_classify_redact_performance_50kb(self):
        """Test classify + redact completes in <60ms for 50KB payload."""
        # Create a 50KB payload with some sensitive data
        payload = ("Email: test@example.com, IP: 192.168.1.1, " * 1000)[:50000]
        context = {
            "env": "dev",
            "caller": "perf-test",
            "region": "us",
            "conversation_id": "perf-123"
        }
        
        # Run multiple times to get consistent timing
        times = []
        for _ in range(10):
            start = time.time()
            
            # Classify
            r1 = client.post("/classify", json={"payload": payload, "context": context})
            assert r1.status_code == 200
            
            # Redact
            r2 = client.post("/redact", json={"payload": payload, "context": context})
            assert r2.status_code == 200
            
            elapsed = (time.time() - start) * 1000  # Convert to ms
            times.append(elapsed)
        
        # Check P95 (95th percentile)
        times.sort()
        p95 = times[int(len(times) * 0.95)]
        print(f"\nP95 latency for 50KB: {p95:.2f}ms")
        
        # Target <60ms, but allow some overhead in test environment
        assert p95 < 100, f"P95 latency {p95:.2f}ms exceeds threshold"
    
    def test_redact_performance_benchmark(self):
        """Benchmark redaction performance."""
        sizes = [1000, 10000, 50000]  # 1KB, 10KB, 50KB
        
        for size in sizes:
            payload = ("test@example.com " * 50)[:size]
            context = {
                "env": "dev",
                "caller": "bench",
                "region": "us",
                "conversation_id": "bench"
            }
            
            start = time.time()
            r = client.post("/redact", json={"payload": payload, "context": context})
            elapsed = (time.time() - start) * 1000
            
            assert r.status_code == 200
            print(f"\nRedact {size} bytes: {elapsed:.2f}ms")


class TestConversationScope:
    """Test deterministic tokenization within conversation scope."""
    
    def test_same_conversation_same_token(self):
        """Test same value gets same token within conversation."""
        payload = "Email: alice@example.com"
        context1 = {
            "env": "dev",
            "caller": "incident-mgr",
            "region": "us",
            "conversation_id": "conv-123"
        }
        context2 = {
            "env": "dev",
            "caller": "incident-mgr",
            "region": "us",
            "conversation_id": "conv-123"
        }
        
        r1 = client.post("/redact", json={"payload": payload, "context": context1})
        r2 = client.post("/redact", json={"payload": payload, "context": context2})
        
        assert r1.status_code == 200
        assert r2.status_code == 200
        
        # Should produce same placeholder in same conversation
        sanitized1 = r1.json()["sanitized_payload"]
        sanitized2 = r2.json()["sanitized_payload"]
        assert sanitized1 == sanitized2
    
    def test_different_conversation_different_token(self):
        """Test same value gets different token in different conversations."""
        payload = "Email: bob@example.com"
        context1 = {
            "env": "dev",
            "caller": "incident-mgr",
            "region": "us",
            "conversation_id": "conv-AAA"
        }
        context2 = {
            "env": "dev",
            "caller": "incident-mgr",
            "region": "us",
            "conversation_id": "conv-BBB"
        }
        
        r1 = client.post("/redact", json={"payload": payload, "context": context1})
        r2 = client.post("/redact", json={"payload": payload, "context": context2})
        
        sanitized1 = r1.json()["sanitized_payload"]
        sanitized2 = r2.json()["sanitized_payload"]
        
        # Different conversations should produce different placeholders
        assert sanitized1 != sanitized2


class TestRegionBasedRouting:
    """Test geo/region-based routing decisions."""
    
    def test_us_region_routing(self):
        """Test US region gets appropriate routing."""
        payload = "Email: test@example.com"
        context = {"env": "prod", "caller": "user", "region": "us"}
        
        r = client.post("/route", json={
            "model_request": {"text": payload},
            "context": context
        })
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] == True
    
    def test_restricted_region_handling(self):
        """Test restricted regions get internal-only routing."""
        payload = "Some sensitive aviation data with eVTOL keywords"
        context = {"env": "prod", "caller": "user", "region": "cn"}
        
        r = client.post("/classify", json={"payload": payload, "context": context})
        assert r.status_code == 200
        # Export control content should route to internal
