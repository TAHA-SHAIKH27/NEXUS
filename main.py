from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import os
import asyncio
import json
import base64
import tempfile
import struct
import numpy as np
import wave
import io
import uuid
import threading
import time
import sys
import re
import faulthandler

# Dump a Python traceback to stderr on a segfault/access violation instead
# of dying silently (exit 3221225477). The watchdog pipes stderr into
# watchdog_crash.log, so the next native crash arrives with evidence.
faulthandler.enable()

# Import local helper modules
from system_ops import (
    get_system_stats, 
    open_application, 
    close_application, 
    list_files, 
    read_file, 
    write_file, 
    delete_file, 
    take_screenshot,
    create_folder,
    create_word_document,
    check_pc_health,
    adjust_volume,
    media_control,
    search_web,
    launch_any_app,
    save_generated_image,
    # New capabilities
    shutdown_pc,
    restart_pc,
    cancel_shutdown,
    sleep_pc,
    lock_screen,
    get_clipboard,
    set_clipboard,
    get_battery_info,
    get_network_info,
    get_weather,
    get_datetime_info,
    open_url,
    open_folder,
    empty_recycle_bin,
    clean_temp_files,
)
import document_intel
import google_oauth
import phone_control
import whatsapp_ops
import code_core
from backend.startup_engine import get_startup_engine

from backend.agent.voice import get_voice_system, get_command_processor, TTSState

app = FastAPI(title="N.E.X.U.S. Core", description="API Service for Windows OS Automation")

# Configure CORS so our React frontend can make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _start_ws_scrcpy():
    """Launch ws-scrcpy on port 8080 for the embedded phone mirror.
    Runs here (not just in the `python main.py` __main__ block) so it also
    starts when uvicorn is invoked directly, e.g. via start_nexus.py's
    `python -m uvicorn main:app` subprocess call."""
    import subprocess
    ws_scrcpy_dir = os.path.join(os.path.dirname(__file__), "ws-scrcpy")
    if not os.path.exists(ws_scrcpy_dir):
        print("[ws-scrcpy] Directory not found, skipping (phone mirror embed will be unavailable).")
        return
    env = os.environ.copy()
    env["PORT"] = "8080"
    env["ADB"] = os.getenv("NEXUS_ADB_PATH", "") or os.getenv("JARVIS_ADB_PATH", "") or "adb"
    try:
        subprocess.Popen(
            ["npm", "start"],
            cwd=ws_scrcpy_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        print("[ws-scrcpy] Started on port 8080")
    except Exception as e:
        print(f"[ws-scrcpy] Failed to start: {e}")


# ── Startup Code Audit (automatic, read-only) ────────────────────────────────────
# After boot, a background worker performs a zero-mutation source scan (AST +
# py_compile - no Nemotron) and publishes the report so the UI can notify the
# user about problem files (with line ranges) and ask whether to apply fixes.

_STARTUP_AUDIT_LOCK = threading.Lock()
_startup_audit_report = None
_STARTUP_AUDIT_WAIT_SECONDS = 15


def _audit_report_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "data", "last_audit.json")


def _run_startup_audit_worker():
    """Run real codebase audit promptly upon boot and persist the report."""
    global _startup_audit_report
    time.sleep(1.0)
    with _STARTUP_AUDIT_LOCK:
        try:
            engine = get_startup_engine()
            audit_res = engine.run_real_audit()
            # Also fetch full code_core report for backwards compatibility
            report = code_core.audit_codebase()
            _startup_audit_report = report
            print(
                f"[startup-audit] Codebase scan finished: health {report['health_score']}%, "
                f"{report['total_files_checked']} files checked, {report['issues_count']} issue(s) "
                f"reported to the UI.",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"[startup-audit] Startup scan failed: {e}", file=sys.stderr)


@app.on_event("startup")
def _start_startup_code_audit():
    """Launch the automatic read-only source audit shortly after boot."""
    try:
        threading.Thread(target=_run_startup_audit_worker, daemon=True).start()
        print("[startup-audit] Startup code check armed - running in background.", file=sys.stderr)
    except Exception as e:
        print(f"[startup-audit] Could not start audit thread: {e}", file=sys.stderr)


def _is_proactor_reset_noise(context: dict) -> bool:
    """True only for the known Windows proactor wart: an abrupt browser /
    health-poll disconnect surfacing as ConnectionResetError inside
    _call_connection_lost. Harmless — the server keeps serving."""
    try:
        exc = context.get("exception")
        if not isinstance(exc, ConnectionResetError):
            return False
        blob = f"{context.get('callback', '')} {context.get('message', '')}"
        return "_call_connection_lost" in blob or "connection_lost" in blob
    except Exception:
        return False


@app.on_event("startup")
def _quiet_proactor_disconnects():
    """Swallow exactly the proactor-reset noise; every other asyncio error
    still goes to the default handler untouched."""
    try:
        import asyncio
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        prev = loop.get_exception_handler()
    except Exception:
        prev = None

    def _handler(loop, context):
        try:
            if _is_proactor_reset_noise(context):
                return
        except Exception:
            pass
        try:
            if prev is not None:
                prev(loop, context)
            else:
                loop.default_exception_handler(context)
        except Exception:
            pass

    try:
        loop.set_exception_handler(_handler)
    except Exception:
        pass

# Configuration persistence
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.json"))

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("gemini_project_id", "")
                data.setdefault("groq_api_key", "")
                data.setdefault("nvidia_api_key", "")
                data.setdefault("nvidia_model", "z-ai/glm-5.3-flash")
                data.setdefault("nvidia_fpo_model", "nvidia/nemotron-3.5-bolt-e4b")
                data.setdefault("nvidia_fpo_timeout_seconds", 120)
                data.setdefault("nvidia_fpo_max_retries", 2)
                data.setdefault("meterless_base_url", "http://127.0.0.1:8088/v1")
                data.setdefault("meterless_runtime_token", "")
                data.setdefault("meterless_app_id", "nexus")
                data.setdefault("meterless_model", "meterless/auto")
                # Zetaris config (all optional; org_id is required for API calls)
                data.setdefault("zetaris_rest_url", "http://localhost:8888/api/v1.0")
                data.setdefault("zetaris_base_url", "http://localhost:3000")
                data.setdefault("zetaris_org_id", "")
                data.setdefault("zetaris_api_key", "")
                data.setdefault("zetaris_username", "")
                data.setdefault("zetaris_password", "")
                data.setdefault("zetaris_default_limit", 100)
                data.setdefault("zetaris_max_limit", 100)
                data.setdefault("zetaris_timeout_seconds", 30)
                return data
        except Exception:
            pass
    return {
        "gemini_api_key": "",
        "huggingface_api_key": "",
        "gemini_project_id": "",
        "groq_api_key": "",
        "nvidia_api_key": "",
        "nvidia_model": "z-ai/glm-5.3-flash",
        "nvidia_fpo_model": "nvidia/nemotron-3.5-bolt-e4b",
        "nvidia_fpo_timeout_seconds": 120,
        "nvidia_fpo_max_retries": 2,
        "meterless_base_url": "http://127.0.0.1:8088/v1",
        "meterless_runtime_token": "",
        "meterless_app_id": "nexus",
        "meterless_model": "meterless/auto",
        "zetaris_rest_url": "http://localhost:8888/api/v1.0",
        "zetaris_base_url": "http://localhost:3000",
        "zetaris_org_id": "",
        "zetaris_api_key": "",
        "zetaris_username": "",
        "zetaris_password": "",
        "zetaris_default_limit": 100,
        "zetaris_max_limit": 100,
        "zetaris_timeout_seconds": 30,
    }

def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ── Notes & Todos persistence ──────────────────────────────────────────────
NOTES_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "notes.json"))
TODOS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "todos.json"))

def _load_json_list(path: str) -> list:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_json_list(path: str, data: list):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# Input data models
class CommandRequest(BaseModel):
    prompt: str
    apiKey: Optional[str] = None

class FileWriteRequest(BaseModel):
    filename: str
    content: str

class ChatStreamRequest(BaseModel):
    prompt: str
    apiKey: Optional[str] = None

class ImageAnalysisRequest(BaseModel):
    image_base64: str
    mime_type: str
    prompt: Optional[str] = ""
    apiKey: Optional[str] = None

class DocumentAnalysisRequest(BaseModel):
    document_text: str
    filename: str
    prompt: Optional[str] = ""
    apiKey: Optional[str] = None

class ConfigModel(BaseModel):
    gemini_api_key: str
    huggingface_api_key: str
    gemini_project_id: Optional[str] = ""
    groq_api_key: str = ""
    nvidia_api_key: Optional[str] = ""
    nvidia_model: Optional[str] = "z-ai/glm-5.3-flash"
    nvidia_fpo_model: Optional[str] = "nvidia/nemotron-3.5-bolt-e4b"
    nvidia_fpo_timeout_seconds: Optional[int] = 120
    nvidia_fpo_max_retries: Optional[int] = 2
    meterless_base_url: Optional[str] = "http://127.0.0.1:8088/v1"
    meterless_runtime_token: Optional[str] = ""
    meterless_app_id: Optional[str] = "nexus"
    meterless_model: Optional[str] = "meterless/auto"
    # Zetaris config (all optional; org_id is required for API calls)
    zetaris_rest_url: Optional[str] = "http://localhost:8888/api/v1.0"
    zetaris_base_url: Optional[str] = "http://localhost:3000"
    zetaris_org_id: Optional[str] = ""
    zetaris_api_key: Optional[str] = ""
    zetaris_username: Optional[str] = ""
    zetaris_password: Optional[str] = ""
    zetaris_default_limit: Optional[int] = 100
    zetaris_max_limit: Optional[int] = 100
    zetaris_timeout_seconds: Optional[int] = 30

