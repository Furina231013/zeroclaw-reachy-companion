from __future__ import annotations

import asyncio
import queue
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContinuousListenConfig:
    """Energy-based continuous listening settings for local microphone input."""

    sample_rate: int = 16000
    block_duration_s: float = 0.05
    start_rms: float = 0.010
    stop_rms: float = 0.006
    min_speech_s: float = 0.35
    silence_s: float = 0.8
    max_utterance_s: float = 8.0
    pre_roll_s: float = 0.2


@dataclass
class ContinuousUtteranceSegmenter:
    """Collect one utterance from streaming audio chunks using simple RMS gates."""

    config: ContinuousListenConfig
    _recording: bool = False
    _recorded_chunks: list[Any] = field(default_factory=list)
    _pre_roll_chunks: list[Any] = field(default_factory=list)
    _recorded_samples: int = 0
    _voiced_samples: int = 0
    _silent_samples: int = 0

    def push(self, chunk: Any) -> Any | None:
        try:
            import numpy as np
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Continuous listening requires numpy.") from exc

        samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return None

        rms = float(np.sqrt(np.mean(np.square(samples))))
        if not self._recording:
            self._remember_pre_roll(samples)
            if rms >= self.config.start_rms:
                self._recording = True
                self._recorded_chunks = [*self._pre_roll_chunks, samples]
                self._recorded_samples = sum(len(item) for item in self._recorded_chunks)
                self._voiced_samples = samples.size
                self._silent_samples = 0
            return None

        self._recorded_chunks.append(samples)
        self._recorded_samples += samples.size
        if rms <= self.config.stop_rms:
            self._silent_samples += samples.size
        else:
            self._voiced_samples += samples.size
            self._silent_samples = 0

        utterance_s = self._recorded_samples / self.config.sample_rate
        voiced_s = self._voiced_samples / self.config.sample_rate
        silence_s = self._silent_samples / self.config.sample_rate
        if utterance_s >= self.config.max_utterance_s:
            return self._finish_recording()
        if voiced_s >= self.config.min_speech_s and silence_s >= self.config.silence_s:
            return self._finish_recording()
        return None

    def _remember_pre_roll(self, samples: Any) -> None:
        max_samples = int(self.config.pre_roll_s * self.config.sample_rate)
        if max_samples <= 0:
            self._pre_roll_chunks = []
            return
        self._pre_roll_chunks.append(samples)
        total = sum(len(item) for item in self._pre_roll_chunks)
        while self._pre_roll_chunks and total > max_samples:
            removed = self._pre_roll_chunks.pop(0)
            total -= len(removed)

    def _finish_recording(self) -> Any | None:
        import numpy as np

        chunks = self._recorded_chunks
        voiced_s = self._voiced_samples / self.config.sample_rate
        self.reset_recording()
        if voiced_s < self.config.min_speech_s:
            return None
        return np.concatenate(chunks).reshape(-1) if chunks else np.zeros(0, dtype=np.float32)

    def reset_recording(self) -> None:
        self._recording = False
        self._recorded_chunks = []
        self._recorded_samples = 0
        self._voiced_samples = 0
        self._silent_samples = 0


async def record_until_enter(*, sample_rate: int = 16000, input_device: str | None = None) -> Any:
    """Record microphone audio between two Enter presses using sounddevice."""
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Real microphone capture requires the optional audio dependencies.") from exc

    chunks: list[Any] = []

    def callback(indata, frames, time, status) -> None:  # noqa: ANN001
        if status:
            print(f"[audio] {status}")
        chunks.append(indata.copy())

    await asyncio.to_thread(input, "Press Enter to start recording...")
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=input_device,
        callback=callback,
    )
    with stream:
        await asyncio.to_thread(input, "Recording. Press Enter to stop...")
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks, axis=0).reshape(-1)


async def record_continuous_utterance(
    *,
    config: ContinuousListenConfig | None = None,
    input_device: str | None = None,
) -> Any:
    """Record one utterance from a continuous microphone stream."""
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Continuous microphone capture requires the optional audio dependencies.") from exc

    listen_config = config or ContinuousListenConfig()
    audio_queue: queue.Queue[Any] = queue.Queue()
    segmenter = ContinuousUtteranceSegmenter(listen_config)

    def callback(indata, frames, time, status) -> None:  # noqa: ANN001
        if status:
            print(f"[audio] {status}")
        audio_queue.put(indata.copy())

    blocksize = max(1, int(listen_config.sample_rate * listen_config.block_duration_s))
    print(
        "[listen] Waiting for speech "
        f"(start_rms={listen_config.start_rms:.4f}, stop_rms={listen_config.stop_rms:.4f})..."
    )
    stream = sd.InputStream(
        samplerate=listen_config.sample_rate,
        blocksize=blocksize,
        channels=1,
        dtype="float32",
        device=input_device,
        callback=callback,
    )
    with stream:
        while True:
            chunk = await asyncio.to_thread(audio_queue.get)
            utterance = segmenter.push(chunk)
            if utterance is not None:
                return np.asarray(utterance, dtype=np.float32).reshape(-1)
