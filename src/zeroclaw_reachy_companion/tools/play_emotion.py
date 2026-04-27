from __future__ import annotations

from zeroclaw_reachy_companion.reachy.emotion import normalize_emotion
from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, require_string


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    emotion = normalize_emotion(require_string(args, "emotion", max_len=40))
    return ToolResult.ok(await context.reachy.play_emotion(emotion))


def tool() -> ToolDefinition:
    """Play a simple named emotion."""
    return ToolDefinition(
        name="play_emotion",
        description="Play a simple emotional expression such as gentle, happy, calm, sleepy, or excited.",
        parameters={
            "type": "object",
            "properties": {
                "emotion": {
                    "type": "string",
                    "description": "Emotion name, for example gentle, happy, calm, sleepy, or excited.",
                }
            },
            "required": ["emotion"],
        },
        handler=_handle,
    )

