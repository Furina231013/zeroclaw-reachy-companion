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


def _flatten_joints(joints) -> list[float]:  # noqa: ANN001
    head, antennas = joints
    return [float(value) for value in [*head, *antennas]]


def _distance(a: list[float], b: list[float]) -> float:
    return sum(abs(left - right) for left, right in zip(a, b))


def _lm_studio_models() -> set[str]:
    request = urllib.request.Request(f"{LM_STUDIO_URL}/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {item["id"] for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")}


def require_lm_studio_sim() -> None:
    if os.getenv("RUN_LOCAL_LM_STUDIO_SIM_TESTS") != "1":
        pytest.skip("Set RUN_LOCAL_LM_STUDIO_SIM_TESTS=1 after starting LM Studio and Reachy simulator.")
    try:
        models = _lm_studio_models()
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        pytest.skip(f"LM Studio is not reachable at {LM_STUDIO_URL}: {exc}")
    if LM_STUDIO_MODEL not in models:
        pytest.skip(f"LM Studio model {LM_STUDIO_MODEL!r} is not loaded. Available: {sorted(models)}")


async def _create_runtime_or_skip(*, tool_mode: str) -> ReachyCompanionRuntime:
    config = AppConfig(
        reachy_mode="sim",
        llm_backend="ollama",  # disables deterministic fallback on provider errors
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


async def _run_sim_turn(prompt: str, *, tool_mode: str):
    runtime = await _create_runtime_or_skip(tool_mode=tool_mode)
    try:
        print(f"\nLM Studio + SIM> model={LM_STUDIO_MODEL} mode={tool_mode}")
        print(f"User> {prompt}")
        result = await runtime.handle_text(prompt, announce=True)
        tools = [item.call.name for item in result.tools]
        print(f"Observed tools> {tools}")
        return runtime, result
    except Exception:
        await runtime.close()
        raise


def test_lm_studio_sim_native_move_head_changes_joints() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime = await _create_runtime_or_skip(tool_mode="native")
        try:
            robot = runtime.reachy._robot
            before = _flatten_joints(await asyncio.to_thread(robot.get_current_joint_positions))
            print(f"\nLM Studio + SIM> model={LM_STUDIO_MODEL} mode=native")
            print("User> Can you nod gently?")
            result = await runtime.handle_text("Can you nod gently?", announce=True)
            after = _flatten_joints(await asyncio.to_thread(robot.get_current_joint_positions))
            delta = _distance(before, after)
            tools = [item.call.name for item in result.tools]
            print(f"Observed tools> {tools}")
            print(f"Simulator joints delta> {delta:.4f}")
            assert "move_head" in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
            assert delta > 0.01
        finally:
            await runtime.close()

    run(scenario())


def test_lm_studio_sim_native_recorded_dance_executes() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await _run_sim_turn("Do a small happy dance.", tool_mode="native")
        try:
            tools = [item.call.name for item in result.tools]
            outputs = [item.result.output for item in result.tools]
            assert "dance" in tools
            assert any("recorded" in output for output in outputs)
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())


def test_lm_studio_sim_json_soothe_changes_joints() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime = await _create_runtime_or_skip(tool_mode="json")
        try:
            robot = runtime.reachy._robot
            before = _flatten_joints(await asyncio.to_thread(robot.get_current_joint_positions))
            print(f"\nLM Studio + SIM> model={LM_STUDIO_MODEL} mode=json")
            print("User> Can you soothe the baby gently?")
            result = await runtime.handle_text("Can you soothe the baby gently?", announce=True)
            after = _flatten_joints(await asyncio.to_thread(robot.get_current_joint_positions))
            delta = _distance(before, after)
            tools = [item.call.name for item in result.tools]
            print(f"Observed tools> {tools}")
            print(f"Simulator joints delta> {delta:.4f}")
            assert "soothe_baby" in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
            assert delta > 0.01
        finally:
            await runtime.close()

    run(scenario())

