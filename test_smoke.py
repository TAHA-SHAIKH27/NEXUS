"""Smoke test for NEXUS."""
import json
from fastapi.testclient import TestClient
import main

client = TestClient(main.app, raise_server_exceptions=False)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), str(detail)[:160]))
    print(f"{'PASS' if cond else 'FAIL'}: {name} {str(detail)[:120]}")


# 1. Core routes present
paths = sorted({getattr(r, "path", "") for r in main.app.routes})
check("core routes registered", "/api/command" in paths and "/api/status" in paths, paths[:8])

# 2. Status / config
r = client.get("/api/status")
check("GET /api/status", r.status_code == 200, r.text[:100])
r = client.get("/api/config")
check("GET /api/config", r.status_code == 200, r.text[:100])

# 3. Command: clear chat
r = client.post("/api/command", json={"prompt": "clear chat", "apiKey": ""})
check("POST /api/command clear chat", r.status_code == 200 and "cleared" in r.text.lower(), r.text[:100])

# 4. Command: time
r = client.post("/api/command", json={"prompt": "what time is it", "apiKey": ""})
check("POST /api/command time", r.status_code == 200 and "speak" in r.json(), r.text[:120])

# 5. Command: stats
r = client.post("/api/command", json={"prompt": "system stats", "apiKey": ""})
check("POST /api/command stats", r.status_code == 200 and "speak" in r.json(), r.text[:120])

# 6. Command: calc
r = client.post("/api/command", json={"prompt": "calculate 12 * 8", "apiKey": ""})
check("POST /api/command calc", r.status_code == 200, r.text[:160])

# 7. Command: memory save + recall
r = client.post("/api/command", json={"prompt": "my name is Smoke Tester", "apiKey": ""})
check("POST /api/command remember name", r.status_code == 200, r.text[:160])
r = client.post("/api/command", json={"prompt": "what is my name?", "apiKey": ""})
body = r.text
check("POST /api/command recall name", r.status_code == 200 and "Smoke Tester" in body, body[:160])

# 8. Command: unknown -> explicit scope notice
r = client.post("/api/command", json={"prompt": "research the history of python and make a ppt", "apiKey": ""})
body = r.text.lower()
check("POST /api/command scope notice", r.status_code == 200 and "cannot handle that directly" in body, r.text[:160])

# 9. Response shape
r = client.post("/api/command", json={"prompt": "battery", "apiKey": ""})
d = r.json() if r.status_code == 200 else {}
shape_ok = all(k in d for k in ("speak", "speak_lang", "logs", "file_data", "refresh_files",
                                "image_data", "timer_data", "clarification_needed", "narration_steps"))
check("command response shape", r.status_code == 200 and shape_ok, list(d.keys()))

# 10. Streaming endpoints (deterministic)
r = client.post("/api/chat/stream", json={"prompt": "hello", "apiKey": ""})
check("POST /api/chat/stream", r.status_code == 200 and len(r.text) > 0, r.text[:120])
r = client.post("/api/command/stream", json={"prompt": "hello", "apiKey": ""})
check("POST /api/command/stream", r.status_code == 200 and "speak" in r.text, r.text[:160])
r = client.post("/api/document/stream", json={"document_text": "Hello world " * 50, "filename": "t.txt", "prompt": "summarize"})
check("POST /api/document/stream", r.status_code == 200 and "extracted text" in r.text.lower(), r.text[:120])

# 11. Voice
r = client.post("/api/voice/command", json={"prompt": "what time is it"})
check("POST /api/voice/command", r.status_code == 200, r.text[:160])
r = client.get("/api/voice/tts/state")
check("GET /api/voice/tts/state", r.status_code == 200, r.text[:120])
r = client.get("/api/voice/mute")
check("GET /api/voice/mute", r.status_code == 200, r.text[:120])

# 12. Notifications / reminders / scheduled
r = client.get("/api/notifications")
check("GET /api/notifications", r.status_code == 200, r.text[:120])
r = client.get("/api/notifications/center")
check("GET /api/notifications/center", r.status_code == 200, r.text[:120])
r = client.get("/api/reminders")
check("GET /api/reminders", r.status_code == 200, r.text[:120])
r = client.get("/api/scheduled")
check("GET /api/scheduled", r.status_code == 200, r.text[:120])

# 13. Notes / todos
r = client.post("/api/notes", json={"text": "smoke note"})
nid = r.json().get("note", {}).get("id") if r.status_code == 200 else None
check("POST /api/notes", r.status_code == 200 and nid, r.text[:120])
if nid:
    client.request("DELETE", f"/api/notes/{nid}")
r = client.post("/api/todos", json={"text": "smoke todo"})
tid = r.json().get("todo", {}).get("id") if r.status_code == 200 else None
check("POST /api/todos", r.status_code == 200 and tid, r.text[:120])
if tid:
    client.request("DELETE", f"/api/todos/{tid}")

# 14. Gallery / files
r = client.get("/api/gallery")
check("GET /api/gallery", r.status_code == 200, r.text[:100])
r = client.get("/api/files")
check("GET /api/files", r.status_code in (200, 400), r.text[:100])

# 15. Scheduler command (reminder)
r = client.post("/api/command", json={"prompt": "remind me in 10 minutes to smoke test", "apiKey": ""})
check("POST /api/command reminder", r.status_code == 200, r.text[:160])

failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
if failed:
    print("FAILED:", failed)
    raise SystemExit(1)
