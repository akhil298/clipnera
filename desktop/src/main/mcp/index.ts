import { randomUUID } from 'node:crypto'
import { appendFile } from 'node:fs/promises'
import { join } from 'node:path'
import { app, BrowserWindow, ipcMain } from 'electron'
import { CLAUDE_INSTALL_COMMAND, IPC, type McpState, type McpWindowRequest, type McpWindowResponse } from '../../shared/ipc'
import type { AgentToolSpec } from '../../shared/api'
import { subtitledAssets } from '../../shared/media'
import type { ExportService } from '../export/service'
import type { MediaLibrary } from '../media/library'
import type { ProjectService } from '../project/service'
import { Pictured, type Session, type Tool } from './protocol'
import { ClaudeCode, macHost } from './claudeCode'
import { McpServer } from './server'
import { DEFAULT_PORT, McpSettingsStore } from './settings'
import { summarizeMedia, summarizeProject } from './summary'

const WINDOW_TIMEOUT_MS = 30_000
// A whole edit by Clipnera's AI takes minutes.
const ASK_TIMEOUT_MS = 20 * 60_000
type WithoutId<T> = T extends unknown ? Omit<T, 'id'> : never

/** apply_edits' arguments, plus the person's words, so a title they asked for may use them (the never-do list keeps made-up text off screen). */
function withRequest(schema: Record<string, unknown>): Record<string, unknown> {
  const properties = (schema.properties ?? {}) as Record<string, unknown>
  return {
    ...schema,
    properties: { ...properties, user_request: { type: 'string', description: 'The person’s message you are carrying out, word for word, when this edit puts words of theirs on screen (a title or card they asked for).' } }
  }
}

/** Lets Claude Code, Codex and other MCP clients drive the open project, when the person allows it. */
/** Until Anthropic approves Clipnera for it, the chat on a person's own Claude is for development builds only. */
const CLAUDE_CHAT_AVAILABLE = !app.isPackaged || process.env.CLIPNERA_PERSONAL_CLAUDE === '1'

export interface McpAccess {
  claude: ClaudeCode
  /** Whether the chat may run on the person's own Claude now. */
  claudeChatOn(): Promise<boolean>
  /** The editor's agent access, turned on if it was off. */
  ensureOn(): Promise<McpState>
}

