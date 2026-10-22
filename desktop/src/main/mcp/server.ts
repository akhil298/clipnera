import { randomUUID, timingSafeEqual } from 'node:crypto'
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import { handle, type Session, type Tool } from './protocol'

const MAX_BODY = 1_000_000

function sameToken(given: string, token: string): boolean {
  const a = Buffer.from(given)
  const b = Buffer.from(token)
  return a.length === b.length && timingSafeEqual(a, b)
}

/**
 * MCP over HTTP on 127.0.0.1 (the Streamable HTTP transport, answering each POST with JSON).
 * Only callers on this Mac with the token get in; anything sent by a web page (an Origin
 * header, or a Host that isn't this address) is refused, so a site can't drive the editor.
 */
export class McpServer {
  private server: Server | null = null
  private readonly sessions = new Map<string, Session>()

  constructor(private readonly tools: (session: Session) => Promise<Tool[]>, private readonly version: string) {}

  get listening(): boolean {
    return this.server?.listening ?? false
  }

  start(port: number, token: string): Promise<void> {
    this.stop()
    const server = createServer((req, res) => void this.serve(req, res, port, token))
    this.server = server
    return new Promise((resolve, reject) => {
      server.once('error', reject)
      server.listen(port, '127.0.0.1', () => resolve())
    })
  }

  stop(): void {
    this.server?.closeAllConnections()
    this.server?.close()
    this.server = null
    this.sessions.clear()
  }

  private async serve(req: IncomingMessage, res: ServerResponse, port: number, token: string): Promise<void> {
    const deny = (status: number, message: string) => {
      // Read what was sent before answering, or the connection resets under the caller.
      req.resume()
      res.writeHead(status, { 'Content-Type': 'text/plain', Connection: 'close' }).end(message)
    }
    if (req.headers.origin) return deny(403, 'Browsers may not call Clipnera Studio')
    if (![`127.0.0.1:${port}`, `localhost:${port}`].includes(req.headers.host ?? '')) return deny(403, 'Wrong host')
    if (!sameToken((req.headers.authorization ?? '').replace(/^Bearer /, ''), token)) return deny(401, 'Missing or wrong token')
    if (new URL(req.url ?? '/', 'http://x').pathname !== '/mcp') return deny(404, 'Not found')
    if (req.method !== 'POST') return deny(405, 'POST JSON-RPC messages to /mcp')

    let body = ''
    for await (const chunk of req) {
      body += chunk
      if (body.length > MAX_BODY) return deny(413, 'Too large')
    }
    let message: unknown
    try {
      message = JSON.parse(body)
    } catch {
      res.writeHead(400, { 'Content-Type': 'application/json' }).end(JSON.stringify({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Not JSON' } }))
      return
    }

    // One session per Mcp-Session-Id: it remembers which agent this is.
    let id = String(req.headers['mcp-session-id'] ?? '')
    let session = this.sessions.get(id)
    if (!session) {
      id = randomUUID()
      session = { client: 'external agent' }
      this.sessions.set(id, session)
    }
    const messages = Array.isArray(message) ? message : [message]
    const answers = (await Promise.all(messages.map((m) => handle(m, () => this.tools(session), session, this.version)))).filter(Boolean)
    if (answers.length === 0) {
      res.writeHead(202, { 'Mcp-Session-Id': id }).end()
      return
    }
    res.writeHead(200, { 'Content-Type': 'application/json', 'Mcp-Session-Id': id }).end(JSON.stringify(Array.isArray(message) ? answers : answers[0]))
  }
}
