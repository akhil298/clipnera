import { describe, expect, it } from 'vitest'
import { handle, Pictured, PROTOCOL_VERSION, type Tool } from './protocol'

const tools: Tool[] = [
  { name: 'echo', description: 'Says it back.', inputSchema: { type: 'object' }, run: async (args) => ({ said: args.text }) },
  { name: 'look', description: 'Shows a still.', inputSchema: { type: 'object' }, run: async () => new Pictured('0:01: the clip', ['/9j/4AAQ']) },
  { name: 'broken', description: 'Fails.', inputSchema: { type: 'object' }, run: async () => { throw new Error('No project is open') } }
]
const call = (message: object, session = { client: '' }) => handle(message, async () => tools, session, '0.1.0')

describe('MCP', () => {
  it('introduces itself and remembers who connected', async () => {
    const session = { client: '' }
    const res = (await call({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { clientInfo: { name: 'claude-code' } } }, session)) as { result: { protocolVersion: string; serverInfo: { name: string }; instructions: string } }
    expect(res.result.protocolVersion).toBe(PROTOCOL_VERSION)
    expect(res.result.serverInfo.name).toBe('clipnera-studio')
    expect(res.result.instructions).toContain('clipnera_run_command')
    expect(session.client).toBe('claude-code')
  })

  it('lists and runs tools; a failing tool reports its reason as a result', async () => {
    expect(await call({ jsonrpc: '2.0', id: 2, method: 'tools/list' })).toMatchObject({ result: { tools: [{ name: 'echo' }, { name: 'look' }, { name: 'broken' }] } })
    expect(await call({ jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'echo', arguments: { text: 'hi' } } })).toMatchObject({ result: { content: [{ type: 'text', text: expect.stringContaining('"said": "hi"') }] } })
    expect(await call({ jsonrpc: '2.0', id: 4, method: 'tools/call', params: { name: 'broken' } })).toMatchObject({ result: { isError: true, content: [{ text: 'No project is open' }] } })
  })

  it('sends the stills a tool looked at as images after its text', async () => {
    expect(await call({ jsonrpc: '2.0', id: 7, method: 'tools/call', params: { name: 'look' } })).toEqual({
      jsonrpc: '2.0', id: 7, result: { content: [{ type: 'text', text: '0:01: the clip' }, { type: 'image', data: '/9j/4AAQ', mimeType: 'image/jpeg' }] }
    })
  })

  it('answers errors the JSON-RPC way and ignores notifications', async () => {
    expect(await call({ jsonrpc: '2.0', id: 5, method: 'tools/call', params: { name: 'nope' } })).toMatchObject({ error: { code: -32602 } })
    expect(await call({ jsonrpc: '2.0', id: 6, method: 'resources/list' })).toMatchObject({ error: { code: -32601 } })
    expect(await call({ jsonrpc: '2.0', method: 'notifications/initialized' })).toBeNull()
    expect(await call({ hello: 'there' })).toMatchObject({ error: { code: -32600 } })
  })
})