export function setUpMcp(projects: ProjectService, library: MediaLibrary, exports: ExportService): McpAccess {
  const store = new McpSettingsStore(join(app.getPath('userData'), 'mcp.json'))
  const pending = new Map<string, (response: McpWindowResponse) => void>()
  // The bridge script ships next to the app; in development it is in desktop/bin.
  const bridge = app.isPackaged ? join(process.resourcesPath, 'clipnera-mcp.mjs') : join(app.getAppPath(), 'bin', 'clipnera-mcp.mjs')
  let error: string | null = null

  /** Asks the editor window, which holds the command registry, and waits for its answer. */
  const ask = (request: WithoutId<McpWindowRequest>, timeout = WINDOW_TIMEOUT_MS): Promise<unknown> => {
    const window = BrowserWindow.getAllWindows()[0]
    if (!window) return Promise.reject(new Error('Clipnera Studio has no window open'))
    const id = randomUUID()
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id)
        reject(new Error('Clipnera Studio did not answer in time'))
      }, timeout)
      pending.set(id, (response) => {
        clearTimeout(timer)
        pending.delete(id)
        if (response.ok) resolve(response.result)
        else reject(new Error(response.error))
      })
      window.webContents.send(IPC.mcpRequest, { ...request, id } as McpWindowRequest)
    })
  }

  const project = () => {
    const open = projects.get().project
    if (!open) throw new Error('No project is open in Clipnera Studio')
    return open
  }
  const text = (value: unknown, name: string) => {
    if (typeof value !== 'string' || !value.trim()) throw new Error(`${name} is required`)
    return value
  }

  // The studio agent's own tools, run on the backend: the same hands Clipnera's AI has (the transcript,
  // edits, the shelves, the hook, frames). Read once; none until the person is signed in.
  let specs: AgentToolSpec[] = []
  const aiTools = async (): Promise<Tool[]> => {
    if (!specs.length) specs = await projects.agentTools().catch(() => [])
    return specs.map((spec) => ({
      name: `clipnera_${spec.name}`,
      description: spec.description,
      inputSchema: spec.name === 'apply_edits' ? withRequest(spec.input_schema) : spec.input_schema,
      run: async ({ user_request, ...args }) => {
        const output = await projects.agentTool(spec.name, {
          arguments: args,
          prompt: typeof user_request === 'string' ? user_request.slice(0, 4000) : '',
          selection: [],
          subtitled: subtitledAssets(library.list(), project().timeline.assets)
        })
        if (output.is_error) throw new Error(output.text)
        return output.images.length ? new Pictured(output.text, output.images) : output.text
      }
    }))
  }

  const tools = async (session: Session): Promise<Tool[]> => [
    {
      name: 'clipnera_get_project',
      description: 'The open project: its tracks and items (times in seconds), captions and look.',
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      run: async () => {
        const open = project()
        return summarizeProject(open.title, open.version, open.timeline, library.list())
      }
    },
    {
      name: 'clipnera_get_media',
      description: "The project's footage and what Clipnera's AI understood of it (summary, what happens part by part).",
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      run: async () => summarizeMedia(library.list(), projects.get().analysis)
    },
    {
      name: 'clipnera_list_commands',
      description: 'Every editor command an agent may run, with what it does and whether it needs arguments.',
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      run: () => ask({ kind: 'commands' })
    },
    {
      name: 'clipnera_run_command',
      description: 'Run one editor command (an id from clipnera_list_commands) with its arguments. Each run is one undoable step.',
      inputSchema: {
        type: 'object',
        properties: { command: { type: 'string', description: 'e.g. timeline.split' }, args: { type: 'object', description: 'The command’s arguments, if it takes any' } },
        required: ['command'],
        additionalProperties: false
      },
      run: async (args) => {
        await ask({ kind: 'run', command: text(args.command, 'command'), args: args.args, client: session.client })
        const open = project()
        return { done: true, project: summarizeProject(open.title, open.version, open.timeline, library.list()) }
      }
    },
    {
      name: 'clipnera_ask_clipnera_ai',
      description: "Hand a request to Clipnera's own AI, which has watched and transcribed the footage (best for whole edits). A plan it makes waits for the person to approve it in the app.",
      inputSchema: { type: 'object', properties: { prompt: { type: 'string' } }, required: ['prompt'], additionalProperties: false },
      run: (args) => ask({ kind: 'ask', prompt: text(args.prompt, 'prompt'), client: session.client }, ASK_TIMEOUT_MS)
    },
    {
      name: 'clipnera_export',
      description: 'Render the saved edit to an MP4 on this Mac (Movies/Clipnera), or check how that render is going. Start one only when the person asked to export in this conversation.',
      inputSchema: { type: 'object', properties: { action: { type: 'string', enum: ['start', 'status'] } }, required: ['action'], additionalProperties: false },
      run: async (args) => {
        if (args.action === 'start') {
          project()
          void exports.start()
        }
        return exports.get()
      }
    },
    ...(await aiTools())
  ]

  const server = new McpServer(tools, app.getVersion())
  const state = async (): Promise<McpState> => {
    const settings = await store.get()
    const port = Number(process.env.CLIPNERA_MCP_PORT) || settings.port || DEFAULT_PORT
    return { enabled: settings.enabled, listening: server.listening, port, token: settings.token, url: `http://127.0.0.1:${port}/mcp`, bridge, error,
             claudeChatAvailable: CLAUDE_CHAT_AVAILABLE, claudeChat: CLAUDE_CHAT_AVAILABLE && settings.claudeChat }
  }
  const broadcast = async () => {
    const current = await state()
    BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.mcpChanged, current))
    return current
  }
  const apply = async () => {
    const current = await state()
    error = null
    server.stop()
    if (current.enabled) await server.start(current.port, current.token).catch((e: Error) => (error = `Couldn't listen on port ${current.port}: ${e.message}`))
    return broadcast()
  }

  ipcMain.handle(IPC.mcpGet, () => state())
  ipcMain.handle(IPC.mcpSetEnabled, async (_event, enabled: unknown) => {
    await store.save({ ...(await store.get()), enabled: enabled === true })
    return apply()
  })
  ipcMain.handle(IPC.mcpRespond, (_event, id: unknown, response: McpWindowResponse) => {
    if (typeof id === 'string') pending.get(id)?.(response)
  })
  // The person's own Claude Code, signed in with their own plan: connected here, opened in Terminal.
  // Tests use a stand-in Claude Code, and record the Terminal commands instead of opening Terminal.
  const testing = !app.isPackaged && process.env.CLIPNERA_CLAUDE_PATH
  const host = testing && process.env.CLIPNERA_TERMINAL_LOG
    ? { ...macHost, terminal: (command: string) => appendFile(process.env.CLIPNERA_TERMINAL_LOG!, `${command}\n`) }
    : macHost
  const claude = new ClaudeCode(host, testing || undefined)
  ipcMain.handle(IPC.claudeStatus, () => claude.status())
  const ensureOn = async (): Promise<McpState> => {
    const current = await state()
    if (current.enabled && current.listening) return current
    await store.save({ ...(await store.get()), enabled: true })
    const started = await apply()
    if (!started.listening) throw new Error(started.error ?? 'Clipnera Studio couldn’t start the connection for Claude')
    return started
  }
  ipcMain.handle(IPC.claudeSetChat, async (_event, on: unknown) => {
    await store.save({ ...(await store.get()), claudeChat: on === true && CLAUDE_CHAT_AVAILABLE })
    return broadcast()
  })
  ipcMain.handle(IPC.claudeOpen, async () => {
    const status = await claude.status()
    if (!status.path) throw new Error('Claude Code isn’t installed on this Mac yet')
    const current = await ensureOn()
    await claude.connect(status.path, current.url, current.token)
    await claude.open(status.path)
    return status
  })
  ipcMain.handle(IPC.claudeInstall, () => host.terminal(CLAUDE_INSTALL_COMMAND))
  app.on('will-quit', () => server.stop())

  // Tests turn it on for a run without touching the saved choice.
  if (!app.isPackaged && process.env.CLIPNERA_MCP_ENABLE === '1') void store.get().then((s) => store.save({ ...s, enabled: true })).then(apply)
  else void apply()
  return { claude, claudeChatOn: async () => (await state()).claudeChat, ensureOn }
}
