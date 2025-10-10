"""
Tests for export control classifier.
"""

import pytest
from mcp_redaction.classifier import (
    classify_export_control,
    should_enforce_internal_only,
)


class TestExportControlClassifier:
    """Test aviation program keyword detection for export control."""
    
    def test_evtol_keywords(self):
        text = "Our eVTOL aircraft design uses advanced vertical take-off technology"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == True
        assert result["confidence"] > 0.7
        assert result["match_count"] >= 2
    
    def test_faa_certification(self):
        text = "FAA Part 23 type certificate airworthiness requirements"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == True
        assert result["match_count"] >= 3
    
    def test_itar_keywords(self):
        text = "This document is subject to ITAR export control regulations"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == True
    
    def test_propulsion_system(self):
        text = "Electric motor propulsion system with battery management"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == True
        assert "propulsion" in result["matched_keywords"][0].lower() or \
               "motor" in result["matched_keywords"][0].lower()
    
    def test_flight_control(self):
        text = "Flight control system with autopilot and avionics"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == True
        assert result["match_count"] >= 2
    
    def test_manufacturing_materials(self):
        text = "Carbon fiber composite material CFRP manufacturing process"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == True
    
    def test_non_controlled_content(self):
        text = "Please review the meeting agenda and confirm attendance"
        result = classify_export_control(text)
        assert result["is_export_controlled"] == False
        assert result["confidence"] == 0.0
        assert result["match_count"] == 0
    
    def test_single_keyword_below_threshold(self):
        text = "We discussed aircraft in the meeting"
        result = classify_export_control(text, threshold=2)
        assert result["is_export_controlled"] == False
        assert result["match_count"] == 1
    
    def test_confidence_scaling(self):
        # More keywords = higher confidence
        text_low = "aircraft design"
        text_high = "eVTOL aircraft design with flight control avionics autopilot FAA certification ITAR"
        
        result_low = classify_export_control(text_low, threshold=1)
        result_high = classify_export_control(text_high)
        
        assert result_high["confidence"] > result_low["confidence"]


class TestInternalOnlyEnforcement:
    """Test internal-only enforcement logic."""
    
    def test_export_controlled_content(self):
        text = "eVTOL aircraft flight control system FAA Part 23"
        context = {"env": "prod", "region": "us"}
        assert should_enforce_internal_only(text, context) == True
    
    def test_non_controlled_content(self):
        text = "General business meeting notes"
        context = {"env": "prod", "region": "us"}
        assert should_enforce_internal_only(text, context) == False
    
    def test_restricted_region_china(self):
        text = "Some general content"
        context = {"env": "prod", "region": "cn"}
        assert should_enforce_internal_only(text, context) == True
    
    def test_restricted_region_russia(self):
        text = "Non-sensitive content"
        context = {"env": "prod", "region": "ru"}
        assert should_enforce_internal_only(text, context) == True
    
    def test_toggle_disabled(self):
        text = "eVTOL aircraft with ITAR controls"
        context = {"env": "prod", "region": "us"}
        assert should_enforce_internal_only(text, context, enable_internal_only=False) == False
    
    def test_dev_environment_unrestricted_region(self):
        text = "General content"
        context = {"env": "dev", "region": "us"}
        assert should_enforce_internal_only(text, context) == False