# ── Code Core request models ────────────────────────────────────────────────
class CodePreviewFixRequest(BaseModel):
    file: str
    issue: Optional[str] = ""

class CodeApplyFixRequest(BaseModel):
    file: str
    proposed_content: str

class CodeProcessFileRequest(BaseModel):
    filename: str
    content: str
    instructions: Optional[str] = ""

# ── Phone control request models ────────────────────────────────────────────
class PhoneTapRequest(BaseModel):
    x: int
    y: int

class PhoneSwipeRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: Optional[int] = 300

class PhoneTextRequest(BaseModel):
    text: str

class PhoneKeyRequest(BaseModel):
    key: str

class PhoneLaunchAppRequest(BaseModel):
    package: str

class PhoneUnlockRequest(BaseModel):
    pin: Optional[str] = None

class PhoneTestPinTapRequest(BaseModel):
    digit: str

@app.get("/api/config")
def get_config():
    cfg = load_config()
    # Mask secrets in response
    masked = dict(cfg)
    for key in ("gemini_api_key", "huggingface_api_key", "groq_api_key", "nvidia_api_key",
                "meterless_runtime_token", "zetaris_api_key", "zetaris_password"):
        if masked.get(key):
            masked[key] = "********"
    return masked


@app.post("/api/config")
def post_config(req: ConfigModel):
    # Merge into existing config so existing keys survive this write
    cfg = load_config()
    cfg.update({
        "gemini_api_key": req.gemini_api_key,
        "huggingface_api_key": req.huggingface_api_key,
        "gemini_project_id": req.gemini_project_id or "",
        "groq_api_key": req.groq_api_key or "",
        "nvidia_api_key": req.nvidia_api_key or "",
        "nvidia_model": req.nvidia_model or "z-ai/glm-5.3-flash",
        "nvidia_fpo_model": req.nvidia_fpo_model or "nvidia/nemotron-3.5-bolt-e4b",
        "nvidia_fpo_timeout_seconds": req.nvidia_fpo_timeout_seconds or 120,
        "nvidia_fpo_max_retries": req.nvidia_fpo_max_retries or 2,
        "meterless_base_url": req.meterless_base_url or "http://127.0.0.1:8088/v1",
        "meterless_runtime_token": req.meterless_runtime_token or "",
        "meterless_app_id": req.meterless_app_id or "nexus",
        "meterless_model": req.meterless_model or "meterless/auto",
        "zetaris_rest_url": req.zetaris_rest_url or "http://localhost:8888/api/v1.0",
        "zetaris_base_url": req.zetaris_base_url or "http://localhost:3000",
        "zetaris_org_id": req.zetaris_org_id or "",
        "zetaris_api_key": req.zetaris_api_key or "",
        "zetaris_username": req.zetaris_username or "",
        "zetaris_password": req.zetaris_password or "",
        "zetaris_default_limit": req.zetaris_default_limit or 100,
        "zetaris_max_limit": req.zetaris_max_limit or 100,
        "zetaris_timeout_seconds": req.zetaris_timeout_seconds or 30,
    })
    save_config(cfg)
    return {"status": "success", "message": "Configuration saved."}


# ── Meterless & NVIDIA Provider Status Endpoints ───────────────────────────────

class ProviderStatusRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None


@app.post("/api/meterless/status")
def meterless_status(req: ProviderStatusRequest):
    """Check Meterless Runtime (Nightshift) connectivity and model availability."""
    try:
        from backend.tools.meterless import get_status
        return get_status(req.config or load_config())
    except Exception as e:
        return {"provider": "meterless", "status": "error", "message": str(e), "live": False}


@app.post("/api/nvidia/status")
def nvidia_status(req: ProviderStatusRequest):
    """Check NVIDIA NIM Nemotron (FPO adapter) connectivity and model catalog."""
    try:
        from backend.tools.nvidia_nemotron import get_status
        return get_status(req.config or load_config())
    except Exception as e:
        return {"provider": "nvidia_nim", "status": "error", "message": str(e), "live": False}


# ── Code Core Endpoints ─────────────────────────────────────────────────────

@app.post("/api/code/audit")
def code_audit():
    return code_core.audit_codebase()

@app.get("/api/code/audit/latest")
def code_audit_latest():
    """Return the most recent startup self-audit report (read-only, no mutations).

    If the background startup worker hasn't published yet, run a fresh audit
    synchronously so early frontend polls always get a complete report.
    """
    global _startup_audit_report
    if _startup_audit_report is None:
        with _STARTUP_AUDIT_LOCK:
            if _startup_audit_report is None:
                try:
                    _startup_audit_report = code_core.audit_codebase()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Audit failed: {e}")
    return _startup_audit_report

class CodeAuditFixRequest(BaseModel):
    issues: Optional[List[dict]] = None

@app.post("/api/code/audit/fix")
def code_audit_fix(req: CodeAuditFixRequest = None):
    """Apply fixes for the startup audit report issues (per-file, with backups,
    validation and auto-rollback). Returns per-file results including download
    URLs for each corrected file."""
    global _startup_audit_report
    if req and req.issues is not None:
        report = {"issues": req.issues}
    elif _startup_audit_report is not None:
        report = _startup_audit_report
    else:
        try:
            report = code_core.audit_codebase()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Audit failed: {e}")
    return code_core.apply_reported_fixes(report)

@app.post("/api/code/preview-fix")
def code_preview_fix(req: CodePreviewFixRequest):
    try:
        return code_core.preview_file_fix(req.file, req.issue)
    except code_core.NemotronUnavailableError as e:
        return {"status": "error", "error_type": "nemotron_unavailable", "file": req.file, "message": str(e)}

@app.post("/api/code/apply-fix")
def code_apply_fix(req: CodeApplyFixRequest):
    return code_core.apply_file_fix(req.file, req.proposed_content)

@app.post("/api/code/process-file")
def code_process_file(req: CodeProcessFileRequest):
    return code_core.process_uploaded_code_file(req.filename, req.content, req.instructions)

@app.get("/api/code/download/{filename}")
def code_download(filename: str):
    file_path = os.path.join(code_core.DOWNLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)


# ── Cinematic Startup & Real Initialization Endpoints ──────────────────────

