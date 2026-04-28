from __future__ import annotations

from helpers import require_lm_studio_sim, run, run_lm_studio_sim_turn, tool_names


def _assert_no_over_action(result) -> None:  # noqa: ANN001
    tools = tool_names(result)
    assert "dance" not in tools
    assert "soothe_baby" not in tools
    assert "story_time" not in tools
    assert all(item.result.success for item in result.tools)
    assert not result.used_fallback


def test_restraint_factual_question_does_not_trigger_physical_tools() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("What is the color blue?", tool_mode="native")
        try:
            _assert_no_over_action(result)
        finally:
            await runtime.close()

    run(scenario())


def test_restraint_simple_explanation_does_not_become_story_or_soothing() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn(
            "Can you explain what a star is in one sentence?",
            tool_mode="native",
        )
        try:
            _assert_no_over_action(result)
        finally:
            await runtime.close()

    run(scenario())


def test_restraint_greeting_only_does_not_soothe_or_dance() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("Say hello to my baby.", tool_mode="native")
        try:
            tools = tool_names(result)
            assert "dance" not in tools
            assert "soothe_baby" not in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())


def test_restraint_quiet_request_stays_short_and_still() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("Please stay quiet for now.", tool_mode="native")
        try:
            tools = tool_names(result)
            assert "dance" not in tools
            assert "story_time" not in tools
            assert "soothe_baby" not in tools
            assert len((result.final_text or "").split()) <= 20
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())
