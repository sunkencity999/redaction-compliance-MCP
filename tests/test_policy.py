"""
Tests for policy engine with geo/region constraints and caller routing.
"""

import pytest
import os
import tempfile
import yaml
from mcp_redaction.policy import PolicyEngine


@pytest.fixture
def sample_policy_file():
    """Create a temporary policy file for testing."""
    policy_data = {
        "version": 2,
        "geo_constraints": {
            "restricted_regions": ["cn", "ru"],
            "region_routing": {
                "us": {
                    "allow_external": True,
                    "preferred_models": ["external:openai:gpt-4"],
                },
                "eu": {
                    "allow_external": True,
                    "data_residency": "eu",
                    "preferred_models": ["external:azure_eu:gpt-4"],
                },
                "restricted": {
                    "allow_external": False,
                    "preferred_models": ["internal:llama3"],
                },
            },
        },
        "caller_rules": {
            "trusted_callers": ["incident-mgr", "runbook-executor"],
            "caller_routing": {
                "incident-mgr": {
                    "allow_categories": ["pii", "ops_sensitive"],
                    "max_detokenize": True,
                },
                "external-analyst": {
                    "allow_categories": [],
                    "max_detokenize": False,
                    "force_redact": True,
                },
            },
        },
        "routes": [
            {
                "name": "secrets_block",
                "match": {"category": "secret"},
                "action": "block",
                "applies_to": {"regions": ["*"], "callers": ["*"]},
            },
            {
                "name": "export_control",
                "match": {"category": "export_control"},
                "action": "internal_only",
                "allow_models": ["internal:llama3"],
                "applies_to": {"regions": ["*"], "callers": ["*"]},
            },
            {
                "name": "pii_us",
                "match": {"category": "pii"},
                "action": "redact",
                "redact": {"allow_detokenize": True},
                "allow_models": ["external:openai:gpt-4"],
                "allow_categories": ["pii", "ops_sensitive"],
                "applies_to": {"regions": ["us"], "callers": ["*"]},
            },
            {
                "name": "pii_eu",
                "match": {"category": "pii"},
                "action": "redact",
                "redact": {"allow_detokenize": True},
                "allow_models": ["external:azure_eu:gpt-4"],
                "allow_categories": ["pii"],
                "applies_to": {"regions": ["eu"], "callers": ["*"]},
            },
        ],
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(policy_data, f)
        temp_path = f.name
    
    yield temp_path
    os.unlink(temp_path)


class TestPolicyDecisions:
    """Test policy decision logic."""
    
    def test_block_secrets(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = [{"type": "secret", "confidence": 0.95}]
        context = {"region": "us", "caller": "user1"}
        
        decision = engine.decide(categories, context)
        assert decision["action"] == "block"
    
    def test_export_control_internal_only(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = [{"type": "export_control", "confidence": 0.9}]
        context = {"region": "us", "caller": "user1"}
        
        decision = engine.decide(categories, context)
        assert decision["action"] == "internal_only"
        assert "internal" in decision["target"]
    
    def test_pii_redact_us_region(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = [{"type": "pii", "confidence": 0.85}]
        context = {"region": "us", "caller": "user1"}
        
        decision = engine.decide(categories, context)
        assert decision["action"] == "redact"
        assert decision["requires_redaction"] == True
        assert "openai" in decision["target"]
        assert "pii" in decision["allowed_categories"]
        assert "ops_sensitive" in decision["allowed_categories"]
    
    def test_pii_redact_eu_region(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = [{"type": "pii", "confidence": 0.85}]
        context = {"region": "eu", "caller": "user1"}
        
        decision = engine.decide(categories, context)
        assert decision["action"] == "redact"
        assert "azure_eu" in decision["target"]
        assert "pii" in decision["allowed_categories"]
        # EU should not include ops_sensitive for PII
        assert "ops_sensitive" not in decision["allowed_categories"]
    
    def test_caller_constraints_trusted(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = [{"type": "pii", "confidence": 0.85}]
        context = {"region": "us", "caller": "incident-mgr"}
        
        decision = engine.decide(categories, context)
        # Should get intersection of route and caller categories
        assert "pii" in decision["allowed_categories"]
        assert "ops_sensitive" in decision["allowed_categories"]
    
    def test_caller_force_redact(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = []  # No sensitive categories
        context = {"region": "us", "caller": "external-analyst"}
        
        decision = engine.decide(categories, context)
        assert decision["requires_redaction"] == True
    
    def test_restricted_region_routing(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        categories = [{"type": "pii", "confidence": 0.85}]
        context = {"region": "cn", "caller": "user1"}
        
        # Secrets should still block regardless of region
        categories_secret = [{"type": "secret", "confidence": 0.95}]
        decision = engine.decide(categories_secret, context)
        assert decision["action"] == "block"


class TestRegionRouting:
    """Test region-specific routing logic."""
    
    def test_get_region_routing_us(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        routing = engine._get_region_routing("us")
        assert routing["allow_external"] == True
        assert "openai" in routing["preferred_models"][0]
    
    def test_get_region_routing_restricted(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        routing = engine._get_region_routing("cn")
        assert routing["allow_external"] == False
        assert "internal" in routing["preferred_models"][0]
    
    def test_get_caller_constraints(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        constraints = engine._get_caller_constraints("incident-mgr")
        assert "pii" in constraints["allow_categories"]
        assert constraints["max_detokenize"] == True


class TestRouteApplies:
    """Test route applicability logic."""
    
    def test_route_applies_wildcard(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        route = {"applies_to": {"regions": ["*"], "callers": ["*"]}}
        context = {"region": "us", "caller": "anyone"}
        assert engine._route_applies(route, context) == True
    
    def test_route_applies_specific_region(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        route = {"applies_to": {"regions": ["us", "eu"], "callers": ["*"]}}
        
        context_us = {"region": "us", "caller": "user1"}
        assert engine._route_applies(route, context_us) == True
        
        context_apac = {"region": "apac", "caller": "user1"}
        assert engine._route_applies(route, context_apac) == False
    
    def test_route_applies_specific_caller(self, sample_policy_file):
        engine = PolicyEngine(sample_policy_file)
        route = {"applies_to": {"regions": ["*"], "callers": ["admin", "operator"]}}
        
        context_admin = {"region": "us", "caller": "admin"}
        assert engine._route_applies(route, context_admin) == True
        
        context_user = {"region": "us", "caller": "user1"}
        assert engine._route_applies(route, context_user) == False
