from __future__ import annotations

import asyncio
import json

from zeroclaw_reachy_companion.providers.zeroclaw_client import (
    ZeroClawTextClient,
    command_from_zeroclaw_payload,
)


def test_command_from_zeroclaw_payload_accepts_final_text_and_tools() -> None:
    command = command_from_zeroclaw_payload(
        {
            "final_text": "I'll help gently.",
            "tools": [
                {
                    "name": "soothe_baby",
                    "arguments": {"style": "gentle"},
                }
            ],
        }
    )

    assert command.speak == "I'll help gently."
    assert len(command.tools) == 1
    assert command.tools[0].name == "soothe_baby"
    assert command.tools[0].arguments == {"style": "gentle"}


def test_command_from_zeroclaw_payload_accepts_openai_style_tool_calls() -> None:
    command = command_from_zeroclaw_payload(
        {
            "response": "Nodding.",
            "tool_calls": [
                {
                    "function": {
                        "name": "move_head",
                        "arguments": '{"yaw": 0, "pitch": -8, "roll": 0, "duration": 0.6}',
                    }
                }
            ],
        }
    )

    assert command.speak == "Nodding."
    assert len(command.tools) == 1
    assert command.tools[0].name == "move_head"
    assert command.tools[0].arguments["pitch"] == -8


def test_zeroclaw_text_client_sends_bearer_token(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps({"final_text": "ok"}).encode("utf-8")

    def fake_urlopen(request, timeout):  # noqa: ANN001
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client = ZeroClawTextClient(
        "http://127.0.0.1:9000/api/turns/text",
        bearer_token="secret-token",
    )
    command = asyncio.run(client.command_for_text("hello"))

    assert command.speak == "ok"
    assert captured["authorization"] == "Bearer secret-token"
    assert captured["timeout"] == 30.0
