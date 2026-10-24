"""Shared runtime — conversation context + reminders + implicit memory capture.

Direct helpers used by /api/command and the notification
endpoints. No LLM, no planning, no tool orchestration. Reminders are a
JSON list in the file returned by _reminder_path() (production:
backend/data/reminders.json). Every store operation loads/saves per call
so test isolation via monkeypatched _reminder_path() works.
"""

import json
import os
import re
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
REMINDERS_FILE = DATA_DIR / "reminders.json"

_VALID_PRIORITIES = {"low", "normal", "important", "urgent"}


def _reminder_path() -> str:
    return str(REMINDERS_FILE)


def _write_json(path: str, data) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _read_list() -> list:
    try:
        path = _reminder_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _normalize(rec: dict) -> dict:
    """Bring legacy shapes (completed flag, missing status) up to date."""
    r = dict(rec)
    if not r.get("status"):
        if r.get("completed"):
            r["status"] = "triggered"
            r["read"] = True
        else:
            r["status"] = "scheduled"
    if r.get("completed") and r.get("status") not in ("triggered", "dismissed",
                                                      "done", "snoozed"):
        r["status"] = "triggered"
        r["read"] = True
    r.setdefault("read", False)
    r.setdefault("dismissed", False)
    if r.get("priority") not in _VALID_PRIORITIES:
        r["priority"] = "normal"
    try:
        r["trigger_count"] = int(r.get("trigger_count") or 0)
    except Exception:
        r["trigger_count"] = 0
    return r


class ConversationContext:
    """Minimal in-memory conversation log (session history lives in agent.py)."""

    def __init__(self):
        self._items: list = []
        self._lock = threading.Lock()

    def add(self, role: str, text: str, meta: dict | None = None):
        with self._lock:
            self._items.append({"role": role, "text": text, "meta": meta or {},
                                "ts": time.time()})
            self._items = self._items[-50:]

    def clear(self):
        with self._lock:
            self._items = []

    def history(self):
        with self._lock:
            return [dict(i) for i in self._items]


