from __future__ import annotations

import asyncio
from typing import Any


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

