from __future__ import annotations

import asyncio
import os

import pytest

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.text_chat_loop import ReachyCompanionRuntime


def run(coro):
    return asyncio.run(coro)


def _flatten_joints(joints) -> list[float]:  # noqa: ANN001
    head, antennas = joints
    return [float(value) for value in [*head, *antennas]]


def _distance(a: list[float], b: list[float]) -> float:
    return sum(abs(left - right) for left, right in zip(a, b))


@pytest.mark.skipif(
    os.getenv("RUN_REACHY_SIM_TESTS") != "1",
    reason="Start reachy-mini-daemon --sim --no-media --headless and set RUN_REACHY_SIM_TESTS=1.",
)
def test_agent_move_head_changes_simulator_joints() -> None:
    async def scenario() -> None:
        runtime = await ReachyCompanionRuntime.create(AppConfig(reachy_mode="sim", llm_backend="mock"))
        try:
            robot = runtime.reachy._robot
            before = _flatten_joints(await asyncio.to_thread(robot.get_current_joint_positions))
            result = await runtime.handle_text("Can you nod gently?", announce=False)
            after = _flatten_joints(await asyncio.to_thread(robot.get_current_joint_positions))
            assert [item.call.name for item in result.tools] == ["move_head", "move_head"]
            assert _distance(before, after) > 0.01
        finally:
            await runtime.close()

    run(scenario())


@pytest.mark.skipif(
    os.getenv("RUN_REACHY_SIM_TESTS") != "1",
    reason="Start reachy-mini-daemon --sim --no-media --headless and set RUN_REACHY_SIM_TESTS=1.",
)
def test_agent_dance_and_stop_execute_on_simulator() -> None:
    async def scenario() -> None:
        runtime = await ReachyCompanionRuntime.create(AppConfig(reachy_mode="sim", llm_backend="mock"))
        try:
            dance = await runtime.handle_text("Do a small happy dance.", announce=False)
            stop = await runtime.handle_text("Stop moving.", announce=False)
            assert [item.call.name for item in dance.tools] == ["dance"]
            assert [item.call.name for item in stop.tools] == ["stop_motion"]
            assert all(item.result.success for item in [*dance.tools, *stop.tools])
        finally:
            await runtime.close()

    run(scenario())

