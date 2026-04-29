from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from zeroclaw_reachy_companion.config import AppConfig, Profile, load_profile
from zeroclaw_reachy_companion.providers import AgentCommand, LocalLLMProvider, ToolCallCommand, command_from_text
from zeroclaw_reachy_companion.providers.local_llm import LocalLLMError
from zeroclaw_reachy_companion.reachy import ReachyClient
from zeroclaw_reachy_companion.runtime.event_router import command_for_event
from zeroclaw_reachy_companion.runtime.events import CompanionEvent
from zeroclaw_reachy_companion.runtime.state import RuntimeState
from zeroclaw_reachy_companion.tools import ToolRegistry, ToolResult, create_tool_registry


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutedTool:
    call: ToolCallCommand
    result: ToolResult


@dataclass(frozen=True)
class CompanionTurnResult:
    final_text: str
    tools: list[ExecutedTool] = field(default_factory=list)
    used_fallback: bool = False
    event_type: str | None = None

    @property
    def response(self) -> str:
        """Backward-compatible alias used by the voice harness and older tests."""
        return self.final_text


AgentTurnResult = CompanionTurnResult


@dataclass(frozen=True)
class GuardedCommand:
    command: AgentCommand
    skipped_tools: tuple[str, ...] = ()


class ReachyCompanionRuntime:
    """Small ZeroClaw-style agent loop for Phase 1 and Phase 2 fallback."""

    def __init__(
        self,
        config: AppConfig,
        reachy: ReachyClient,
        registry: ToolRegistry,
        profile: Profile,
        provider: LocalLLMProvider,
        state: RuntimeState | None = None,
    ):
        self.config = config
        self.reachy = reachy
        self.registry = registry
        self.profile = profile
        self.provider = provider
        self.state = state or RuntimeState()

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

    async def handle_text(self, user_text: str, *, announce: bool = True) -> CompanionTurnResult:
        command, used_fallback = await self._command_for_text(user_text, announce=announce)
        return await self.handle_command(
            command,
            user_text=user_text,
            announce=announce,
            used_fallback=used_fallback,
        )

    async def handle_command(
        self,
        command: AgentCommand,
        *,
        user_text: str = "",
        announce: bool = True,
        used_fallback: bool = False,
        event_type: str | None = None,
    ) -> CompanionTurnResult:
        if user_text:
            guarded = _guard_command(command, user_text=user_text, state=self.state)
            command = guarded.command
            for skipped in guarded.skipped_tools:
                logger.info("Skipped tool call after behavior guard: %s", skipped)
                if announce:
                    print(f"[guard] skipped tool: {skipped}")
        return await self._execute_command(
            command,
            announce=announce,
            used_fallback=used_fallback,
            event_type=event_type,
        )

    async def handle_event(
        self,
        event: CompanionEvent | dict[str, Any],
        *,
        announce: bool = False,
    ) -> CompanionTurnResult:
        companion_event = CompanionEvent.from_value(event)
        command = command_for_event(companion_event, self.state)
        return await self._execute_command(
            command,
            announce=announce,
            used_fallback=False,
            event_type=companion_event.type,
        )

    async def _execute_command(
        self,
        command: AgentCommand,
        *,
        announce: bool,
        used_fallback: bool,
        event_type: str | None = None,
    ) -> CompanionTurnResult:
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

        return CompanionTurnResult(
            final_text=command.speak,
            tools=executed,
            used_fallback=used_fallback,
            event_type=event_type,
        )

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


FACTUAL_PATTERNS = (
    "what is",
    "what are",
    "explain",
    "why is",
    "why are",
    "how does",
    "how do",
)
QUIET_PHRASES = ("quiet", "stay quiet", "soft", "silence")
CALMING_PHRASES = ("upset", "cry", "crying", "sleepy", "bedtime", "settle down", "calm")
DANCE_PHRASES = ("dance", "party", "celebrate", "happy dance", "playful movement")
COMPANY_PHRASES = ("keep him company", "keep her company", "keep them company", "keep my baby company")
GREETING_PHRASES = ("say hello", "hello to my baby", "greet")


def _guard_command(command: AgentCommand, *, user_text: str, state: RuntimeState) -> GuardedCommand:
    text = _normalize_text(user_text)
    factual = _is_factual_question(text)
    quiet_request = _has_any(text, QUIET_PHRASES)
    quiet_context = state.quiet_mode or quiet_request
    explicit_dance = _has_any(text, DANCE_PHRASES)
    story_requested = "story" in text
    comfort_request = _is_comfort_request(text)
    greeting_request = _is_greeting_request(text)
    calming_context = _is_calming_context(text) or quiet_context

    kept: list[ToolCallCommand] = []
    skipped: list[str] = []
    for tool_call in command.tools:
        reason = _blocked_reason(
            tool_call.name,
            factual=factual,
            quiet_context=quiet_context,
            calming_context=calming_context,
            explicit_dance=explicit_dance,
            story_requested=story_requested,
            comfort_request=comfort_request,
            greeting_request=greeting_request,
        )
        if reason:
            skipped.append(f"{tool_call.name}: {reason}")
            continue
        kept.append(_constrain_tool_call(tool_call, quiet_context=quiet_context))

    final_text = command.speak.strip()
    if quiet_context:
        final_text = _quiet_text(
            final_text,
            default="Okay, I'll stay quiet." if quiet_request else "Sure. I'll keep it calm and brief.",
        )

    kept = _add_semantic_support(
        kept,
        user_text=text,
        final_text=final_text,
        factual=factual,
        quiet_context=quiet_context,
        quiet_request=quiet_request,
    )

    return GuardedCommand(
        command=AgentCommand(speak=final_text, tools=kept, raw_text=command.raw_text),
        skipped_tools=tuple(skipped),
    )


