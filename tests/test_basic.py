import os, json
from fastapi.testclient import TestClient
from mcp_redaction.server import app

os.environ.setdefault("MCP_TOKEN_SALT", "test-salt")

client = TestClient(app)

def test_classify_and_redact_and_detokenize():
    payload = "Contact me at jane.doe@joby.aero, db at postgres://svc:pw@db.az.corp:5432/app"
    ctx = {"purpose":"summarize","env":"dev","conversation_id":"INC-1","caller":"incident-mgr"}
    r = client.post("/classify", json={"payload": payload, "context": ctx})
    assert r.status_code == 200
    cats = r.json()["categories"]
    assert any(c["type"] in ("pii","ops_sensitive","secret") for c in cats)

    r = client.post("/redact", json={"payload": payload, "context": ctx})
    assert r.status_code == 200
    s = r.json()["sanitized_payload"]
    handle = r.json()["token_map_handle"]
    assert "«token:" in s

    r = client.post("/detokenize", json={
        "payload": s,
        "token_map_handle": handle,
        "allow_categories": ["pii","ops_sensitive"],
        "context": ctx
    })
    assert r.status_code == 200
    restored = r.json()["restored_payload"]
    assert "jane.doe@joby.aero" in restored
