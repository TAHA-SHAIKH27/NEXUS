"""Shared identity memory — name / home city / general facts.

Direct store backed by backend/data/persistent_memory.json
(a JSON list of {id, key, value, text, ...}). No LLM, no network, stdlib only.
"""

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

DATA_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
MEMORY_FILE = DATA_DIR / "persistent_memory.json"

_lock = threading.Lock()
_records: list = []


def _load():
    global _records
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _records = data if isinstance(data, list) else []
        else:
            _records = []
            _save()
    except Exception:
        _records = []


def _save():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = str(MEMORY_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_records, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, str(MEMORY_FILE))
    except Exception:
        pass


_load()


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9\u0900-\u097f]+", (text or "").lower()))


def _get_latest(key: str) -> str:
    kl = (key or "").casefold()
    for r in reversed(_records):
        if str(r.get("key", "")).casefold() == kl:
            return str(r.get("value", "") or "")
    return ""


def get_user_name() -> str:
    return _get_latest("name")


def get_home_city() -> str:
    for k in ("home city", "default city", "weather city", "city", "location"):
        v = _get_latest(k)
        if v:
            return v
    return ""


def remember(text: str, category: str = "general", source: str = "nexus-command") -> dict:
    """Store a fact. Returns {"status": "ok"|"skipped", ...}."""
    global _records
    text = (text or "").strip()
    if not text:
        return {"status": "skipped", "message": "Empty text."}
    # Guard: never store questions as facts.
    if text.rstrip().endswith("?"):
        return {"status": "skipped", "message": "Question, not a fact."}
    with _lock:
        rec = {
            "id": str(uuid.uuid4()),
            "text": text,
            "source_text": text,
            "key": "fact",
            "value": text,
            "category": category,
            "source": source,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        _records.append(rec)
        _save()
    return {"status": "ok", "id": rec["id"]}


def store_fact(key: str, value: str, source: str = "nexus-implicit") -> dict:
    """Store/replace a keyed fact such as name or home city."""
    global _records
    key = (key or "").strip() or "fact"
    value = (value or "").strip()
    if not value:
        return {"status": "skipped"}
    with _lock:
        _records = [r for r in _records
                    if str(r.get("key", "")).casefold() != key.casefold()]
        rec = {
            "id": str(uuid.uuid4()),
            "text": f"{key}: {value}",
            "source_text": value,
            "key": key,
            "value": value,
            "category": "identity" if key in ("name", "home city", "default city",
                                              "weather city", "city", "location") else "general",
            "source": source,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        _records.append(rec)
        _save()
    return {"status": "ok", "id": rec["id"]}


def recall(prompt: str, limit: int = 5) -> dict:
    """Lexical recall over stored facts. Returns {"memories": [...]}."""
    pt = _tokens(prompt)
    scored = []
    with _lock:
        for r in _records:
            rt = _tokens(str(r.get("text", "")) + " " + str(r.get("key", "")))
            overlap = len(pt & rt)
            if overlap:
                scored.append((overlap, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return {"memories": [dict(r) for _, r in scored[:max(1, limit)]]}


def forget(key_or_text: str) -> dict:
    global _records
    with _lock:
        before = len(_records)
        kl = (key_or_text or "").casefold()
        _records = [r for r in _records
                    if kl not in str(r.get("text", "")).casefold()
                    and kl != str(r.get("key", "")).casefold()]
        _save()
        return {"status": "success", "removed": before - len(_records)}


def clear() -> dict:
    global _records
    with _lock:
        _records = []
        _save()
    return {"status": "success"}


def memory_context(prompt: str, limit: int = 8) -> str:
    """Compact memory context lines for prompt injection (offline-safe)."""
    try:
        mems = recall(prompt, limit=limit).get("memories", [])
    except Exception:
        return ""
    lines = []
    for m in mems[:limit]:
        t = str(m.get("text", "") or "").strip()
        if t:
            lines.append(f"- {t[:200]}")
    return "\n".join(lines)
