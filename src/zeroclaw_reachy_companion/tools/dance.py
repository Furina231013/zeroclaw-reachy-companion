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
    """Start a dance only for explicit playful or celebratory requests."""
    return ToolDefinition(
        name="dance",
        description=(
            "Use only when the user explicitly asks for dancing, celebration, or playful movement. "
            "Do not use during bedtime, quiet time, calming, upset baby, or factual explanation."
        ),
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
