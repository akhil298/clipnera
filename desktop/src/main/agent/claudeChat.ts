import { spawn, type ChildProcess } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { createInterface } from 'node:readline'
import type { AgentEvent, AgentRequest } from '../../shared/agent'

/** The model name the chat uses for the person's own Claude, through their Claude Code. */
export const CLAUDE_CODE_MODEL = 'claude-code'
// Claude Code reaches the editor only through these tools: no files, no shell on this Mac.
const SERVER = 'clipnera'
export const SYSTEM = [
  'You are a professional video editor inside Clipnera Studio, talking to the person in its chat panel. They hired you for',
  'your judgement: decide what the video needs, make it, check it, and be able to say why every cut, zoom, sound and title is there.',
  'Before your first edit in a conversation, read clipnera_editing_playbook and work the way it says.',
  'You edit only through the clipnera tools. Read the project and footage with clipnera_get_project, clipnera_get_media,',
  'clipnera_get_transcript_range and clipnera_media_search (find every moment by what is said). Edit with clipnera_apply_edits,',
  'one idea per call (each is one undoable step on the timeline); pass the person\'s message as user_request when a title uses',
  'their words. Use the shelves through clipnera_find_effects, clipnera_set_music, clipnera_find_broll and clipnera_place_broll,',
  'and clipnera_open_with_moment for a hook. Check your work with clipnera_look_at_frames. clipnera_run_command runs the',
  'editor\'s own commands (playhead, selection, panels). Export with clipnera_export only when asked.',
  'For two or more changes, keep a to-do list and work through it item by item, carrying on after a failure.',
  'Write plainly, without markdown headings or tables. Never mention tools, ids, files or terminals: the person only sees the editor.'
].join(' ')

export interface ClaudeChatDeps {
  /** The person's Claude Code, or null when it isn't installed. */
  claudePath(): Promise<string | null>
  /** The editor's agent access, turned on: its address and token. */
  editorAccess(): Promise<{ url: string; token: string }>
  /** Where Claude Code runs: a folder of the app's own, so no project's settings load. */
  workdir: string
  emit(event: AgentEvent): void
}

type Block = { type: string; text?: string; id?: string; name?: string; input?: Record<string, unknown>; tool_use_id?: string; is_error?: boolean; content?: unknown }
type StreamLine = {
  type: string
  subtype?: string
  session_id?: string
  is_error?: boolean
  result?: string
  message?: { content?: Block[] | string }
}

/** What a tool call does, as the chat's tool line says it. */
export function toolLabel(name: string, input: Record<string, unknown> = {}): string {
  const tool = name.replace(`mcp__${SERVER}__`, '')
  switch (tool) {
    case 'clipnera_get_project':
      return 'Reading the timeline'
    case 'clipnera_get_media':
      return 'Looking at the footage'
    case 'clipnera_list_commands':
      return 'Looking through the editor'
    case 'clipnera_run_command':
      return `Running ${String(input.command ?? 'a command')}`
    case 'clipnera_ask_clipnera_ai':
      return 'Planning the edit with Clipnera'
    case 'clipnera_export':
      return input.action === 'start' ? 'Starting the export' : 'Checking the export'
    case 'clipnera_editing_playbook':
      return 'Reading the editing playbook'
    case 'clipnera_get_timeline':
      return 'Reading the timeline'
    case 'clipnera_get_transcript_range':
      return 'Reading the transcript'
    case 'clipnera_media_search':
      return `Searching the footage for “${String(input.query ?? '')}”`
    case 'clipnera_find_effects':
      return 'Looking through the effects'
    case 'clipnera_look_at_frames':
      return 'Looking at the frames'
    case 'clipnera_apply_edits':
    case 'clipnera_set_music':
    case 'clipnera_place_broll':
    case 'clipnera_open_with_moment':
      return String(input.label ?? 'Editing')
    default:
      return tool.replace(/_/g, ' ')
  }
}

