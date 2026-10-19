import { toFrames, type Timeline } from '@timeline'
import type { AgentRequest, StudioPanel } from '../../../shared/agent'
import type { AgentMessage } from '../../../shared/ipc'
import type { Player } from '../player/player'
import { auth } from '../state/auth'
import { reason } from '../state/errors'
import { chat, reduce, startTurn, turnSettled } from '../state/chat'
import { project, settled } from '../state/project'
import { rules } from '../state/rules'
import { media } from '../state/media'
import { BURNED_IN_TEXT_SHARE } from '../../../shared/media'
import { saveTake } from './takes'
import { toggleVoice } from '../state/voice'
import { rangeLabel, timelineView } from '../state/selection'
import type { SideView } from '../state/layout'
import type { CommandRegistry } from './registry'

const MODEL_KEY = 'clipnera.aiModel'
/** The model the chat uses unless the person picks another, when the backend offers it. */
export const PREFERRED_MODEL = 'gpt-6-astra-1'
const TOUCHED_MS = 4000
const PANELS: Partial<Record<StudioPanel, SideView>> = { media: 'media', sounds: 'sounds', text: 'text', captions: 'text', effects: 'effects', transitions: 'effects' }

function savedModel(): string | null {
  try {
    return localStorage.getItem(MODEL_KEY)
  } catch {
    return null
  }
}

export function pickModel(model: string): void {
  chat.set({ model })
  try {
    localStorage.setItem(MODEL_KEY, model)
  } catch {
    // Remembering the pick is a convenience.
  }
}

/** Items that are new or different in `after`: what the AI just changed, for its cursor. */
export function changedItems(before: Timeline | null, after: Timeline): string[] {
  const old = new Map(before?.tracks.flatMap((t) => t.items.map((i) => [i.id, JSON.stringify(i)] as const)) ?? [])
  return after.tracks.flatMap((t) => t.items).filter((i) => old.get(i.id) !== JSON.stringify(i)).map((i) => i.id)
}

export async function sendPrompt(prompt: string, player: Player, from?: string): Promise<void> {
  const text = prompt.trim()
  const state = chat.get()
  if (!text) throw new Error('Type what you want done')
  if (state.unavailable) throw new Error(state.unavailable)
  if (state.running) throw new Error('The AI is still working. Press Esc to stop it.')
  // The agent reads the project from the backend, so the person's own edits go first.
  await settled()
  const timeline = project.get().timeline
  const { mode, time } = player.state.get()
  const { range, point } = timelineView.get()
  let questions = 0
  for (const t of [...state.turns].reverse()) {
    if (!t.ask) break
    questions++
  }
  const request: AgentRequest = {
    prompt: text.slice(0, 2000),
    selection: timelineView.get().selection.slice(0, 200),
    playhead: mode === 'timeline' && timeline ? toFrames(time * timeline.fps) : 0,
    range: range && timeline ? { start: toFrames(range.start * timeline.fps), end: Math.max(toFrames(range.end * timeline.fps), toFrames(range.start * timeline.fps) + 1) } : null,
    point: point ? { x: point.x, y: point.y } : null,
    rules: rules.get().list,
    subtitled: media.get().items.filter((m) => timeline?.assets[m.id] && (m.onScreenText?.share ?? 0) >= BURNED_IN_TEXT_SHARE).map((m) => m.id).slice(0, 50),
    history: state.turns.slice(-6).map((t) => ({ prompt: t.prompt.slice(0, 2000), reply: t.text.join('\n\n').slice(0, 4000) })),
    questions_asked: questions,
    auto: state.auto,
    model: state.model,
    effort: null
  }
  // Whatever the AI does, the edit before it is one click away.
  if (timeline?.tracks.some((t) => t.items.length)) await saveTake(`Before “${text.slice(0, 50)}”`, 'auto').catch(() => undefined)
  const turn = startTurn(text, from ? `via ${from}` : range ? rangeLabel(range) : point ? 'this spot' : null)
  // A spot is about one request; a range stays until it's cleared.
  if (point) timelineView.set({ point: null })
  await window.clipnera.agent.send(request)
  await turnSettled(turn)
}

const ARRIVAL_MS = 5000

/** Resolves once every id is on the timeline: the agent's edit and its "select this" race each other. */
function whenOnTimeline(ids: string[]): Promise<void> {
  const present = () => {
    const items = new Set(project.get().timeline?.tracks.flatMap((t) => t.items.map((i) => i.id)) ?? [])
    return ids.every((id) => items.has(id))
  }
  if (present()) return Promise.resolve()
  return new Promise((resolve) => {
    const done = () => {
      off()
      clearTimeout(timer)
      resolve()
    }
    const off = project.subscribe(() => present() && done())
    const timer = setTimeout(done, ARRIVAL_MS)
  })
}

