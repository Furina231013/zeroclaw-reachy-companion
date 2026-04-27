from __future__ import annotations

import asyncio
from typing import Any


class MockSTT:
    name = "mock"

    async def listen_text(self, prompt: str = "Mock STT input> ") -> str:
        return await asyncio.to_thread(input, prompt)

    async def transcribe(self, audio: Any, sample_rate: int = 16000) -> str:
        return ""


class FasterWhisperSTT:
    name = "faster-whisper"

    def __init__(self, model_size: str = "base.en", device: str = "auto", compute_type: str = "int8"):
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Faster-Whisper requires the optional audio dependencies.") from exc

        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def transcribe(self, audio: Any, sample_rate: int = 16000) -> str:
        def _run() -> str:
            segments, _ = self.model.transcribe(audio, beam_size=5)
            return " ".join(segment.text for segment in segments).strip()

        return await asyncio.to_thread(_run)


def create_stt_backend(name: str):
    backend = (name or "mock").lower()
    if backend == "mock":
        return MockSTT()
    if backend == "faster-whisper":
        return FasterWhisperSTT()
    raise ValueError(f"Unsupported STT backend: {name}")

