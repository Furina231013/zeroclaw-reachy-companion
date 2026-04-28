from __future__ import annotations

from zeroclaw_reachy_companion.reachy.motion import validate_head_pose
from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, number_arg


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    yaw = number_arg(args, "yaw", default=0.0, min_value=-60.0, max_value=60.0)
    pitch = number_arg(args, "pitch", default=0.0, min_value=-60.0, max_value=60.0)
    roll = number_arg(args, "roll", default=0.0, min_value=-60.0, max_value=60.0)
    duration = number_arg(args, "duration", default=1.0, min_value=0.1, max_value=10.0)
    validate_head_pose(yaw, pitch, roll, duration)
    return ToolResult.ok(await context.reachy.move_head(yaw=yaw, pitch=pitch, roll=roll, duration=duration))


def tool() -> ToolDefinition:
    """Move Reachy Mini's head by compact yaw/pitch/roll degrees."""
    return ToolDefinition(
        name="move_head",
        description=(
            "Use for subtle nods, greetings, or gentle expression. "
            "Avoid large motion during quiet, bedtime, or calming contexts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "yaw": {"type": "number", "description": "Left/right head turn in degrees, -60 to 60."},
                "pitch": {"type": "number", "description": "Up/down nod in degrees, -60 to 60."},
                "roll": {"type": "number", "description": "Side tilt in degrees, -60 to 60."},
                "duration": {"type": "number", "description": "Motion duration in seconds, 0.1 to 10."},
            },
            "required": [],
        },
        handler=_handle,
    )
