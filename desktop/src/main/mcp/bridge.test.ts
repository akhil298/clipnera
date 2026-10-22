import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { McpServer } from './server'

const PORT = 47961
const TOKEN = 'b'.repeat(48)
const BRIDGE = join(__dirname, '../../../bin/clipnera-mcp.mjs')
let server: McpServer

beforeAll(async () => {
  server = new McpServer(async (session) => [{ name: 'who', description: 'Who is calling.', inputSchema: { type: 'object' }, run: async () => session.client }], '0.1.0')
  await server.start(PORT, TOKEN)
})
afterAll(() => server.stop())

/** Runs the bridge with `lines` on stdin and returns what it printed. */
function bridge(lines: object[], settings: object | null): Promise<object[]> {
  const dir = mkdtempSync(join(tmpdir(), 'mcp-'))
  const config = join(dir, 'mcp.json')
  if (settings) writeFileSync(config, JSON.stringify(settings))
  const child = spawn(process.execPath, [BRIDGE], { env: { ...process.env, CLIPNERA_MCP_CONFIG: config } })
  let out = ''
  child.stdout.on('data', (d) => (out += d))
  child.stdin.end(lines.map((l) => JSON.stringify(l)).join('\n') + '\n')
  return new Promise((resolve) => child.on('exit', () => resolve(out.trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)))))
}

describe('the stdio bridge', () => {
  it('carries an MCP conversation to the app, keeping the session', async () => {
    const out = await bridge(
      [
        { jsonrpc: '2.0', id: 1, method: 'initialize', params: { clientInfo: { name: 'codex' } } },
        { jsonrpc: '2.0', method: 'notifications/initialized' },
        { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'who' } }
      ],
      { enabled: true, port: PORT, token: TOKEN }
    )
    expect(out).toHaveLength(2)
    expect(out[1]).toMatchObject({ id: 2, result: { content: [{ text: 'codex' }] } })
  })

  it('says what to do when the app is not set up', async () => {
    const [out] = await bridge([{ jsonrpc: '2.0', id: 1, method: 'ping' }], null)
    expect(out).toMatchObject({ id: 1, error: { message: expect.stringContaining('turn on Agents') } })
  })
})
