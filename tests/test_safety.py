"""
Tests for output safety filter.
"""

import pytest
import os
import json
import tempfile
from mcp_redaction.safety import SafetyFilter, output_safety, get_safety_filter


class TestSafetyFilter:
    """Test safety filter with dangerous command detection."""
    
    def test_detect_rm_rf_root(self):
        filter = SafetyFilter()
        text = "To clean up, run: rm -rf /"
        issues = filter.scan(text)
        assert len(issues) > 0
        assert any("root directory" in issue["description"].lower() for issue in issues)
    
    def test_detect_shutdown_command(self):
        filter = SafetyFilter()
        text = "Execute: shutdown -h now"
        issues = filter.scan(text)
        assert len(issues) > 0
        assert any("shutdown" in issue["description"].lower() for issue in issues)
    
    def test_detect_kubectl_delete_all(self):
        filter = SafetyFilter()
        text = "kubectl delete namespace --all"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_detect_docker_prune(self):
        filter = SafetyFilter()
        text = "docker system prune -a --volumes --force"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_detect_drop_database(self):
        filter = SafetyFilter()
        text = "Run: DROP DATABASE production"
        issues = filter.scan(text)
        assert len(issues) > 0
        assert any("database" in issue["description"].lower() for issue in issues)
    
    def test_detect_aws_s3_force_delete(self):
        filter = SafetyFilter()
        text = "aws s3 rb s3://my-bucket --force"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_detect_terraform_auto_destroy(self):
        filter = SafetyFilter()
        text = "terraform destroy -auto-approve"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_detect_iptables_flush(self):
        filter = SafetyFilter()
        text = "iptables -F"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_detect_chmod_777_root(self):
        filter = SafetyFilter()
        text = "chmod 777 /"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_detect_crontab_remove(self):
        filter = SafetyFilter()
        text = "crontab -r"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_safe_content_no_issues(self):
        filter = SafetyFilter()
        text = "Please check the logs and restart the service"
        issues = filter.scan(text)
        assert len(issues) == 0
    
    def test_annotate_warning_mode(self):
        filter = SafetyFilter()
        text = "Run: rm -rf /"
        annotated = filter.annotate(text, mode="warning")
        assert "SAFETY WARNING" in annotated
        assert text in annotated
    
    def test_annotate_block_mode(self):
        filter = SafetyFilter()
        text = "Run: rm -rf /"
        annotated = filter.annotate(text, mode="block")
        assert "BLOCKED" in annotated
        assert "rm -rf /" not in annotated
    
    def test_annotate_silent_mode(self):
        filter = SafetyFilter()
        text = "Run: rm -rf /"
        annotated = filter.annotate(text, mode="silent")
        assert annotated == text
        assert "WARNING" not in annotated
    
    def test_multiple_issues_detection(self):
        filter = SafetyFilter()
        text = """
        First: rm -rf /
        Second: shutdown -h now
        Third: DROP DATABASE prod
        """
        issues = filter.scan(text)
        assert len(issues) >= 3
    
    def test_issue_location_tracking(self):
        filter = SafetyFilter()
        text = "Safe text\nrm -rf /\nMore text"
        issues = filter.scan(text)
        assert len(issues) > 0
        assert issues[0]["line"] == 2


class TestExternalConfig:
    """Test external config file loading."""
    
    def test_load_custom_patterns(self):
        config_data = {
            "dangerous_patterns": [
                {"pattern": r"custom-dangerous-cmd", "description": "Custom dangerous command"},
                {"pattern": r"risky-operation", "description": "Risky operation"},
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            filter = SafetyFilter(config_path)
            text = "Run: custom-dangerous-cmd"
            issues = filter.scan(text)
            assert len(issues) > 0
            assert any("Custom dangerous command" in issue["description"] for issue in issues)
        finally:
            os.unlink(config_path)
    
    def test_invalid_config_file_graceful_fallback(self):
        # Non-existent file should not crash
        filter = SafetyFilter("/nonexistent/config.json")
        # Should still have default patterns
        text = "rm -rf /"
        issues = filter.scan(text)
        assert len(issues) > 0


class TestOutputSafetyFunction:
    """Test the output_safety convenience function."""
    
    def test_output_safety_default(self):
        text = "Run: rm -rf /"
        result = output_safety(text)
        assert "SAFETY WARNING" in result
    
    def test_output_safety_block_mode(self):
        text = "Run: rm -rf /"
        result = output_safety(text, mode="block")
        assert "BLOCKED" in result
    
    def test_output_safety_safe_content(self):
        text = "This is safe content"
        result = output_safety(text)
        assert result == text


class TestCaseSensitivity:
    """Test case-insensitive pattern matching."""
    
    def test_case_insensitive_rm(self):
        filter = SafetyFilter()
        text = "RM -RF /"
        issues = filter.scan(text)
        assert len(issues) > 0
    
    def test_case_insensitive_shutdown(self):
        filter = SafetyFilter()
        text = "SHUTDOWN -h NOW"
        issues = filter.scan(text)
        assert len(issues) > 0
