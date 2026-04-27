from __future__ import annotations

from zeroclaw_reachy_companion.config import load_profile
from zeroclaw_reachy_companion.providers.local_llm import parse_json_command


def test_baby_companion_profile_loads() -> None:
    profile = load_profile("baby_companion")
    assert profile.name == "baby_companion"
    assert "Do not claim to see the room" in profile.system_prompt
    assert "Do not claim to detect crying" in profile.system_prompt


def test_json_command_fallback_parses_speak_and_move_head() -> None:
    command = parse_json_command(
        """
        {
          "speak": "I will nod gently.",
          "tools": [
            {
              "name": "move_head",
              "arguments": {
                "yaw": 0,
                "pitch": -8,
                "roll": 0,
                "duration": 0.6
              }
            }
          ]
        }
        """
    )
    assert command.speak == "I will nod gently."
    assert len(command.tools) == 1
    assert command.tools[0].name == "move_head"
    assert command.tools[0].arguments["pitch"] == -8


def test_json_command_parse_failure_falls_back_to_plain_speech() -> None:
    command = parse_json_command("Sure, I can help with a tiny story.")
    assert command.speak == "Sure, I can help with a tiny story."
    assert command.tools == []

