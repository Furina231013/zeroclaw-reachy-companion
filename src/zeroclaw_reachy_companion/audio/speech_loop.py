from __future__ import annotations

from zeroclaw_reachy_companion.audio.audio_io import ContinuousListenConfig, record_continuous_utterance, record_until_enter


def _audio_summary(audio, sample_rate: int = 16000) -> str:  # noqa: ANN001
    try:
        import numpy as np

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return "duration=0.00s rms=0.0000 peak=0.0000"
        duration = samples.size / sample_rate
        rms = float(np.sqrt(np.mean(np.square(samples))))
        peak = float(np.max(np.abs(samples)))
        return f"duration={duration:.2f}s rms={rms:.4f} peak={peak:.4f}"
    except Exception:
        return "summary unavailable"


async def capture_utterance(  # noqa: ANN001
    stt_backend,
    vad_backend,
    *,
    input_device: str | None = None,
    listen_mode: str = "enter",
    continuous_config: ContinuousListenConfig | None = None,
) -> str:
    """Capture one utterance using mock input or optional microphone audio."""
    if getattr(stt_backend, "name", "") == "mock":
        return (await stt_backend.listen_text()).strip()

    if listen_mode == "continuous":
        audio = await record_continuous_utterance(config=continuous_config, input_device=input_device)
    else:
        audio = await record_until_enter(input_device=input_device)

    print(f"[audio] {_audio_summary(audio)}")
    if getattr(vad_backend, "name", "") != "disabled" and not vad_backend.contains_speech(audio):
        print("[audio] No speech detected.")
        return ""
    text = (await stt_backend.transcribe(audio)).strip()
    print(f"[ASR] {text or '<empty>'}")
    return text
