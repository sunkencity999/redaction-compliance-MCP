from pydantic import BaseModel
from typing import Optional
import os

class Settings(BaseModel):
    app_name: str = "Redaction & Compliance MCP"
    port: int = int(os.getenv("PORT", "8019"))
    audit_path: str = os.getenv("AUDIT_PATH", "./audit/audit.jsonl")
    token_backend: str = os.getenv("TOKEN_BACKEND", "memory")  # memory|redis
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    policy_path: str = os.getenv("POLICY_PATH", "mcp_redaction/sample_policies/default.yaml")
    token_salt_env: str = os.getenv("TOKEN_SALT_ENV", "MCP_TOKEN_SALT")  # env var name holding HMAC salt
    max_payload_kb: int = int(os.getenv("MAX_PAYLOAD_KB", "256"))
    detokenize_trusted_callers: str = os.getenv("DETOK_TRUSTED", "incident-mgr,runbook-executor")

settings = Settings()
