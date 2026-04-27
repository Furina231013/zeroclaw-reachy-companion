from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import (
    ToolContext,
    ToolDefinition,
    ToolResult,
    number_arg,
    optional_string,
)


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    style = optional_string(args, "style", default="gentle", max_len=50) or "gentle"
    duration = number_arg(args, "duration", default=5.0, min_value=0.5, max_value=30.0)
    return ToolResult.ok(await context.reachy.dance(style=style, duration=duration))


def tool() -> ToolDefinition:
    """Start a short dance or rhythmic expressive motion."""
    return ToolDefinition(
        name="dance",
        description="Do a short expressive dance or rhythmic motion. Use for dance, celebration, or playful movement.",
        parameters={
            "type": "object",
            "properties": {
                "style": {"type": "string", "description": "Dance style, for example gentle, happy, or playful."},
                "duration": {"type": "number", "description": "Approximate duration in seconds, 0.5 to 30."},
            },
            "required": [],
        },
        handler=_handle,
    )

