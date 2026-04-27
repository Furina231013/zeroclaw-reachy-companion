from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from zeroclaw_reachy_companion.reachy import ReachyClient


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    error: str | None = None

    @classmethod
    def ok(cls, output: str) -> "ToolResult":
        return cls(success=True, output=output)

    @classmethod
    def fail(cls, error: str, output: str = "") -> "ToolResult":
        return cls(success=False, output=output, error=error)


@dataclass(frozen=True)
class ToolContext:
    reachy: ReachyClient


ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]


@dataclass(frozen=True)
class ToolDefinition:
    """A Python mirror of ZeroClaw's Tool trait surface."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def zeroclaw_spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def openai_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, context: ToolContext, args: dict[str, Any]) -> ToolResult:
        try:
            return await self.handler(context, args)
        except Exception as exc:
            return ToolResult.fail(f"{type(exc).__name__}: {exc}")


class ToolRegistry:
    def __init__(self, context: ToolContext, tools: list[ToolDefinition]):
        self.context = context
        self._tools = {tool.name: tool for tool in tools}

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def zeroclaw_specs(self) -> list[dict[str, Any]]:
        return [tool.zeroclaw_spec() for tool in self._tools.values()]

    def openai_specs(self) -> list[dict[str, Any]]:
        return [tool.openai_spec() for tool in self._tools.values()]

    async def execute(self, name: str, args: dict[str, Any] | None = None) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.fail(f"unknown tool: {name}")
        return await tool.execute(self.context, args or {})


def require_string(args: dict[str, Any], name: str, *, default: str | None = None, max_len: int = 500) -> str:
    value = args.get(name, default)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{name} is required")
    if len(value) > max_len:
        raise ValueError(f"{name} must be at most {max_len} characters")
    return value


def optional_string(args: dict[str, Any], name: str, *, default: str | None = None, max_len: int = 200) -> str | None:
    value = args.get(name, default)
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"{name} must be at most {max_len} characters")
    return value


def number_arg(
    args: dict[str, Any],
    name: str,
    *,
    default: float,
    min_value: float,
    max_value: float,
) -> float:
    value = args.get(name, default)
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not min_value <= parsed <= max_value:
        raise ValueError(f"{name} must be between {min_value:g} and {max_value:g}")
    return parsed

