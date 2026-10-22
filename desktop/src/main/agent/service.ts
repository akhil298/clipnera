import { OWN_KEY_MODELS, type AgentEvent, type AgentRequest, type AiModels, type PlanCard, type PlanEvent, type RenderStatus, type VoiceText } from '../../shared/agent'
import type { EditorOpsResponse } from '../../shared/api'
import type { AgentMessage } from '../../shared/ipc'
import { api, API_URL, ApiRequestError } from '../api'
import type { ProjectService } from '../project/service'
import { CLAUDE_CODE_MODEL, type ClaudeChat } from './claudeChat'
import { readEvents } from './sse'

export interface AgentDeps {
  token(): Promise<string | null>
  /** Called when a turn or plan ends: it may have spent credits. */
  settled(): void
  /** The AI started an export (its start_export tool). */
  rendering(render: RenderStatus): void
  projects: ProjectService
  emit(message: AgentMessage): void
  /** The chat on the person's own Claude, when they turned it on (personal, in development builds). */
  claude?: { chat: ClaudeChat; offered(): Promise<boolean> }
  /** The person's own Anthropic API key, when they saved one. */
  anthropicKey?(): Promise<string | null>
}

const message = (error: unknown) => (error instanceof Error ? error.message : String(error))
const PLAN_RUNS = new Set(['approved', 'running'])

/**
 * The chat's link to the backend's studio agent (POST /editor/projects/{id}/agent, SSE).
 * Every event goes to the chat as it arrives; whenever the agent changes the project the
 * timeline is refreshed. Whole-edit plans are followed step by step once approved.
 */
export class AgentService {
  private turn: AbortController | null = null
  private readonly plans = new Map<string, AbortController>()

  constructor(private readonly deps: AgentDeps) {}

  get running(): boolean {
    return this.turn !== null || this.plans.size > 0
  }

  async models(): Promise<AiModels> {
    const found = await api.getData<AiModels>('/editor/models', await this.auth())
    // Claude on the person's own API key, and their own Claude through Claude Code, join the list when set up.
    const ownKey = (await this.deps.anthropicKey?.()) ? [...OWN_KEY_MODELS] : []
    const claudeCode = (await this.deps.claude?.offered()) ? [CLAUDE_CODE_MODEL] : []
    return { ...found, models: [...found.models, ...ownKey, ...claudeCode] }
  }

  async send(request: AgentRequest): Promise<void> {
    if (this.turn || this.deps.claude?.chat.running) throw new Error('The AI is still working on your last request')
    const projectId = this.projectId()
    if (request.model === CLAUDE_CODE_MODEL && this.deps.claude) return this.sendToClaude(projectId, request)
    const token = await this.auth()
    const turn = (this.turn = new AbortController())
    try {
      // A turn on the person's own key carries it, for that turn only.
      const key = (OWN_KEY_MODELS as readonly string[]).includes(request.model ?? '') ? await this.deps.anthropicKey?.() : null
      const body = await api.stream(`/editor/projects/${projectId}/agent`, request, token, turn.signal, key ? { 'X-Anthropic-Key': key } : {})
      await readEvents(body, (event) => this.onAgent(event as AgentEvent))
    } catch (error) {
      if (turn.signal.aborted) this.deps.emit({ source: 'app', message: { event: 'stopped' } })
      else this.deps.emit({ source: 'app', message: { event: 'error', data: { message: message(error) } } })
    } finally {
      this.turn = null
      this.deps.emit({ source: 'app', message: { event: 'idle' } })
      this.deps.settled()
    }
  }

  /** The turn on the person's own Claude: its events go to the chat like the backend agent's. */
  private async sendToClaude(projectId: string, request: AgentRequest): Promise<void> {
    try {
      await this.deps.claude!.chat.send(projectId, request)
    } catch (error) {
      this.deps.emit({ source: 'app', message: { event: 'error', data: { message: message(error) } } })
    } finally {
      this.deps.emit({ source: 'app', message: { event: 'idle' } })
    }
  }

