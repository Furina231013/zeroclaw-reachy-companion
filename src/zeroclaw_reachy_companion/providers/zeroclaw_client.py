from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from zeroclaw_reachy_companion.providers.local_llm import AgentCommand, ToolCallCommand


class ZeroClawClientError(RuntimeError):
    """Raised when the ZeroClaw text bridge cannot produce a command."""


@dataclass(frozen=True)
class ZeroClawTextClient:
    """HTTP client used by Reachy voice mode to delegate text logic to ZeroClaw."""

    url: str
    timeout_s: float = 30.0
    bearer_token: str | None = None

    async def command_for_text(self, text: str) -> AgentCommand:
        payload = {
            "text": text,
            "source": "reachy_voice",
        }
        data = await asyncio.to_thread(self._post_json, payload)
        return command_from_zeroclaw_payload(data)

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        request = urllib.request.Request(
            self.url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ZeroClawClientError(f"ZeroClaw text request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ZeroClawClientError(f"ZeroClaw text response is not JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ZeroClawClientError("ZeroClaw text response must be a JSON object")
        return data


def command_from_zeroclaw_payload(data: dict[str, Any]) -> AgentCommand:
    speak = data.get("final_text") or data.get("speak") or data.get("response") or ""
    if not isinstance(speak, str):
        speak = str(speak)

    tools_data = data.get("tools") or data.get("tool_calls") or []
    tools: list[ToolCallCommand] = []
    if isinstance(tools_data, list):
        for item in tools_data:
            tool_call = _tool_call_from_payload(item)
            if tool_call is not None:
                tools.append(tool_call)

    return AgentCommand(speak=speak.strip(), tools=tools, raw_text=json.dumps(data, ensure_ascii=False))


def _tool_call_from_payload(item: Any) -> ToolCallCommand | None:
    if not isinstance(item, dict):
        return None
    function = item.get("function") if isinstance(item.get("function"), dict) else {}
    name = item.get("name") or function.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    args = item.get("arguments", function.get("arguments", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    return ToolCallCommand(name=name.strip(), arguments=args)
