import type { AiModels, PlanCard, TodoStatus } from '../../../shared/agent'
import type { AgentMessage } from '../../../shared/ipc'
import { createStore } from './store'

export interface ToolLine {
  id: string
  label: string
  status: 'running' | 'ok' | 'failed'
  error?: string
}

export interface EditChip {
  label: string
  undoStepId: string
  undone: boolean
}

export interface Turn {
  id: number
  prompt: string
  /** The selected range the request was about, e.g. "0:42–1:10". */
  scope: string | null
  /** What the agent said, paragraph by paragraph. */
  text: string[]
  tools: ToolLine[]
  edits: EditChip[]
  todos: { text: string; status: TodoStatus }[]
  ask: { question: string; options: string[] } | null
  plan: PlanCard | null
  status: 'working' | 'done' | 'stopped' | 'failed'
  /** Why the turn ended, when it wasn't simply answered. */
  note: string | null
}

export interface ChatState {
  turns: Turn[]
  /** A turn or a plan is in progress. */
  running: boolean
  models: AiModels | null
  model: string | null
  auto: boolean
  /** Why the AI can't be used here (preview mode, no access), or null. */
  unavailable: string | null
  /** Timeline items the AI just changed, highlighted as its cursor. */
  touched: string[]
}

export const chat = createStore<ChatState>({ turns: [], running: false, models: null, model: null, auto: false, unavailable: null, touched: [] })

const FINAL_PLAN = new Set(['done', 'failed', 'rejected', 'stopped'])

function updateTurn(turns: Turn[], match: (t: Turn) => boolean, change: (t: Turn) => Partial<Turn>): Turn[] {
  const index = turns.findLastIndex(match)
  if (index < 0) return turns
  const next = [...turns]
  next[index] = { ...turns[index], ...change(turns[index]) }
  return next
}

const current = (t: Turn) => t.status === 'working'
const withPlan = (planId: string) => (t: Turn) => t.plan?.id === planId

/** How one agent, plan or app message changes the conversation. */
export function reduce(state: ChatState, msg: AgentMessage): ChatState {
  const turns = (match: (t: Turn) => boolean, change: (t: Turn) => Partial<Turn>) => ({ ...state, turns: updateTurn(state.turns, match, change) })

  if (msg.source === 'app') {
    const { message } = msg
    if (message.event === 'stopped') return turns(current, () => ({ status: 'stopped', note: 'Stopped. What was already done stays, and each step can be undone.' }))
    if (message.event === 'error') return turns(current, () => ({ status: 'failed', note: message.data.message }))
    return { ...turns(current, (t) => ({ status: 'done', note: t.note })), running: state.turns.some((t) => t.plan && !FINAL_PLAN.has(t.plan.status)) }
  }

  if (msg.source === 'plan') {
    const { message, planId } = msg
    switch (message.event) {
      case 'plan.updated':
        return turns(withPlan(planId), () => ({ plan: message.data }))
      case 'agent.step':
        return turns(withPlan(planId), (t) => ({
          plan: t.plan && { ...t.plan, steps: t.plan.steps.map((s) => (s.id === message.data.step_id ? { ...s, status: message.data.status, note: message.data.note } : s)) }
        }))
      case 'op.applied':
        return message.data.cursor ? { ...state, touched: message.data.cursor.items } : state
      case 'done':
        return { ...turns(withPlan(planId), (t) => ({ plan: t.plan && { ...t.plan, status: message.data.status } })), running: false }
    }
  }

  const { message } = msg
  switch (message.event) {
    case 'text':
      return turns(current, (t) => ({ text: [...t.text, message.data.text] }))
    case 'tool':
      return turns(current, (t) => ({ tools: [...t.tools, { id: message.data.id, label: message.data.label, status: 'running' }] }))
    case 'tool_done':
      return turns(current, (t) => ({
        tools: t.tools.map((tool) => (tool.id === message.data.id ? { ...tool, status: message.data.ok ? 'ok' : 'failed', error: message.data.error ?? undefined } : tool))
      }))
    case 'edit':
      return turns(current, (t) => ({ edits: [...t.edits, { label: message.data.label, undoStepId: message.data.undo_step_id, undone: false }] }))
    case 'undone':
      return { ...state, turns: state.turns.map((t) => ({ ...t, edits: t.edits.map((e) => (e.undoStepId === message.data.undo_step_id ? { ...e, undone: true } : e)) })) }
    case 'todos':
      return turns(current, () => ({ todos: message.data.items }))
    case 'ask':
      return turns(current, () => ({ ask: message.data }))
    case 'plan':
      return state.turns.some(withPlan(message.data.id)) ? turns(withPlan(message.data.id), () => ({ plan: message.data })) : turns(current, () => ({ plan: message.data }))
    case 'result':
      return turns(current, (t) => ({
        text: message.data.message ? [...t.text, message.data.message] : t.text,
        edits: message.data.undo_step_id ? [...t.edits, { label: message.data.message, undoStepId: message.data.undo_step_id, undone: false }] : t.edits,
        plan: message.data.plan ?? t.plan,
        ask: message.data.options.length ? { question: message.data.message, options: message.data.options } : t.ask
      }))
    case 'done':
      return turns(current, () => ({ status: 'done', note: message.data.reason === 'answered' || message.data.reason === 'handed_over' ? null : message.data.message }))
    case 'error':
      return turns(current, () => ({ status: 'failed', note: message.data.message }))
    case 'ui':
    case 'render':
      return state
  }
}

let nextTurn = 1

/** Starts a turn in the chat; returns its id. */
export function startTurn(prompt: string, scope: string | null = null): number {
  const id = nextTurn++
  chat.set((s) => ({
    running: true,
    turns: [...s.turns, { id, prompt, scope, text: [], tools: [], edits: [], todos: [], ask: null, plan: null, status: 'working', note: null }]
  }))
  return id
}

// The reply to "send" and the turn's last events travel separately; a turn that never hears its end gives up after this.
const SETTLE_MS = 5000

/** Resolves once the chat shows the turn finished (or after a short wait). */
export function turnSettled(id: number): Promise<void> {
  const finished = () => chat.get().turns.find((t) => t.id === id)?.status !== 'working'
  if (finished()) return Promise.resolve()
  return new Promise((resolve) => {
    const done = () => {
      off()
      clearTimeout(timer)
      resolve()
    }
    const off = chat.subscribe(() => finished() && done())
    const timer = setTimeout(done, SETTLE_MS)
  })
}
