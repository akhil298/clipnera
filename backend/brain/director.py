"""The director: plan a multi-step edit with read tools, score candidates, choose one (BLUEPRINT §3.5.2).

A tool loop on the "director" role. It reads the media, sends its IntentFrame and K PlanIR
candidates to evaluate_plan_candidates (validate → compile → dry run → score), and finishes with
plan_choose, or ask_user when nothing reasonable can be assumed. The planner's model comes
from the user's ``ai.planner.model`` feature key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.loop import TurnLimits, run_turn
from agent_runtime.tools import AgentTool, ToolBox
from brain.answer import READ_ONLY
from brain.clarify import decide_clarify
from brain.context import EditContext
from brain.evaluate import Evaluation, evaluate_candidates
from brain.intent import IntentFrame
from brain.plan_ir import PlanIR
from brain.route import RouteDecision
from brain.score import ScoredPlan
from clients.ai import get_role_client
from editor.service import EditorService

PROMPTS = Path(__file__).parent / "prompts"
SYSTEM = (PROMPTS / "sp_common.md").read_text(encoding="utf-8") + "\n\n" + (PROMPTS / "director.md").read_text(encoding="utf-8")
LIMITS = TurnLimits(max_steps=10, seconds=240, usd=1.0, max_tokens=8000)
MAX_EVALUATIONS = 2
MAX_CANDIDATES = 3


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvaluateInput(_Closed):
    frame: IntentFrame
    candidates: list[PlanIR] = Field(..., min_length=1, max_length=MAX_CANDIDATES)


class ChooseInput(_Closed):
    candidate: str = Field(..., description="The candidate id evaluate_plan_candidates returned, e.g. c1.")
    reason: str = Field(..., max_length=300, description="Why this one, and which is the runner-up.")


class AskInput(_Closed):
    question: str = Field(..., min_length=1, max_length=200)
    options: list[str] = Field(..., min_length=2, max_length=4)


@dataclass
class DirectorRun:
    """The tool context: the read tools need service/user_id/project_id; the rest is this run's state."""

    service: EditorService
    user_id: str
    project_id: str
    ctx: EditContext
    prompt: str
    allowed_owned: set[str]
    use_judge: bool
    frame: IntentFrame | None = None
    evaluation: Evaluation | None = None
    evaluations: int = 0
    chosen: str | None = None
    reason: str = ""
    question: AskInput | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class DirectorResult:
    kind: str  # plan | ask | failed
    best: ScoredPlan | None = None
    runner_up: ScoredPlan | None = None
    frame: IntentFrame | None = None
    question: str | None = None
    options: list[str] = field(default_factory=list)
    message: str = ""
    reason: str = ""


async def _evaluate(run: DirectorRun, args: EvaluateInput) -> dict[str, Any]:
    if run.evaluations >= MAX_EVALUATIONS:
        return {"error": "You've evaluated twice already. Call plan_choose with the best valid candidate."}
    run.evaluations += 1
    run.frame = args.frame
    run.evaluation = await evaluate_candidates(run.prompt, args.frame, args.candidates, run.ctx,
                                               allowed_owned=run.allowed_owned, use_judge=run.use_judge)
    best, _ = run.evaluation.best()
    return {"candidates": run.evaluation.report(),
            "best_valid": f"c{best.index + 1}" if best else None,
            "next": "Call plan_choose." if best else "Every candidate failed; fix the errors and evaluate again."}


async def _choose(run: DirectorRun, args: ChooseInput) -> str:
    valid = {f"c{s.index + 1}" for s in (run.evaluation.scored if run.evaluation else []) if s.eligible}
    if args.candidate not in valid:
        return f"{args.candidate} isn't a valid evaluated candidate. Valid: {sorted(valid) or 'none'}."
    run.chosen, run.reason = args.candidate, args.reason
    return "Chosen. Stop now; the plan goes to the user."


async def _ask(run: DirectorRun, args: AskInput) -> str:
    run.question = args
    return "Asked. Stop now; the user will answer."


_PLANNING = [
    *READ_ONLY.tools(),
    AgentTool("evaluate_plan_candidates", "Validate, compile and score your IntentFrame and 1-3 PlanIR candidates. "
                                          "Returns per candidate its score, components, errors and warnings.",
              EvaluateInput, _evaluate),
    AgentTool("plan_choose", "Choose the evaluated candidate to show the user.", ChooseInput, _choose),
]
TOOLS = ToolBox([
    *_PLANNING,
    AgentTool("ask_user", "Ask one question with 2-4 options drawn from the footage, after looking at it, "
                          "when the request has two very different readings.", AskInput, _ask),
])
# Once the user has been asked, the director can only plan.
TOOLS_NO_ASK = ToolBox(_PLANNING)


async def direct(service: EditorService, user_id: str, ctx: EditContext, prompt: str, decision: RouteDecision, *,
                 allowed_owned: set[str], recent_turns: list[str], asked_in_conversation: int = 0,
                 may_ask: bool = True) -> DirectorResult:
    run = DirectorRun(service, user_id, ctx.project_id, ctx, prompt, allowed_owned,
                      use_judge=int(ctx.features.get("ai.plan.candidates_k", 1)) > 1)
    route = decision.model_dump(exclude={"safety"})
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{SYSTEM}\n\n{ctx.render()}"},
        {"role": "user", "content": "\n".join([
            f"<route>{json.dumps(route, sort_keys=True)}</route>",
            f"<recent_turns>{json.dumps(recent_turns[-3:])}</recent_turns>",
            f"<human_owned_ok>{sorted(allowed_owned)}</human_owned_ok>",
            f"<questions_left>{1 if may_ask else 0}</questions_left>",
            f"Request: {prompt}",
        ])},
    ]
    client = get_role_client("director", plan_override=str(ctx.features.get("ai.planner.model") or "") or None)
    try:
        async for event in run_turn(client, messages, TOOLS if may_ask else TOOLS_NO_ASK, run, LIMITS):
            if event.type == "text" and event.data.get("text"):
                run.notes.append(event.data["text"])
            if run.chosen or run.question:
                break
    finally:
        await client.close()

    if run.question:
        return DirectorResult("ask", frame=run.frame, question=run.question.question, options=run.question.options)
    if run.evaluation is None:
        return DirectorResult("failed", message="I couldn't put a plan together for that. Try saying what to make.")
    best, runner_up = run.evaluation.best()
    if run.chosen:
        chosen = next(s for s in run.evaluation.scored if f"c{s.index + 1}" == run.chosen)
        runner_up = best if best is not chosen else runner_up
        best = chosen
    if best is None:
        reasons = [e for errors in run.evaluation.invalid.values() for e in errors][:3]
        reasons += [f"{k}: {v}" for s in run.evaluation.scored for k, v in s.summary()["step_errors"].items()][:3]
        return DirectorResult("failed", message="I couldn't make a plan that works: " + "; ".join(reasons or ["no valid candidate"]))
    if run.frame is not None and may_ask:
        clarify = decide_clarify(run.frame, asked_this_turn=0, asked_in_conversation=asked_in_conversation)
        if clarify.ask:
            return DirectorResult("ask", frame=run.frame, question=clarify.question, options=clarify.options)
    return DirectorResult("plan", best=best, runner_up=runner_up, frame=run.frame, reason=run.reason)
