from __future__ import annotations

from zeroclaw_reachy_companion.audio.audio_io import record_until_enter


async def capture_utterance(stt_backend, vad_backend, *, input_device: str | None = None) -> str:  # noqa: ANN001
    """Capture one utterance using mock input or optional microphone audio."""
    if getattr(stt_backend, "name", "") == "mock":
        return (await stt_backend.listen_text()).strip()

    audio = await record_until_enter(input_device=input_device)
    if getattr(vad_backend, "name", "") != "disabled" and not vad_backend.contains_speech(audio):
        print("[audio] No speech detected.")
        return ""
    return (await stt_backend.transcribe(audio)).strip()