@app.get("/api/startup/stream")
async def startup_stream():
    """Stream real-time startup events (SSE) as initialization progresses."""
    engine = get_startup_engine()
    return StreamingResponse(
        engine.stream_startup_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/startup/init")
async def startup_init():
    """Execute full verified startup initialization and return state."""
    engine = get_startup_engine()
    return engine.initialize_full_system()


@app.get("/api/startup/status")
async def startup_status():
    """Get current startup status without triggering another full scan unless uninitialized."""
    engine = get_startup_engine()
    if not engine._initialized:
        return engine.initialize_full_system()
    return engine._last_state



# ===== Google OAuth (alternative to the raw Gemini API key) =====

@app.get("/api/oauth/status")
def oauth_status():
    """Report whether Nexus currently has a linked, usable Google account."""
    return {"authenticated": google_oauth.is_authenticated()}


@app.post("/api/oauth/login")
def oauth_login():
    """
    Kick off the OAuth consent flow. This opens a local browser window for
    the user to sign in with Google and approve access; blocks until the
    flow completes or fails.
    """
    res = google_oauth.start_oauth_flow()
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/oauth/logout")
def oauth_logout():
    """Unlink the Google account, forcing the app back to API-key/offline mode."""
    return google_oauth.logout()


# ── Proactive Gmail watcher (announcements) ──────────────────────
# Background thread: one check shortly after start (restart check) + every
# poll_minutes. Important mail → voice announcement (queued, never cuts off
# current speech) + on-screen toast via /api/notifications. Same guarded
# worker pattern as the startup audit: never raises, never blocks boot.
import collections as _collections

_NOTIFICATIONS = _collections.deque(maxlen=20)
_NOTIFICATIONS_LOCK = threading.Lock()
_GMAIL_WORKER_STARTED = False


def _push_notification(kind: str, title: str, body: str, speak: str = "",
                       center_id: str = "") -> Dict[str, Any]:
    item = {"id": str(uuid.uuid4()), "kind": kind, "title": title, "body": body,
            "speak": speak, "dismissed": False, "ts": time.time(),
            "center_id": center_id}
    with _NOTIFICATIONS_LOCK:
        _NOTIFICATIONS.append(item)
    return item


def _announce_mail(message: Dict[str, Any], voice: bool = True) -> None:
    """Queue one mail arrival: toast + Notification Center always, voice only
    for important mail (or when explicitly asked). Best-effort only."""
    speak_text = message.get("speak") or message.get("toast") or ""
    important = bool(message.get("important"))
    title = (f"Important mail from {message.get('from_name', 'Unknown sender')}"
             if important else f"New mail from {message.get('from_name', 'Unknown sender')}")
    mid = str(message.get("id") or "").strip()
    center_id = f"gmail:{mid}" if mid else str(uuid.uuid4())
    _push_notification("gmail", title, str(message.get("subject", "")), speak_text,
                       center_id=center_id)
    try:
        from backend.agent import notifications as _nc
        _nc.upsert_notification(center_id,
                                "gmail", title, str(message.get("subject", "")),
                                speak_text if voice else "",
                                priority="important" if important else "normal",
                                ref_type="gmail", ref_id=mid)
    except Exception as exc:
        print(f"[gmail] persist announce failed: {exc}")
    if not voice or not message.get("speak"):
        return
    try:
        voice_sys = get_voice_system()
        # Priority -10, no interrupt: announcements truly wait behind any
        # active reply AND behind any queued reply (PriorityQueue pops the
        # highest number first, so a low number sorts last). The old value
        # of 5 did the opposite — it jumped AHEAD of normal replies
        # (priority 0), delaying answers and sounding like a duplicate TTS
        # ~30s later.
        voice_sys.speak(speak_text, priority=-10, interrupt=False)
    except Exception as exc:
        print(f"[gmail] TTS announce failed: {exc}")


def _gmail_check_cycle(reason: str) -> Dict[str, Any]:
    """Run one poll cycle + announce. Returns the raw cycle result."""
    try:
        from backend.tools import gmail_notify
        result = gmail_notify.check_for_important()
    except Exception as exc:
        print(f"[gmail] check failed ({reason}): {exc}")
        return {"status": "error", "announced": []}
    if result.get("status") == "not_linked":
        print("[gmail] Not linked — link Gmail in Settings to enable mail announcements.")
        return result
    for message in result.get("announced", []):
        _announce_mail(message, voice=True)
        print(f"[gmail] Announced ({reason}): {message.get('from_name', '?')} — "
              f"{str(message.get('subject', ''))[:80]}")
    for message in result.get("notified", []):
        _announce_mail(message, voice=False)
        print(f"[gmail] Toast ({reason}): {message.get('from_name', '?')} — "
              f"{str(message.get('subject', ''))[:80]}")
    return result


def _gmail_watch_worker() -> None:
    """Restart check after grace, then every poll_minutes. Never raises."""
    try:
        time.sleep(60)  # let TTS + UI settle before the first announcement
        from backend.tools import gmail_notify
        watch = gmail_notify.load_watch()
        if watch.get("announce_on_restart", True):
            _gmail_check_cycle("restart")
        while True:
            try:
                minutes = float(gmail_notify.load_watch().get("poll_minutes") or 30)
            except (TypeError, ValueError):
                minutes = 30
            time.sleep(max(60.0, minutes * 60.0))
            _gmail_check_cycle("scheduled")
    except Exception as exc:
        print(f"[gmail] watcher stopped: {exc}")


def _ensure_gmail_worker() -> None:
    global _GMAIL_WORKER_STARTED
    if _GMAIL_WORKER_STARTED:
        return
    _GMAIL_WORKER_STARTED = True
    thread = threading.Thread(target=_gmail_watch_worker,
                              name="nexus-gmail-watch", daemon=True)
    thread.start()


_ensure_gmail_worker()


@app.get("/api/gmail/status")
def gmail_status():
    """Gmail link state + watcher schedule for the Settings UI."""
    try:
        from backend.tools import gmail_notify
        watch = gmail_notify.load_watch()
        seen = gmail_notify.load_seen()
        return {"linked": gmail_notify.is_gmail_linked(),
                "poll_minutes": watch.get("poll_minutes", 30),
                "vip_senders": watch.get("vip_senders", []),
                "last_check": seen.get("last_check", 0.0)}
    except Exception as exc:
        return {"linked": False, "error": str(exc)[:160]}


@app.post("/api/gmail/login")
def gmail_login():
    """Link Gmail (read-only). Opens the browser for consent; blocks like /api/oauth/login."""
    from backend.tools import gmail_notify
    res = gmail_notify.start_gmail_oauth_flow()
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/gmail/logout")
def gmail_logout():
    from backend.tools import gmail_notify
    return gmail_notify.logout_gmail()


@app.post("/api/gmail/check")
def gmail_check_now():
    """Manual 'check mail now' — same cycle the scheduler runs."""
    return _gmail_check_cycle("manual")


@app.get("/api/notifications")
def list_notifications():
    """Undismissed toasts for the UI (polled alongside /api/status).

    Shape preserved for the existing toast stack; unread_count (persistent
    notifications + unread triggered reminders) added for the badge."""
    with _NOTIFICATIONS_LOCK:
        items = [dict(n) for n in _NOTIFICATIONS if not n.get("dismissed")]
    return {"notifications": items, "count": len(items),
            "unread_count": _center_unread_count()}


class DismissRequest(BaseModel):
    id: str = ""
    all: bool = False


@app.post("/api/notifications/dismiss")
def dismiss_notification(req: DismissRequest):
    center_ids: list = []
    with _NOTIFICATIONS_LOCK:
        removed = 0
        for item in _NOTIFICATIONS:
            if req.all or (req.id and item.get("id") == req.id):
                if not item.get("dismissed"):
                    item["dismissed"] = True
                    removed += 1
                cid = str(item.get("center_id") or "").strip()
                if cid:
                    center_ids.append(cid)
    persistent = {"status": "skipped"}
    if req.id:
        # Toast ids are ephemeral uuids; the linked Notification Center id
        # lives in center_id. Dismiss both so a toast never resurrects via
        # the Center badge, and dismissing never 404s on a random uuid.
        if center_ids:
            outs = [_do_center_action("dismiss", cid) for cid in center_ids]
            persistent = outs[0] if outs else {"status": "skipped"}
            if persistent.get("status") != "success":
                persistent = _do_center_action("dismiss", req.id)
        else:
            persistent = _do_center_action("dismiss", req.id)
    elif req.all:
        try:
            from backend.agent import notifications as _nc
            from backend.agent.phase1_runtime import runtime as _rt
            for item in _nc.list_notifications():
                _nc.dismiss(item["id"])
            for reminder in _rt.reminders.active_for_bar():
                _rt.reminders.dismiss(reminder["id"])
            persistent = {"status": "success"}
        except Exception as exc:
            persistent = {"status": "error", "message": str(exc)[:160]}
    return {"status": "success", "dismissed": removed, "persistent": persistent,
            "unread_count": _center_unread_count()}


# ── Notification Center (persistent, stable IDs) ─────────────────────────────
# Reminders + scheduled messages are VIEWS over their own stores (no second
# reminder system, no duplicate records). Only gmail/whatsapp/system
# notifications live in the notification store. The backend is the source of
# truth: every action mutates backend state first, the frontend mirrors it.
def _center_unread_count() -> int:
    total = 0
    try:
        from backend.agent import notifications as _nc
        total += _nc.unread_count()
    except Exception:
        pass
    try:
        from backend.agent.phase1_runtime import runtime as _rt
        total += _rt.reminders.unread_count()
    except Exception:
        pass
    return total


def _split_center_id(nid: str):
    nid = (nid or "").strip()
    for prefix in ("reminder:", "scheduled:"):
        if nid.startswith(prefix):
            return prefix[:-1], nid[len(prefix):]
    return "notification", nid


def _reminder_to_item(reminder: Dict[str, Any]) -> Dict[str, Any]:
    rid = str(reminder.get("id") or "")
    ts = (reminder.get("notified_at") or reminder.get("due_at")
          or reminder.get("created_at") or "")
    return {"id": f"reminder:{rid}", "kind": "reminder", "title": "Reminder",
            "body": str(reminder.get("text") or ""),
            "ts": ts, "due_at": reminder.get("due_at"),
            "read": bool(reminder.get("read")),
            "dismissed": bool(reminder.get("dismissed")),
            "priority": reminder.get("priority") or "normal",
            "status": reminder.get("status") or "scheduled",
            "ref_id": rid}


def _job_to_item(job: Dict[str, Any]) -> Dict[str, Any]:
    jid = str(job.get("id") or "")
    status = str(job.get("status") or "pending")
    return {"id": f"scheduled:{jid}", "kind": "scheduled",
            "title": f"WhatsApp to {job.get('contact') or 'Unknown'}",
            "body": str(job.get("message") or ""),
            "ts": job.get("send_at") or job.get("created_at") or "",
            "due_at": job.get("send_at"),
            "read": status != "pending", "dismissed": False,
            "priority": "normal", "status": status, "ref_id": jid,
            "contact": job.get("contact") or ""}


def _do_center_action(action: str, nid: str,
                       minutes: float = 10.0,
                       when_iso: str = "") -> Dict[str, Any]:
    """Route one read/unread/dismiss/delete/snooze by stable id prefix."""
    kind, bare = _split_center_id(nid)
    try:
        if kind == "reminder":
            from backend.agent.phase1_runtime import runtime as _rt
            store = _rt.reminders
            if action == "read":
                return store.mark_read(bare)
            if action == "unread":
                return store.mark_unread(bare)
            if action == "dismiss":
                return store.dismiss(bare)
            if action == "delete":
                return store.remove(bare)
            if action == "snooze":
                return store.snooze(bare, minutes=minutes,
                                    when_iso=when_iso or None)
            return {"status": "error", "message": f"Unknown action '{action}'."}
        if kind == "scheduled":
            from backend.tools import scheduler as _sched
            if action == "delete":
                job = _sched.get_job(bare)
                if job is not None and job.get("status") == "pending":
                    return _sched.cancel_job_by_id(bare)
                return _sched.delete_job_by_id(bare)
            if action in ("read", "dismiss"):
                return {"status": "success", "message": "Noted, sir."}
            if action == "snooze" or action == "reschedule":
                return {"status": "error",
                        "message": "Reschedule a message with a new time, sir."}
            if action == "unread":
                return {"status": "error",
                        "message": "Scheduled messages have no unread state, sir."}
            return {"status": "error", "message": f"Unknown action '{action}'."}
        from backend.agent import notifications as _nc
        if action == "read":
            return _nc.mark_read(bare if bare != nid else nid)
        if action == "unread":
            return _nc.mark_unread(bare if bare != nid else nid)
        if action == "dismiss":
            return _nc.dismiss(bare if bare != nid else nid)
        if action == "delete":
            return _nc.delete(bare if bare != nid else nid)
        return {"status": "error", "message": f"Unknown action '{action}'."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)[:160]}


