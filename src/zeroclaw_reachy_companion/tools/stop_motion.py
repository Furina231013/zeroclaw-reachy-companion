from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    return ToolResult.ok(await context.reachy.stop_motion())


def tool() -> ToolDefinition:
    """Stop current robot motion."""
    return ToolDefinition(
        name="stop_motion",
        description="Stop the current movement, dance, or queued motion.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_handle,
    )

