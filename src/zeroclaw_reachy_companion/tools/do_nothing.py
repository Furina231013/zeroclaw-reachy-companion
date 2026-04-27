from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, optional_string


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    reason = optional_string(args, "reason", default="just chilling", max_len=120) or "just chilling"
    return ToolResult.ok(f"doing nothing: {reason}")


def tool() -> ToolDefinition:
    """Stay still and silent."""
    return ToolDefinition(
        name="do_nothing",
        description="Choose to stay still and silent. Use when no physical or spoken response is needed.",
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

