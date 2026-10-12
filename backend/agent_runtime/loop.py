"""One agent turn: the model calls tools until it answers, or a limit stops it.

The loop is provider-neutral (it only uses BaseAI.chat_with_tools and
tool_results) and reports what happens as events, which the API streams to
the browser over SSE. Each turn has its own dollar cap on top of the step and
time limits; a model call that would go past it is not made.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_runtime.tools import ToolBox
from clients.ai.base import BaseAI, ToolResult
from usage.context import RunBudget, llm_scope

StopReason = Literal["answered", "steps", "time", "budget", "refused"]


@dataclass(frozen=True)
class TurnLimits:
    max_steps: int
    seconds: float
    usd: float
    max_tokens: int = 4096


@dataclass(frozen=True)
class AgentEvent:
    type: Literal["text", "tool_call", "tool_result", "done"]
    data: dict[str, Any] = field(default_factory=dict)


async def run_turn(client: BaseAI, messages: list[dict[str, Any]], toolbox: ToolBox, context: Any,
                   limits: TurnLimits) -> AsyncIterator[AgentEvent]:
    """Run one turn on ``messages``, which grows in place with every step so the caller can keep it.

    Tool calls run in order, one at a time: they edit the same project, so a
    later call must see what an earlier one did.
    """
    budget = RunBudget(cap_usd=limits.usd)
    deadline = time.monotonic() + limits.seconds
    specs = toolbox.specs()
    for step in range(limits.max_steps):
        if time.monotonic() > deadline:
            yield _done("time", step, budget)
            return
        if budget.exhausted:
            yield _done("budget", step, budget)
            return
        with llm_scope(budget=budget):
            reply = await client.chat_with_tools(messages, specs, max_tokens=limits.max_tokens)
        messages.append(reply.message)
        if reply.text:
            yield AgentEvent("text", {"text": reply.text})
        if reply.refused:
            # Nothing in a declined reply is run, even a tool call that came before the decline.
            yield _done("refused", step + 1, budget)
            return
        if not reply.calls:
            yield _done("answered", step + 1, budget)
            return
        results: list[ToolResult] = []
        for call in reply.calls:
            yield AgentEvent("tool_call", {"id": call.id, "name": call.name, "arguments": call.arguments})
            if reply.truncated:
                # The reply was cut off at the output cap, so this call's input may be incomplete.
                result = ToolResult(call.id, "Your reply was cut off before this call finished. Send it again, shorter.", is_error=True)
            else:
                result = await toolbox.call(context, call)
            results.append(result)
            yield AgentEvent("tool_result", {"id": call.id, "name": call.name, "ok": not result.is_error, "content": result.content})
        messages.extend(client.tool_results(results))
    yield _done("steps", limits.max_steps, budget)


def _done(reason: StopReason, steps: int, budget: RunBudget) -> AgentEvent:
    return AgentEvent("done", {"reason": reason, "steps": steps, "cost_usd": round(budget.spent_usd, 6)})
