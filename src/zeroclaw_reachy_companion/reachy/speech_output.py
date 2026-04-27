from __future__ import annotations

import re


def clean_spoken_text(text: str) -> str:
    """Remove common markdown and expressive markers before TTS."""
    cleaned = re.sub(r"\[(HAPPY|STORY|SAD|CALM|GENTLE)\]", "", text, flags=re.IGNORECASE)
    cleaned = cleaned.replace("**", "").replace("*", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def short_story(topic: str | None = None) -> str:
    topic_text = (topic or "bedtime").strip().lower()
    if "pig" in topic_text:
        return (
            "Once upon a time, three little pigs built homes. The strongest home kept them safe, "
            "and they learned that careful work can feel very cozy."
        )
    if "gold" in topic_text:
        return (
            "Goldilocks found three bowls, three chairs, and three beds. She learned to be gentle "
            "with other people's homes, then hurried back to her own warm bed."
        )
    return (
        "Once upon a time, a little star watched over a sleepy robot. The robot blinked softly, "
        "listened to the quiet night, and dreamed of kind adventures."
    )

