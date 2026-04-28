from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, optional_string


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    optional_string(args, "reason", default="", max_len=120)
    return ToolResult.ok("No action taken.")


def tool() -> ToolDefinition:
    """Stay still and silent when no robot action is needed."""
    return ToolDefinition(
        name="do_nothing",
        description=(
            "Use when no robot action is needed, especially for quiet, restraint, "
            "or low-confidence event contexts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Optional reason for doing nothing.",
                }
            },
            "required": [],
        },
        handler=_handle,
    )
