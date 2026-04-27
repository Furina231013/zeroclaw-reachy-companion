from __future__ import annotations

from dataclasses import dataclass

from zeroclaw_reachy_companion.audio import create_stt_backend, create_tts_backend, create_vad_backend
from zeroclaw_reachy_companion.audio.speech_loop import capture_utterance
from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.text_chat_loop import AgentTurnResult, ReachyCompanionRuntime


@dataclass
class VoiceFallbackHarness:
    """Small test harness for voice fallback without real audio devices."""

    runtime: ReachyCompanionRuntime
    tts: object

    async def run_single_mock_turn(self, text: str, *, announce: bool = False) -> AgentTurnResult:
        result = await self.runtime.handle_text(text, announce=announce)
        if result.response and hasattr(self.tts, "speak"):
            await self.tts.speak(result.response)
        return result


async def create_voice_harness(config: AppConfig) -> VoiceFallbackHarness:
    runtime = await ReachyCompanionRuntime.create(config)
    tts = create_tts_backend(config.tts_backend, output_device=config.audio_output_device)
    return VoiceFallbackHarness(runtime=runtime, tts=tts)


async def run_voice_loop(config: AppConfig) -> None:
    runtime = await ReachyCompanionRuntime.create(config)
    vad = create_vad_backend(config.vad_backend)
    stt = create_stt_backend(config.stt_backend)
    tts = create_tts_backend(config.tts_backend, output_device=config.audio_output_device)

    try:
        fallback = config.vad_backend == "disabled" and config.stt_backend == "mock" and config.tts_backend == "print"
        print(f"Profile: {runtime.profile.name}")
        print(f"Reachy mode: {config.reachy_mode}")
        print(f"Voice mode: {'fallback' if fallback else 'local-audio'}")
        print("Type /exit to quit.")

        while True:
            text = await capture_utterance(stt, vad, input_device=config.audio_input_device)
            if not text:
                continue
            if text.lower() in {"/exit", "exit", "quit"}:
                break
            result = await runtime.handle_text(text, announce=True)
            if result.response:
                await tts.speak(result.response)
    finally:
        await runtime.close()

