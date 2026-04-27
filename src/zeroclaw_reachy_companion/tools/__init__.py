from __future__ import annotations

from zeroclaw_reachy_companion.reachy import ReachyClient
from zeroclaw_reachy_companion.tools import (
    dance,
    do_nothing,
    move_head,
    play_emotion,
    soothe_baby,
    speak,
    stop_dance,
    stop_emotion,
    stop_motion,
    story_time,
)
from zeroclaw_reachy_companion.tools.base import ToolContext, ToolDefinition, ToolRegistry, ToolResult


def create_tool_registry(reachy: ReachyClient) -> ToolRegistry:
    tools: list[ToolDefinition] = [
        speak.tool(),
        move_head.tool(),
        play_emotion.tool(),
        story_time.tool(),
        soothe_baby.tool(),
        dance.tool(),
        stop_motion.tool(),
        stop_dance.tool(),
        stop_emotion.tool(),
        do_nothing.tool(),
    ]
    return ToolRegistry(ToolContext(reachy=reachy), tools)


__all__ = [
    "ToolContext",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    "create_tool_registry",
]
