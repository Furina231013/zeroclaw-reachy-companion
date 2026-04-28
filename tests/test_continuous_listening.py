from __future__ import annotations

import pytest

from zeroclaw_reachy_companion.audio.audio_io import ContinuousListenConfig, ContinuousUtteranceSegmenter
from zeroclaw_reachy_companion.runtime.voice_chat_loop import EXIT_PHRASES, PAUSE_PHRASES, _matches_voice_command, _normalize_voice_command


np = pytest.importorskip("numpy")


def _config() -> ContinuousListenConfig:
    return ContinuousListenConfig(
        sample_rate=10,
        start_rms=0.20,
        stop_rms=0.05,
        min_speech_s=0.30,
        silence_s=0.20,
        max_utterance_s=2.0,
        pre_roll_s=0.10,
    )


def test_continuous_segmenter_returns_one_utterance_after_speech_then_silence() -> None:
    segmenter = ContinuousUtteranceSegmenter(_config())
    chunks = [
        np.zeros(1, dtype=np.float32),
        np.zeros(1, dtype=np.float32),
        np.ones(1, dtype=np.float32) * 0.5,
        np.ones(1, dtype=np.float32) * 0.5,
        np.ones(1, dtype=np.float32) * 0.5,
        np.ones(1, dtype=np.float32) * 0.5,
        np.zeros(1, dtype=np.float32),
        np.zeros(1, dtype=np.float32),
    ]

    result = None
    for chunk in chunks:
        result = segmenter.push(chunk)
        if result is not None:
            break

    assert result is not None
    assert result.size >= 6


def test_continuous_segmenter_ignores_silence_only() -> None:
    segmenter = ContinuousUtteranceSegmenter(_config())
    for _ in range(12):
        assert segmenter.push(np.zeros(1, dtype=np.float32)) is None


def test_continuous_segmenter_discards_short_noise_burst() -> None:
    segmenter = ContinuousUtteranceSegmenter(_config())
    chunks = [
        np.ones(1, dtype=np.float32) * 0.6,
        np.zeros(1, dtype=np.float32),
        np.zeros(1, dtype=np.float32),
        np.zeros(1, dtype=np.float32),
    ]

    for chunk in chunks:
        assert segmenter.push(chunk) is None


def test_voice_command_normalization_for_exit_and_pause() -> None:
    assert _normalize_voice_command("Stop listening.") == "stop listening"
    assert _normalize_voice_command("  Pause   listening! ") == "pause listening"
    assert _matches_voice_command("please stop listening now", EXIT_PHRASES)
    assert _matches_voice_command("pause listening please", PAUSE_PHRASES)
