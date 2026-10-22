import { chmodSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { AgentEvent } from '../../shared/agent'
import { ClaudeChat, eventsOf, toolLabel } from './claudeChat'

describe('the chat on the person’s own Claude', () => {
  it('shows what Claude says and does as the chat’s own events', () => {
    expect(eventsOf({ type: 'assistant', message: { content: [{ type: 'text', text: ' Warming it up. ' }, { type: 'tool_use', id: 't1', name: 'mcp__clipnera__clipnera_run_command', input: { command: 'look.set' } }] } }))
      .toEqual([{ event: 'text', data: { text: 'Warming it up.' } }, { event: 'tool', data: { id: 't1', name: 'mcp__clipnera__clipnera_run_command', label: 'Running look.set' } }])
    expect(eventsOf({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 't1', is_error: true, content: [{ type: 'text', text: 'No such look' }] }] } }))
      .toEqual([{ event: 'tool_done', data: { id: 't1', ok: false, error: 'No such look' } }])
    expect(eventsOf({ type: 'result', is_error: false, result: 'ok' })).toEqual([{ event: 'done', data: { reason: 'answered', message: null } }])
    expect(eventsOf({ type: 'result', is_error: true, result: 'Usage limit reached' })).toEqual([{ event: 'error', data: { message: 'Usage limit reached' } }])
    expect(toolLabel('mcp__clipnera__clipnera_get_project')).toBe('Reading the timeline')
  })

  it('runs Claude Code with only the editor’s tools, and carries the conversation on', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'claude-chat-'))
    const log = join(dir, 'args.json')
    const fake = join(dir, 'claude')
    writeFileSync(fake, `#!/usr/bin/env node
const fs = require('fs')
const seen = fs.existsSync(${JSON.stringify(log)}) ? JSON.parse(fs.readFileSync(${JSON.stringify(log)}, 'utf8')) : []
seen.push(process.argv.slice(2)); fs.writeFileSync(${JSON.stringify(log)}, JSON.stringify(seen))
console.log(JSON.stringify({ type: 'system', subtype: 'init', session_id: 'sess-1' }))
console.log(JSON.stringify({ type: 'assistant', message: { content: [{ type: 'text', text: 'Done.' }] } }))
console.log(JSON.stringify({ type: 'result', is_error: false, result: 'Done.', session_id: 'sess-1' }))
`)
    chmodSync(fake, 0o755)
    const events: AgentEvent[] = []
    const chat = new ClaudeChat({ claudePath: async () => fake, editorAccess: async () => ({ url: 'http://127.0.0.1:1/mcp', token: 'tok' }), workdir: join(dir, 'work'), emit: (e) => events.push(e) })
    await chat.send('p1', { prompt: 'Make it warmer' } as never)
    await chat.send('p1', { prompt: 'And brighter' } as never)
    const [first, second] = JSON.parse(readFileSync(log, 'utf8')) as string[][]
    const value = (args: string[], flag: string) => args[args.indexOf(flag) + 1]
    expect(value(first, '-p')).toBe('Make it warmer')
    // No files, no shell: built-in tools off, only the editor's MCP server, only its tools allowed.
    expect(value(first, '--tools')).toBe('')
    expect(first).toContain('--strict-mcp-config')
    expect(value(first, '--allowedTools')).toBe('mcp__clipnera')
    expect(JSON.parse(value(first, '--mcp-config'))).toEqual({ mcpServers: { clipnera: { type: 'http', url: 'http://127.0.0.1:1/mcp', headers: { Authorization: 'Bearer tok' } } } })
    expect(first).not.toContain('--resume')
    expect(value(second, '--resume')).toBe('sess-1')
    expect(events.filter((e) => e.event === 'text')).toHaveLength(2)
  })
})
