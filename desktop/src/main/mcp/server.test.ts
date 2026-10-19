import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { McpServer } from './server'

let PORT = 47930
const TOKEN = 'x'.repeat(48)
let server: McpServer | null = null

// Each test gets its own port: fetch pools connections, and a pooled one to a stopped server resets.
beforeEach(() => void PORT++)
afterEach(() => server?.stop())

const post = (body: unknown, headers: Record<string, string> = {}) =>
  fetch(`http://127.0.0.1:${PORT}/mcp`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`, ...headers }, body: JSON.stringify(body) })

describe('the MCP server', () => {
  it('answers JSON-RPC from this Mac with the token, and keeps a session per agent', async () => {
    server = new McpServer((session) => [{ name: 'who', description: 'Who is calling.', inputSchema: { type: 'object' }, run: async () => session.client }], '0.1.0')
    await server.start(PORT, TOKEN)
    const init = await post({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { clientInfo: { name: 'codex' } } })
    const session = init.headers.get('mcp-session-id')!
    expect(init.status).toBe(200)
    const who = await (await post({ jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'who' } }, { 'Mcp-Session-Id': session })).json()
    expect(who.result.content[0].text).toBe('codex')
    expect((await post({ jsonrpc: '2.0', method: 'notifications/initialized' }, { 'Mcp-Session-Id': session })).status).toBe(202)
  })

  it('refuses a wrong token, web pages, and other paths', async () => {
    server = new McpServer(() => [], '0.1.0')
    await server.start(PORT, TOKEN)
    const ping = { jsonrpc: '2.0', id: 1, method: 'ping' }
    expect((await post(ping, { Authorization: 'Bearer nope' })).status).toBe(401)
    expect((await post(ping, { Origin: 'https://evil.example' })).status).toBe(403)
    expect((await fetch(`http://127.0.0.1:${PORT}/other`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: '{}' })).status).toBe(404)
    expect((await fetch(`http://127.0.0.1:${PORT}/mcp`, { headers: { Authorization: `Bearer ${TOKEN}` } })).status).toBe(405)
  })
})