const text = (content: unknown): string =>
  typeof content === 'string' ? content : Array.isArray(content) ? content.map((c) => (c as Block).text ?? '').join(' ') : ''

/** The chat's events for one line of Claude Code's stream-json output. */
export function eventsOf(line: StreamLine): AgentEvent[] {
  const blocks = Array.isArray(line.message?.content) ? line.message.content : []
  if (line.type === 'assistant') {
    return blocks.flatMap((b): AgentEvent[] => {
      if (b.type === 'text' && b.text?.trim()) return [{ event: 'text', data: { text: b.text.trim() } }]
      if (b.type === 'tool_use' && b.id && b.name) return [{ event: 'tool', data: { id: b.id, name: b.name, label: toolLabel(b.name, b.input) } }]
      return []
    })
  }
  if (line.type === 'user') {
    return blocks
      .filter((b) => b.type === 'tool_result' && b.tool_use_id)
      .map((b): AgentEvent => ({ event: 'tool_done', data: { id: b.tool_use_id!, ok: !b.is_error, error: b.is_error ? text(b.content).slice(0, 300) || 'failed' : null } }))
  }
  if (line.type === 'result') {
    return line.is_error
      ? [{ event: 'error', data: { message: line.result?.trim() || 'Claude couldn’t finish that.' } }]
      : [{ event: 'done', data: { reason: 'answered', message: null } }]
  }
  return []
}

/**
 * The chat on the person's own Claude: their Claude Code, signed in with their own plan, run in the
 * background (its documented headless mode) with only the editor's tools, its stream shown in the
 * chat as the backend agent's would be. One Claude conversation per project, continued turn by turn.
 */
export class ClaudeChat {
  private child: ChildProcess | null = null
  private readonly sessions = new Map<string, string>()

  constructor(private readonly deps: ClaudeChatDeps) {}

  get running(): boolean {
    return this.child !== null
  }

  async send(projectId: string, request: AgentRequest): Promise<void> {
    const path = await this.deps.claudePath()
    if (!path) throw new Error('Claude Code isn’t installed on this Mac: open Use my Claude to install it')
    const { url, token } = await this.deps.editorAccess()
    const config = JSON.stringify({ mcpServers: { [SERVER]: { type: 'http', url, headers: { Authorization: `Bearer ${token}` } } } })
    const session = this.sessions.get(projectId)
    const args = [
      '-p', request.prompt, '--output-format', 'stream-json', '--verbose',
      '--mcp-config', config, '--strict-mcp-config', '--tools', '', '--allowedTools', `mcp__${SERVER}`,
      '--permission-mode', 'dontAsk', '--append-system-prompt', SYSTEM,
      ...(session ? ['--resume', session] : [])
    ]
    await mkdir(this.deps.workdir, { recursive: true })
    const child = spawn(path, args, { cwd: this.deps.workdir, stdio: ['ignore', 'pipe', 'pipe'] })
    this.child = child
    let ended = false
    let stderr = ''
    child.stderr?.on('data', (chunk: Buffer) => (stderr = (stderr + chunk.toString()).slice(-2000)))
    const lines = createInterface({ input: child.stdout! })
    lines.on('line', (raw) => {
      let line: StreamLine
      try {
        line = JSON.parse(raw) as StreamLine
      } catch {
        return
      }
      if (line.session_id) this.sessions.set(projectId, line.session_id)
      for (const event of eventsOf(line)) {
        if (event.event === 'done' || event.event === 'error') ended = true
        this.deps.emit(event)
      }
    })
    await new Promise<void>((resolve) => child.on('close', () => resolve()))
    this.child = null
    if (!ended) this.deps.emit({ event: 'error', data: { message: stderr.trim().split('\n').pop() || 'Claude stopped without answering.' } })
  }

  /** Ends the turn: what Claude already changed stays, each step undoable in the editor. */
  stop(): void {
    this.child?.kill('SIGINT')
  }
}
