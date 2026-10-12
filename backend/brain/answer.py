"""The answer path: questions about the project, answered from the media with read-only tools.

The answer role sees the LCV and may call the media tools and get_timeline; it is given no
editing tool at all (TODO 5.6.2), so a question can never change the project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import ToolBox
from clients.ai import get_role_client
from editor.agent_tools import EDITOR_TOOLS
from understanding import lcv

ANSWER_PROMPT = (Path(__file__).parent / "prompts" / "answer.md").read_text(encoding="utf-8")
LIMITS = TurnLimits(max_steps=5, seconds=45, usd=0.05, max_tokens=1200)
EXECUTOR_BUDGET = lcv.BUDGETS["executor"]

# Reading tools only: the editor's toolbox minus anything that changes the project.
READ_ONLY = ToolBox([tool for tool in EDITOR_TOOLS.tools() if tool.name != "apply_edits"])


async def answer(context: Any, question: str) -> str:
    """``context`` is an editor.agent_tools.EditorContext for the open project."""
    media = await context.service.media(context.user_id, context.project_id)
    view = lcv.render(lcv.assets_for(media.names, media.muds, media.statuses), EXECUTOR_BUDGET)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{ANSWER_PROMPT}\n\n{view}"},
        {"role": "user", "content": question},
    ]
    client = get_role_client("answer")
    text: list[str] = []
    try:
        async for event in run_turn(client, messages, READ_ONLY, context, LIMITS):
            if event.type == "text":
                text.append(event.data["text"])
            elif event.type == "done" and event.data["reason"] == "refused":
                return "I can't help with that one."
    finally:
        await client.close()
    return text[-1].strip() if text else "I couldn't find an answer to that in this project."
