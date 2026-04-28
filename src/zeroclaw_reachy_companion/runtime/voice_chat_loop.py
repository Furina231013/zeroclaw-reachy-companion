from __future__ import annotations

import asyncio
from dataclasses import dataclass

from zeroclaw_reachy_companion.audio import create_stt_backend, create_tts_backend, create_vad_backend
from zeroclaw_reachy_companion.audio.audio_io import ContinuousListenConfig
from zeroclaw_reachy_companion.audio.speech_loop import capture_utterance
from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.reachy.speech_output import clean_spoken_text
from zeroclaw_reachy_companion.runtime.text_chat_loop import AgentTurnResult, ReachyCompanionRuntime


EXIT_PHRASES = {"/exit", "exit", "quit", "stop listening", "exit voice mode"}
PAUSE_PHRASES = {"pause listening", "pause voice mode", "take a break"}


@dataclass
class VoiceFallbackHarness:
    """Small test harness for voice fallback without real audio devices."""

    runtime: ReachyCompanionRuntime
    tts: object

    async def run_single_mock_turn(self, text: str, *, announce: bool = False) -> AgentTurnResult:
        result = await self.runtime.handle_text(text, announce=announce)
        if hasattr(self.tts, "speak"):
            for tts_text in tts_texts_for_turn(result):
                await self.tts.speak(tts_text)
        return result


async def create_voice_harness(config: AppConfig) -> VoiceFallbackHarness:
    runtime = await ReachyCompanionRuntime.create(config)
    tts = create_tts_backend(config.tts_backend, output_device=config.audio_output_device)
    return VoiceFallbackHarness(runtime=runtime, tts=tts)


async def run_voice_loop(config: AppConfig) -> None:
    runtime = await ReachyCompanionRuntime.create(config)
    vad = create_vad_backend(config.vad_backend)
    stt = create_stt_backend(
        config.stt_backend,
        model_size=config.stt_model,
        language=config.stt_language,
        initial_prompt=config.stt_initial_prompt,
        hotwords=config.stt_hotwords,
    )
    tts = create_tts_backend(config.tts_backend, output_device=config.audio_output_device)
    continuous_config = ContinuousListenConfig(
        start_rms=config.continuous_start_rms,
        stop_rms=config.continuous_stop_rms,
        silence_s=config.continuous_silence_s,
        min_speech_s=config.continuous_min_speech_s,
        max_utterance_s=config.continuous_max_utterance_s,
    )

    try:
        fallback = config.vad_backend == "disabled" and config.stt_backend == "mock" and config.tts_backend == "print"
        print(f"Profile: {runtime.profile.name}")
        print(f"Reachy mode: {config.reachy_mode}")
        print(f"Voice mode: {'fallback' if fallback else 'local-audio'}")
        print(f"Listen mode: {config.listen_mode}")
        if config.listen_mode == "continuous":
            print("Say 'stop listening' to exit, 'pause listening' to pause, or press Ctrl+C.")
        else:
            print("Type /exit to quit.")

        while True:
            text = await capture_utterance(
                stt,
                vad,
                input_device=config.audio_input_device,
                listen_mode=config.listen_mode,
                continuous_config=continuous_config,
            )
            if not text:
                continue
            normalized_text = _normalize_voice_command(text)
            if _matches_voice_command(normalized_text, EXIT_PHRASES):
                break
            if _matches_voice_command(normalized_text, PAUSE_PHRASES):
                print("[voice] Paused. Press Enter to resume, or Ctrl+C to exit.")
                await asyncio.to_thread(input)
                print("[voice] Resumed.")
                continue
            result = await runtime.handle_text(text, announce=True)
            for tts_text in tts_texts_for_turn(result):
                print(f"[TTS] {tts_text}")
                await tts.speak(tts_text)
    finally:
        await runtime.close()


def tts_texts_for_turn(result: AgentTurnResult) -> list[str]:
    """Return assistant and tool speech texts that should be sent to the voice backend."""
    texts: list[str] = []
    seen: set[str] = set()
    candidates = [result.final_text]
    candidates.extend(item.result.spoken_text or "" for item in result.tools)

    for candidate in candidates:
        cleaned = clean_spoken_text(candidate)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        texts.append(cleaned)
    return texts


def _normalize_voice_command(text: str) -> str:
    return " ".join(text.lower().strip().strip(".!?").split())


def _matches_voice_command(text: str, phrases: set[str]) -> bool:
    if text in phrases:
        return True
    return any(len(phrase.split()) > 1 and phrase in text for phrase in phrases)
