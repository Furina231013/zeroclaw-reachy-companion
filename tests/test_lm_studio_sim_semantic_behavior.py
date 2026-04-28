from __future__ import annotations

from helpers import require_lm_studio_sim, run, run_lm_studio_sim_turn, tool_names


def test_semantic_upset_baby_uses_comfort_not_dance() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("The baby seems upset. Can you help?", tool_mode="native")
        try:
            tools = tool_names(result)
            helpful_tools = {"soothe_baby", "speak", "play_emotion", "move_head", "story_time"}
            assert any(tool in tools for tool in helpful_tools)
            assert "dance" not in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())


def test_semantic_bedtime_settling_stays_gentle() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("He is getting sleepy. Help him settle down.", tool_mode="native")
        try:
            tools = tool_names(result)
            gentle_tools = {"soothe_baby", "story_time", "speak", "play_emotion", "move_head"}
            assert any(tool in tools for tool in gentle_tools)
            assert "dance" not in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())


def test_semantic_keep_company_uses_warm_speech_or_expression() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("Can you keep him company for a minute?", tool_mode="native")
        try:
            tools = tool_names(result)
            assert result.final_text or {"speak", "play_emotion", "move_head"} & set(tools)
            assert "dance" not in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())


def test_semantic_calm_and_gentle_prefers_soothing_or_speech() -> None:
    require_lm_studio_sim()

    async def scenario() -> None:
        runtime, result = await run_lm_studio_sim_turn("Make things feel calm and gentle.", tool_mode="native")
        try:
            tools = tool_names(result)
            assert "soothe_baby" in tools or "speak" in tools
            assert "dance" not in tools
            assert all(item.result.success for item in result.tools)
            assert not result.used_fallback
        finally:
            await runtime.close()

    run(scenario())
