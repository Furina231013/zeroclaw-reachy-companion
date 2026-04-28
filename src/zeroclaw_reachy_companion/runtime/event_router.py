from __future__ import annotations

from typing import Any

from zeroclaw_reachy_companion.providers import AgentCommand, ToolCallCommand
from zeroclaw_reachy_companion.runtime.events import CompanionEvent
from zeroclaw_reachy_companion.runtime.state import RuntimeState


CRY_CONFIDENCE_THRESHOLD = 0.65


def command_for_event(event: CompanionEvent | dict[str, Any], state: RuntimeState) -> AgentCommand:
    """Route a mock event to deterministic companion actions."""
    companion_event = CompanionEvent.from_value(event)

    if companion_event.type == "baby_cry_detected":
        return _baby_cry_command(companion_event)
    if companion_event.type == "danger_object_detected":
        return _danger_object_command(companion_event)
    if companion_event.type == "quiet_time_started":
        state.quiet_mode = True
        return AgentCommand(
            speak="Quiet time is on. I'll keep things soft and short.",
            tools=[ToolCallCommand("do_nothing", {"reason": "quiet time started"})],
            raw_text=companion_event.type,
        )

    return AgentCommand(
        speak=f"Event {companion_event.type} noted.",
        tools=[ToolCallCommand("do_nothing", {"reason": f"unsupported event: {companion_event.type}"})],
        raw_text=companion_event.type,
    )


def _baby_cry_command(event: CompanionEvent) -> AgentCommand:
    if event.confidence >= CRY_CONFIDENCE_THRESHOLD:
        return AgentCommand(
            speak="Cry event received. I'll soothe gently.",
            tools=[ToolCallCommand("soothe_baby", {"style": "gentle"})],
            raw_text=event.type,
        )

    return AgentCommand(
        speak="Low-confidence cry event noted. I'll stay calm.",
        tools=[ToolCallCommand("do_nothing", {"reason": "low-confidence cry event"})],
        raw_text=event.type,
    )


def _danger_object_command(event: CompanionEvent) -> AgentCommand:
    label = event.payload.get("label") or "object"
    label_text = str(label).strip()[:80] or "object"
    warning = f"Warning: {label_text} may be nearby. Please move it away safely."
    return AgentCommand(
        speak=warning,
        tools=[ToolCallCommand("speak", {"text": warning})],
        raw_text=event.type,
    )
