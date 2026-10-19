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
  'Clipnera Studio is a video editor open on this Mac. Use these tools to read and edit the open project.',
  'Read first: clipnera_get_project, clipnera_get_media. Then edit with clipnera_run_command, using the ids from clipnera_list_commands.',
  'Times in commands are seconds unless a command says frames. Each command is one step the person can undo.',
  'For a whole edit ("edit the video", "make it tight with captions"), use clipnera_ask_clipnera_ai: Clipnera’s own AI has watched and transcribed the footage.',
  'Never export or publish unless the person asked you to in this conversation.'
].join('\n')

const reply = (id: Request['id'], result: unknown) => ({ jsonrpc: '2.0', id: id ?? null, result })
const failure = (id: Request['id'], code: number, message: string) => ({ jsonrpc: '2.0', id: id ?? null, error: { code, message } })

/** Answers one JSON-RPC message; null for notifications, which get no answer. */
export async function handle(message: unknown, tools: Tool[], session: Session, version: string): Promise<object | null> {
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
      return reply(req.id, { tools: tools.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) })
    case 'tools/call': {
      const tool = tools.find((t) => t.name === req.params?.name)
      if (!tool) return failure(req.id, -32602, `Unknown tool ${String(req.params?.name)}`)
      try {
        const result = await tool.run((req.params?.arguments as Record<string, unknown>) ?? {})
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
