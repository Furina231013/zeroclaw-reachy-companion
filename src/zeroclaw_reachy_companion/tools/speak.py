from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, require_string


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    text = require_string(args, "text", max_len=700)
    return ToolResult.ok(await context.reachy.speak(text))


def tool() -> ToolDefinition:
    """Speak short text aloud through Reachy/TTS output."""
    return ToolDefinition(
        name="speak",
        description="Speak a short child-friendly sentence aloud. Use for direct verbal robot responses.",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Short text for the robot to say aloud.",
                }
            },
            "required": ["text"],
        },
        handler=_handle,
    )

