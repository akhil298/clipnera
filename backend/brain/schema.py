"""What one prompt turn returns. Phase 10's turns endpoint serves it, with matching frontend types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from brain.route import RouteDecision
from clients.ai.roles import Effort

TurnKind = Literal["edit", "answer", "clarify", "choices", "plan", "plan_needed", "refused"]
PlanStatusName = Literal["proposed", "approved", "running", "paused", "done", "failed", "rejected", "stopped"]
StepStatusName = Literal["pending", "running", "done", "failed", "skipped"]


class TurnRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    # Ids of the items selected in the studio.
    selection: list[str] = Field(default_factory=list, max_length=200)
    # The playhead, in timeline frames.
    playhead: int = Field(0, ge=0)
    # The user's last few prompts, oldest first, so "again" and "that" make sense.
    recent_turns: list[str] = Field(default_factory=list, max_length=3)
    # Questions the AI has asked in a row since it last did or answered something. After one it
    # must decide for itself (brain.turns.QUESTIONS_PER_REQUEST).
    questions_asked: int = Field(0, ge=0, le=20)
    # Auto mode: never ask, and run the plan straight away instead of waiting for approval.
    auto: bool = False
    # The OpenAI deployment and reasoning effort picked in the chat; None for the defaults.
    model: str | None = Field(None, min_length=1, max_length=80)
    effort: Effort | None = None


class AiModels(BaseModel):
    """What the studio's AI chat lets the user pick."""

    models: list[str]
    default_model: str
    efforts: list[str]


class TurnChoice(BaseModel):
    """One quick-pick chip: an item the prompt might mean."""

    id: str
    label: str


class PlanCardStep(BaseModel):
    id: str
    kind: str
    intent: str
    why: str
    enabled: bool
    optional: bool
    status: StepStatusName
    credits: int
    depends_on: list[str]
    # What happened when it ran, or why it failed.
    note: str
    # Once done: the id for POST /editor/projects/{id}/steps/{step}/undo.
    undo_step_id: str | None = None


class GhostClip(BaseModel):
    """A shot the plan would place, for the dashed preview on the timeline (frames)."""

    at: int
    end: int
    label: str


class PlanCard(BaseModel):
    id: str
    status: PlanStatusName
    title: str
    summary: str
    # E.g. "30.0 s · 9 shots · on the beat".
    result_line: str
    # The most this plan can cost; steps that fail or are skipped aren't charged.
    credits: int
    credits_charged: int
    steps: list[PlanCardStep]
    assumptions: list[str]
    warnings: list[str]
    # Premium assets the plan uses, each with a free swap (none until premium assets exist).
    premium: list[str]
    ghost: list[GhostClip]
    fps: int
    # "Try the other version" is offered while this is set.
    runner_up_title: str | None
    error: str | None


class PlanPatch(BaseModel):
    """Turn steps on or off and reorder them before approving."""

    enabled: dict[str, bool] = Field(default_factory=dict)
    order: list[str] | None = None


class TurnResult(BaseModel):
    kind: TurnKind
    # What to show the user: the answer, the question, or what was done.
    message: str
    # Set when the project changed.
    version: int | None = None
    # The step to pass to POST /editor/projects/{id}/steps/{step_id}/undo for this turn's Undo chip.
    undo_step_id: str | None = None
    choices: list[TurnChoice] = Field(default_factory=list)
    # Chips for a clarifying question; picking one sends it as the next prompt.
    options: list[str] = Field(default_factory=list)
    plan: PlanCard | None = None
    route: RouteDecision | None = None


class StylePreference(BaseModel):
    """Something the AI learned from the user's corrections (brain.style)."""

    key: str
    label: str
    # A readable value, e.g. "about 1.30× the default size".
    value: str
    confidence: float
    # Confident enough to shape plans.
    in_use: bool


class LibrarySound(BaseModel):
    """A sound effect from Clipnera's own clean-licensed library (static/motion/sfx)."""

    id: str
    name: str
    tags: list[str]
    seconds: float
    # Path under the API host, e.g. /static/sfx/pop.wav.
    url: str
    licence: str
    # What kind of sound it is: transition, impact, pop, ui, money…
    category: str


class SoundSearchResponse(BaseModel):
    results: list[LibrarySound]
    count: int
    has_more: bool


