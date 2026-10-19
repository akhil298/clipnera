import { randomUUID } from 'node:crypto'
import { join } from 'node:path'
import { app, BrowserWindow, ipcMain } from 'electron'
import { IPC, type McpState, type McpWindowRequest, type McpWindowResponse } from '../../shared/ipc'
import type { MediaLibrary } from '../media/library'
import type { ProjectService } from '../project/service'
import type { Session, Tool } from './protocol'
import { McpServer } from './server'
import { DEFAULT_PORT, McpSettingsStore } from './settings'
import { summarizeMedia, summarizeProject } from './summary'

const WINDOW_TIMEOUT_MS = 30_000
// A whole edit by Clipnera's AI takes minutes.
const ASK_TIMEOUT_MS = 20 * 60_000
type WithoutId<T> = T extends unknown ? Omit<T, 'id'> : never

/** Lets Claude Code, Codex and other MCP clients drive the open project, when the person allows it. */
export function setUpMcp(projects: ProjectService, library: MediaLibrary): void {
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

  const tools = (session: Session): Tool[] => [
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
      description: "The project's footage and what Clipnera's AI understood of it (summary, best moments).",
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
    }
  ]

  const server = new McpServer(tools, app.getVersion())
  const state = async (): Promise<McpState> => {
    const settings = await store.get()
    const port = Number(process.env.CLIPNERA_MCP_PORT) || settings.port || DEFAULT_PORT
    return { enabled: settings.enabled, listening: server.listening, port, token: settings.token, url: `http://127.0.0.1:${port}/mcp`, bridge, error }
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
  app.on('will-quit', () => server.stop())

  // Tests turn it on for a run without touching the saved choice.
  if (!app.isPackaged && process.env.CLIPNERA_MCP_ENABLE === '1') void store.get().then((s) => store.save({ ...s, enabled: true })).then(apply)
  else void apply()
}
