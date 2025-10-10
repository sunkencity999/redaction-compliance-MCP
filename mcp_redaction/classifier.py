"""
Export control and sensitive content classifier.
Detects aviation program keywords and other compliance-sensitive content.
"""

import re
from typing import List, Dict, Any

# Aviation program keywords - ITAR/EAR sensitive
AVIATION_KEYWORDS = [
    # Aircraft design and performance
    r"\b(?:eVTOL|vertical[\s-]?take[\s-]?off|VTOL)\b",
    r"\b(?:aircraft[\s-]?design|airframe|propulsion[\s-]?system)\b",
    r"\b(?:flight[\s-]?control|avionics|autopilot)\b",
    r"\b(?:aerodynamic|aerodynamics|lift[\s-]?coefficient)\b",
    
    # Regulatory and certification
    r"\b(?:FAA|Federal[\s-]?Aviation[\s-]?Administration)\b",
    r"\b(?:Part[\s-]?23|Part[\s-]?27|Part[\s-]?29|Part[\s-]?33)\b",
    r"\b(?:type[\s-]?certificate|TC|STC|airworthiness)\b",
    r"\b(?:ITAR|International[\s-]?Traffic[\s-]?in[\s-]?Arms)\b",
    r"\b(?:EAR|Export[\s-]?Administration[\s-]?Regulations)\b",
    r"\b(?:ECCN|export[\s-]?control)\b",
    
    # Propulsion and power systems
    r"\b(?:battery[\s-]?management|BMS|power[\s-]?distribution)\b",
    r"\b(?:electric[\s-]?motor|propeller|rotor[\s-]?blade)\b",
    r"\b(?:energy[\s-]?density|specific[\s-]?power)\b",
    
    # Flight operations
    r"\b(?:flight[\s-]?envelope|V-speed|cruise[\s-]?speed)\b",
    r"\b(?:payload[\s-]?capacity|range[\s-]?calculation)\b",
    r"\b(?:takeoff[\s-]?weight|MTOW|maximum[\s-]?takeoff)\b",
    
    # Manufacturing and materials
    r"\b(?:composite[\s-]?material|carbon[\s-]?fiber|CFRP)\b",
    r"\b(?:manufacturing[\s-]?process|tooling|assembly[\s-]?jig)\b",
    r"\b(?:quality[\s-]?assurance|AS9100|aerospace[\s-]?standard)\b",
]

# Compile patterns for performance
AVIATION_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in AVIATION_KEYWORDS]


def classify_export_control(text: str, threshold: int = 2) -> Dict[str, Any]:
    """
    Classify text for export control sensitivity.
    
    Args:
        text: Text to classify
        threshold: Minimum number of keyword matches to trigger classification
    
    Returns:
        Dictionary with classification results including:
        - is_export_controlled: bool
        - confidence: float (0.0 to 1.0)
        - matched_keywords: list of matched keyword patterns
        - match_count: int
    """
    matches = []
    matched_spans = []
    
    for pattern in AVIATION_PATTERNS:
        for match in pattern.finditer(text):
            matches.append(match.group(0))
            matched_spans.append((match.start(), match.end()))
    
    match_count = len(matches)
    is_controlled = match_count >= threshold
    
    # Confidence based on number of matches
    if match_count == 0:
        confidence = 0.0
    elif match_count < threshold:
        confidence = 0.3
    elif match_count < threshold * 2:
        confidence = 0.7
    elif match_count < threshold * 3:
        confidence = 0.85
    else:
        confidence = 0.95
    
    return {
        "is_export_controlled": is_controlled,
        "confidence": confidence,
        "matched_keywords": matches[:10],  # Limit to first 10 for brevity
        "match_count": match_count,
        "matched_spans": matched_spans[:10],
    }


def should_enforce_internal_only(
    text: str, 
    context: Dict[str, Any],
    enable_internal_only: bool = True
) -> bool:
    """
    Determine if content should be restricted to internal-only based on
    export control classification and context.
    
    Args:
        text: Text to evaluate
        context: Request context with env, region, caller info
        enable_internal_only: Toggle to enable/disable internal-only enforcement
    
    Returns:
        True if content should be internal-only
    """
    if not enable_internal_only:
        return False
    
    # Check export control classification
    ec_result = classify_export_control(text)
    if ec_result["is_export_controlled"]:
        return True
    
    # Check context-based rules
    env = context.get("env", "").lower()
    region = context.get("region", "").lower()
    
    # Production environment with export-controlled regions
    if env == "prod" and region in ["cn", "ru", "ir"]:
        return True
    
    return False
