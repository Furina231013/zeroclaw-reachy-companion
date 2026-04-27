from __future__ import annotations

import asyncio

import yaml

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.text_chat_loop import ReachyCompanionRuntime


def run(coro):
    return asyncio.run(coro)


def load_manifest() -> dict:
    with open("scenarios/reachy_phase12.yaml", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_simple_phase12_scenarios_with_mock_agent() -> None:
    manifest = load_manifest()

    async def scenario() -> None:
        runtime = await ReachyCompanionRuntime.create(AppConfig(reachy_mode="dry_run", llm_backend="mock"))
        try:
            for case in manifest["simple_cases"]:
                result = await runtime.handle_text(case["prompt"], announce=False)
                actual = [item.call.name for item in result.tools]
                assert actual == case["companion_expected_tools"], case["id"]
        finally:
            await runtime.close()

    run(scenario())


def test_complex_phase12_scenarios_with_mock_agent() -> None:
    manifest = load_manifest()

    async def scenario() -> None:
        runtime = await ReachyCompanionRuntime.create(AppConfig(reachy_mode="dry_run", llm_backend="mock"))
        try:
            for case in manifest["complex_cases"]:
                for turn in case["turns"]:
                    result = await runtime.handle_text(turn["prompt"], announce=False)
                    actual = [item.call.name for item in result.tools]
                    assert actual == turn["companion_expected_tools"], case["id"]
        finally:
            await runtime.close()

    run(scenario())