  /** Stops the turn in flight and any plan that is running. Edits already made stay, each undoable. */
  async stop(): Promise<void> {
    this.deps.claude?.chat.stop()
    this.turn?.abort()
    const token = await this.deps.token()
    for (const [planId, stream] of this.plans) {
      stream.abort()
      if (token) await api.postData(`/editor/plans/${planId}/stop`, {}, token).catch(() => undefined)
    }
    this.plans.clear()
  }

  async approve(planId: string): Promise<PlanCard> {
    const card = await api.postData<PlanCard>(`/editor/plans/${planId}/approve`, {}, await this.auth())
    this.deps.emit({ source: 'agent', message: { event: 'plan', data: card } })
    void this.follow(planId)
    return card
  }

  async reject(planId: string): Promise<PlanCard> {
    const card = await api.postData<PlanCard>(`/editor/plans/${planId}/reject`, {}, await this.auth())
    this.deps.emit({ source: 'agent', message: { event: 'plan', data: card } })
    return card
  }

  /** Takes back one AI step (its undo chip), whatever has happened since. */
  async undoStep(stepId: string): Promise<void> {
    await api.postData<EditorOpsResponse>(`/editor/projects/${this.projectId()}/steps/${stepId}/undo`, {}, await this.auth())
    await this.deps.projects.refresh()
  }

  /** Sends a voice note to the backend's transcription (the same as footage gets). */
  async transcribe(audio: Uint8Array, type: string, seconds: number): Promise<string> {
    const form = new FormData()
    form.append('audio', new Blob([new Uint8Array(audio)], { type }), 'note.webm')
    form.append('seconds', String(seconds))
    const response = await fetch(`${API_URL}/api/v1/editor/voice`, { method: 'POST', headers: { Authorization: `Bearer ${await this.auth()}` }, body: form })
    const json = (await response.json().catch(() => null)) as { data?: VoiceText; message?: string; error?: string } | null
    if (!response.ok || !json?.data) throw new ApiRequestError(response.status, json?.error ?? 'VOICE_FAILED', json?.message ?? 'The voice note could not be read')
    return json.data.text
  }

  private onAgent(event: AgentEvent): void {
    this.deps.emit({ source: 'agent', message: event })
    const changed =
      event.event === 'edit' || event.event === 'undone' || (event.event === 'result' && event.data.version !== null)
    if (changed) void this.deps.projects.refresh().catch(() => undefined)
    if (event.event === 'render') this.deps.rendering(event.data)
    // In auto mode a plan starts by itself; follow it like an approved one.
    if (event.event === 'plan' && PLAN_RUNS.has(event.data.status)) void this.follow(event.data.id)
  }

  private async follow(planId: string): Promise<void> {
    if (this.plans.has(planId)) return
    const stream = new AbortController()
    this.plans.set(planId, stream)
    try {
      const body = await api.stream(`/editor/plans/${planId}/stream`, undefined, await this.auth(), stream.signal)
      await readEvents(body, (raw) => {
        const event = raw as PlanEvent
        this.deps.emit({ source: 'plan', planId, message: event })
        if (event.event === 'op.applied' || event.event === 'done') void this.deps.projects.refresh().catch(() => undefined)
      })
    } catch (error) {
      if (!stream.signal.aborted) this.deps.emit({ source: 'app', message: { event: 'error', data: { message: message(error) } } })
    } finally {
      this.plans.delete(planId)
      this.deps.emit({ source: 'app', message: { event: 'idle' } })
      this.deps.settled()
    }
  }

  private projectId(): string {
    const id = this.deps.projects.get().project?.id
    if (!id) throw new Error('No project is open')
    return id
  }

  private async auth(): Promise<string> {
    const token = await this.deps.token()
    if (!token) throw new Error('Sign in to use the AI')
    return token
  }
}
