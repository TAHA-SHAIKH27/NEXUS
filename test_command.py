"""Test script for /api/command endpoint."""
import json
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Test simple command
resp = client.post("/api/command", json={"prompt": "what time is it", "apiKey": ""})
print(f"Command result: {resp.status_code}")
data = resp.json()
if resp.status_code == 200 and "speak" in data:
    print(f"Response speak: {data['speak'][:100]}")
else:
    print(f"Response: {json.dumps(data, indent=2)[:500]}")

# Test clear history
resp2 = client.post("/api/command", json={"prompt": "clear chat", "apiKey": ""})
print(f"\nClear history result: {resp2.status_code}")
data2 = resp2.json()
if resp2.status_code == 200:
    print(f"Response: {json.dumps(data2, indent=2)[:500]}")

# Test system stats
resp3 = client.post("/api/command", json={"prompt": "system stats", "apiKey": ""})
print(f"\nSystem stats result: {resp3.status_code}")
data3 = resp3.json()
if resp3.status_code == 200 and "speak" in data3:
    print(f"Response speak: {data3['speak'][:100]}")
else:
    print(f"Response: {json.dumps(data3, indent=2)[:500]}")