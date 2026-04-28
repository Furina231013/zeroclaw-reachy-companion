from __future__ import annotations

import asyncio
import os

import pytest

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.reachy import ReachyClient
from zeroclaw_reachy_companion.runtime.text_chat_loop import ReachyCompanionRuntime
from zeroclaw_reachy_companion.runtime.voice_chat_loop import create_voice_harness, tts_texts_for_turn
from zeroclaw_reachy_companion.tools import create_tool_registry


def run(coro):
    return asyncio.run(coro)


def test_reachy_client_dry_run_initializes() -> None:
    async def scenario() -> None:
        client = ReachyClient(mode="dry_run")
        await client.connect()
        assert client.actions == ["[DRY-RUN] connect"]
        await client.close()

    run(scenario())


def test_speak_tool_dry_run_returns_success() -> None:
    async def scenario() -> None:
        client = ReachyClient(mode="dry_run")
        registry = create_tool_registry(client)
        result = await registry.execute("speak", {"text": "Hello from smoke test."})
        assert result.success
        assert "spoke:" in result.output
        assert result.spoken_text == "Hello from smoke test."

    run(scenario())


def test_move_head_parameter_validation() -> None:
    async def scenario() -> None:
        client = ReachyClient(mode="dry_run")
        registry = create_tool_registry(client)
        ok = await registry.execute("move_head", {"yaw": 10, "pitch": -5, "roll": 0, "duration": 1.2})
        bad = await registry.execute("move_head", {"yaw": 1000})
        assert ok.success
        assert not bad.success
        assert "yaw" in (bad.error or "")

    run(scenario())


@pytest.mark.skipif(
    os.getenv("RUN_RECORDED_LIBRARY_TESTS") != "1",
    reason="Recorded move libraries are optional runtime dependencies.",
)
def test_recorded_library_aliases_resolve() -> None:
    client = ReachyClient(mode="sim")
    assert client._resolve_dance_name("happy") == "groovy_sway_and_roll"
    assert client._resolve_dance_name("gentle") == "side_to_side_sway"
    assert client._resolve_emotion_name("calm") == "calming1"
    assert client._resolve_emotion_name("happy") == "cheerful1"


def test_voice_fallback_single_turn_no_audio_dependencies() -> None:
    async def scenario() -> None:
        config = AppConfig(
            mode="voice",
            reachy_mode="dry_run",
            llm_backend="mock",
            vad_backend="disabled",
            stt_backend="mock",
            tts_backend="print",
        )
        harness = await create_voice_harness(config)
        try:
            result = await harness.run_single_mock_turn("Can you soothe the baby?", announce=False)
            assert result.response
            assert result.tools[0].call.name == "soothe_baby"
        finally:
            await harness.runtime.close()

    run(scenario())


def test_voice_turn_tts_includes_tool_spoken_text() -> None:
    async def scenario() -> None:
        config = AppConfig(mode="voice", reachy_mode="dry_run", llm_backend="mock", tts_backend="print")
        runtime = await ReachyCompanionRuntime.create(config)
        try:
            result = await runtime.handle_text("Can you soothe the baby?", announce=False)
            texts = tts_texts_for_turn(result)
            assert "Of course. I'll be gentle." in texts
            assert any("slow, soft breath" in text for text in texts)
        finally:
            await runtime.close()

    run(scenario())


def test_text_runtime_mock_story_turn() -> None:
    async def scenario() -> None:
        config = AppConfig(reachy_mode="dry_run", llm_backend="mock")
        runtime = await ReachyCompanionRuntime.create(config)
        try:
            result = await runtime.handle_text("Tell me a short bedtime story.", announce=False)
            assert result.response
            assert [item.call.name for item in result.tools] == ["play_emotion", "story_time"]
        finally:
            await runtime.close()

    run(scenario())
