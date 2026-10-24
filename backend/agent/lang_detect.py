"""Shared language detection + TTS voice selection (stdlib only, no model calls).

Direct helper: picks the reply language for
`speak_lang` and matches it to an installed SAPI voice. Covers Hindi,
Marathi, Urdu, English, French and Spanish via script + keyword + accent
hints. Deterministic and offline-safe; never raises.
"""

import re

LANGS = {"hi", "mr", "ur", "en", "fr", "es"}

_DEV_RE = re.compile(r"[\u0900-\u097F]")
_URDU_RE = re.compile(r"[\u0600-\u06FF]")
_FR_ACCENT_RE = re.compile(r"[àâçéèêëîïôûùüÿœæ]", re.I)
_ES_ACCENT_RE = re.compile(r"[áéíóúüñ¿¡]", re.I)

_MR_HINT_RE = re.compile(
    r"\b(havaman|sanga|vinod|maskari|tumcha|tumch|tumhi|lakshat|thevin|kasa|kase|"
    r"kay|kuthe|kiti|aahes|aahe|aahat|mala|prahije|pahije|nako|hoc?ya)\b"
    r"|हवामान|विनोद|मस्करी|सांगा|तुमच|तुम्ही|लक्षात|कसं|कसे|काय|कुठे|किती|आहे|"
    r"आहेस|आहात|मला|पाहिजे",
    re.I,
)
_HI_HINT_RE = re.compile(
    r"\b(mausam|sunao|suna|batao|kitne|baje|samay|kya|kaun|kab|kahan|kaise|"
    r"kitna|awaz|badhao|ghatao|chutkula|tathya|aap|tum|namaste|shukriya|"
    r"dhanyavad|hindi|hinglish)\b"
    r"|मौसम|आवाज़|आवाज|सुनाओ|बताओ|कितने|समय|चुटकुला|तथ्य|नमस्ते|शुक्रिया|हिंदी",
    re.I,
)
_UR_HINT_RE = re.compile(
    r"\burdu\b|اردو|آپ|کیسے|ہیں|میں|بتاؤ|بتاو",
    re.I,
)
_FR_HINT_RE = re.compile(
    r"\bfrench\b|\bfran[çc]ais\b|\bbonjour\b|\bmerci\b|c'est|gar[çc]on",
    re.I,
)
_ES_HINT_RE = re.compile(
    r"\bspanish\b|\bespa[nñ]ol\b|\bhola\b|\bgracias\b|[¿¡]",
    re.I,
)


def _has(blob: str, rx) -> bool:
    try:
        return bool(rx.search(blob or ""))
    except Exception:
        return False


def detect_lang(text: str, prompt: str = "") -> str:
    """Return one of hi/mr/ur/en/fr/es. Never raises (defaults 'en')."""
    try:
        blob = f"{prompt or ''} {text or ''}"
        if not blob.strip():
            return "en"
        # Urdu: Arabic script or explicit Urdu hints win first.
        if _has(blob, _URDU_RE) or _has(blob, _UR_HINT_RE):
            return "ur"
        # French / Spanish hints and accents.
        if _has(blob, _FR_HINT_RE) or _has(blob, _FR_ACCENT_RE):
            # Spanish-specific markers take precedence on overlap.
            if _has(blob, _ES_HINT_RE) or _has(blob, _ES_ACCENT_RE):
                # Both present: explicit word hints decide.
                if re.search(r"\bspanish\b|\bespa[nñ]ol\b|\bhola\b|\bgracias\b", blob, re.I):
                    return "es"
                if re.search(r"\bfrench\b|\bfran[çc]ais\b|\bbonjour\b|\bmerci\b", blob, re.I):
                    return "fr"
                return "es" if _has(blob, _ES_ACCENT_RE) else "fr"
            return "fr"
        if _has(blob, _ES_HINT_RE) or _has(blob, _ES_ACCENT_RE):
            return "es"
        # Marathi markers beat the Hindi default for Devanagari text.
        if _has(blob, _MR_HINT_RE):
            return "mr"
        # Devanagari (or Hindi hints) without Marathi markers → Hindi.
        if _has(blob, _DEV_RE) or _has(blob, _HI_HINT_RE):
            return "hi"
        return "en"
    except Exception:
        return "en"


def prefer_marathi(text: str) -> bool:
    """True when Marathi markers are present (scheduler helper)."""
    try:
        return _has(text or "", _MR_HINT_RE)
    except Exception:
        return False


# LCID (hex string, e.g. SAPI "language" field) → lang code.
_LCID_LANG = {
    "439": "hi",  # Hindi
    "44e": "mr",  # Marathi
    "420": "ur",  # Urdu
    "409": "en",  # English (US)
    "809": "en",  # English (UK)
    "40c": "fr",  # French
    "40a": "es",  # Spanish
}

_LANG_NAME_HINTS = {
    "hi": ("hindi", "swara", "hemant", "kalpana", "madhur"),
    "mr": ("marathi",),
    "ur": ("urdu",),
    "en": ("english", "david", "zira", "mark", "hazel"),
    "fr": ("french", "fran", "hortense", "julie"),
    "es": ("spanish", "espa", "helena", "pablo", "sabina"),
}


def select_voice_for_lang(voices, lang: str):
    """Pick the best installed voice for `lang`.

    Prefers an LCID match, then a name hint, else None. Never raises.
    """
    try:
        if not voices or lang not in LANGS:
            return None
        want = (lang or "").lower()
        for v in voices:
            try:
                lcid = str((v or {}).get("language", "")).lower().lstrip("0") or "0"
                if _LCID_LANG.get(str((v or {}).get("language", "")).lower()) == want:
                    return v
            except Exception:
                continue
        hints = _LANG_NAME_HINTS.get(want, ())
        for v in voices:
            try:
                name = str((v or {}).get("name", "")).lower()
                if any(h in name for h in hints):
                    return v
            except Exception:
                continue
        return None
    except Exception:
        return None
