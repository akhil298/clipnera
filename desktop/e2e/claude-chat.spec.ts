import { chmodSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

const PORT = 47983

/**
 * A stand-in for the person's own Claude Code in its headless mode: signed in with a Claude plan, and
 * when asked, really calling the editor's tools (from the --mcp-config it was given) and streaming
 * stream-json lines like Claude Code does.
 */
function fakeClaude(dir: string): string {
  const path = join(dir, 'claude')
  writeFileSync(path, `#!/usr/bin/env node
const args = process.argv.slice(2)
if (args[0] === '--version') { console.log('2.1.300 (Claude Code)'); process.exit(0) }
if (args[0] === 'auth') { console.log(JSON.stringify({ authMethod: 'claude.ai' })); process.exit(0) }
if (args[0] === 'mcp') process.exit(0)
const out = (line) => console.log(JSON.stringify(line))
;(async () => {
  const server = JSON.parse(args[args.indexOf('--mcp-config') + 1]).mcpServers.clipnera
  let session = ''
  const rpc = async (id, method, params) => {
    const res = await fetch(server.url, { method: 'POST', headers: { ...server.headers, 'Content-Type': 'application/json', ...(session ? { 'Mcp-Session-Id': session } : {}) }, body: JSON.stringify({ jsonrpc: '2.0', id, method, params }) })
    session = res.headers.get('mcp-session-id') || session
    return res.json()
  }
  out({ type: 'system', subtype: 'init', session_id: 'sess-1' })
  await rpc(1, 'initialize', { protocolVersion: '2025-06-18', clientInfo: { name: 'claude-code' }, capabilities: {} })
  out({ type: 'assistant', message: { content: [{ type: 'text', text: 'I will give it a warm film look.' }, { type: 'tool_use', id: 'tu1', name: 'mcp__clipnera__clipnera_run_command', input: { command: 'look.set' } }] } })
  const done = await rpc(2, 'tools/call', { name: 'clipnera_run_command', arguments: { command: 'look.set', args: { look: 'warm_film' } } })
  out({ type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 'tu1', is_error: done.result.isError === true, content: done.result.content }] } })
  out({ type: 'assistant', message: { content: [{ type: 'text', text: 'The whole video now has a warm film look.' }] } })
  out({ type: 'result', is_error: false, result: 'done', session_id: 'sess-1' })
})()
`)
  chmodSync(path, 0o755)
  return path
}

test('the chat runs on the person’s own Claude, which edits through the editor’s tools', async () => {
  const backend = await startFakeBackend()
  const dir = mkdtempSync(join(tmpdir(), 'clipnera-claude-chat-'))
  const { app, page } = await launch(backend.url, newProfile(), { CLIPNERA_CLAUDE_PATH: fakeClaude(dir), CLIPNERA_TERMINAL_LOG: join(dir, 'terminal.txt'), CLIPNERA_MCP_PORT: String(PORT) })
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()

    // Turn it on (personal), then pick it in the chat's model menu.
    await page.getByRole('button', { name: 'Use my Claude' }).click()
    const toggle = page.getByLabel(/Also use my Claude in Clipnera’s chat/)
    await toggle.click()
    await expect(toggle).toBeChecked()
    await page.getByRole('button', { name: 'Done' }).click()
    await expect(page.getByLabel('AI model').locator('option', { hasText: 'My Claude (Claude Code)' })).toHaveCount(1)
    await page.getByLabel('AI model').selectOption('claude-code')

    await page.getByLabel('Message the AI').fill('Make it look warmer')
    await page.getByLabel('Message the AI').press('Enter')
    const turn = page.locator('.turn').last()
    await expect(turn).toContainText('The whole video now has a warm film look.')
    await expect(turn.locator('.turn-tools')).toContainText('Running look.set')
    // The edit really happened, through the editor's own command.
    await expect.poll(() => [...backend.projects.values()][0].timeline.look).toBe('warm_film')
    expect(backend.agentRequests).toHaveLength(0)
  } finally {
    await app.close()
    await backend.close()
  }
})
