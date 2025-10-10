"""
Tests for detector module - credential detection, validation, and span merging.
"""

import pytest
from mcp_redaction.detectors import find_spans, luhn_check, validate_ssn_format


class TestCredentialDetection:
    """Test detection of various credential types."""
    
    def test_aws_credentials(self):
        text = "AWS key: AKIAIOSFODNN7EXAMPLE and secret abc123xyz789"
        spans = find_spans(text)
        assert len(spans) > 0
        assert any(cat == "secret" for cat, _ in spans)
    
    def test_azure_storage_key(self):
        text = "AccountKey=abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd=="
        spans = find_spans(text)
        assert len(spans) > 0
        assert spans[0][0] == "secret"
    
    def test_azure_sas_token(self):
        text = "https://storage.blob.core.windows.net/?sv=2020-08-04&ss=bfqt&sig=abc123xyz"
        spans = find_spans(text)
        assert len(spans) > 0
    
    def test_gcp_api_key(self):
        text = "GCP API Key: AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe"
        spans = find_spans(text)
        assert len(spans) > 0
        assert spans[0][0] == "secret"
    
    def test_jwt_token(self):
        text = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        spans = find_spans(text)
        assert len(spans) > 0
        assert spans[0][0] == "secret"
    
    def test_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        spans = find_spans(text)
        assert len(spans) > 0
    
    def test_pem_private_key(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        spans = find_spans(text)
        assert len(spans) > 0
        assert spans[0][0] == "secret"
    
    def test_kubeconfig_token(self):
        text = "apiVersion: v1\nkind: Config\nclusters:\n  - cluster:\n      server: https://k8s.example.com"
        spans = find_spans(text)
        assert len(spans) > 0
    
    def test_connection_string(self):
        text = "postgres://user:password123@db.internal:5432/mydb"
        spans = find_spans(text)
        assert len(spans) > 0
        assert spans[0][0] == "secret"


class TestPIIDetection:
    """Test PII detection with validation."""
    
    def test_email_detection(self):
        text = "Contact me at john.doe@joby.aero"
        spans = find_spans(text)
        assert len(spans) == 1
        assert spans[0][0] == "pii"
    
    def test_phone_detection(self):
        text = "Call me at +1-555-123-4567"
        spans = find_spans(text)
        assert len(spans) == 1
        assert spans[0][0] == "pii"
    
    def test_valid_credit_card(self):
        # Valid Visa test card number
        text = "Card: 4532015112830366"
        spans = find_spans(text)
        assert len(spans) == 1
        assert spans[0][0] == "pii"
    
    def test_invalid_credit_card_rejected(self):
        # Invalid Luhn checksum
        text = "Card: 4532015112830367"
        spans = find_spans(text)
        # Should not detect invalid card
        assert not any(cat == "pii" and text[s:e] == "4532015112830367" for cat, (s, e) in spans)
    
    def test_valid_ssn(self):
        text = "SSN: 123-45-6789"
        spans = find_spans(text)
        assert len(spans) == 1
        assert spans[0][0] == "pii"
    
    def test_invalid_ssn_rejected(self):
        # Invalid SSN (area code 000)
        text = "SSN: 000-45-6789"
        spans = find_spans(text)
        assert not any(text[s:e] == "000-45-6789" for _, (s, e) in spans)
    
    def test_invalid_ssn_666_rejected(self):
        # Invalid SSN (area code 666)
        text = "SSN: 666-45-6789"
        spans = find_spans(text)
        assert not any(text[s:e] == "666-45-6789" for _, (s, e) in spans)


class TestOpsDetection:
    """Test ops-sensitive data detection."""
    
    def test_internal_domain_joby(self):
        text = "Connect to server.na.joby.aero"
        spans = find_spans(text)
        assert len(spans) >= 1
        assert any(cat == "ops_sensitive" for cat, _ in spans)
    
    def test_internal_domain_azure(self):
        text = "Database at db01.az.joby.aero"
        spans = find_spans(text)
        assert len(spans) >= 1
        assert any(cat == "ops_sensitive" for cat, _ in spans)
    
    def test_ip_address(self):
        text = "Server IP: 192.168.1.100"
        spans = find_spans(text)
        assert len(spans) >= 1
        assert any(cat == "ops_sensitive" for cat, _ in spans)
    
    def test_hostname_internal(self):
        text = "server.internal domain.local"
        spans = find_spans(text)
        assert len(spans) >= 2


class TestSpanMerging:
    """Test overlapping span handling."""
    
    def test_overlapping_spans_priority(self):
        # Email in connection string - secret should take priority
        text = "postgres://admin:pass@db.internal:5432/app"
        spans = find_spans(text)
        # Connection string should be detected as secret (higher priority)
        assert spans[0][0] == "secret"
    
    def test_non_overlapping_spans(self):
        text = "Email: test@example.com and server: 192.168.1.1"
        spans = find_spans(text)
        assert len(spans) == 2


class TestValidationFunctions:
    """Test validation helper functions."""
    
    def test_luhn_check_valid(self):
        assert luhn_check("4532015112830366") == True
        assert luhn_check("4532-0151-1283-0366") == True  # With dashes
        assert luhn_check("4532 0151 1283 0366") == True  # With spaces
    
    def test_luhn_check_invalid(self):
        assert luhn_check("4532015112830367") == False
        assert luhn_check("1234567890123456") == False
    
    def test_ssn_validation_valid(self):
        assert validate_ssn_format("123-45-6789") == True
        assert validate_ssn_format("987-65-4321") == True
    
    def test_ssn_validation_invalid(self):
        assert validate_ssn_format("000-45-6789") == False
        assert validate_ssn_format("666-45-6789") == False
        assert validate_ssn_format("900-45-6789") == False
        assert validate_ssn_format("999-45-6789") == False
