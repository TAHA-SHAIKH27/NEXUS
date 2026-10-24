"""Shared Marathi detection (keyword + Devanagari hints, stdlib only)."""

import re

_MR_WORDS = re.compile(
    r"\b(havaman|sanga|vinod|maskari|tumcha|tumch|lakshat|thevin|baghoon|yetो|"
    r"kasa|kay|kuthe|kiti)\b|हवामान|विनोद|मस्करी|सांगा|तुमच|लक्षात|कसं|काय|कुठे|किती",
    re.I,
)


def is_marathi(text: str) -> bool:
    try:
        return bool(_MR_WORDS.search(text or ""))
    except Exception:
        return False
