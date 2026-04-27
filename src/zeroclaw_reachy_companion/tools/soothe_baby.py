from __future__ import annotations

from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolResult, optional_string


SOOTHING_LINES = {
    "gentle": "Shhh, it's okay. I'm here with you. Let's take a slow, soft breath.",
    "sleepy": "Shhh, little one. The room is calm, and it is time to rest.",
    "cheerful": "I'm right here. We can be calm together, one tiny smile at a time.",
}


async def _handle(context: ToolContext, args: dict) -> ToolResult:
    style = optional_string(args, "style", default="gentle", max_len=40) or "gentle"
    style = style.lower().replace(" ", "_")
    line = SOOTHING_LINES.get(style, SOOTHING_LINES["gentle"])
    await context.reachy.play_emotion("calm")
    await context.reachy.move_head(yaw=0, pitch=-5, roll=0, duration=2.0)
    spoken = await context.reachy.speak(line)
    return ToolResult.ok(f"soothe_baby complete: {spoken}")


def tool() -> ToolDefinition:
    """Soothe with calm speech and gentle motion."""
    return ToolDefinition(
        name="soothe_baby",
        description="Soothe or comfort with a calm expression, gentle head motion, and a short reassuring line.",
        parameters={
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "description": "Soothing style: gentle, sleepy, or cheerful.",
                }
            },
            "required": [],
        },
        handler=_handle,
    )

