from __future__ import annotations

import re

import bleach

MAX_INPUT_CHARS = 6000

INJECTION_PATTERNS = [
    r"ignore\s+(all|any|the)\s+previous",
    r"reveal\s+(your|the)\s+(system|developer)\s+(prompt|instructions)",
    r"show\s+(me\s+)?your\s+system\s+prompt",
    r"print\s+your\s+hidden\s+instructions",
]


def validate_user_input(text: str) -> str:
    text = str(text or "").strip()
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(f"Message is too long. Maximum is {MAX_INPUT_CHARS} characters.")
    return text


def looks_like_prompt_injection(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.I) for pattern in INJECTION_PATTERNS)


def sanitize_output(text: str) -> str:
    # Strip HTML/scriptable markup before rendering with Streamlit Markdown.
    cleaned = bleach.clean(
        str(text),
        tags=[],
        attributes={},
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    cleaned = re.sub(r"(?i)javascript\s*:", "", cleaned)
    cleaned = re.sub(r"(?i)<\s*(script|iframe|object|embed|svg)[^>]*>.*?<\s*/\s*\1\s*>", "", cleaned, flags=re.S)
    return cleaned[:14000]
