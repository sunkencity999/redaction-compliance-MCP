"""
Output safety filter to detect and annotate potentially dangerous commands.
"""

import re, os, json
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Expanded dangerous command patterns
DEFAULT_DANGEROUS_PATTERNS = [
    # Filesystem destruction
    (r'rm\s+-rf\s+/', "Recursive delete from root directory"),
    (r'rm\s+-rf\s+/\*', "Delete all files in root"),
    (r'rm\s+-[rf]+\s+~/', "Delete home directory"),
    (r'mkfs\.\w+\s+/dev/', "Format disk/partition"),
    (r'dd\s+if=.*\s+of=/dev/[sh]d[a-z]', "Direct disk write"),
    
    # System control
    (r'shutdown\s+-[hr]\s+now', "Immediate system shutdown/reboot"),
    (r'reboot\s+--force', "Forced system reboot"),
    (r'init\s+[06]', "System halt/reboot via init"),
    (r'systemctl\s+poweroff', "System poweroff"),
    (r'halt\s+-p', "System halt"),
    
    # Kubernetes/Container destruction
    (r'kubectl\s+delete\s+(?:namespace|ns)\s+--all', "Delete all Kubernetes namespaces"),
    (r'kubectl\s+delete\s+\w+\s+--all(?:\s+-n|\s+--namespace)', "Delete all resources in namespace"),
    (r'kubectl\s+drain\s+.*--delete-(?:local-data|emptydir-data)', "Forcefully drain node"),
    (r'docker\s+rm\s+-f\s+\$\(docker\s+ps\s+-aq\)', "Force remove all containers"),
    (r'docker\s+system\s+prune\s+-a\s+--volumes\s+--force', "Prune all Docker data"),
    
    # Database destruction
    (r'DROP\s+DATABASE\s+\w+', "Drop database"),
    (r'TRUNCATE\s+TABLE', "Truncate table"),
    (r'DELETE\s+FROM\s+\w+(?:\s+WHERE\s+1=1)?', "Delete all rows from table"),
    (r'psql.*-c\s+["\']DROP', "PostgreSQL drop command"),
    (r'mysql.*-e\s+["\']DROP', "MySQL drop command"),
    
    # Cloud infrastructure destruction
    (r'aws\s+s3\s+rb\s+s3://.*--force', "Force delete S3 bucket"),
    (r'aws\s+ec2\s+terminate-instances\s+--instance-ids\s+.*\*', "Terminate EC2 instances with wildcard"),
    (r'az\s+group\s+delete\s+--name\s+.*--yes\s+--no-wait', "Delete Azure resource group"),
    (r'gcloud\s+projects\s+delete', "Delete GCP project"),
    (r'terraform\s+destroy\s+-auto-approve', "Auto-approve Terraform destroy"),
    
    # Network/Firewall
    (r'iptables\s+-F', "Flush all iptables rules"),
    (r'iptables\s+-X', "Delete all iptables chains"),
    (r'ufw\s+disable', "Disable firewall"),
    
    # User/Permission manipulation
    (r'chmod\s+777\s+/', "Set world-writable permissions on root"),
    (r'chown\s+-R\s+\w+:\w+\s+/', "Recursive ownership change from root"),
    (r'passwd\s+root', "Change root password"),
    (r'userdel\s+-r\s+root', "Delete root user"),
    
    # Package/Service manipulation
    (r'apt-get\s+remove\s+--purge\s+.*sudo', "Remove sudo package"),
    (r'yum\s+remove\s+sudo', "Remove sudo package (yum)"),
    (r'systemctl\s+stop\s+ssh(?:d)?', "Stop SSH service"),
    (r'systemctl\s+disable\s+ssh(?:d)?', "Disable SSH service"),
    
    # Fork bombs and resource exhaustion
    (r':\(\)\{\s*:\|:&\s*\};:', "Fork bomb pattern"),
    (r'while\s+true;\s*do.*done', "Infinite loop"),
    (r'yes\s+>\s+/dev/', "Resource exhaustion"),
    
    # Cron/Scheduled tasks
    (r'crontab\s+-r', "Remove all cron jobs"),
    (r'\*\s+\*\s+\*\s+\*\s+\*\s+rm\s+-rf', "Scheduled recursive delete"),
]


