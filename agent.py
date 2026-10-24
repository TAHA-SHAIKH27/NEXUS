import os
import json
import re
import time
import urllib.request
import urllib.error
import base64
import io
from datetime import datetime
from system_ops import list_files, read_file


def _smart_network_message(exc: BaseException | None = None, mode: str = "chat") -> str:
    """Diagnose live connectivity and explain it Nexus-style.

    Replaces the old single generic "network issue communicating with my
    neural processors" line. Distinguishes Wi-Fi off / router-no-internet /
    DNS failure / Google-unreachable / brief wobble. Never raises — falls
    back to the legacy generic line if diagnostics themselves fail.
    """
    try:
        from net_diagnostics import build_nexus_message, get_connectivity_snapshot
        snap = get_connectivity_snapshot()
        return build_nexus_message(snap, exc, mode=mode)
    except Exception:
        return "I encountered a network issue communicating with my neural processors, sir. Please check your internet connection and API key."


# Offline response templates — used when Gemini is unavailable.
OFFLINE_RESPONSES = {
    "hello": "Hello — good to hear from you. What are we working on?",
    "hi": "Hey — I'm here and listening. What's the plan?",
    "how are you": "Running cool and thinking fast, thanks for asking. How can I help?",
    "who are you": "I'm Nexus — your desktop right hand. I run apps, files, mail, reminders and research, and I talk you through it all as I go.",
    "status": "All green on my side — CPU, memory and disk are sitting comfortably. Want the exact numbers?",
    "goodbye": "I'll be right here whenever you need me.",
}


# ===== CONVERSATION HISTORY (session, persisted to disk) =====
# Stores the last N conversation messages to give Gemini context (5 turns = 10 messages).
# Persisted to backend/data/session_memory.json so chat/command/vision/document context
# survives backend restarts, and restored on startup.
MAX_HISTORY = 10
conversation_history = []  # list of {"role": "user"|"assistant", "text": str}


def _session_history_path() -> str:
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend", "data"))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "session_memory.json")


def _load_session_history() -> list:
    """Restore the last session's conversation history from disk (best-effort)."""
    try:
        with open(_session_history_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            valid = [e for e in data if isinstance(e, dict) and e.get("role") in ("user", "assistant")]
            return valid[-MAX_HISTORY:]
    except (OSError, ValueError, TypeError):
        pass
    return []


def _save_session_history() -> None:
    """Persist the current session conversation history atomically."""
    tmp = None
    try:
        path = _session_history_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(conversation_history, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(tmp, path)
        except OSError:
            last_exc = None
            for _ in range(5):
                try:
                    os.replace(tmp, path)
                    break
                except OSError as exc:
                    last_exc = exc
                    time.sleep(0.15)
            else:
                if last_exc is not None:
                    raise last_exc
    except (OSError, ValueError, TypeError):
        pass
    finally:
        if tmp is not None:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass


conversation_history = _load_session_history()


def add_to_history(role: str, text: str):
    """Add a message to conversation history, keeping it bounded to last 5 queries (10 messages)."""
    global conversation_history
    conversation_history.append({"role": role, "text": text})
    if len(conversation_history) > MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]
    _save_session_history()


def clear_history():
    """Clear the in-memory session history and remove its persisted file."""
    global conversation_history
    conversation_history = []
    try:
        os.remove(_session_history_path())
    except OSError:
        pass


def get_history_text() -> str:
    """Format conversation history for the AI prompt."""
    if not conversation_history:
        return "No previous conversation."
    
    lines = []
    for entry in conversation_history:
        prefix = "User" if entry["role"] == "user" else "Nexus"
        lines.append(f"{prefix}: {entry['text']}")
    return "\n".join(lines)


# HF image generation models (fallback list when live lookup fails).
_HF_IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
]


def generate_image_huggingface(prompt: str, hf_api_key: str, save_name: str = "") -> dict:
    """Generate an image using huggingface_hub's InferenceClient and save it to work_files."""
    if not hf_api_key:
        return {"status": "error", "message": "No Hugging Face API key configured. Please add it in Settings."}

    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        return {"status": "error", "message": "huggingface_hub isn't installed, sir. Run: pip install huggingface_hub"}

    client = InferenceClient(provider="auto", api_key=hf_api_key)

    last_error = None
    image_bytes = None
    for model_id in _HF_IMAGE_MODELS:
        try:
            pil_image = client.text_to_image(prompt, model=model_id)
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            image_bytes = buf.getvalue()
            break
        except Exception as e:
            last_error = e
            continue

    if image_bytes is None:
        err_str = str(last_error) if last_error else "unknown error"
        if "401" in err_str or "403" in err_str or "invalid" in err_str.lower():
            return {"status": "error", "message": "Your Hugging Face API key appears to be invalid. Please check it in Settings."}
        if "503" in err_str or "loading" in err_str.lower():
            return {"status": "error", "message": "The image model is currently loading. Please try again in a moment, sir."}
        return {"status": "error", "message": f"Image generation failed: {err_str[:200]}"}

    # Determine filename
    if not save_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_name = f"generated_{timestamp}.png"
    elif not save_name.endswith(('.png', '.jpg', '.jpeg')):
        save_name += ".png"

    # Save to the in-project work_files/images so the FILES/GALLERY view shows it
    # and it persists across restarts.
    work_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "work_files"))
    img_dir = os.path.join(work_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    save_path = os.path.join(img_dir, save_name)
    with open(save_path, "wb") as f:
        f.write(image_bytes)

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    return {
        "status": "success",
        "message": f"Image generated and saved as images/{save_name}",
        "filename": f"images/{save_name}",
        "image_base64": b64_image
    }