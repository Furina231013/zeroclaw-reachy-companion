from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    return ToolResult.ok(await context.reachy.stop_motion())


def tool() -> ToolDefinition:
    """Stop current dance motion."""
    return ToolDefinition(
        name="stop_dance",
        description="Stop the current dance move and clear active motion, matching the original app's stop_dance tool.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_handle,
    )

