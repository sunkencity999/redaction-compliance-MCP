import yaml, os
from typing import Dict, Any, List, Optional

class PolicyEngine:
    def __init__(self, path: str):
        self.path = path
        self.doc = self._load()

    def _load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def reload(self):
        self.doc = self._load()

    def _route_applies(self, route: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if a route applies to the given context (region, caller).
        """
        applies_to = route.get("applies_to", {})
        
        # Check region constraint
        allowed_regions = applies_to.get("regions", ["*"])
        if "*" not in allowed_regions:
            region = context.get("region", "unknown").lower()
            if region not in allowed_regions:
                return False
        
        # Check caller constraint
        allowed_callers = applies_to.get("callers", ["*"])
        if "*" not in allowed_callers:
            caller = context.get("caller", "unknown")
            if caller not in allowed_callers:
                return False
        
        return True

    def _get_caller_constraints(self, caller: str) -> Dict[str, Any]:
        """
        Get caller-specific constraints from policy.
        """
        caller_rules = self.doc.get("caller_rules", {})
        caller_routing = caller_rules.get("caller_routing", {})
        return caller_routing.get(caller, {})

    def _get_region_routing(self, region: str) -> Dict[str, Any]:
        """
        Get region-specific routing from policy.
        """
        geo_constraints = self.doc.get("geo_constraints", {})
        region_routing = geo_constraints.get("region_routing", {})
        restricted_regions = geo_constraints.get("restricted_regions", [])
        
        # Check if region is restricted
        if region.lower() in restricted_regions:
            return region_routing.get("restricted", {})
        
        return region_routing.get(region.lower(), {})

    def decide(self, categories: List[Dict[str,Any]], context: Dict[str,Any]) -> Dict[str,Any]:
        """
        Make a policy decision based on content categories and request context.
        
        Returns decision with:
        - action: allow|block|redact|internal_only
        - target: target model/system
        - requires_redaction: bool
        - allow_detokenize: bool
        - allowed_categories: list of categories that can be detokenized
        - policy_version: version of policy applied
        """
        cats = {c["type"] for c in categories}
        region = context.get("region", "unknown")
        caller = context.get("caller", "unknown")
        
        # Get caller and region constraints
        caller_constraints = self._get_caller_constraints(caller)
        region_routing = self._get_region_routing(region)
        
        # Default decision
        decision = {
            "action": "allow",
            "target": "internal:default",
            "requires_redaction": False,
            "allow_detokenize": True,
            "allowed_categories": ["ops_sensitive", "pii"],
            "policy_version": str(self.doc.get("version", "1"))
        }
        
        # Apply caller force_redact if specified
        if caller_constraints.get("force_redact", False):
            decision["requires_redaction"] = True
        
        # Evaluate routes in order
        for route in self.doc.get("routes", []):
            # Check if route applies to this context
            if not self._route_applies(route, context):
                continue
            
            m = route.get("match", {}).get("category")
            if m in cats or m is None:  # None matches default/allow
                action = route.get("action", "allow")
                decision["action"] = action
                
                if action == "block":
                    return decision
                
                if action == "redact":
                    decision["requires_redaction"] = True
                    # Use region-specific models if available
                    models = route.get("allow_models") or region_routing.get("preferred_models") or ["external:unspecified"]
                    decision["target"] = models[0]
                    decision["allow_detokenize"] = route.get("redact", {}).get("allow_detokenize", True)
                    
                    # Merge route categories with caller constraints
                    route_categories = route.get("allow_categories", ["ops_sensitive", "pii"])
                    caller_categories = caller_constraints.get("allow_categories", route_categories)
                    decision["allowed_categories"] = list(set(route_categories) & set(caller_categories))
                
                if action == "internal_only":
                    models = route.get("allow_models") or region_routing.get("internal_fallback") or ["internal:default"]
                    decision["target"] = models[0]
                    decision["requires_redaction"] = False
                    decision["allow_detokenize"] = False
                
                # For first matching route, return (unless it's a default)
                if m is not None:
                    return decision
        
        return decision
