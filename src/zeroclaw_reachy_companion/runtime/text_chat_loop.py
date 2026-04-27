from __future__ import annotations

import json
from dataclasses import dataclass, field

from zeroclaw_reachy_companion.config import AppConfig, Profile, load_profile
from zeroclaw_reachy_companion.providers import AgentCommand, LocalLLMProvider, ToolCallCommand, command_from_text
from zeroclaw_reachy_companion.providers.local_llm import LocalLLMError
from zeroclaw_reachy_companion.reachy import ReachyClient
from zeroclaw_reachy_companion.tools import ToolRegistry, ToolResult, create_tool_registry


@dataclass(frozen=True)
class ExecutedTool:
    call: ToolCallCommand
    result: ToolResult


@dataclass(frozen=True)
class AgentTurnResult:
    response: str
    tools: list[ExecutedTool] = field(default_factory=list)
    used_fallback: bool = False


class ReachyCompanionRuntime:
    """Small ZeroClaw-style agent loop for Phase 1 and Phase 2 fallback."""

    def __init__(
        self,
        config: AppConfig,
        reachy: ReachyClient,
        registry: ToolRegistry,
        profile: Profile,
        provider: LocalLLMProvider,
    ):
        self.config = config
        self.reachy = reachy
        self.registry = registry
        self.profile = profile
        self.provider = provider

    @classmethod
    async def create(cls, config: AppConfig) -> "ReachyCompanionRuntime":
        profile = load_profile(config.profile)
        reachy = ReachyClient(mode=config.reachy_mode, host=config.reachy_host, port=config.reachy_port)
        await reachy.connect()
        registry = create_tool_registry(reachy)
        provider = LocalLLMProvider(
            base_url=config.local_llm_url,
            model=config.local_llm_model,
            tool_mode=config.tool_mode,
        )
        return cls(config=config, reachy=reachy, registry=registry, profile=profile, provider=provider)

    async def close(self) -> None:
        await self.reachy.close()

    async def handle_text(self, user_text: str, *, announce: bool = True) -> AgentTurnResult:
        command, used_fallback = await self._command_for_text(user_text, announce=announce)
        if announce and command.speak:
            print(f"Agent> {command.speak}")

        executed: list[ExecutedTool] = []
        for tool_call in command.tools[: self.config.max_tool_turns]:
            if announce:
                print(f"Tool: {tool_call.name}({json.dumps(tool_call.arguments, ensure_ascii=False)})")
            result = await self.registry.execute(tool_call.name, tool_call.arguments)
            executed.append(ExecutedTool(call=tool_call, result=result))
            if announce and not result.success:
                print(f"Tool error: {result.error}")

        return AgentTurnResult(response=command.speak, tools=executed, used_fallback=used_fallback)

    async def _command_for_text(self, user_text: str, *, announce: bool) -> tuple[AgentCommand, bool]:
        if self.config.llm_backend == "mock":
            return command_from_text(user_text), True

        try:
            command = await self.provider.chat_command(
                user_text=user_text,
                system_prompt=self.profile.system_prompt,
                tool_specs=self.registry.openai_specs(),
            )
            if command.speak or command.tools:
                return command, False
            return command_from_text(user_text), True
        except LocalLLMError as exc:
            if not self.config.allow_heuristic_fallback or self.config.llm_backend == "ollama":
                raise
            if announce:
                print(f"[WARN] Local LLM unavailable, using deterministic fallback: {exc}")
            return command_from_text(user_text), True


async def run_text_loop(config: AppConfig) -> None:
    runtime = await ReachyCompanionRuntime.create(config)
    try:
        print(f"Profile: {runtime.profile.name}")
        print(f"Reachy mode: {config.reachy_mode}")
        print("Type /exit to quit.")
        while True:
            try:
                user_text = input("User> ").strip()
            except EOFError:
                break
            if not user_text:
                continue
            if user_text.lower() in {"/exit", "exit", "quit"}:
                break
            await runtime.handle_text(user_text, announce=True)
    finally:
        await runtime.close()

