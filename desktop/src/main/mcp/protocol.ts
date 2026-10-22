/**
 * The Model Context Protocol, as much as Claude Code and Codex use: JSON-RPC 2.0 with
 * initialize, tools/list, tools/call and ping. One request in, one response out.
 */

export const PROTOCOL_VERSION = '2025-06-18'

export interface Tool {
  name: string
  description: string
  inputSchema: Record<string, unknown>
  run(args: Record<string, unknown>): Promise<unknown>
}

/** A tool's answer with pictures: the agent sees the JPEG stills (base64) after the text. */
export class Pictured {
  constructor(readonly text: string, readonly jpegs: string[]) {}
}

export interface Session {
  /** Who connected (initialize's clientInfo.name), e.g. "claude-code". */
  client: string
}

interface Request {
  jsonrpc?: string
  id?: string | number | null
  method?: string
  params?: Record<string, unknown>
}

export const INSTRUCTIONS = [
  'Clipnera Studio is a video editor open on this Mac. Use these tools to read and edit the open project the way a professional editor would:',
  'read clipnera_editing_playbook before your first edit.',
  'Read first: clipnera_get_project, clipnera_get_media, then the words: clipnera_get_transcript_range and clipnera_media_search find every line by what is said.',
  'Edit with clipnera_apply_edits (Timeline operations, one idea per call, each one undoable step), and the shelves: clipnera_find_effects, clipnera_set_music,',
  'clipnera_find_broll and clipnera_place_broll, clipnera_open_with_moment for a hook. Check your work with clipnera_look_at_frames.',
  'clipnera_run_command runs the editor’s own commands (clipnera_list_commands): playhead, selection, panels, undo.',
  'Never export or publish unless the person asked you to in this conversation.'
].join('\n')

const reply = (id: Request['id'], result: unknown) => ({ jsonrpc: '2.0', id: id ?? null, result })
const failure = (id: Request['id'], code: number, message: string) => ({ jsonrpc: '2.0', id: id ?? null, error: { code, message } })

/** Answers one JSON-RPC message; null for notifications, which get no answer. */
export async function handle(message: unknown, tools: () => Promise<Tool[]>, session: Session, version: string): Promise<object | null> {
  const req = (message ?? {}) as Request
  if (req.jsonrpc !== '2.0' || typeof req.method !== 'string') return failure(req.id, -32600, 'Not a JSON-RPC 2.0 request')
  const notification = req.id === undefined
  switch (req.method) {
    case 'initialize': {
      const info = req.params?.clientInfo as { name?: unknown } | undefined
      session.client = typeof info?.name === 'string' && info.name ? info.name.slice(0, 40) : 'external agent'
      return reply(req.id, { protocolVersion: PROTOCOL_VERSION, capabilities: { tools: {} }, serverInfo: { name: 'clipnera-studio', version }, instructions: INSTRUCTIONS })
    }
    case 'ping':
      return reply(req.id, {})
    case 'tools/list':
      return reply(req.id, { tools: (await tools()).map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) })
    case 'tools/call': {
      const tool = (await tools()).find((t) => t.name === req.params?.name)
      if (!tool) return failure(req.id, -32602, `Unknown tool ${String(req.params?.name)}`)
      try {
        const result = await tool.run((req.params?.arguments as Record<string, unknown>) ?? {})
        if (result instanceof Pictured) {
          return reply(req.id, { content: [{ type: 'text', text: result.text }, ...result.jpegs.map((data) => ({ type: 'image', data, mimeType: 'image/jpeg' }))] })
        }
        return reply(req.id, { content: [{ type: 'text', text: typeof result === 'string' ? result : JSON.stringify(result, null, 1) }] })
      } catch (error) {
        // Tool failures go back as results, so the agent can read them and try again.
        return reply(req.id, { content: [{ type: 'text', text: error instanceof Error ? error.message : String(error) }], isError: true })
      }
    }
    default:
      return notification ? null : failure(req.id, -32601, `Unknown method ${req.method}`)
  }
}
