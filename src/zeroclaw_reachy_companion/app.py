from __future__ import annotations

import argparse
import asyncio
import logging

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime import run_text_loop, run_voice_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("ZeroClaw Reachy Companion")
    parser.add_argument("--mode", choices=["text", "voice"], default=None)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--reachy-mode", choices=["dry_run", "sim", "real"], default=None)
    parser.add_argument("--reachy-host", default=None)
    parser.add_argument("--reachy-port", type=int, default=None)
    parser.add_argument("--local-llm-url", default=None)
    parser.add_argument("--local-llm-model", default=None)
    parser.add_argument("--llm", dest="llm_backend", choices=["auto", "ollama", "mock"], default=None)
    parser.add_argument("--tool-mode", choices=["json", "native"], default=None)
    parser.add_argument("--vad", dest="vad_backend", choices=["disabled", "silero"], default=None)
    parser.add_argument("--stt", dest="stt_backend", choices=["mock", "faster-whisper"], default=None)
    parser.add_argument("--stt-model", default=None)
    parser.add_argument("--stt-language", default=None)
    parser.add_argument("--stt-initial-prompt", default=None)
    parser.add_argument("--stt-hotwords", default=None)
    parser.add_argument("--tts", dest="tts_backend", choices=["print", "kokoro"], default=None)
    parser.add_argument("--listen-mode", choices=["enter", "continuous"], default=None)
    parser.add_argument("--continuous-start-rms", type=float, default=None)
    parser.add_argument("--continuous-stop-rms", type=float, default=None)
    parser.add_argument("--continuous-silence-s", type=float, default=None)
    parser.add_argument("--continuous-min-speech-s", type=float, default=None)
    parser.add_argument("--continuous-max-utterance-s", type=float, default=None)
    parser.add_argument("--audio-input-device", default=None)
    parser.add_argument("--audio-output-device", default=None)
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--max-tool-turns", type=int, default=None)
    return parser


async def async_main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = AppConfig.from_args(args)
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    if config.mode == "voice":
        await run_voice_loop(config)
    else:
        await run_text_loop(config)


def main(argv: list[str] | None = None) -> None:
    try:
        asyncio.run(async_main(argv))
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print(f"Startup failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
