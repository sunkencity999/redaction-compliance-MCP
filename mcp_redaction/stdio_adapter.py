# Minimal JSON-RPC over stdio adapter (skeleton)
# Integrate this with your agent runtime that expects MCP-style stdio tools.
# For brevity, this stub simply calls the REST endpoints locally.

import sys, json, requests, os

BASE = os.environ.get("MCP_REDACTION_BASE", "http://127.0.0.1:8019")

def handle(req):
    method = req.get("method")
    params = req.get("params", {})
    if method == "classify":
        r = requests.post(f"{BASE}/classify", json=params, timeout=10)
        return r.json()
    if method == "redact":
        r = requests.post(f"{BASE}/redact", json=params, timeout=10)
        return r.json()
    if method == "detokenize":
        r = requests.post(f"{BASE}/detokenize", json=params, timeout=10)
        return r.json()
    if method == "route":
        r = requests.post(f"{BASE}/route", json=params, timeout=10)
        return r.json()
    return {"ok": False, "error": "unknown_method"}

def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
            resp = handle(req)
        except Exception as e:
            resp = {"ok": False, "error": str(e)}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