class ReminderStore:
    """File-backed reminder store (list-based JSON, per-op load/save)."""

    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._path = path

    def _load(self) -> list:
        if self._path:
            try:
                if os.path.exists(self._path):
                    with open(self._path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return [_normalize(r) for r in data] if isinstance(data, list) else []
            except Exception:
                pass
            return []
        return [_normalize(r) for r in _read_list()]

    def _save(self, items: list) -> None:
        if self._path:
            _write_json(self._path, items)
        else:
            _write_json(_reminder_path(), items)

    def _find(self, items: list, rid):
        for r in items:
            if str(r.get("id")) == str(rid):
                return r
        return None

    def history(self) -> list:
        return self._load()

    def list(self) -> list:
        """Newest-first list (scheduler contract)."""
        return sorted(self._load(),
                      key=lambda r: str(r.get("created_at") or ""),
                      reverse=True)

    def get(self, rid):
        items = self._load()
        found = self._find(items, rid)
        return dict(found) if found is not None else None

    def add(self, text: str, due_at: str = "", priority: str = "normal",
            repeat: str = "") -> dict:
        import uuid as _uuid
        from datetime import datetime as _dt
        text = (text or "").strip()
        if not text:
            return {"status": "error", "message": "Empty reminder text."}
        if priority not in _VALID_PRIORITIES:
            priority = "normal"
        with self._lock:
            now = _dt.now().astimezone().isoformat()
            rec = {
                "id": str(_uuid.uuid4()),
                "text": text,
                "due_at": due_at or "",
                "repeat": repeat or None,
                "completed": False,
                "created_at": now,
                "updated_at": now,
                "status": "scheduled",
                "notified": False,
                "notified_at": None,
                "read": False,
                "dismissed": False,
                "snoozed_until": None,
                "priority": priority,
                "trigger_count": 0,
            }
            items = self._load()
            items.append(rec)
            self._save(items)
            return {"status": "success",
                    "message": f"Reminder set, sir: '{text[:120]}'.",
                    "reminder": dict(rec)}

    def due(self) -> list:
        from datetime import datetime as _dt
        now = _dt.now().astimezone()
        out = []
        for r in self._load():
            if r.get("status") not in ("scheduled", "snoozed"):
                continue
            if r.get("dismissed") or r.get("completed"):
                continue
            when_s = r.get("snoozed_until") or r.get("due_at") or ""
            try:
                when = _dt.fromisoformat(str(when_s).replace("Z", "+00:00"))
            except Exception:
                continue
            if when <= now:
                out.append(r)
        return out

    def mark_triggered(self, rid) -> dict:
        from datetime import datetime as _dt
        with self._lock:
            items = self._load()
            r = self._find(items, rid)
            if r is None:
                return {"status": "error", "message": "Not found."}
            r["status"] = "triggered"
            r["notified"] = True
            r["notified_at"] = _dt.now().astimezone().isoformat()
            r["read"] = False
            r["trigger_count"] = int(r.get("trigger_count") or 0) + 1
            r["updated_at"] = _dt.now().astimezone().isoformat()
            self._save(items)
            return {"status": "success", "reminder": dict(r)}

    def active_for_bar(self) -> list:
        return [r for r in self._load()
                if r.get("status") == "triggered"
                and not r.get("read") and not r.get("dismissed")]

    def unread_count(self) -> int:
        return len(self.active_for_bar())

    def mark_read(self, rid) -> dict:
        with self._lock:
            items = self._load()
            r = self._find(items, rid)
            if r is None:
                return {"status": "error", "message": "Not found."}
            r["read"] = True
            self._save(items)
            return {"status": "success"}

    def mark_unread(self, rid) -> dict:
        with self._lock:
            items = self._load()
            r = self._find(items, rid)
            if r is None:
                return {"status": "error", "message": "Not found."}
            r["read"] = False
            self._save(items)
            return {"status": "success"}

    def dismiss(self, rid) -> dict:
        with self._lock:
            items = self._load()
            r = self._find(items, rid)
            if r is None:
                return {"status": "error", "message": "Not found."}
            r["dismissed"] = True
            r["status"] = "dismissed"
            self._save(items)
            return {"status": "success"}

    def remove(self, rid) -> dict:
        with self._lock:
            items = [r for r in self._load() if str(r.get("id")) != str(rid)]
            self._save(items)
            return {"status": "success"}

    def set_priority(self, rid, priority: str) -> dict:
        if priority not in _VALID_PRIORITIES:
            return {"status": "error",
                    "message": f"Unknown priority '{priority}', sir."}
        with self._lock:
            items = self._load()
            r = self._find(items, rid)
            if r is None:
                return {"status": "error", "message": "Not found."}
            r["priority"] = priority
            self._save(items)
            return {"status": "success"}

    def snooze(self, rid, minutes: float = 10.0,
               when_iso: str | None = None) -> dict:
        from datetime import datetime as _dt, timedelta as _td
        with self._lock:
            items = self._load()
            r = self._find(items, rid)
            if r is None:
                return {"status": "error", "message": "Not found."}
            if when_iso:
                try:
                    wake = _dt.fromisoformat(str(when_iso).replace("Z", "+00:00"))
                except Exception:
                    return {"status": "error",
                            "message": "Invalid time format."}
            else:
                try:
                    minutes_f = float(minutes)
                except Exception:
                    return {"status": "error",
                            "message": "Invalid snooze duration."}
                if minutes_f <= 0:
                    return {"status": "error",
                            "message": "Snooze duration must be positive."}
                wake = _dt.now().astimezone() + _td(minutes=minutes_f)
            wake_iso = wake.isoformat()
            r["snoozed_until"] = wake_iso
            r["status"] = "snoozed"
            self._save(items)
            return {"status": "success", "wake_at": wake_iso}


class _Runtime:
    def __init__(self):
        self.conversation = ConversationContext()
        self.reminders = ReminderStore()


runtime = _Runtime()


_NAME_RES = [
    re.compile(r"\bmy name is\s+([A-Za-z][A-Za-z .'\-]{1,40})", re.I),
    re.compile(r"\bcall me\s+([A-Za-z][A-Za-z .'\-]{1,40})", re.I),
]

_CITY_RES = [
    re.compile(r"\bi live in\s+([A-Za-z][A-Za-z .'\-]{1,40})", re.I),
    re.compile(r"\bi am from\s+([A-Za-z][A-Za-z .'\-]{1,40})", re.I),
    re.compile(r"\bmy (?:home\s+)?city is\s+([A-Za-z][A-Za-z .'\-]{1,40})", re.I),
]


def _clean_name(s: str) -> str:
    s = (s or "").strip().strip(" .,'\"")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\b(and|but|for|because|so)\b.*$", "", s, flags=re.I).strip()
    return s[:60]


def capture_implicit_memories(prompt: str) -> list:
    """Extract name/city facts from free text and persist them.

    Returns a list of {"key": ...} for newly stored facts (stdlib only).
    Never raises.
    """
    saved = []
    try:
        from backend.agent import phase1_memory as _pm
    except Exception:
        return saved
    try:
        text = (prompt or "").strip()
        if not text or text.rstrip().endswith("?"):
            return saved
        for rx in _NAME_RES:
            m = rx.search(text)
            if m:
                name = _clean_name(m.group(1))
                if len(name) >= 2:
                    try:
                        _pm.store_fact("name", name)
                        saved.append({"key": "name"})
                    except Exception:
                        pass
                break
        for rx in _CITY_RES:
            m = rx.search(text)
            if m:
                city = _clean_name(m.group(1))
                if len(city) >= 2:
                    try:
                        _pm.store_fact("home city", city)
                        saved.append({"key": "home city"})
                    except Exception:
                        pass
                break
    except Exception:
        pass
    return saved


def answer_from_memory(prompt: str) -> str | None:
    """Answer name/city questions straight from stored facts (no LLM)."""
    try:
        from backend.agent import phase1_memory as _pm
    except Exception:
        return None
    try:
        pl = (prompt or "").lower()
        if not pl:
            return None
        is_q = ("?" in (prompt or "")) or bool(re.search(
            r"\b(what|who|where|which|my|your)\b", pl))
        if not is_q:
            return None
        if re.search(r"\bmy name\b|what.*name|who am i\b", pl):
            name = _pm.get_user_name()
            if name:
                return f"Your name is {name}, sir."
            return None
        if re.search(r"\bwhere.*live\b|my city\b|home city\b|what city\b|which city\b", pl):
            city = _pm.get_home_city()
            if city:
                return f"Your home city is {city}, sir."
            return None
    except Exception:
        pass
    return None
