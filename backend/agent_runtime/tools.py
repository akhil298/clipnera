"""Typed tools for an agent: each one validates its input before it runs.

A tool's failure is not the turn's failure. A bad input or a refused edit goes
back to the model as an error result it can read and fix, the same way a
person would see "that clip overlaps the next one" and try again.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from clients.ai.base import ToolCall, ToolResult, ToolSpec
from core.exceptions import CustomException

ToolOutput = str | dict[str, Any] | list[Any]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input: type[BaseModel]
    # Called with the turn's context (whatever the caller passes, e.g. the open project) and the validated input.
    run: Callable[[Any, Any], Awaitable[ToolOutput]]

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, schema=self.input.model_json_schema())


class ToolBox:
    def __init__(self, tools: Iterable[AgentTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    async def call(self, context: Any, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.id, f"There is no tool called {call.name}.", is_error=True)
        try:
            arguments = tool.input.model_validate(call.arguments)
        except ValidationError as exc:
            return ToolResult(call.id, f"Invalid input: {_describe(exc)}", is_error=True)
        try:
            output = await tool.run(context, arguments)
        except CustomException as exc:
            detail = {key: value for key, value in exc.extra.items() if key != "message"}
            suffix = f" ({json.dumps(detail)})" if detail else ""
            return ToolResult(call.id, f"{exc.code}: {exc.message}{suffix}", is_error=True)
        return ToolResult(call.id, output if isinstance(output, str) else json.dumps(output))


def _describe(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'input'}: {error['msg']}" for error in exc.errors()[:5]
    )
