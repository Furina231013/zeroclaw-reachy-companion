from __future__ import annotations

from typing import Any


class DisabledVAD:
    name = "disabled"

    def contains_speech(self, audio: Any, sample_rate: int = 16000) -> bool:
        return True


class SileroVAD:
    name = "silero"

    def __init__(self, threshold: float = 0.5):
        try:
            import numpy as np
            import torch
            from silero_vad import load_silero_vad
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Silero VAD requires the optional audio dependencies.") from exc

        self._np = np
        self._torch = torch
        self._model = load_silero_vad(onnx=False)
        self.threshold = threshold

    def contains_speech(self, audio: Any, sample_rate: int = 16000) -> bool:
        samples = self._np.asarray(audio, dtype=self._np.float32).reshape(-1)
        if samples.size == 0:
            return False
        chunk_size = 512 if sample_rate == 16000 else 256
        with self._torch.no_grad():
            for start in range(0, samples.size, chunk_size):
                chunk = samples[start : start + chunk_size]
                if chunk.size < chunk_size:
                    break
                probability = self._model(self._torch.from_numpy(chunk), sample_rate).item()
                if probability > self.threshold:
                    return True
        return False


def create_vad_backend(name: str):
    backend = (name or "disabled").lower()
    if backend == "disabled":
        return DisabledVAD()
    if backend == "silero":
        return SileroVAD()
    raise ValueError(f"Unsupported VAD backend: {name}")