class RenderStatus(BaseModel):
    id: str
    status: Literal["queued", "rendering", "done", "failed"]
    stage: str
    version: int
    # A signed link, once done; valid for an hour.
    download_url: str | None
    error: str | None


class StepSpend(BaseModel):
    calls: int
    usd: float


class RolloutMetrics(BaseModel):
    """How the AI editor is doing over the last ``days`` (TODO 18.1.3)."""

    days: int
    turns: int
    plans: int
    plans_approved: int
    ai_steps: int
    ai_steps_undone: int
    # Share of AI steps a person undid.
    undo_rate: float
    cost_per_turn_usd: float
    # By step: editor_turn, editor_plan, media_understanding.
    spend: dict[str, StepSpend]


# ---------------------------------------------------------------------------- the studio agent (brain/studio.py)

# The studio's asset panel tabs (frontend opencut assets-panel-store TAB_KEYS).
StudioPanel = Literal["media", "sounds", "text", "stickers", "effects", "transitions", "captions", "adjustment",
                      "settings"]
TodoStatus = Literal["pending", "active", "done"]
AgentStopReason = Literal["answered", "steps", "time", "budget", "refused", "handed_over", "failed"]


class AgentExchange(BaseModel):
    """One earlier prompt and what the agent said back, so the conversation carries on."""

    prompt: str = Field(..., min_length=1, max_length=2000)
    reply: str = Field("", max_length=4000)


class AgentRequest(BaseModel):
    """POST /editor/projects/{id}/agent: one prompt for the studio agent, answered as server-sent events."""

    prompt: str = Field(..., min_length=1, max_length=2000)
    # Ids of the items selected in the studio.
    selection: list[str] = Field(default_factory=list, max_length=200)
    # The playhead, in timeline frames.
    playhead: int = Field(0, ge=0)
    # The conversation so far, oldest first.
    history: list[AgentExchange] = Field(default_factory=list, max_length=6)
    # Questions the AI has asked in a row (brain.turns.QUESTIONS_PER_REQUEST).
    questions_asked: int = Field(0, ge=0, le=20)
    # Auto mode: never ask, and run whole-edit plans without waiting for approval.
    auto: bool = False
    model: str | None = Field(None, min_length=1, max_length=80)
    effort: Effort | None = None


class AgentText(BaseModel):
    """event: text. What the agent says, between tool calls or as its answer."""

    text: str


class AgentToolCall(BaseModel):
    """event: tool. A tool call starting, with a line the user reads."""

    id: str
    name: str
    label: str


class AgentToolDone(BaseModel):
    """event: tool_done. A tool call finished; ``error`` says why it didn't work."""

    id: str
    ok: bool
    error: str | None = None


class AgentEdit(BaseModel):
    """event: edit. The agent changed the project: one undoable step."""

    label: str
    version: int
    # For POST /editor/projects/{id}/steps/{step_id}/undo.
    undo_step_id: str


class AgentUndone(BaseModel):
    """event: undone. The agent took back one of its own edits."""

    undo_step_id: str
    version: int


class AgentUi(BaseModel):
    """event: ui. Something for the studio to do: move the playhead, select, play a range, open a panel."""

    action: Literal["seek", "select", "play", "panel"]
    # seek and play: where, in seconds; play stops at ``end``.
    seconds: float | None = None
    end: float | None = None
    item_ids: list[str] = Field(default_factory=list)
    panel: StudioPanel | None = None


class AgentTodo(BaseModel):
    text: str = Field(..., min_length=1, max_length=100)
    status: TodoStatus


class AgentTodos(BaseModel):
    """event: todos. The agent's to-do list for a longer job, replaced whole each time."""

    items: list[AgentTodo]


class AgentAsk(BaseModel):
    """event: ask. A question for the user; picking an option sends it as the next prompt."""

    question: str
    options: list[str] = Field(default_factory=list)


class AgentDone(BaseModel):
    """event: done. The turn is over; ``message`` explains a stop that wasn't an answer."""

    reason: AgentStopReason
    message: str | None = None


class AgentError(BaseModel):
    """event: error. The turn broke off; what to tell the user."""

    message: str


# Also streamed: event "plan" (PlanCard), "render" (RenderStatus), "result" (TurnResult, for
# undo, redo, split and delete, which need no model).