/** The agent asked the studio to do something: run it as the AI, so the Activity log says so. */
function act(registry: CommandRegistry, player: Player, msg: AgentMessage): void {
  if (msg.source !== 'agent' || msg.message.event !== 'ui') return
  const ui = msg.message.data
  const run = (id: string, args?: unknown) => void registry.execute(id, args, 'ai').catch(() => undefined)
  if ((ui.action === 'seek' || ui.action === 'play') && player.state.get().mode !== 'timeline') run('player.showTimeline')
  if (ui.action === 'seek' && ui.seconds !== null) run('player.seek', { seconds: ui.seconds })
  if (ui.action === 'play' && ui.seconds !== null) run('player.playRange', { from: ui.seconds, to: ui.end ?? ui.seconds + 5 })
  if (ui.action === 'select') void whenOnTimeline(ui.item_ids).then(() => run('timeline.select', { items: ui.item_ids }))
  if (ui.action === 'panel' && ui.panel && PANELS[ui.panel]) run('view.showSideView', { view: PANELS[ui.panel] })
}

export function registerAgentCommands(registry: CommandRegistry, player: Player): () => void {
  const offEvents = window.clipnera.agent.onEvent((msg) => {
    chat.set(reduce(chat.get(), msg))
    act(registry, player, msg)
  })

  // Highlight what the AI changed whenever the project moves on while it works.
  let before = project.get().timeline
  let version = project.get().project?.version ?? 0
  let clear: ReturnType<typeof setTimeout> | undefined
  const offProject = project.subscribe(() => {
    const { project: snapshot, timeline } = project.get()
    if (!snapshot || !timeline) return
    if (snapshot.version > version && chat.get().running) {
      chat.set({ touched: changedItems(before, timeline) })
      clearTimeout(clear)
      clear = setTimeout(() => chat.set({ touched: [] }), TOUCHED_MS)
    }
    version = snapshot.version
    before = timeline
  })

  // The models (and whether the AI is available at all) depend on who is signed in.
  const loadModels = () =>
    void window.clipnera.agent
      .models()
      .then((models) => {
        const saved = savedModel()
        const fallback = models.models.includes(PREFERRED_MODEL) ? PREFERRED_MODEL : models.default_model
        chat.set({ models, unavailable: null, model: saved && models.models.includes(saved) ? saved : fallback })
      })
      .catch((error: unknown) => chat.set({ models: null, unavailable: reason(error) }))
  let signedIn: string | null = null
  const followAuth = () => {
    const state = auth.get().state
    const user = state.status === 'signedIn' ? state.user.id : null
    if (user === signedIn) return
    signedIn = user
    if (user) loadModels()
    else chat.set({ models: null, unavailable: 'Sign in to use the AI' })
  }
  const offAuth = auth.subscribe(followAuth)
  followAuth()

  const disposers = [
    registry.register<{ prompt: string }>({
      id: 'agent.send',
      title: 'Ask the AI',
      category: 'AI',
      description: 'Send a request to the AI editor.',
      aiCanRun: false,
      needsArgs: true,
      run: (args) => sendPrompt(String(args?.prompt ?? ''), player)
    }),
    registry.register({
      id: 'agent.stop',
      title: 'Stop the AI',
      category: 'AI',
      description: 'Stop the AI. What it already did stays, and each step can be undone.',
      shortcut: 'Escape',
      aiCanRun: false,
      when: () => chat.get().running,
      run: () => window.clipnera.agent.stop()
    }),
    registry.register({
      id: 'voice.toggle',
      title: 'Voice Note',
      category: 'AI',
      description: 'Start or stop a voice note for the AI; what you say goes in the chat box.',
      shortcut: 'Shift+Mod+V',
      aiCanRun: false,
      run: () => toggleVoice()
    }),
    registry.register<{ step: string }>({
      id: 'agent.undoStep',
      title: 'Undo an AI Step',
      category: 'AI',
      description: 'Take back one step the AI made.',
      aiCanRun: false,
      needsArgs: true,
      run: (args) => window.clipnera.agent.undoStep(String(args?.step ?? ''))
    })
  ]
  return () => {
    offEvents()
    offProject()
    offAuth()
    clearTimeout(clear)
    disposers.forEach((dispose) => dispose())
  }
}