def _blocked_reason(
    tool_name: str,
    *,
    factual: bool,
    quiet_context: bool,
    calming_context: bool,
    explicit_dance: bool,
    story_requested: bool,
    comfort_request: bool,
    greeting_request: bool,
) -> str | None:
    if greeting_request and tool_name == "soothe_baby":
        return "greeting without comfort request"

    if tool_name == "dance":
        if quiet_context:
            return "quiet context"
        if calming_context and not explicit_dance:
            return "calming context"
        if factual and not explicit_dance:
            return "factual question"

    if factual:
        if tool_name == "soothe_baby":
            return "factual question"
        if tool_name == "story_time" and not story_requested:
            return "factual question without story request"

    if quiet_context:
        if tool_name == "story_time" and not story_requested:
            return "quiet context without story request"
        if tool_name == "soothe_baby" and not comfort_request:
            return "quiet request"

    return None


def _constrain_tool_call(tool_call: ToolCallCommand, *, quiet_context: bool) -> ToolCallCommand:
    if tool_call.name != "speak" or not quiet_context:
        return tool_call

    text = str(tool_call.arguments.get("text") or "").strip()
    constrained = _quiet_text(text, default="Okay, I'll keep it quiet.")
    if constrained == text:
        return tool_call
    return ToolCallCommand("speak", {**tool_call.arguments, "text": constrained})


def _add_semantic_support(
    tools: list[ToolCallCommand],
    *,
    user_text: str,
    final_text: str,
    factual: bool,
    quiet_context: bool,
    quiet_request: bool,
) -> list[ToolCallCommand]:
    names = {tool.name for tool in tools}

    if quiet_request and not tools:
        return [*tools, ToolCallCommand("do_nothing", {"reason": "quiet request"})]

    if factual:
        return tools

    if "nod" in user_text and "move_head" not in names and not quiet_context:
        return [
            *tools,
            ToolCallCommand("move_head", {"yaw": 0, "pitch": -8, "roll": 0, "duration": 0.6}),
            ToolCallCommand("move_head", {"yaw": 0, "pitch": 8, "roll": 0, "duration": 0.6}),
        ]

    comfort_tools = {"soothe_baby", "speak", "play_emotion", "move_head", "story_time"}
    if _is_comfort_request(user_text) and not (names & comfort_tools) and not quiet_context:
        return [*tools, ToolCallCommand("soothe_baby", {"style": _soothing_style(user_text)})]

    if _is_calm_request(user_text) and not (names & {"soothe_baby", "speak"}) and not quiet_context:
        return [*tools, ToolCallCommand("soothe_baby", {"style": _soothing_style(user_text)})]

    if _is_company_request(user_text) and not (names & {"speak", "play_emotion", "move_head"}):
        text = final_text or "I'm here with him. I'll keep gentle company."
        return [*tools, ToolCallCommand("speak", {"text": _short_text(text, default="I'm here with him.")})]

    return tools


def _is_factual_question(text: str) -> bool:
    return any(text.startswith(pattern) or f" {pattern}" in text for pattern in FACTUAL_PATTERNS)


def _is_calming_context(text: str) -> bool:
    return _has_any(text, CALMING_PHRASES) or ("calm" in text and "gentle" in text)


def _is_comfort_request(text: str) -> bool:
    return _has_any(text, ("upset", "cry", "crying", "soothe", "comfort", "settle down", "sleepy", "bedtime"))


def _is_calm_request(text: str) -> bool:
    return "calm" in text or "gentle" in text and "nod" not in text


def _is_company_request(text: str) -> bool:
    return _has_any(text, COMPANY_PHRASES) or _has_any(text, GREETING_PHRASES)


def _is_greeting_request(text: str) -> bool:
    return _has_any(text, GREETING_PHRASES)


def _soothing_style(text: str) -> str:
    if "sleepy" in text or "bedtime" in text or "settle down" in text:
        return "sleepy"
    return "gentle"


def _short_text(text: str, *, default: str) -> str:
    stripped = text.strip()
    if not stripped:
        return default
    words = stripped.split()
    if len(words) <= 20:
        return stripped
    return default


def _quiet_text(text: str, *, default: str) -> str:
    stripped = text.strip()
    if not stripped:
        return default
    lowered = stripped.lower()
    if any(word in lowered for word in ("dance", "party", "energetic")):
        return default
    return _short_text(stripped, default=default)


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


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