class CenterActionRequest(BaseModel):
    id: str = ""


class SnoozeRequest(BaseModel):
    id: str = ""
    minutes: float = 10.0
    when: str = ""


class RescheduleRequest(BaseModel):
    when: str = ""


@app.get("/api/notifications/unread-count")
def notifications_unread_count():
    return {"unread": _center_unread_count()}


@app.get("/api/notifications/center")
def notification_center():
    """Aggregated snapshot for the Notification Center panel."""
    try:
        from backend.agent import notifications as _nc
        _nc.purge_expired()
        standalone = _nc.list_notifications(include_dismissed=True)
    except Exception:
        standalone = []
    try:
        from backend.agent.phase1_runtime import runtime as _rt
        history = _rt.reminders.history()
        active = [r for r in history if r.get("status") == "triggered"
                  and not r.get("read") and not r.get("dismissed")]
        upcoming = [r for r in history
                    if r.get("status") in ("scheduled", "snoozed")
                    and not r.get("completed")]
        past = [r for r in history
                if r.get("status") in ("triggered", "dismissed", "done")]
    except Exception:
        active, upcoming, past = [], [], []
    try:
        from backend.tools import scheduler as _sched
        jobs = _sched.list_scheduled(include_done=True)
    except Exception:
        jobs = []
    return {"notifications": standalone,
            "reminders": {"active": [_reminder_to_item(r) for r in active],
                          "upcoming": [_reminder_to_item(r) for r in upcoming],
                          "history": [_reminder_to_item(r) for r in past]},
            "scheduled": [_job_to_item(j) for j in jobs],
            "unread_count": _center_unread_count()}


@app.get("/api/reminders")
def list_reminders_api():
    try:
        from backend.agent.phase1_runtime import runtime as _rt
        history = _rt.reminders.history()
        return {"active": [_reminder_to_item(r) for r in _rt.reminders.active_for_bar()],
                "upcoming": [_reminder_to_item(r) for r in history
                             if r.get("status") in ("scheduled", "snoozed")
                             and not r.get("completed")],
                "history": [_reminder_to_item(r) for r in history
                            if r.get("status") in ("triggered", "dismissed", "done")],
                "unread": _rt.reminders.unread_count()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:200])


@app.get("/api/scheduled")
def list_scheduled_api():
    try:
        from backend.tools import scheduler as _sched
        jobs = _sched.list_scheduled(include_done=True)
        return {"jobs": [_job_to_item(j) for j in jobs],
                "pending": sum(1 for j in jobs if j.get("status") == "pending")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:200])


@app.post("/api/notifications/read")
def notification_read(req: CenterActionRequest):
    if not req.id.strip():
        raise HTTPException(status_code=400, detail="Notification id required.")
    res = _do_center_action("read", req.id)
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "Not found."))
    return {**res, "unread_count": _center_unread_count()}


@app.post("/api/notifications/unread")
def notification_unread(req: CenterActionRequest):
    if not req.id.strip():
        raise HTTPException(status_code=400, detail="Notification id required.")
    res = _do_center_action("unread", req.id)
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "Not found."))
    return {**res, "unread_count": _center_unread_count()}


@app.post("/api/notifications/read-all")
def notification_read_all():
    try:
        from backend.agent import notifications as _nc
        result = _nc.mark_all_read()
    except Exception as exc:
        result = {"status": "error", "message": str(exc)[:160]}
    try:
        from backend.agent.phase1_runtime import runtime as _rt
        marked = 0
        for reminder in _rt.reminders.active_for_bar():
            if _rt.reminders.mark_read(reminder["id"]).get("status") == "success":
                marked += 1
        result["reminders_marked"] = marked
    except Exception:
        pass
    return {**result, "unread_count": _center_unread_count()}


@app.post("/api/notifications/delete")
def notification_delete(req: CenterActionRequest):
    if not req.id.strip():
        raise HTTPException(status_code=400, detail="Notification id required.")
    res = _do_center_action("delete", req.id)
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "Not found."))
    return {**res, "unread_count": _center_unread_count()}


@app.post("/api/notifications/clear-history")
def notification_clear_history():
    """Delete read notification history. Never touches unread items, future
    reminders, or scheduled messages (different stores by construction)."""
    try:
        from backend.agent import notifications as _nc
        result = _nc.clear_read_history()
    except Exception as exc:
        result = {"status": "error", "message": str(exc)[:160]}
    return {**result, "unread_count": _center_unread_count()}


@app.post("/api/notifications/snooze")
def notification_snooze(req: SnoozeRequest):
    if not req.id.strip():
        raise HTTPException(status_code=400, detail="Notification id required.")
    kind, _ = _split_center_id(req.id)
    if kind != "reminder":
        raise HTTPException(status_code=400,
                            detail="Only reminders can be snoozed, sir.")
    res = _do_center_action("snooze", req.id, minutes=req.minutes,
                            when_iso=(req.when or "").strip())
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "Snooze failed."))
    wake = str(res.get("wake_at") or "")
    try:
        from backend.tools.scheduler import describe_when as _describe
        from datetime import datetime as _dt
        human = _describe(_dt.fromisoformat(wake)) if wake else wake
    except Exception:
        human = wake
    return {**res, "human": human, "unread_count": _center_unread_count()}


@app.delete("/api/reminders/{reminder_id}")
def delete_reminder_api(reminder_id: str):
    if not reminder_id.strip():
        raise HTTPException(status_code=400, detail="Reminder id required.")
    _, bare = _split_center_id(reminder_id)
    try:
        from backend.agent.phase1_runtime import runtime as _rt
        res = _rt.reminders.remove(bare)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:200])
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "Not found."))
    return {**res, "unread_count": _center_unread_count()}


@app.delete("/api/scheduled/{job_id}")
def delete_scheduled_api(job_id: str):
    """Cancel a pending message (kept as history) or delete a history entry."""
    if not job_id.strip():
        raise HTTPException(status_code=400, detail="Scheduled message id required.")
    _, bare = _split_center_id(job_id)
    try:
        res = _do_center_action("delete", f"scheduled:{bare}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:200])
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("message", "Not found."))
    return res


@app.post("/api/scheduled/{job_id}/reschedule")
def reschedule_scheduled_api(job_id: str, req: RescheduleRequest):
    if not (req.when or "").strip():
        raise HTTPException(status_code=400, detail="New time required.")
    try:
        from datetime import datetime as _dt
        when = _dt.fromisoformat(req.when.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid time format.")
    _, bare = _split_center_id(job_id)
    try:
        from backend.tools import scheduler as _sched
        res = _sched.reschedule_job_by_id(bare, when)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:200])
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "Reschedule failed."))
    return res


# ── Scheduler ticker (reminders + scheduled WhatsApp) ────────────
# Fires due reminders (voice + toast, exactly once) and sends due scheduled
# WhatsApp messages via the existing desktop sender. Same guarded daemon
# pattern as the Gmail watcher; stores are file-backed so jobs survive
# backend/PC restarts.
def _on_reminder_due(payload: Dict[str, Any]) -> None:
    text = str(payload.get("text") or "").strip()
    if not text:
        return
    speak_text = f"Sir, reminder: {text[:200]}."
    rid = ""
    try:
        rid = str((payload.get("reminder") or {}).get("id") or payload.get("id") or "").strip()
    except Exception:
        rid = ""
    _push_notification("reminder", "Reminder", text[:200], speak_text,
                       center_id=f"reminder:{rid}" if rid else "")
    try:
        # Low priority so live replies always jump ahead of queued reminders.
        get_voice_system().speak(speak_text, priority=-10, interrupt=False)
    except Exception as exc:
        print(f"[scheduler] reminder TTS failed: {exc}")


def _send_scheduled_whatsapp(contact: str, message: str) -> Dict[str, Any]:
    try:
        return whatsapp_ops.send_whatsapp_message(contact, message)
    except Exception as exc:
        return {"status": "error", "message": f"Scheduled send failed: {exc}"}


