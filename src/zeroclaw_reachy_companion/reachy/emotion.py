from __future__ import annotations


KNOWN_EMOTIONS = {
    "gentle",
    "happy",
    "calm",
    "sad",
    "sleepy",
    "surprised",
    "excited",
}


def normalize_emotion(emotion: str) -> str:
    value = (emotion or "").strip().lower().replace(" ", "_")
    if not value:
        raise ValueError("emotion is required")
    if len(value) > 40:
        raise ValueError("emotion is too long")
    return value

