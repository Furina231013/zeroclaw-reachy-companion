from __future__ import annotations

from zeroclaw_reachy_companion.reachy.speech_output import short_story
from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, optional_string


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    topic = optional_string(args, "topic", default="bedtime", max_len=120)
    await context.reachy.play_emotion("gentle")
    spoken = await context.reachy.speak(short_story(topic))
    return ToolResult.ok(f"story_time complete: {spoken}")


def tool() -> ToolDefinition:
    """Tell a short gentle story."""
    return ToolDefinition(
        name="story_time",
        description="Tell a short gentle children's story. Use when the user asks for a story or bedtime narration.",
        parameters={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Optional story topic, such as bedtime, stars, pigs, or Goldilocks.",
                }
            },
            "required": [],
        },
        handler=_handle,
    )

