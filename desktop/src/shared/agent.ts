/** The studio agent's contract. Each type mirrors the Pydantic model named beside it in backend/brain/schema.py. */

/** clients/ai/roles.py Effort */
export type Effort = 'low' | 'medium' | 'high' | 'xhigh'

/** AiModels */
/** The Claude models for a person's own Anthropic API key (backend clients/ai/roles.py OWN_KEY_MODELS). */
export const OWN_KEY_MODELS = ['claude-sonnet-5-5', 'claude-opus-5-5'] as const

export interface AiModels {
  models: string[]
  default_model: string
  efforts: string[]
}

/** AgentExchange */
export interface AgentExchange {
  prompt: string
  reply: string
}

/** FrameRange — a selected stretch of the timeline, in frames; end exclusive. */
export interface FrameRange {
  start: number
  end: number
}

/** FramePoint — a spot in the picture, as shares of the frame's width and height. */
export interface FramePoint {
  x: number
  y: number
}

/** AgentRequest — POST /editor/projects/{id}/agent */
export interface AgentRequest {
  prompt: string
  selection: string[]
  /** Timeline frames. */
  playhead: number
  /** The part of the timeline the request is about (Select & ask). */
  range: FrameRange | null
  /** A spot in the picture the request is about, at the playhead (Point & ask). */
  point: FramePoint | null
  /** The user's standing rules for this project. */
  rules: string[]
  /** Assets in the project whose picture already has subtitles burned in (the text scan). */
  subtitled: string[]
  history: AgentExchange[]
  questions_asked: number
  auto: boolean
  model: string | null
  effort: Effort | null
}

export type StudioPanel = 'media' | 'sounds' | 'text' | 'stickers' | 'effects' | 'transitions' | 'captions' | 'adjustment' | 'settings'
export type TodoStatus = 'pending' | 'active' | 'done'
export type AgentStopReason = 'answered' | 'steps' | 'time' | 'budget' | 'refused' | 'handed_over' | 'failed'
export type PlanStatusName = 'proposed' | 'approved' | 'running' | 'paused' | 'done' | 'failed' | 'rejected' | 'stopped'
export type StepStatusName = 'pending' | 'running' | 'done' | 'failed' | 'skipped'
export type TurnKind = 'edit' | 'answer' | 'clarify' | 'choices' | 'plan' | 'plan_needed' | 'refused'

/** PlanCardStep */
export interface PlanCardStep {
  id: string
  kind: string
  intent: string
  why: string
  enabled: boolean
  optional: boolean
  status: StepStatusName
  credits: number
  depends_on: string[]
  note: string
  undo_step_id: string | null
}

/** GhostClip (frames) */
export interface GhostClip {
  at: number
  end: number
  label: string
}

/** PlanOutlinePart: a part of the planned edit (seconds on the edit). */
export interface PlanOutlinePart {
  start: number
  end: number
  /** The opening words of its first sentence, quoted. */
  said: string
  actions: string[]
}

/** PlanCard */
export interface PlanCard {
  id: string
  status: PlanStatusName
  title: string
  summary: string
  result_line: string
  credits: number
  credits_charged: number
  steps: PlanCardStep[]
  assumptions: string[]
  warnings: string[]
  premium: string[]
  ghost: GhostClip[]
  /** The edit part by part; empty on plans made before it existed. */
  outline: PlanOutlinePart[]
  fps: number
  runner_up_title: string | null
  error: string | null
}

/** TurnChoice */
export interface TurnChoice {
  id: string
  label: string
}

/** TurnResult (event "result"). `route` is brain/route.py RouteDecision, which the app only passes along. */
export interface TurnResult {
  kind: TurnKind
  message: string
  version: number | null
  undo_step_id: string | null
  choices: TurnChoice[]
  options: string[]
  plan: PlanCard | null
  route: Record<string, unknown> | null
}

/** RenderStatus (event "render") */
export interface RenderStatus {
  id: string
  status: 'queued' | 'rendering' | 'done' | 'failed'
  stage: string
  version: number
  download_url: string | null
  error: string | null
}

/** The agent's server-sent events, by name. */
export type AgentEvent =
  | { event: 'text'; data: { text: string } }
  | { event: 'tool'; data: { id: string; name: string; label: string } }
  | { event: 'tool_done'; data: { id: string; ok: boolean; error: string | null } }
  | { event: 'edit'; data: { label: string; version: number; undo_step_id: string } }
  | { event: 'undone'; data: { undo_step_id: string; version: number } }
  | { event: 'ui'; data: { action: 'seek' | 'select' | 'play' | 'panel'; seconds: number | null; end: number | null; item_ids: string[]; panel: StudioPanel | null } }
  | { event: 'todos'; data: { items: { text: string; status: TodoStatus }[] } }
  | { event: 'ask'; data: { question: string; options: string[] } }
  | { event: 'plan'; data: PlanCard }
  | { event: 'render'; data: RenderStatus }
  | { event: 'result'; data: TurnResult }
  | { event: 'done'; data: { reason: AgentStopReason; message: string | null } }
  | { event: 'error'; data: { message: string } }

/** What a running plan streams (brain/api.py GET /editor/plans/{id}/stream). */
export type PlanEvent =
  | { event: 'agent.step'; data: { step_id: string; status: StepStatusName; note: string } }
  /** cursor: who changed the project and the first items they touched — the agent cursor. */
  | { event: 'op.applied'; data: { version: number; cursor: { author: string; items: string[] } | null } }
  | { event: 'plan.updated'; data: PlanCard }
  | { event: 'done'; data: { status: PlanStatusName } }

/** brain/schema.py VoiceText — POST /editor/voice (multipart: audio, seconds) */
export interface VoiceText {
  text: string
}
