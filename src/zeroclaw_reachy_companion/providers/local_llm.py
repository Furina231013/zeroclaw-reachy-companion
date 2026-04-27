from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


class LocalLLMError(RuntimeError):
    """Raised when the local provider cannot produce a response."""


@dataclass(frozen=True)
class ToolCallCommand:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentCommand:
    speak: str = ""
    tools: list[ToolCallCommand] = field(default_factory=list)
    raw_text: str = ""


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_json_command(text: str) -> AgentCommand:
    """Parse JSON command fallback, falling back to ordinary speech text."""
    raw_text = text
    candidate = _strip_code_fence(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        extracted = _extract_first_json_object(candidate)
        if extracted is None:
            return AgentCommand(speak=candidate.strip(), raw_text=raw_text)
        try:
            data = json.loads(extracted)
        except json.JSONDecodeError:
            return AgentCommand(speak=candidate.strip(), raw_text=raw_text)

    if not isinstance(data, dict):
        return AgentCommand(speak=candidate.strip(), raw_text=raw_text)

    speak = data.get("speak") or data.get("response") or ""
    if not isinstance(speak, str):
        speak = str(speak)

    tools_data = data.get("tools") or data.get("tool_calls") or []
    tools: list[ToolCallCommand] = []
    if isinstance(tools_data, list):
        for item in tools_data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                function = item.get("function")
                if isinstance(function, dict):
                    name = function.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            args = item.get("arguments", {})
            if isinstance(args, str):
                try:
                    parsed_args = json.loads(args or "{}")
                    args = parsed_args if isinstance(parsed_args, dict) else {}
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            tools.append(ToolCallCommand(name=name.strip(), arguments=args))

    return AgentCommand(speak=speak.strip(), tools=tools, raw_text=raw_text)


def command_from_text(user_text: str) -> AgentCommand:
    """Deterministic local fallback for demos and tests when Ollama is absent."""
    text = user_text.lower()
    if "story" in text or "bedtime" in text:
        return AgentCommand(
            speak="I'll tell a tiny bedtime story.",
            tools=[
                ToolCallCommand("play_emotion", {"emotion": "gentle"}),
                ToolCallCommand("story_time", {"topic": "bedtime"}),
            ],
            raw_text=user_text,
        )
    if "soothe" in text or "comfort" in text or "calm" in text:
        return AgentCommand(
            speak="Of course. I'll be gentle.",
            tools=[ToolCallCommand("soothe_baby", {"style": "gentle"})],
            raw_text=user_text,
        )
    if "dance" in text:
        return AgentCommand(
            speak="I'll do a small happy dance.",
            tools=[ToolCallCommand("dance", {"style": "happy", "duration": 4.0})],
            raw_text=user_text,
        )
    if "stop" in text:
        return AgentCommand(
            speak="Stopping now.",
            tools=[ToolCallCommand("stop_motion", {})],
            raw_text=user_text,
        )
    if "nod" in text:
        return AgentCommand(
            speak="I'll nod gently.",
            tools=[
                ToolCallCommand("move_head", {"yaw": 0, "pitch": -8, "roll": 0, "duration": 0.6}),
                ToolCallCommand("move_head", {"yaw": 0, "pitch": 8, "roll": 0, "duration": 0.6}),
            ],
            raw_text=user_text,
        )
    if "look left" in text or "turn left" in text:
        return AgentCommand(
            speak="Looking left.",
            tools=[ToolCallCommand("move_head", {"yaw": 18, "pitch": 0, "roll": 0, "duration": 1.0})],
            raw_text=user_text,
        )
    return AgentCommand(
        speak="I'm here with you. I can speak, move, tell a story, soothe, dance, or stop moving.",
        raw_text=user_text,
    )


class LocalLLMProvider:
    """Minimal local LLM provider for Ollama or OpenAI-compatible endpoints."""

    def __init__(self, base_url: str, model: str, *, tool_mode: str = "json", timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.tool_mode = tool_mode
        self.timeout_s = timeout_s
        self.history: list[dict[str, str]] = []

    async def chat_command(self, user_text: str, system_prompt: str, tool_specs: list[dict[str, Any]]) -> AgentCommand:
        if self.tool_mode == "native":
            response = await self._chat_native_tools(user_text, system_prompt, tool_specs)
        else:
            response = await self._chat_json_command(user_text, system_prompt, tool_specs)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": response.raw_text or response.speak})
        self.history = self.history[-10:]
        return response

    async def _chat_json_command(
        self,
        user_text: str,
        system_prompt: str,
        tool_specs: list[dict[str, Any]],
    ) -> AgentCommand:
        tool_summary = json.dumps(tool_specs, ensure_ascii=False)
        json_instruction = (
            "Return only one JSON object with this shape: "
            '{"speak":"short response for TTS","tools":[{"name":"tool_name","arguments":{}}]}. '
            "Use only listed tools and keep speak short. If no tool is needed, return an empty tools array. "
            f"Available tools: {tool_summary}"
        )
        messages = [{"role": "system", "content": f"{system_prompt}\n\n{json_instruction}"}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_text})
        content, tool_calls = await self._post_chat(messages, tools=None)
        if tool_calls:
            return AgentCommand(speak=content, tools=tool_calls, raw_text=content)
        return parse_json_command(content)

    async def _chat_native_tools(
        self,
        user_text: str,
        system_prompt: str,
        tool_specs: list[dict[str, Any]],
    ) -> AgentCommand:
        # Native tool-call history must preserve assistant tool_calls and tool
        # result messages. This Phase 1 loop executes tools locally and does not
        # yet feed those structures back to the provider, so keep native requests
        # stateless to avoid previous tool calls leaking into the next command.
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": user_text})
        content, tool_calls = await self._post_chat(messages, tools=tool_specs)
        if tool_calls:
            return AgentCommand(speak=content, tools=tool_calls, raw_text=content)
        return parse_json_command(content)

    async def _post_chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[str, list[ToolCallCommand]]:
        if self.base_url.endswith("/v1"):
            return await self._post_openai_compatible(messages, tools)
        return await self._post_ollama(messages, tools)

    async def _post_ollama(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[str, list[ToolCallCommand]]:
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        data = await asyncio.to_thread(self._post_json, url, payload)
        message = data.get("message") or {}
        content = str(message.get("content") or "")
        return content, _parse_native_tool_calls(message.get("tool_calls") or [])

    async def _post_openai_compatible(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[str, list[ToolCallCommand]]:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["parallel_tool_calls"] = False
        data = await asyncio.to_thread(self._post_json, url, payload)
        choices = data.get("choices") or []
        if not choices:
            raise LocalLLMError("provider returned no choices")
        message = choices[0].get("message") or {}
        content = str(message.get("content") or "")
        return content, _parse_native_tool_calls(message.get("tool_calls") or [])

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise LocalLLMError(f"local LLM request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LocalLLMError(f"local LLM returned invalid JSON: {exc}") from exc


def _parse_native_tool_calls(items: list[Any]) -> list[ToolCallCommand]:
    calls: list[ToolCallCommand] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if isinstance(item.get("function"), dict) else item
        name = function.get("name")
        if not isinstance(name, str) or not name:
            continue
        args = function.get("arguments", {})
        if isinstance(args, str):
            try:
                parsed = json.loads(args or "{}")
                args = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        calls.append(ToolCallCommand(name=name, arguments=args))
    return calls