def _on_whatsapp_result(job: Dict[str, Any], result: Dict[str, Any]) -> None:
    contact = str(job.get("contact") or "Unknown")
    ok = result.get("status") == "success"
    jid_early = str(job.get("id") or "").strip()
    wa_center = f"wa:{jid_early}" if jid_early else ""
    if ok:
        speak_text = f"Scheduled WhatsApp delivered to {contact}, sir."
        _push_notification("whatsapp", "WhatsApp delivered",
                           f"To {contact}: {str(job.get('message') or '')[:120]}",
                           speak_text, center_id=wa_center)
    else:
        speak_text = (f"Sir, the scheduled WhatsApp to {contact} failed: "
                      f"{str(result.get('message') or 'unknown error')[:160]}")
        _push_notification("whatsapp", "WhatsApp failed", speak_text, speak_text,
                           center_id=wa_center)
    try:
        from backend.agent import notifications as _nc
        jid = str(job.get("id") or "").strip()
        _nc.upsert_notification(f"wa:{jid}" if jid else str(uuid.uuid4()),
                                "whatsapp",
                                "WhatsApp delivered" if ok else "WhatsApp failed",
                                (f"To {contact}: {str(job.get('message') or '')[:120]}"
                                 if ok else speak_text),
                                speak_text,
                                priority="normal" if ok else "urgent",
                                ref_type="scheduled", ref_id=jid)
    except Exception as exc:
        print(f"[scheduler] persist whatsapp result failed: {exc}")
    try:
        # Low priority so live replies always jump ahead of status chatter.
        get_voice_system().speak(speak_text, priority=-10, interrupt=False)
    except Exception as exc:
        print(f"[scheduler] whatsapp TTS failed: {exc}")


def _ensure_scheduler_worker() -> None:
    try:
        from backend.tools import scheduler as _scheduler
        _scheduler.ensure_scheduler_worker(_on_reminder_due, _on_whatsapp_result,
                                           _send_scheduled_whatsapp)
    except Exception as exc:
        print(f"[scheduler] worker failed to start: {exc}")


_ensure_scheduler_worker()

@app.get("/api/status")
async def read_status():
    return {"status": "online", "system": "N.E.X.U.S.", "message": "All systems operational, sir."}


@app.get("/health")
def read_health():
    return {"status": "ok"}



@app.get("/api/network/status")
def network_status():
    """Live connectivity snapshot for the HUD (cached ~10s in net_diagnostics).

    Lets the frontend distinguish backend-down vs Wi-Fi-off vs
    router-no-internet vs Google-unreachable instead of one generic OFFLINE.
    """
    try:
        from net_diagnostics import STATE_LABELS, get_connectivity_snapshot
        snap = get_connectivity_snapshot()
        state = snap.get("state", "wifi_off")
        return {
            "status": "success",
            "state": state,
            "state_label": STATE_LABELS.get(state, state),
            "online": state == "online",
            "internet": bool(snap.get("internet")),
            "dns": bool(snap.get("dns")),
            "gemini_reachable": bool(snap.get("gemini_reachable")),
            "ssid": snap.get("ssid", ""),
            "local_ips": snap.get("local_ips", []),
            "up_interfaces": snap.get("up_interfaces", []),
        }
    except Exception as e:
        return {"status": "error", "state": "unknown", "message": str(e)}


# ── Voice Command Endpoint (for native voice service) ──────────────────────
class VoiceCommandRequest(BaseModel):
    prompt: str


class TTSRequest(BaseModel):
    text: str
    priority: int = 0
    interrupt: bool = True
    lang: Optional[str] = None


@app.post("/api/voice/command")
async def voice_command(req: VoiceCommandRequest):
    """Endpoint for the native voice service to send recognized commands.

    The classification step is instant (no I/O); the full command runs in a
    worker thread via asyncio.to_thread so this endpoint never blocks the
    event loop either (same watchdog-timeout root cause as /api/command).
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Empty prompt")

    # Get command processor and process the voice command
    processor = get_command_processor()

    result = await processor.process_command(req.prompt.strip(), None)

    if result.get("status") == "interrupted":
        return {"status": "interrupted", "speak": "Interrupted, sir."}
    elif result.get("status") == "new_command":
        # Process as new command — process_command is sync (threadpool),
        # so offload it instead of awaiting a coroutine.
        command_req = CommandRequest(prompt=req.prompt.strip(), apiKey=None)
        return await asyncio.to_thread(process_command, command_req)

    return result


@app.post("/api/voice/tts")
async def voice_tts(req: TTSRequest):
    """Text-to-speech endpoint with interruption support."""
    voice = get_voice_system()
    success = voice.speak(req.text, priority=req.priority, interrupt=req.interrupt, lang=req.lang)
    return {"status": "success" if success else "error", "speaking": voice.is_speaking()}


@app.post("/api/voice/tts/interrupt")
async def voice_tts_interrupt():
    """Interrupt current TTS playback."""
    voice = get_voice_system()
    interrupted = voice.interrupt()
    return {"status": "success", "interrupted": interrupted}


@app.get("/api/voice/tts/state")
async def voice_tts_state():
    """Get current TTS state."""
    voice = get_voice_system()
    return {"status": "success", "state": voice.get_state().value, "speaking": voice.is_speaking(), "muted": voice.is_muted()}


@app.get("/api/voice/voices")
async def voice_list():
    """Installed TTS voices (SAPI) with genders + which one NEXUS uses.

    Reads only worker-maintained state — never touches the SAPI COM object
    from a request thread (that cross-thread access crashes the backend)."""
    voice = get_voice_system()
    try:
        ready = voice._sapi_ready
        if not ready.is_set():
            await asyncio.to_thread(ready.wait, 8.0)
    except Exception:
        pass
    return {
        "status": "success",
        "active_voice_id": getattr(voice, "_active_voice_id", ""),
        "voices": voice.get_available_voices(),
    }


class VoiceMuteRequest(BaseModel):
    muted: bool = False


@app.get("/api/voice/mute")
async def voice_mute_state():
    """Whether backend speech (reminders, announcements) is muted."""
    return {"status": "success", "muted": get_voice_system().is_muted()}


@app.post("/api/voice/mute")
async def voice_mute(req: VoiceMuteRequest):
    """Mute/unmute backend speech. Muting stops in-flight speech and drops
    queued announcements (toasts/notifications are unaffected)."""
    muted = get_voice_system().set_muted(req.muted)
    return {"status": "success", "muted": muted}


# ── Notes endpoints ───────────────────────────────────────────────────────
@app.get("/api/notes")
def get_notes():
    return {"notes": _load_json_list(NOTES_FILE)}

@app.post("/api/notes")
def add_note(req: dict):
    text = (req.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note text cannot be empty.")
    from datetime import datetime
    notes = _load_json_list(NOTES_FILE)
    note = {"id": int(datetime.now().timestamp() * 1000), "text": text,
            "time": datetime.now().strftime("%b %d %H:%M")}
    notes.append(note)
    _save_json_list(NOTES_FILE, notes)
    return {"status": "success", "note": note}

@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int):
    notes = _load_json_list(NOTES_FILE)
    notes = [n for n in notes if n.get("id") != note_id]
    _save_json_list(NOTES_FILE, notes)
    return {"status": "success"}

# ── Todos endpoints ───────────────────────────────────────────────────────
@app.get("/api/todos")
def get_todos():
    return {"todos": _load_json_list(TODOS_FILE)}

@app.post("/api/todos")
def add_todo(req: dict):
    text = (req.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Todo text cannot be empty.")
    from datetime import datetime
    todos = _load_json_list(TODOS_FILE)
    todo = {"id": int(datetime.now().timestamp() * 1000), "text": text, "done": False}
    todos.append(todo)
    _save_json_list(TODOS_FILE, todos)
    return {"status": "success", "todo": todo}

@app.patch("/api/todos/{todo_id}")
def toggle_todo(todo_id: int):
    todos = _load_json_list(TODOS_FILE)
    for t in todos:
        if t.get("id") == todo_id:
            t["done"] = not t.get("done", False)
            break
    _save_json_list(TODOS_FILE, todos)
    return {"status": "success"}

@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: int):
    todos = _load_json_list(TODOS_FILE)
    todos = [t for t in todos if t.get("id") != todo_id]
    _save_json_list(TODOS_FILE, todos)
    return {"status": "success"}

@app.get("/api/stats")
def read_stats():
    stats = get_system_stats()
    if "error" in stats:
        raise HTTPException(status_code=500, detail=stats["error"])
    return stats

@app.get("/api/files")
def get_files(subdir: str = ""):
    res = list_files(subdir)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.get("/api/files/read")
def get_file_content(filename: str):
    res = read_file(filename)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["message"])
    return res

@app.post("/api/files/write")
def post_file_content(req: FileWriteRequest):
    res = write_file(req.filename, req.content)
    if res["status"] == "error":
        raise HTTPException(status_code=500, detail=res["message"])
    return res

@app.delete("/api/files/delete")
def remove_file(filename: str):
    res = delete_file(filename)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["message"])
    return res

# Serve generated images from work_files
@app.get("/api/images/{filename}")
def serve_image(filename: str):
    work_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "work_files"))
    img_path = os.path.join(work_dir, "images", filename)
    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(img_path, media_type="image/png")


# ===== Phone Control (ADB / scrcpy) =====

@app.get("/api/phone/devices")
def phone_devices():
    """List connected Android devices and their authorization status."""
    return phone_control.list_devices()


@app.post("/api/phone/mirror")
def phone_mirror():
    """Launch scrcpy to open a live, interactive mirror window of the phone."""
    res = phone_control.start_mirror()
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/screenshot")
def phone_screenshot():
    """Capture the phone's current screen and return it as base64 for preview."""
    res = phone_control.screenshot_as_base64()
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/phone/stream")
def phone_stream():
    """Live-ish mirror: streams repeated screencap frames as multipart/x-mixed-replace,
    which browsers render natively in an <img> tag without any client-side decoding."""
    dev = phone_control.get_primary_device()
    if not dev:
        raise HTTPException(status_code=400, detail="No authorized Android device found, sir.")

    def generate():
        boundary = "nexusframe"
        for frame in phone_control.stream_frames(dev):
            yield (
                f"--{boundary}\r\nContent-Type: image/png\r\nContent-Length: {len(frame)}\r\n\r\n"
            ).encode() + frame + b"\r\n"

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=nexusframe")


