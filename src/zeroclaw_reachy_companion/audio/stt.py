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

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "auto",
        compute_type: str = "int8",
        language: str | None = "en",
        initial_prompt: str = "",
        hotwords: str = "",
    ):
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Faster-Whisper requires the optional audio dependencies.") from exc

        self.model_size = model_size
        self.language = language or None
        self.initial_prompt = initial_prompt.strip() or None
        self.hotwords = hotwords.strip() or None
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def transcribe(self, audio: Any, sample_rate: int = 16000) -> str:
        def _run() -> str:
            segments, _ = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=5,
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt,
                hotwords=self.hotwords,
                vad_filter=False,
            )
            return " ".join(segment.text for segment in segments).strip()

        return await asyncio.to_thread(_run)


def create_stt_backend(
    name: str,
    *,
    model_size: str = "base.en",
    language: str | None = "en",
    initial_prompt: str = "",
    hotwords: str = "",
):
    backend = (name or "mock").lower()
    if backend == "mock":
        return MockSTT()
    if backend == "faster-whisper":
        return FasterWhisperSTT(
            model_size=model_size,
            language=language,
            initial_prompt=initial_prompt,
            hotwords=hotwords,
        )
    raise ValueError(f"Unsupported STT backend: {name}")
