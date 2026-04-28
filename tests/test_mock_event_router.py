from __future__ import annotations

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.text_chat_loop import ReachyCompanionRuntime

from helpers import run, tool_names


async def _create_runtime() -> ReachyCompanionRuntime:
    return await ReachyCompanionRuntime.create(AppConfig(reachy_mode="dry_run", llm_backend="mock"))


def _combined_text(result) -> str:  # noqa: ANN001
    outputs = " ".join(item.result.output for item in result.tools)
    return f"{result.final_text} {outputs}".lower()


def test_high_confidence_baby_cry_triggers_soothe_baby() -> None:
    async def scenario() -> None:
        runtime = await _create_runtime()
        try:
            result = await runtime.handle_event(
                {
                    "type": "baby_cry_detected",
                    "confidence": 0.92,
                    "source": "yamnet_mock",
                }
            )
            tools = tool_names(result)
            assert result.event_type == "baby_cry_detected"
            assert "soothe_baby" in tools
            assert "dance" not in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())


def test_low_confidence_baby_cry_does_not_force_soothing() -> None:
    async def scenario() -> None:
        runtime = await _create_runtime()
        try:
            result = await runtime.handle_event(
                {
                    "type": "baby_cry_detected",
                    "confidence": 0.30,
                    "source": "yamnet_mock",
                }
            )
            tools = tool_names(result)
            assert "soothe_baby" not in tools
            assert "dance" not in tools
            assert all(item.result.success for item in result.tools)
            assert len(result.final_text.split()) <= 20
        finally:
            await runtime.close()

    run(scenario())


def test_danger_object_detected_warns_without_photo_or_signal_claims() -> None:
    async def scenario() -> None:
        runtime = await _create_runtime()
        try:
            result = await runtime.handle_event(
                {
                    "type": "danger_object_detected",
                    "confidence": 0.88,
                    "source": "yolo_mock",
                    "payload": {"label": "scissors"},
                }
            )
            tools = tool_names(result)
            text = _combined_text(result)
            assert result.event_type == "danger_object_detected"
            assert result.final_text
            assert "scissors" in text
            assert "dance" not in tools
            assert "soothe_baby" not in tools
            assert "photo" not in text
            assert "signal" not in text
            assert "notification" not in text
            assert all(item.result.success for item in result.tools)
        finally:
            await runtime.close()

    run(scenario())


def test_quiet_mode_restrains_later_text_turn() -> None:
    async def scenario() -> None:
        runtime = await _create_runtime()
        try:
            event_result = await runtime.handle_event(
                {
                    "type": "quiet_time_started",
                    "confidence": 1.0,
                    "source": "mock",
                }
            )
            assert runtime.state.quiet_mode
            assert tool_names(event_result) == ["do_nothing"]

            result = await runtime.handle_text("Tell me something fun.", announce=True)
            tools = tool_names(result)
            assert "dance" not in tools
            assert "story_time" not in tools
            assert len(result.final_text.split()) <= 20
            assert all(item.result.success for item in result.tools)
        finally:
            await runtime.close()

    run(scenario())
