import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

const PORT = 47981

test('Claude Code drives the open project through MCP, within the AI’s rules', async () => {
  const backend = await startFakeBackend()
  const profile = newProfile()
  const { app, page } = await launch(backend.url, profile, { CLIPNERA_MCP_ENABLE: '1', CLIPNERA_MCP_PORT: String(PORT) })
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()

    const { token } = JSON.parse(readFileSync(join(profile, 'mcp.json'), 'utf8'))
    let session = ''
    let id = 0
    const rpc = async (method: string, params?: object) => {
      const res = await fetch(`http://127.0.0.1:${PORT}/mcp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...(session ? { 'Mcp-Session-Id': session } : {}) },
        body: JSON.stringify({ jsonrpc: '2.0', id: ++id, method, params })
      })
      session = res.headers.get('mcp-session-id') ?? session
      return res.json()
    }
    const tool = async (name: string, args: object = {}) => {
      const res = await rpc('tools/call', { name, arguments: args })
      return { text: res.result.content[0].text as string, error: res.result.isError === true }
    }

    expect((await rpc('initialize', { protocolVersion: '2025-06-18', clientInfo: { name: 'claude-code' }, capabilities: {} })).result.serverInfo.name).toBe('clipnera-studio')
    const names = (await rpc('tools/list')).result.tools.map((t: { name: string }) => t.name)
    expect(names).toEqual(['clipnera_get_project', 'clipnera_get_media', 'clipnera_list_commands', 'clipnera_run_command', 'clipnera_ask_clipnera_ai',
                           'clipnera_export', 'clipnera_editing_playbook', 'clipnera_apply_edits', 'clipnera_look_at_frames'])

    const projectView = JSON.parse((await tool('clipnera_get_project')).text)
    expect(projectView.tracks[0].items[0]).toMatchObject({ type: 'clip', start: 0, end: 3, what: 'clip.mp4' })
    expect(JSON.parse((await tool('clipnera_get_media')).text)[0]).toMatchObject({ name: 'clip.mp4', status: 'ready' })
    const commandIds = JSON.parse((await tool('clipnera_list_commands')).text).map((c: { id: string }) => c.id)
    expect(commandIds).toContain('timeline.split')
    expect(commandIds).not.toContain('export.video')

    // Edit: playhead to 1 s, split — logged under the agent's name.
    await tool('clipnera_run_command', { command: 'player.seek', args: { seconds: 1 } })
    const split = JSON.parse((await tool('clipnera_run_command', { command: 'timeline.split' })).text)
    expect(split.project.tracks[0].items.map((i: { start: number }) => i.start)).toEqual([0, 1])
    await expect(page.getByRole('group', { name: 'Video 1' }).getByRole('button')).toHaveCount(2)
    await expect(page.getByLabel('Activity log').getByRole('listitem').filter({ hasText: 'timeline.split' }).first()).toContainText('claude-code')

    // The AI's own tools, run on the backend: the playbook, an edit (the title may use the person's words), frames.
    expect((await tool('clipnera_editing_playbook')).text).toContain('professional editor')
    const version = JSON.parse((await tool('clipnera_get_project')).text).version
    const title = { op: 'add_item', track: 't9', item: { type: 'text', id: 'x1', at: 0, text: 'BREAKFAST', style: 'title', dur: 30 } }
    const edited = await tool('clipnera_apply_edits', { base_version: version, label: 'Breakfast card', ops: [{ op: 'add_track', id: 't9', kind: 'text' }, title], user_request: 'A card that says BREAKFAST' })
    expect(edited.error).toBe(false)
    expect(backend.agentToolRuns.at(-1)).toMatchObject({ name: 'apply_edits', body: { prompt: 'A card that says BREAKFAST', arguments: { label: 'Breakfast card' } } })
    expect(backend.agentToolRuns.at(-1)?.body.arguments).not.toHaveProperty('user_request')
    await expect(page.getByRole('group', { name: 'Text 1' }).getByRole('button')).toHaveCount(1)
    const frames = await rpc('tools/call', { name: 'clipnera_look_at_frames', arguments: { times: [1] } })
    expect(frames.result.content).toEqual([{ type: 'text', text: '0:01: clip c1' }, { type: 'image', data: '/9j/4AAQSkZJRg==', mimeType: 'image/jpeg' }])

    // What the AI may not do, an outside agent may not do either.
    const refused = await tool('clipnera_run_command', { command: 'export.video' })
    expect(refused.error).toBe(true)
    expect(refused.text).toMatch(/can't run/)

    // A whole request goes to Clipnera's own AI, and its answer comes back.
    const answer = JSON.parse((await tool('clipnera_ask_clipnera_ai', { prompt: 'Tighten the intro' })).text)
    expect(answer.reply).toContain('I split the clip')
    expect(backend.agentRequests.at(-1)).toMatchObject({ prompt: 'Tighten the intro' })
    await expect(page.locator('.turn-prompt').last()).toContainText('via claude-code')

    // The sheet says it's on and gives the setup lines.
    await page.getByRole('button', { name: /Agents on/ }).click()
    const sheet = page.getByRole('dialog', { name: 'Connect Claude Code or Codex' })
    await expect(sheet).toContainText(`On, at http://127.0.0.1:${PORT}/mcp`)
    await expect(sheet.locator('#mcp-claude')).toContainText(token)
    await expect(sheet.locator('#mcp-codex')).toContainText('clipnera-mcp.mjs')
  } finally {
    await app.close()
    await backend.close()
  }
})
