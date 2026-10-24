"""Shared reply styling — smalltalk + human polish (no LLM calls)."""

import re

_SMALLTALK = [
    (re.compile(r"\b(hello|hi|hey|namaste)\b", re.I),
     "Hello — good to hear from you. What are we working on?"),
    (re.compile(r"\bthank|thanks|shukriya|dhanyavad\b", re.I),
     "Anytime, sir."),
    (re.compile(r"\bgood (morning|afternoon|evening|night)\b", re.I),
     "Good day to you too, sir. What shall we do?"),
    (re.compile(r"\bhow are you\b", re.I),
     "Running cool and thinking fast, thanks for asking. How can I help?"),
    (re.compile(r"\bwho are you\b", re.I),
     "I'm Nexus — your desktop right hand."),
    (re.compile(r"\bbye|goodbye|see you\b", re.I),
     "I'll be right here whenever you need me."),
]


def smalltalk(prompt: str) -> str | None:
    """Return a canned smalltalk reply, or None when not applicable."""
    try:
        pl = (prompt or "").strip().lower()
        if not pl or len(pl) > 120:
            return None
        for rx, reply in _SMALLTALK:
            if rx.search(pl):
                return reply
    except Exception:
        pass
    return None


def humanize_normal(tool: str, gemini_speak: str, result: str, prompt: str) -> str:
    """Prefer the tool result (facts) over framing; never raises."""
    try:
        base = (gemini_speak or result or "").strip()
        return base or "I have completed your request, sir."
    except Exception:
        return "I have completed your request, sir."


def humanize_error(kind: str, message: str) -> str:
    try:
        return (message or "Something went wrong, sir.").strip()
    except Exception:
        return "Something went wrong, sir."
