"""Voice system — TTS queue and command triage.

Provides a bounded text-to-speech queue (muting
drops pending speech), mute state, voice queries, and a minimal command
processor for the native voice service endpoint (/api/voice/command).
"""

import queue
import threading
from enum import Enum, auto
from typing import Any, Dict, Optional

_MAX_QUEUE = 20


class TTSState(Enum):
    IDLE = auto()
    SPEAKING = auto()
    INTERRUPTED = auto()


_voice_system: Optional["VoiceSystem"] = None
_voice_lock = threading.Lock()


def get_voice_system() -> "VoiceSystem":
    """Get the singleton voice system instance."""
    global _voice_system
    with _voice_lock:
        if _voice_system is None:
            _voice_system = VoiceSystem()
    return _voice_system


def get_command_processor() -> "VoiceCommandProcessor":
    """Get a command processor for voice-recognized commands."""
    return VoiceCommandProcessor()


def is_muted() -> bool:
    return get_voice_system().is_muted()


def set_muted(muted: bool) -> bool:
    return get_voice_system().set_muted(muted)


def speak(text: str, priority: int = 0, interrupt: bool = True,
          lang: Optional[str] = None) -> bool:
    return get_voice_system().speak(text, priority=priority,
                                    interrupt=interrupt, lang=lang)


class VoiceCommandProcessor:
    """Minimal voice command triage.

    Classifies a transcript as an interruption / new command and lets the
    HTTP layer route it.
    """

    def set_controller(self, controller: Any) -> None:
        """Compatibility no-op kept so older callers do not break."""
        return None

    async def process_command(self, prompt: str, state: Any = None) -> Dict[str, Any]:
        text = (prompt or "").strip()
        if not text:
            return {"status": "error", "message": "Empty prompt."}
        tl = text.lower()
        if any(w in tl for w in ("stop", "cancel", "interrupt", "quiet",
                                 "shut up", "enough", "hold on", "wait")):
            return {"status": "interrupted"}
        # Everything else is a fresh command for /api/command.
        return {"status": "new_command"}


class VoiceSystem:
    """Bounded TTS queue façade (logs instead of driving SAPI here)."""

    def __init__(self):
        self._state = TTSState.IDLE
        self._muted = False
        self._tts_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._sapi_ready = threading.Event()
        self._sapi_ready.set()
        self._available_voices: list = []
        self._active_voice_id = ""

    def speak(self, text: str, priority: int = 0, interrupt: bool = True,
              lang: Optional[str] = None) -> bool:
        """Queue speech. Returns False when muted (speech dropped)."""
        if self._muted:
            return False
        try:
            print(f"[TTS] (priority={priority}, interrupt={interrupt}): {(text or '')[:120]}")
        except Exception:
            pass
        item = {"text": text, "priority": priority,
                "interrupt": interrupt, "lang": lang}
        try:
            if self._tts_queue.qsize() >= _MAX_QUEUE:
                try:
                    self._tts_queue.get_nowait()
                except Exception:
                    pass
            self._tts_queue.put_nowait(item)
        except Exception:
            pass
        self._state = TTSState.SPEAKING
        return True

    def clear_queue(self) -> None:
        """Drop all queued speech."""
        try:
            while True:
                self._tts_queue.get_nowait()
        except Exception:
            pass
        self._state = TTSState.IDLE
        return None

    def interrupt(self) -> bool:
        """Interrupt current TTS playback."""
        self.clear_queue()
        self._state = TTSState.INTERRUPTED
        self._state = TTSState.IDLE
        return True

    def is_speaking(self) -> bool:
        return self._state == TTSState.SPEAKING

    def get_state(self) -> TTSState:
        return self._state

    def is_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> bool:
        """Mute/unmute. Muting drops queued announcements; returns new state."""
        self._muted = bool(muted)
        if self._muted:
            self.clear_queue()
        return self._muted

    def get_available_voices(self) -> list:
        return list(self._available_voices)
