import { chmodSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

const PORT = 47982

/** A stand-in for the person's own Claude Code: signed in with a Claude plan, and noting what it was asked. */
function fakeClaude(dir: string): { path: string; calls: string } {
  const path = join(dir, 'claude')
  const calls = join(dir, 'calls.txt')
  writeFileSync(path, `#!/bin/bash
echo "$@" >> ${JSON.stringify(calls)}
case "$1 $2" in
  "--version ") echo "2.1.300 (Claude Code)" ;;
  "auth status") echo '{"authMethod":"claude.ai"}' ;;
esac
exit 0
`)
  chmodSync(path, 0o755)
  return { path, calls }
}

test('Use my Claude connects the person’s own Claude Code to the editor and opens it', async () => {
  const backend = await startFakeBackend()
  const dir = mkdtempSync(join(tmpdir(), 'clipnera-claude-'))
  const claude = fakeClaude(dir)
  const terminal = join(dir, 'terminal.txt')
  const { app, page } = await launch(backend.url, newProfile(), { CLIPNERA_CLAUDE_PATH: claude.path, CLIPNERA_TERMINAL_LOG: terminal, CLIPNERA_MCP_PORT: String(PORT) })
  try {
    await signIn(page)
    await page.getByRole('button', { name: 'Use my Claude' }).click()
    const section = page.getByRole('region', { name: 'Use your Claude' })
    await expect(section).toContainText('signed in with your Claude plan')
    await section.getByRole('button', { name: 'Open in Claude Code' }).click()
    await expect(section).toContainText('connected')

    // Claude Code was pointed at the editor, for every folder, with the editor's own token…
    await expect.poll(() => (existsSync(claude.calls) ? readFileSync(claude.calls, 'utf8') : '')).toContain('mcp add --transport http --scope user clipnera')
    const added = readFileSync(claude.calls, 'utf8').split('\n').find((l) => l.startsWith('mcp add'))!
    const url = added.split(' ').find((part) => part.startsWith('http://'))!
    const token = /Bearer (\w+)/.exec(added)![1]
    expect(url).toBe(`http://127.0.0.1:${PORT}/mcp`)
    // …and opened in Terminal, ready to edit.
    await expect.poll(() => (existsSync(terminal) ? readFileSync(terminal, 'utf8') : '')).toContain(`'${claude.path}' 'You are connected to Clipnera Studio`)

    // What Claude Code was given really reaches the editor.
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', clientInfo: { name: 'claude-code' }, capabilities: {} } })
    })
    expect((await res.json()).result.serverInfo.name).toBe('clipnera-studio')
  } finally {
    await app.close()
    await backend.close()
  }
})