@app.get("/api/phone/screenshot/{filename}")
def serve_phone_screenshot(filename: str):
    """Serve a previously captured phone screenshot from work_files/phone."""
    path = os.path.join(phone_control.PHONE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(path, media_type="image/png")


@app.post("/api/phone/tap")
def phone_tap(req: PhoneTapRequest):
    res = phone_control.tap(req.x, req.y)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/swipe")
def phone_swipe(req: PhoneSwipeRequest):
    res = phone_control.swipe(req.x1, req.y1, req.x2, req.y2, req.duration_ms or 300)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/text")
def phone_text(req: PhoneTextRequest):
    res = phone_control.input_text(req.text)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/key")
def phone_key(req: PhoneKeyRequest):
    res = phone_control.press_key(req.key)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/phone/apps")
def phone_apps():
    res = phone_control.list_installed_packages()
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/launch_app")
def phone_launch_app(req: PhoneLaunchAppRequest):
    res = phone_control.launch_app(req.package)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/unlock")
def phone_unlock(req: PhoneUnlockRequest):
    """Wake the phone and dismiss the lock screen, optionally entering a PIN."""
    res = phone_control.unlock_phone(req.pin)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/test_pin_tap")
def phone_test_pin_tap(req: PhoneTestPinTapRequest):
    """Calibration helper: wake the screen and tap where a single digit
    should be on the lock screen's PIN pad, without swiping or submitting
    anything. Use this to verify/tune NEXUS_PIN_Y_OFFSET / NEXUS_PIN_X_OFFSET."""
    res = phone_control.test_pin_digit_tap(req.digit)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/phone/ocr")
def phone_ocr():
    """OCR the most recent phone screenshot (requires pytesseract + Pillow + Tesseract binary)."""
    res = phone_control.ocr_last_screenshot()
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/chat/stream")
def chat_stream(req: ChatStreamRequest):
    """Free-form conversational endpoint (Chat mode).

    Returns a deterministic reply (smalltalk/history-aware) as plain text.
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    def _gen():
        try:
            import agent as _agent_mod
            _agent_mod.add_to_history("user", req.prompt)
            try:
                from backend.agent import human_replies as _hr
                small = _hr.smalltalk(req.prompt)
            except Exception:
                small = None
            if small:
                text = small
            else:
                text = ("Chat is limited, sir. "
                        "I can still handle reminders, scheduled messages, notes, and "
                        "status checks via /api/command.")
            try:
                _agent_mod.add_to_history("assistant", text)
            except Exception:
                pass
        except Exception as exc:
            text = f"Chat unavailable, sir: {exc}"
        yield text

    return StreamingResponse(_gen(), media_type="text/plain; charset=utf-8")


@app.post("/api/command/stream")
def command_stream(req: ChatStreamRequest):
    """Command endpoint (streaming).

    Streams a single JSON envelope with a deterministic `speak`
    message instead.
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    def _gen():
        payload = {
            "type": "speak",
            "text": ("Command streaming is unavailable, sir. Please use "
                     "/api/command for direct commands."),
        }
        yield "data: " + json.dumps(payload) + "\n\n"
        yield "data: " + json.dumps({"type": "done", "message": "Stream complete"}) + "\n\n"

    return StreamingResponse(_gen(), media_type="text/plain; charset=utf-8")


@app.post("/api/vision/stream")
def vision_stream(req: ImageAnalysisRequest):
    """Image understanding endpoint.

    Unavailable here. Returns an explicit notice instead of a silent fake.
    """
    if not req.image_base64.strip():
        raise HTTPException(status_code=400, detail="No image data received.")
    if not req.mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File does not appear to be an image.")

    def _gen():
        yield ("Image analysis is unavailable, sir.")

    return StreamingResponse(_gen(), media_type="text/plain; charset=utf-8")


@app.post("/api/document/extract")
async def extract_document(file: UploadFile = File(...)):
    """Upload a PDF/DOCX/PPTX/TXT/MD, extract its plain text, and hand it
    back to the frontend to hold onto until the user sends a question about
    it (see /api/document/stream). Nothing is persisted to disk afterward."""
    filename = file.filename or "document"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in document_intel.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext or 'unknown'}', sir. Try PDF, DOCX, PPTX, TXT, or MD.")

    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {str(e)}")

    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="That file is over the 25MB limit, sir.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        result = document_intel.extract_text(tmp_path, filename)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/api/document/stream")
def document_stream(req: DocumentAnalysisRequest):
    """Ask about previously-extracted document text.

    Returns a deterministic lexical summary (first sections + question echo).
    /api/document/extract above is retained unchanged.
    """
    if not req.document_text.strip():
        raise HTTPException(status_code=400, detail="No document text received.")

    def _gen():
        text = (req.document_text or "").strip()
        question = (req.prompt or "").strip()
        head = text[:1500]
        tail = ""
        if question:
            tail = f"\n\nQuestion noted: {question[:300]}"
        yield (f"Here is the start of the extracted text ({len(text)} chars), sir:\n\n"
               f"{head}{tail}")

    return StreamingResponse(_gen(), media_type="text/plain; charset=utf-8")


