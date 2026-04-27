from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = Path(__file__).resolve().parent / "profiles"


def load_dotenv(path: Path | None = None) -> None:
    """Load a small .env file without overriding existing environment values."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _first_value(cli_value: Any, env_key: str, default: Any) -> Any:
    if cli_value not in (None, ""):
        return cli_value
    value = os.getenv(env_key)
    if value not in (None, ""):
        return value
    return default


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration merged from .env and CLI flags."""

    mode: str = "text"
    profile: str = "baby_companion"
    reachy_mode: str = "dry_run"
    reachy_host: str = "localhost"
    reachy_port: int | None = None
    local_llm_url: str = "http://localhost:11434"
    local_llm_model: str = "ministral-3:3b"
    llm_backend: str = "auto"
    tool_mode: str = "json"
    vad_backend: str = "disabled"
    stt_backend: str = "mock"
    tts_backend: str = "print"
    audio_input_device: str | None = None
    audio_output_device: str | None = None
    log_level: str = "INFO"
    max_tool_turns: int = 4
    allow_heuristic_fallback: bool = True

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "AppConfig":
        load_dotenv()
        return cls(
            mode=_first_value(getattr(args, "mode", None), "MODE", "text"),
            profile=_first_value(getattr(args, "profile", None), "PROFILE", "baby_companion"),
            reachy_mode=_first_value(getattr(args, "reachy_mode", None), "REACHY_MODE", "dry_run"),
            reachy_host=_first_value(getattr(args, "reachy_host", None), "REACHY_HOST", "localhost"),
            reachy_port=_optional_int(_first_value(getattr(args, "reachy_port", None), "REACHY_PORT", None)),
            local_llm_url=_first_value(getattr(args, "local_llm_url", None), "LOCAL_LLM_URL", "http://localhost:11434"),
            local_llm_model=_first_value(
                getattr(args, "local_llm_model", None),
                "LOCAL_LLM_MODEL",
                "ministral-3:3b",
            ),
            llm_backend=_first_value(getattr(args, "llm_backend", None), "LLM_BACKEND", "auto"),
            tool_mode=_first_value(getattr(args, "tool_mode", None), "TOOL_MODE", "json"),
            vad_backend=_first_value(getattr(args, "vad_backend", None), "VAD_BACKEND", "disabled"),
            stt_backend=_first_value(getattr(args, "stt_backend", None), "STT_BACKEND", "mock"),
            tts_backend=_first_value(getattr(args, "tts_backend", None), "TTS_BACKEND", "print"),
            audio_input_device=_first_value(getattr(args, "audio_input_device", None), "AUDIO_INPUT_DEVICE", None),
            audio_output_device=_first_value(getattr(args, "audio_output_device", None), "AUDIO_OUTPUT_DEVICE", None),
            log_level=_first_value(getattr(args, "log_level", None), "LOG_LEVEL", "INFO"),
            max_tool_turns=int(_first_value(getattr(args, "max_tool_turns", None), "MAX_TOOL_TURNS", 4)),
            allow_heuristic_fallback=_bool_env("ALLOW_HEURISTIC_FALLBACK", True),
        )


@dataclass(frozen=True)
class Profile:
    """Loaded companion profile."""

    name: str
    description: str
    system_prompt: str


def _parse_minimal_yaml(text: str) -> dict[str, str]:
    """Tiny fallback parser for the profile YAML used by this project."""
    result: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "|":
            i += 1
            block: list[str] = []
            while i < len(lines):
                block_line = lines[i]
                if block_line and not block_line.startswith((" ", "\t")):
                    break
                block.append(block_line[2:] if block_line.startswith("  ") else block_line.lstrip())
                i += 1
            result[key] = "\n".join(block).rstrip() + "\n"
            continue
        result[key] = value.strip('"').strip("'")
        i += 1
    return result


def load_profile(name: str = "baby_companion") -> Profile:
    path = PROFILE_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        data = yaml.safe_load(text) or {}
    except Exception:
        data = _parse_minimal_yaml(text)

    return Profile(
        name=str(data.get("name") or name),
        description=str(data.get("description") or ""),
        system_prompt=str(data.get("system_prompt") or ""),
    )

