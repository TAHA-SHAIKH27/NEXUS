"""Shared Hindi detection (keyword + Devanagari hints, stdlib only)."""

import re

_HI_WORDS = re.compile(
    r"\b(mausam|sunao|suna|batao|kitne|baje|samay|kya|kaun|kab|kahan|kaise|kitna|"
    r"awaz|badhao|ghatao|chutkula|jok|tathya|aap|tum|namaste|shukriya|dhanyavad)\b"
    r"|मौसम|आवाज़|आवाज|सुनाओ|बताओ|कितने|समय|चुटकुला|जोक|नमस्ते|शुक्रिया",
    re.I,
)


def is_hindi(text: str) -> bool:
    try:
        return bool(_HI_WORDS.search(text or ""))
    except Exception:
        return False