@app.post("/api/command")
def process_command(req: CommandRequest):
    """Sync (threadpool) endpoint — NEVER block the event loop.

    Previously `async def` with blocking Gemini/WhatsApp/phone/screenshot
    calls inline, which stalled the loop for 10-30s per command. During that
    window /api/status + watchdog health checks timed out, the UI looked
    frozen, dismiss POSTs failed, and queued TTS fired late (perceived as a
    duplicate reply). As a plain `def`, FastAPI runs this in its threadpool
    so /api/status stays snappy even mid-reply.
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Command prompt cannot be empty.")

    # Check for chat reset keywords
    prompt_lower = req.prompt.lower().strip()
    if prompt_lower in ["clear chat", "reset history", "forget everything", "clear memory", "reset"]:
        import agent
        agent.clear_history()
        try:
            from backend.agent import phase1_memory, phase1_runtime
            if prompt_lower in ["clear memory", "forget everything", "reset"]:
                phase1_memory.clear()
            phase1_runtime.runtime.conversation.clear()
        except Exception:
            pass
        return {
            "speak": "Memory banks cleared, sir. Starting fresh.",
            "speak_lang": "en",
            "logs": ["ACTION: Cleared conversation history"],
            "file_data": None,
            "refresh_files": False,
            "image_data": None
        }

    # Deterministic handlers: reminders + scheduled WhatsApp are
    # answered instantly without an LLM round-trip (same style as the reset
    # keywords above). Immediate WhatsApp sends fall through to Gemini below.
    try:
        from backend.tools import scheduler as _scheduler
        _direct = _scheduler.handle_schedule_command(req.prompt)
        if _direct is not None:
            return _direct
    except Exception as exc:
        print(f"[scheduler] direct handler failed: {exc}")

    # ── Zetaris connector (explicit command: zetaris: ...) ──────────────────
    # Handles: zetaris: test connection, zetaris: list datasources, zetaris: query SELECT ...
    try:
        from backend.tools import zetaris as _zetaris
        _zetaris_result = _zetaris.handle_zetaris_command(req.prompt, load_config())
        if _zetaris_result is not None:
            return _zetaris_result
    except Exception as exc:
        print(f"[zetaris] handler failed: {exc}")

    # ── Agricultural FPO connector ──────────────────────────────────────────
    try:
        from backend.tools import fpo_analytics as _fpo
        _fpo_result = _fpo.handle_fpo_agent_command(req.prompt)
        if _fpo_result is not None:
            return _fpo_result
    except Exception as exc:
        print(f"[fpo] handler failed: {exc}")

    # ── Deterministic identity memory (never LLM-dependent) ──────────────
    # "My name is Taha" / "I live in Pune" / "Pune only for weather" are
    # saved here on EVERY command — even offline or rate-limited — so the
    # facts are already in memory context before the LLM call below.
    # Name/city QUESTIONS are answered straight from memory too.
    _memory_note = ""
    try:
        from backend.agent import phase1_runtime as _rt
        _saved = _rt.capture_implicit_memories(req.prompt)
        if _saved:
            try:
                from backend.agent import phase1_memory as _pm
                _nick = _pm.get_user_name()
                _city = _pm.get_home_city()
                _bits = []
                try:
                    from backend.agent import marathi as _mmod
                    _mr_mode = _mmod.is_marathi(req.prompt)
                except Exception:
                    _mr_mode = False
                try:
                    from backend.agent import hindi as _hmod
                    _hi_mode = (not _mr_mode) and _hmod.is_hindi(req.prompt)
                except Exception:
                    _hi_mode = False
                for _item in _saved:
                    _k = str((_item or {}).get("key", "")).casefold()
                    if _k == "name" and _nick:
                        _bits.append(f"तुमचं नाव ({_nick}) लक्षात ठेवीन" if _mr_mode
                                     else f"आपका नाम ({_nick}) याद रखूँगा" if _hi_mode
                                     else f"noted your name ({_nick})")
                    elif _k in ("default city", "weather city", "city", "location",
                                "home city") and _city:
                        _bits.append(f"{_city} — हवामान तिथलंच सांगेन" if _mr_mode
                                     else f"{_city} — मौसम वहीं का बताऊँगा" if _hi_mode
                                     else f"locked in {_city} for weather")
                if _bits:
                    _memory_note = ("नोंदवलं — " if _mr_mode
                                    else "नोट किया — " if _hi_mode else "Noted — ") \
                        + (" आणि ".join(_bits) if _mr_mode else " और ".join(_bits)) \
                        + ("।" if (_mr_mode or _hi_mode) else ".")
            except Exception:
                pass
        _mem_answer = _rt.answer_from_memory(req.prompt)
        if _mem_answer:
            try:
                import agent as _agent_mod
                _agent_mod.add_to_history("user", req.prompt)
                _agent_mod.add_to_history("assistant", _mem_answer)
            except Exception:
                pass
            try:
                _rt.runtime.conversation.add("user", req.prompt, {"intent": "question"})
                _rt.runtime.conversation.add("assistant", _mem_answer, {})
            except Exception:
                pass
            try:
                from backend.agent.lang_detect import detect_lang as _dl
                _mem_lang = _dl(_mem_answer, req.prompt)
            except Exception:
                _mem_lang = "en"
            return {
                "speak": _mem_answer,
                "speak_lang": _mem_lang,
                "logs": [f"INPUT RECEIVED: \"{req.prompt}\"", "MEMORY: Answered from stored memory"],
                "file_data": None,
                "refresh_files": False,
                "image_data": None,
                "timer_data": None,
                "clarification_needed": None,
                "narration_steps": [],
            }
    except Exception as exc:
        print(f"[memory] deterministic handler failed: {exc}")

    # ── Deterministic local intents ────────
    # The intents below are single-step, direct tool calls.
    try:
        import agent as _agent_hist
        _agent_hist.add_to_history("user", req.prompt)
    except Exception:
        pass
    execution_logs = [f"INPUT RECEIVED: \"{req.prompt}\""]
    speak_text = ""
    file_data = None
    refresh_files = False
    image_data = None
    timer_data = None
    clarification_needed = None
    narration_steps = []
    pl = req.prompt.lower().strip()

    def _base_response():
        try:
            from backend.agent.lang_detect import detect_lang
            lang = detect_lang(speak_text, req.prompt)
        except Exception:
            lang = "en"
        full_speak = speak_text or "I have completed your request, sir."
        try:
            if _memory_note and _memory_note.casefold() not in (full_speak or "").casefold():
                full_speak = f"{_memory_note} {full_speak}".strip()
        except Exception:
            pass
        try:
            import agent as _agent_hist2
            _agent_hist2.add_to_history("assistant", full_speak)
        except Exception:
            pass
        return {
            "speak": full_speak,
            "speak_lang": lang,
            "logs": execution_logs,
            "file_data": file_data,
            "refresh_files": refresh_files,
            "image_data": image_data,
            "timer_data": timer_data,
            "clarification_needed": clarification_needed,
            "narration_steps": narration_steps,
        }

    # --- Date / time ---
    if any(x in pl for x in ["what time", "what's the time", "current time",
                             "what day", "what's the date", "current date",
                             "today's date", "time now", "date today"]):
        execution_logs.append("ACTION: Getting date/time")
        res = get_datetime_info()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- System stats ---
    if ("system stats" in pl or "cpu" in pl or "hardware" in pl
            or "pc working good" in pl):
        execution_logs.append("ACTION: Loading HUD diagnostics...")
        try:
            stats = get_system_stats()
            if isinstance(stats, dict) and "error" not in stats:
                procs = stats.get("processes", []) or []
                top = ", ".join(
                    p.get("name", "?") for p in procs[:5] if p.get("name")
                ) or "no processes sampled"
                speak_text = (
                    f"CPU at {stats.get('cpu', '?')} percent, memory at "
                    f"{stats.get('memory', '?')} percent, disk at "
                    f"{stats.get('disk', '?')} percent, sir. "
                    f"Busiest applications: {top}."
                )
                execution_logs.append(f"RESULT: {speak_text}")
            else:
                speak_text = "I couldn't sample the system stats, sir."
        except Exception as exc:
            speak_text = f"Diagnostics failed, sir: {exc}"
            execution_logs.append(f"RESULT: {speak_text}")
        return _base_response()

    # --- Health check ---
    if "health" in pl or "diagnose" in pl or "diagnostic" in pl:
        execution_logs.append("ACTION: Performing system diagnosis health check")
        res = check_pc_health()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Battery ---
    if any(x in pl for x in ["battery", "charge level", "power level", "battery life"]):
        execution_logs.append("ACTION: Checking battery")
        res = get_battery_info()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Network ---
    if any(x in pl for x in ["ip address", "my ip", "network info", "wifi",
                             "network status", "am i connected",
                             "internet connection"]):
        execution_logs.append("ACTION: Getting network info")
        res = get_network_info()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Weather (home-city default, explicit city wins) ---
    if "weather" in pl or "temperature" in pl or "forecast" in pl:
        m = re.search(r"(?:weather|temperature|forecast)(?:\s+in|\s+for|\s+at)?\s+([\w\s]+)", pl)
        city = m.group(1).strip() if m else ""
        city = re.sub(r"\b(today|now|currently|please|right now|only|always|by default|"
                      r"as default|remember|just|alone|for me|tomorrow|"
                      r"day after tomorrow|tonight|today)\b", "", city, flags=re.I).strip()
        city = re.sub(r"\s+", " ", city).strip(" ,.")
        if not city:
            try:
                from backend.agent import phase1_memory as _wmem
                city = _wmem.get_home_city() or ""
            except Exception:
                city = ""
        day = 0
        if re.search(r"\bday\s+after\s+tomorrow\b", pl):
            day = 2
        elif re.search(r"\btomorrow\b", pl):
            day = 1
        execution_logs.append(f"ACTION: Fetching weather for {city or 'home city'} (day+{day})")
        res = get_weather(city, day)
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Calculator (safe local math) ---
    try:
        from backend.tools.knowledge import quick_math_detect as _qmd
        _expr = _qmd(req.prompt)
    except Exception:
        _expr = None
    if _expr or any(k in pl for k in ["calculate", "compute", "evaluate", "solve"]):
        execution_logs.append("ACTION: Calculating")
        try:
            from backend.tools import knowledge as _know
            res = _know.calculate(_expr or req.prompt)
        except Exception as exc:
            res = {"status": "error", "message": f"Couldn't crunch that: {exc}"}
        execution_logs.append(f"RESULT: {res.get('message', '')[:200]}")
        speak_text = res.get("message", "Couldn't crunch that.")
        return _base_response()

    # --- Unit conversion ---
    if "convert" in pl or "conversion" in pl:
        execution_logs.append("ACTION: Converting")
        try:
            from backend.tools import knowledge as _know
            res = _know.convert_units(req.prompt)
        except Exception as exc:
            res = {"status": "error", "message": f"Couldn't convert that: {exc}"}
        execution_logs.append(f"RESULT: {res.get('message', '')[:200]}")
        speak_text = res.get("message", "Couldn't convert that.")
        return _base_response()

    # --- Dictionary ---
    if any(k in pl for k in ["define", "definition", "meaning of", "mean by"]):
        execution_logs.append("ACTION: Dictionary lookup")
        try:
            from backend.tools import knowledge as _know
            res = _know.define_word(req.prompt)
        except Exception as exc:
            res = {"status": "error", "message": f"Dictionary lookup failed: {exc}"}
        execution_logs.append(f"RESULT: {res.get('message', '')[:200]}")
        speak_text = res.get("message", "Couldn't define that.")
        return _base_response()

    # --- Jokes & facts ---
    if re.search(r"\bjoke\b", pl) or "make me laugh" in pl or "cheer me up" in pl:
        execution_logs.append("ACTION: Telling a joke")
        try:
            from backend.tools import knowledge as _know
            res = _know.get_joke("en")
        except Exception:
            res = {"status": "success",
                   "message": "Why do programmers prefer dark mode? Because light attracts bugs."}
        speak_text = res.get("message", "")
        return _base_response()
    if re.search(r"\bfact\b", pl) or "amaze me" in pl or "surprise me" in pl:
        execution_logs.append("ACTION: Sharing a fact")
        try:
            from backend.tools import knowledge as _know
            res = _know.get_fact("en")
        except Exception:
            res = {"status": "success",
                   "message": "Honey never spoils \u2014 3,000-year-old pots found in tombs were still edible."}
        speak_text = res.get("message", "")
        return _base_response()

    # --- Volume ---
    if "volume up" in pl or "louder" in pl or "increase volume" in pl:
        execution_logs.append("ACTION: Increasing system volume")
        res = adjust_volume("up")
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if "volume down" in pl or "quieter" in pl or "decrease volume" in pl:
        execution_logs.append("ACTION: Decreasing system volume")
        res = adjust_volume("down")
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if "mute" in pl:
        execution_logs.append("ACTION: Toggling system mute")
        res = adjust_volume("mute")
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Media ---
    if "next track" in pl or "skip song" in pl or "skip track" in pl:
        execution_logs.append("ACTION: Skipping media track")
        res = media_control("next")
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if "previous track" in pl or "prev track" in pl or "go back a track" in pl:
        execution_logs.append("ACTION: Playing previous media track")
        res = media_control("prev")
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if ("play" in pl and "pause" in pl) or "toggle media" in pl:
        execution_logs.append("ACTION: Toggling media playback")
        res = media_control("play")
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Screenshot (PC display) ---
    if ("screenshot" in pl or "capture screen" in pl) and "phone" not in pl:
        execution_logs.append("ACTION: Taking screenshot")
        res = take_screenshot()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        refresh_files = True
        return _base_response()

    # --- Power controls (single direct calls, user-explicit) ---
    if "cancel shutdown" in pl or "abort shutdown" in pl or "cancel restart" in pl:
        execution_logs.append("ACTION: Cancel shutdown")
        res = cancel_shutdown()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if any(x in pl for x in ["shut down", "shutdown", "turn off the pc", "power off"]):
        delay_match = re.search(r"in\s+(\d+)\s*min", pl)
        delay = int(delay_match.group(1)) * 60 if delay_match else 0
        execution_logs.append("ACTION: Shutdown initiated")
        res = shutdown_pc(delay)
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if any(x in pl for x in ["restart", "reboot"]):
        delay_match = re.search(r"in\s+(\d+)\s*min", pl)
        delay = int(delay_match.group(1)) * 60 if delay_match else 0
        execution_logs.append("ACTION: Restart initiated")
        res = restart_pc(delay)
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if any(x in pl for x in ["sleep", "hibernate", "put pc to sleep"]):
        execution_logs.append("ACTION: Sleep PC")
        res = sleep_pc()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()
    if "lock" in pl and any(x in pl for x in ["lock", "lock screen", "lock pc", "lock computer"]):
        execution_logs.append("ACTION: Lock screen")
        res = lock_screen()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Clipboard ---
    if "clipboard" in pl and any(x in pl for x in ["what's in", "read", "show"]):
        execution_logs.append("ACTION: Reading clipboard")
        res = get_clipboard()
        execution_logs.append(f"RESULT: {res['message']}")
        speak_text = res["message"]
        return _base_response()

    # --- Timer (frontend-driven) ---
    timer_match = re.search(r"(?:set(?:\s+a)?\s+timer|timer)(?:\s+for)?\s+(\d+)\s*"
                            r"(second|minute|hour|sec|min|hr)s?", pl)
    if timer_match:
        amount = int(timer_match.group(1))
        unit = timer_match.group(2)
        if unit in ("hour", "hr"):
            seconds = amount * 3600
        elif unit in ("minute", "min"):
            seconds = amount * 60
        else:
            seconds = amount
        timer_data = {"seconds": seconds, "label": "Timer"}
        execution_logs.append(f"ACTION: Setting timer for {seconds} seconds")
        minutes = seconds // 60
        secs = seconds % 60
        time_str = f"{minutes}m {secs}s" if minutes else f"{secs}s"
        speak_text = f"Timer set for {time_str}, sir."
        return _base_response()

    # --- Notes / todos ---
    note_match = re.search(r"(?:add(?:\s+a)?\s+note|note(?:\s+that)?)\s*[:\"]?\s*(.+)", pl)
    if note_match and "todo" not in pl and "remind" not in pl:
        note_text = note_match.group(1).strip()
        if note_text:
            execution_logs.append("ACTION: Adding note")
            from datetime import datetime as dt
            notes = _load_json_list(NOTES_FILE)
            note = {"id": int(dt.now().timestamp() * 1000), "text": note_text,
                    "time": dt.now().strftime("%b %d %H:%M")}
            notes.append(note)
            _save_json_list(NOTES_FILE, notes)
            execution_logs.append("RESULT: Note added")
            speak_text = "Note added, sir."
            return _base_response()
    todo_match = re.search(r"(?:add(?:\s+a)?\s+todo|todo(?:\s+item)?)\s*[:\"]?\s*(.+)", pl)
    if todo_match and "remind" not in pl:
        todo_text = todo_match.group(1).strip()
        if todo_text:
            execution_logs.append("ACTION: Adding todo")
            from datetime import datetime as dt
            todos = _load_json_list(TODOS_FILE)
            todo = {"id": int(dt.now().timestamp() * 1000), "text": todo_text, "done": False}
            todos.append(todo)
            _save_json_list(TODOS_FILE, todos)
            execution_logs.append("RESULT: Todo added")
            speak_text = "Todo added, sir."
            return _base_response()

    # --- Smalltalk (no tools needed) ---
    try:
        from backend.agent import human_replies as _hr
        _small = _hr.smalltalk(req.prompt)
        if _small:
            speak_text = _small
            execution_logs.append("SMALLTALK: Answered without tools")
            return _base_response()
    except Exception:
        pass

    # --- Default: be explicit, never fake it ---
    execution_logs.append("RESULT: No deterministic handler matched")
    speak_text = ("I cannot handle that directly, sir. I can still handle time, "
                  "system stats, battery, network, weather, calculations, "
                  "volume, media, screenshots, notes, todos, reminders and "
                  "scheduled messages directly.")
    return _base_response()


# ── Gallery endpoints ─────────────────────────────────────────────────────────

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_DOC_EXTS = {".docx", ".pptx", ".ppt", ".xlsx", ".xls", ".pdf", ".csv", ".txt", ".md", ".html", ".htm", ".rtf"}

@app.get("/api/gallery")
def get_gallery():
    """Recursively scan work_files for images and documents, returning metadata
    for each file. Categorises into: pc_screenshot, phone, generated, document,
    other. Documents (docx/pptx/pdf/...) persist across restarts and always show."""
    work_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "work_files"))
    if not os.path.exists(work_dir):
        return {"images": []}

    items = []
    for root, dirs, files in os.walk(work_dir):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            is_image = ext in _IMAGE_EXTS
            is_doc = ext in _DOC_EXTS
            if not is_image and not is_doc:
                continue
            full_path = os.path.join(root, fname)
            rel = os.path.relpath(full_path, work_dir).replace("\\", "/")
            size = 0
            mtime = 0
            try:
                st = os.stat(full_path)
                size = st.st_size
                mtime = st.st_mtime
            except OSError:
                pass

            # Categorise based on folder / filename prefix
            rel_lower = rel.lower()
            kind = "image" if is_image else "document"
            if not is_image:
                category = "document"
            elif rel_lower.startswith("phone/") or fname.startswith("phone_"):
                category = "phone"
            elif rel_lower.startswith("images/") or fname.startswith("gen_") or fname.startswith("image_"):
                category = "generated"
            elif rel_lower.startswith("screenshots/") or fname.startswith("screenshot_") or fname.startswith("screen_"):
                category = "pc_screenshot"
            else:
                category = "other"

            items.append({
                "filename": fname,
                "path": rel,
                "size": size,
                "mtime": mtime,
                "category": category,
                "kind": kind,
                "ext": ext.lstrip("."),
            })

    # Newest first
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return {"images": items}


@app.get("/api/files/serve")
def serve_work_file(path: str):
    """Serve a file from work_files by its relative path (safe — refuses path traversal)."""
    work_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "work_files"))
    full_path = os.path.abspath(os.path.join(work_dir, path))
    # Guard against path traversal
    if not full_path.startswith(work_dir + os.sep) and full_path != work_dir:
        raise HTTPException(status_code=403, detail="Access denied.")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found.")
    ext = os.path.splitext(full_path)[1].lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".rtf": "application/rtf",
    }
    media_type = mime_map.get(ext, "application/octet-stream")
    return FileResponse(full_path, media_type=media_type)



# ── Agricultural FPO Analytics Endpoints ──────────────────────────────
@app.get("/api/fpo/stats")
def api_fpo_stats(fpo_id: Optional[str] = None, crop_name: Optional[str] = None):
    from backend.tools import fpo_analytics
    return fpo_analytics.get_overview_stats(fpo_id=fpo_id, crop_name=crop_name)

@app.get("/api/fpo/inventory")
def api_fpo_inventory(page: int = 1, page_size: int = 25, 
                      crop_name: Optional[str] = None, 
                      district: Optional[str] = None,
                      risk_level: Optional[str] = None,
                      search: Optional[str] = None):
    from backend.tools import fpo_analytics
    return fpo_analytics.get_inventory_batches(page=page, page_size=page_size, 
                                              crop_name=crop_name, district=district,
                                              risk_level=risk_level, search=search)

@app.get("/api/fpo/market-prices")
def api_fpo_market_prices(crop_name: Optional[str] = None, market_name: Optional[str] = None):
    from backend.tools import fpo_analytics
    return fpo_analytics.get_market_intelligence(crop_name=crop_name, market_name=market_name)

@app.get("/api/fpo/logistics")
def api_fpo_logistics():
    from backend.tools import fpo_analytics
    return fpo_analytics.get_logistics_intelligence()

@app.get("/api/fpo/risks")
def api_fpo_risks(risk_level: Optional[str] = None):
    from backend.tools import fpo_analytics
    return fpo_analytics.get_risk_centre(risk_level=risk_level)

@app.get("/api/fpo/decisions")
def api_fpo_decisions():
    from backend.tools import fpo_analytics
    return fpo_analytics.get_decisions_scenarios()

@app.get("/api/fpo/datasources")
def api_fpo_datasources():
    from backend.tools import fpo_analytics
    return fpo_analytics.get_datasources_status()

@app.get("/api/fpo/filters")
def api_fpo_filters():
    from backend.tools import fpo_analytics
    return fpo_analytics.get_filter_options()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
