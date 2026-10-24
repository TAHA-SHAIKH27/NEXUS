"""Shared notification center — used by /api/notifications endpoints.

Shared direct store. Data lives in the JSON file
returned by _store_path() (production: backend/data/notifications.json) as
a JSON list. Every operation loads/saves per call so test isolation via
monkeypatched _store_path() works and restarts never lose data.
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path

DATA_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")))
NOTIFICATIONS_FILE = DATA_DIR / "notifications.json"

_lock = threading.Lock()


def _store_path() -> str:
    return str(NOTIFICATIONS_FILE)


def _load() -> list:
    try:
        path = _store_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save(items: list) -> None:
    try:
        path = _store_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
    except Exception:
        pass


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().astimezone().isoformat()


def upsert_notification(center_id, kind, title, body, speak="",
                        priority="normal", ref_type=None, ref_id=None) -> dict:
    """Insert or replace a notification by stable id.

    Returns {"status": "success", "created": bool, "notification": item}.
    """
    with _lock:
        items = _load()
        nid = center_id or str(uuid.uuid4())
        created = not any(n.get("id") == nid for n in items)
        item = {
            "id": nid,
            "kind": kind,
            "title": title,
            "body": body,
            "speak": speak,
            "priority": priority,
            "ref_type": ref_type or "",
            "ref_id": ref_id or "",
            "meta": {},
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "read": False,
            "dismissed": False,
            "ts": time.time(),
        }
        items = [n for n in items if n.get("id") != nid]
        items.append(item)
        _save(items)
    return {"status": "success", "created": created, "notification": dict(item)}


def list_notifications(include_dismissed=False) -> list:
    items = _load()
    return [dict(n) for n in items
            if include_dismissed or not n.get("dismissed")]


def unread_count() -> int:
    return sum(1 for n in _load()
               if not n.get("dismissed") and not n.get("read"))


def _find(items: list, nid):
    for n in items:
        if n.get("id") == nid:
            return n
    return None


def mark_read(nid) -> dict:
    with _lock:
        items = _load()
        n = _find(items, nid)
        if n is None:
            return {"status": "error", "message": "Not found."}
        n["read"] = True
        n["updated_at"] = _now_iso()
        _save(items)
        return {"status": "success"}


def mark_unread(nid) -> dict:
    with _lock:
        items = _load()
        n = _find(items, nid)
        if n is None:
            return {"status": "error", "message": "Not found."}
        n["read"] = False
        n["updated_at"] = _now_iso()
        _save(items)
        return {"status": "success"}


def mark_all_read() -> dict:
    with _lock:
        items = _load()
        marked = 0
        for n in items:
            if not n.get("dismissed") and not n.get("read"):
                n["read"] = True
                n["updated_at"] = _now_iso()
                marked += 1
        _save(items)
        return {"status": "success", "marked": marked}


def dismiss(nid) -> dict:
    with _lock:
        items = _load()
        n = _find(items, nid)
        if n is None:
            return {"status": "error", "message": "Not found."}
        n["dismissed"] = True
        n["updated_at"] = _now_iso()
        _save(items)
        return {"status": "success"}


def delete(nid) -> dict:
    with _lock:
        items = _load()
        if not any(n.get("id") == nid for n in items):
            return {"status": "error", "message": "Not found."}
        _save([n for n in items if n.get("id") != nid])
    return {"status": "success"}


def clear_read_history() -> dict:
    """Delete read/dismissed history; unread items always survive."""
    with _lock:
        items = _load()
        kept = [n for n in items
                if not (n.get("dismissed") or n.get("read"))]
        cleared = len(items) - len(kept)
        _save(kept)
        return {"status": "success", "cleared": cleared}


def purge_expired(max_age_days: float = 30.0) -> dict:
    """Delete old READ items only; unread items are never purged."""
    from datetime import datetime
    with _lock:
        items = _load()
        now = datetime.now().astimezone()
        kept = []
        purged = 0
        for n in items:
            if n.get("read") or n.get("dismissed"):
                stamp = n.get("updated_at") or n.get("created_at") or ""
                try:
                    when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                    age_days = (now - when).total_seconds() / 86400.0
                except Exception:
                    age_days = 0.0
                if age_days > max_age_days:
                    purged += 1
                    continue
            kept.append(n)
        _save(kept)
        return {"status": "success", "purged": purged}
