from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Context(BaseModel):
    purpose: Optional[str] = None
    env: Optional[str] = None
    region: Optional[str] = None
    conversation_id: Optional[str] = None
    caller: Optional[str] = None

class Category(BaseModel):
    type: str
    confidence: float

class ClassifyRequest(BaseModel):
    payload: Any
    context: Optional[Context] = None

class ClassifyResponse(BaseModel):
    ok: bool = True
    categories: List[Category] = []
    suggested_action: Optional[str] = None
    errors: Optional[List[str]] = None

class RedactRequest(BaseModel):
    payload: Any
    policy: str = "default"
    scope: Dict[str, Any] = {}
    context: Optional[Context] = None

class RedactionEvent(BaseModel):
    type: str
    placeholder: str
    range: Optional[List[int]] = None
    note: Optional[str] = None

class RedactResponse(BaseModel):
    ok: bool = True
    sanitized_payload: Any
    token_map_handle: Optional[str] = None
    redactions: List[RedactionEvent] = []
    errors: Optional[List[str]] = None

class DetokenizeRequest(BaseModel):
    payload: Any
    token_map_handle: str
    allow_categories: List[str] = []
    context: Optional[Context] = None

class DetokenizeResponse(BaseModel):
    ok: bool = True
    restored_payload: Any
    errors: Optional[List[str]] = None

class RouteRequest(BaseModel):
    model_request: Dict[str, Any]
    policy: str = "default"
    context: Optional[Context] = None

class ExecutionStep(BaseModel):
    tool: str
    args: Dict[str, Any] = {}

class ExecutionPlan(BaseModel):
    target: str
    pre: List[ExecutionStep] = []
    post: List[ExecutionStep] = []

class RouteResponse(BaseModel):
    ok: bool = True
    plan: Optional[ExecutionPlan] = None
    decision: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None

class AuditQueryRequest(BaseModel):
    q: Optional[str] = None
    limit: int = 100

class AuditRecord(BaseModel):
    ts: str
    caller: Optional[str] = None
    context: Optional[Context] = None
    action: str
    categories: List[Category] = []
    decision: Optional[Dict[str, Any]] = None
    redaction_counts: Dict[str, int] = {}
    target: Optional[str] = None
    policy_version: Optional[str] = None
