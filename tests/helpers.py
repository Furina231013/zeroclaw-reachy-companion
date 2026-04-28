from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request

import pytest

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.text_chat_loop import ReachyCompanionRuntime


LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-vl-8b")


def run(coro):  # noqa: ANN001
    return asyncio.run(coro)


def tool_names(result) -> list[str]:  # noqa: ANN001
    return [item.call.name for item in result.tools]


def require_lm_studio_sim() -> None:
    if os.getenv("RUN_LOCAL_LM_STUDIO_SIM_TESTS") != "1":
        pytest.skip("Set RUN_LOCAL_LM_STUDIO_SIM_TESTS=1 after starting LM Studio and Reachy simulator.")
    try:
        models = _lm_studio_models()
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        pytest.skip(f"LM Studio is not reachable at {LM_STUDIO_URL}: {exc}")
    if LM_STUDIO_MODEL not in models:
        pytest.skip(f"LM Studio model {LM_STUDIO_MODEL!r} is not loaded. Available: {sorted(models)}")


async def create_lm_studio_sim_runtime_or_skip(*, tool_mode: str = "native") -> ReachyCompanionRuntime:
    config = AppConfig(
        reachy_mode="sim",
        llm_backend="ollama",
        local_llm_url=LM_STUDIO_URL,
        local_llm_model=LM_STUDIO_MODEL,
        tool_mode=tool_mode,
        max_tool_turns=6,
    )
    try:
        return await ReachyCompanionRuntime.create(config)
    except Exception as exc:
        pytest.skip(
            "Reachy simulator daemon is not reachable. Start it with: "
            "uv run mjpython .venv/bin/reachy-mini-daemon --sim --no-media --log-level INFO "
            f"({type(exc).__name__}: {exc})"
        )


async def run_lm_studio_sim_turn(prompt: str, *, tool_mode: str = "native"):
    runtime = await create_lm_studio_sim_runtime_or_skip(tool_mode=tool_mode)
    try:
        print(f"\nLM Studio + SIM> model={LM_STUDIO_MODEL} mode={tool_mode}")
        print(f"User> {prompt}")
        result = await runtime.handle_text(prompt, announce=True)
        print(f"Observed tools> {tool_names(result)}")
        return runtime, result
    except Exception:
        await runtime.close()
        raise


def _lm_studio_models() -> set[str]:
    request = urllib.request.Request(f"{LM_STUDIO_URL}/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {item["id"] for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")}
