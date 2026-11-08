"""engine.language
Utility functions for detecting the script and language of a given text.
Supports basic detection of Telugu script, Latin script, and mixed content.
Also provides a stub for dialect identification based on a registry.

The implementation is deliberately lightweight and does not rely on external dependencies, making it suitable for offline execution and unit testing.
"""


import re
from typing import Literal

# Unicode range for Telugu script: U+0C00 – U+0C7F
TELUGU_SCRIPT_RE = re.compile(r"[\u0C00-\u0C7F]")

# Latin alphabet letters
LATIN_SCRIPT_RE = re.compile(r"[A-Za-z]")

def detect_script(text: str) -> Literal["telugu", "latin", "mixed", "none"]:
    """Return the dominant script of *text*.

    - ``telugu`` – contains at least one Telugu character and no Latin letters.
    - ``latin`` – contains Latin letters and no Telugu characters.
    - ``mixed`` – contains both Telugu and Latin characters.
    - ``none`` – contains neither (e.g., punctuation or numbers only).
    """
    has_telugu = bool(TELUGU_SCRIPT_RE.search(text))
    has_latin = bool(LATIN_SCRIPT_RE.search(text))
    if has_telugu and has_latin:
        return "mixed"
    if has_telugu:
        return "telugu"
    if has_latin:
        return "latin"
    return "none"

def detect_language(text: str) -> Literal["telugu", "english", "mixed", "unknown"]:
    """High-level language determination based on script detection and dialect analysis.

    - ``telugu`` – pure Telugu script.
    - ``english`` – Latin script without Romanized Telugu tokens.
    - ``mixed`` – both scripts present, or Latin script containing Romanized Telugu tokens.
    - ``unknown`` – cannot determine (no recognizable characters).
    """
    script = detect_script(text)
    if script == "telugu":
        return "telugu"
    if script == "latin":
        if identify_dialect(text) == "romanized":
            return "mixed"
        return "english"
    if script == "mixed":
        return "mixed"
    return "unknown"

# ---------------------------------------------------------------------------
# Dialect registry – extensible map of dialect descriptors and simple regexes.
# ---------------------------------------------------------------------------

_DIALECTS = [
    {
        "name": "classical",
        "description": "Classical literary Telugu used in historic texts.",
        "patterns": [r"(?:^|\s|[^\w\u0C00-\u0C7F])(దుర్గాపురాణ|శైవశాస్ర్త్ర)(?:$|\s|[^\w\u0C00-\u0C7F])"],
    },
    {
        "name": "vyavaharika",
        "description": "Modern spoken Telugu (vyavahārika).",
        "patterns": [r"(?:^|\s|[^\w\u0C00-\u0C7F])(చెప్పుద్దాం|ఎయితే)(?:$|\s|[^\w\u0C00-\u0C7F])"],
    },
    {
        "name": "romanized",
        "description": "Telugu written using Latin characters (Romaṇized).",
        "patterns": [r"\b(naaku|emi|chaala)\b"],
    },
]

def identify_dialect(text: str) -> str | None:
    """Return the name of a matching dialect or ``None`` if unknown.

    The function iterates over the registry and returns the first dialect whose
    pattern matches the supplied *text*.  It is deliberately simple – more
    sophisticated classifiers can replace this stub without changing the public
    API.
    """
    for dialect in _DIALECTS:
        for pat in dialect["patterns"]:
            if re.search(pat, text, flags=re.IGNORECASE):
                return dialect["name"]
    return None