class SafetyFilter:
    """
    Output safety filter with configurable dangerous command patterns.
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize safety filter.
        
        Args:
            config_path: Optional path to external JSON config file with custom patterns
        """
        self.patterns: List[Tuple[re.Pattern, str]] = []
        self._load_patterns(config_path)
    
    def _load_patterns(self, config_path: str = None):
        """Load dangerous command patterns from default and optional config file."""
        # Load default patterns
        for pattern_str, description in DEFAULT_DANGEROUS_PATTERNS:
            try:
                compiled = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                self.patterns.append((compiled, description))
            except re.error as e:
                # Log but don't fail on invalid patterns
                print(f"Warning: Invalid regex pattern '{pattern_str}': {e}")
        
        # Load external config if provided
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    custom_patterns = config.get("dangerous_patterns", [])
                    for item in custom_patterns:
                        pattern_str = item.get("pattern")
                        description = item.get("description", "Custom dangerous pattern")
                        if pattern_str:
                            compiled = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                            self.patterns.append((compiled, description))
            except Exception as e:
                print(f"Warning: Failed to load safety config from {config_path}: {e}")
    
    def scan(self, text: str) -> List[Dict[str, Any]]:
        """
        Scan text for dangerous command patterns.
        
        Returns:
            List of detected issues with pattern, description, and match location
        """
        issues = []
        for pattern, description in self.patterns:
            for match in pattern.finditer(text):
                issues.append({
                    "matched_text": match.group(0),
                    "description": description,
                    "start": match.start(),
                    "end": match.end(),
                    "line": text[:match.start()].count('\n') + 1,
                })
        return issues
    
    def annotate(self, text: str, mode: str = "warning") -> str:
        """
        Annotate text with safety warnings.
        
        Args:
            text: Text to scan and annotate
            mode: 'warning' (append warning), 'block' (replace dangerous commands), 'silent' (no change)
        
        Returns:
            Annotated text
        """
        issues = self.scan(text)
        
        if not issues:
            return text
        
        if mode == "silent":
            return text
        
        if mode == "block":
            # Replace dangerous commands with safety message
            result = text
            for issue in sorted(issues, key=lambda x: x["start"], reverse=True):
                start, end = issue["start"], issue["end"]
                replacement = f"[BLOCKED: {issue['description']}]"
                result = result[:start] + replacement + result[end:]
            return result
        
        # Default: warning mode
        if len(issues) == 1:
            warning = f"\n\n⚠️  [SAFETY WARNING] Potentially destructive command detected:\n  • {issues[0]['description']}"
        else:
            warnings_list = "\n".join(f"  • {issue['description']}" for issue in issues[:5])
            more = f"\n  ... and {len(issues) - 5} more" if len(issues) > 5 else ""
            warning = f"\n\n⚠️  [SAFETY WARNING] {len(issues)} potentially destructive commands detected:\n{warnings_list}{more}"
        
        return text + warning


# Global safety filter instance
_safety_filter = None

def get_safety_filter() -> SafetyFilter:
    """Get or create global safety filter instance."""
    global _safety_filter
    if _safety_filter is None:
        config_path = os.getenv("SAFETY_CONFIG_PATH")
        _safety_filter = SafetyFilter(config_path)
    return _safety_filter


def output_safety(text: str, mode: str = "warning") -> str:
    """
    Apply safety filter to text output.
    
    Args:
        text: Text to filter
        mode: 'warning' (default), 'block', or 'silent'
    
    Returns:
        Filtered/annotated text
    """
    filter = get_safety_filter()
    return filter.annotate(text, mode)
