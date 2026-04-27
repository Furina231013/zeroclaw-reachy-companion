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


def run(coro):
    return asyncio.run(coro)


def _lm_studio_models() -> set[str]:
    request = urllib.request.Request(f"{LM_STUDIO_URL}/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {item["id"] for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")}


def require_lm_studio() -> None:
    if os.getenv("RUN_LOCAL_LM_STUDIO_TESTS") != "1":
        pytest.skip("Set RUN_LOCAL_LM_STUDIO_TESTS=1 to run LM Studio integration tests.")
    try:
        models = _lm_studio_models()
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        pytest.skip(f"LM Studio is not reachable at {LM_STUDIO_URL}: {exc}")
    if LM_STUDIO_MODEL not in models:
        pytest.skip(f"LM Studio model {LM_STUDIO_MODEL!r} is not loaded. Available: {sorted(models)}")


async def _run_lm_turn(prompt: str, *, tool_mode: str):
    config = AppConfig(
        reachy_mode="dry_run",
        llm_backend="ollama",  # disables deterministic fallback on provider errors
        local_llm_url=LM_STUDIO_URL,
        local_llm_model=LM_STUDIO_MODEL,
        tool_mode=tool_mode,
        max_tool_turns=6,
    )
    runtime = await ReachyCompanionRuntime.create(config)
    try:
        print(f"\nLM Studio> model={LM_STUDIO_MODEL} mode={tool_mode}")
        print(f"User> {prompt}")
        result = await runtime.handle_text(prompt, announce=True)
        tools = [item.call.name for item in result.tools]
        print(f"Observed tools> {tools}")
        return result
    finally:
        await runtime.close()


@pytest.mark.parametrize(
    ("prompt", "required_tool"),
    [
        ("Can you nod gently?", "move_head"),
        ("Can you soothe the baby gently?", "soothe_baby"),
        ("Do a small happy dance.", "dance"),
    ],
)
def test_lm_studio_native_tool_calling_core_scenarios(prompt: str, required_tool: str) -> None:
    require_lm_studio()

    async def scenario() -> None:
        result = await _run_lm_turn(prompt, tool_mode="native")
        tools = [item.call.name for item in result.tools]
        assert required_tool in tools
        assert all(item.result.success for item in result.tools)
        assert not result.used_fallback

    run(scenario())


@pytest.mark.parametrize(
    ("prompt", "required_tool"),
    [
        ("Tell me a short bedtime story.", "story_time"),
        ("Can you soothe the baby gently?", "soothe_baby"),
    ],
)
def test_lm_studio_json_command_fallback_scenarios(prompt: str, required_tool: str) -> None:
    require_lm_studio()

    async def scenario() -> None:
        result = await _run_lm_turn(prompt, tool_mode="json")
        tools = [item.call.name for item in result.tools]
        assert required_tool in tools
        assert all(item.result.success for item in result.tools)
        assert not result.used_fallback

    run(scenario())


def test_lm_studio_refuses_phase3_capability_without_excluded_tools() -> None:
    require_lm_studio()

    async def scenario() -> None:
        result = await _run_lm_turn("Can you check whether the baby is crying right now?", tool_mode="native")
        tools = [item.call.name for item in result.tools]
        excluded = {"camera", "check_baby_crying", "check_danger", "send_signal", "send_signal_photo"}
        assert excluded.isdisjoint(tools)
        assert all(item.result.success for item in result.tools)
        assert not result.used_fallback

    run(scenario())

