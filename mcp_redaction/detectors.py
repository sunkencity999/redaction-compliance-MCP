import re, regex
from typing import List, Tuple, Dict

# Internal domains dictionary - Joby Aviation specific
INTERNAL_DOMAINS = [
    r"[\w.-]*\.na\.joby\.aero\b",
    r"[\w.-]*\.az\.joby\.aero\b",
    r"[\w.-]*\.joby\.aero\b",
    r"[\w.-]*\.internal\b",
    r"[\w.-]*\.local\b",
    r"[\w.-]*\.corp\b",
]

# High-precision patterns
PATTERNS = {
    # AWS credentials
    "secret_aws_akid": regex.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "secret_aws_secret": regex.compile(r"\b[A-Za-z0-9/+=]{40}\b"),
    
    # Azure credentials
    "secret_azure_storage": regex.compile(r"\bAccountKey=[A-Za-z0-9+/=]{86,88}\b"),
    "secret_azure_conn_str": regex.compile(r"DefaultEndpointsProtocol=https?;AccountName=[^;]+;AccountKey=[^;]+"),
    "secret_azure_sas": regex.compile(r"\?sv=\d{4}-\d{2}-\d{2}&[^\s]+sig=[A-Za-z0-9%]+"),
    
    # GCP credentials
    "secret_gcp_api_key": regex.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "secret_gcp_oauth": regex.compile(r"\b[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com\b"),
    
    # OAuth and Bearer tokens
    "secret_oauth_bearer": regex.compile(r"\b[Bb]earer\s+[A-Za-z0-9_\-\.~+/]+=*\b"),
    "secret_oauth_token": regex.compile(r"access_token['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.~+/]{20,})['\"]?"),
    
    # JWT tokens
    "secret_jwt": regex.compile(r"\beyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
    
    # PEM certificates and keys
    "secret_pem_private": regex.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "secret_pem_rsa": regex.compile(r"-----BEGIN RSA PRIVATE KEY-----"),
    "secret_pem_dsa": regex.compile(r"-----BEGIN DSA PRIVATE KEY-----"),
    "secret_pem_ec": regex.compile(r"-----BEGIN EC PRIVATE KEY-----"),
    "secret_pkcs12": regex.compile(r"-----BEGIN ENCRYPTED PRIVATE KEY-----"),
    
    # Kubernetes config
    "secret_kubeconfig": regex.compile(r"apiVersion:\s*v1\s*\nkind:\s*Config"),
    "secret_kube_token": regex.compile(r"token:\s*[A-Za-z0-9_\-\.]{20,}"),
    
    # Generic secrets
    "secret_basic_auth": regex.compile(r"\b[a-zA-Z0-9._%+-]+:[^@\s]{6,}@"),
    "secret_conn_str": regex.compile(r"(?:postgres|mysql|mongodb|redis|amqps?)://[^ \n]+", regex.IGNORECASE),
    "secret_api_key": regex.compile(r"['\"]?(?:api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})['\"]?", regex.IGNORECASE),
    
    # PII - Credit Cards (will validate with Luhn)
    "pii_credit_card": regex.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
    
    # PII - SSN
    "pii_ssn": regex.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    
    # PII - Email and Phone
    "pii_email": regex.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "pii_phone": regex.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"),
    
    # Ops Sensitive - Internal domains and IPs
    "ops_internal_domain": regex.compile("|".join(INTERNAL_DOMAINS)),
    "ops_hostname": regex.compile(r"\b(?:[a-zA-Z0-9-]+\.)+(?:internal|local|corp|na|az)\b"),
    "ip_addr": regex.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

CATEGORY_ORDER = [
    ("secret", [
        "secret_aws_akid", "secret_aws_secret", "secret_azure_storage", "secret_azure_conn_str",
        "secret_azure_sas", "secret_gcp_api_key", "secret_gcp_oauth", "secret_oauth_bearer",
        "secret_oauth_token", "secret_jwt", "secret_pem_private", "secret_pem_rsa", "secret_pem_dsa",
        "secret_pem_ec", "secret_pkcs12", "secret_kubeconfig", "secret_kube_token",
        "secret_basic_auth", "secret_conn_str", "secret_api_key"
    ]),
    ("pii", ["pii_credit_card", "pii_ssn", "pii_email", "pii_phone"]),
    ("ops_sensitive", ["ops_internal_domain", "ops_hostname", "ip_addr"]),
]

def luhn_check(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.
    Returns True if valid, False otherwise.
    """
    # Remove spaces and dashes
    card_number = card_number.replace(" ", "").replace("-", "")
    if not card_number.isdigit():
        return False
    
    # Luhn algorithm
    total = 0
    reverse_digits = card_number[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:  # Every second digit from right
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0

def validate_ssn_format(ssn: str) -> bool:
    """
    Validate SSN format (must be XXX-XX-XXXX where X is digit).
    Basic validation: area (first 3) != 000, 666, or 900-999.
    """
    parts = ssn.split("-")
    if len(parts) != 3:
        return False
    area = int(parts[0])
    if area == 0 or area == 666 or area >= 900:
        return False
    return True

def find_spans(text: str) -> List[Tuple[str, Tuple[int,int]]]:
    """
    Find sensitive data spans in text with validation.
    Returns list of (category, (start, end)) tuples.
    """
    spans = []
    for cat, keys in CATEGORY_ORDER:
        for k in keys:
            pat = PATTERNS[k]
            for m in pat.finditer(text):
                matched_text = m.group(0)
                
                # Validate credit cards with Luhn check
                if k == "pii_credit_card":
                    if not luhn_check(matched_text):
                        continue  # Skip invalid credit card numbers
                
                # Validate SSN format
                if k == "pii_ssn":
                    if not validate_ssn_format(matched_text):
                        continue  # Skip invalid SSN formats
                
                spans.append((cat, (m.start(), m.end())))
    
    # Merge overlaps with priority by CATEGORY_ORDER
    spans.sort(key=lambda x: (x[1][0], x[1][1]))
    merged = []
    for cat, rng in spans:
        if not merged:
            merged.append((cat, rng))
            continue
        last_cat, (ls, le) = merged[-1]
        s, e = rng
        if s <= le:
            # Overlap: keep the earlier category by priority order
            continue
        merged.append((cat, (s,e)))
    return merged
