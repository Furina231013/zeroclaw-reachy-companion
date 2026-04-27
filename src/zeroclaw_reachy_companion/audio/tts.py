from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

from zeroclaw_reachy_companion.reachy.speech_output import clean_spoken_text


class PrintTTS:
    name = "print"

    async def speak(self, text: str) -> str:
        cleaned = clean_spoken_text(text)
        if cleaned:
            print(f"[TTS-PRINT] {cleaned}")
        return cleaned


class KokoroTTS:
    name = "kokoro"

    def __init__(self, output_device: str | None = None, model_path: str = "kokoro-v0_19.onnx", voices_path: str = "voices.npz"):
        try:
            import numpy as np
            import sounddevice as sd
            from huggingface_hub import hf_hub_download
            from kokoro_onnx import Kokoro
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Kokoro TTS requires the optional audio dependencies.") from exc

        self._np = np
        self._sd = sd
        self.output_device = output_device
        model = Path(model_path)
        voices = Path(voices_path)
        if not model.exists():
            revision = "e9d173129d407bf1378c402aba163de4dde2615e"
            model_path = hf_hub_download(
                repo_id="hexgrad/Kokoro-82M",
                filename="kokoro-v0_19.onnx",
                local_dir=".",
                revision=revision,
            )
        if not voices.exists():
            urlretrieve(
                "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                voices_path,
            )
        self.kokoro = Kokoro(model_path, voices_path)

    async def speak(self, text: str) -> str:
        cleaned = clean_spoken_text(text)
        if not cleaned:
            return ""

        def _run() -> None:
            samples, sample_rate = self.kokoro.create(cleaned, voice="af_sarah", speed=1.0, lang="en-us")
            self._sd.play(samples.astype(self._np.float32), sample_rate, device=self.output_device)
            self._sd.wait()

        await asyncio.to_thread(_run)
        return cleaned


def create_tts_backend(name: str, *, output_device: str | None = None):
    backend = (name or "print").lower()
    if backend == "print":
        return PrintTTS()
    if backend == "kokoro":
        return KokoroTTS(output_device=output_device)
    raise ValueError(f"Unsupported TTS backend: {name}")
