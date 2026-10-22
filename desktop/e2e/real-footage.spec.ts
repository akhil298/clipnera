import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

// A slice of a real vlog with subtitles burned in (CLIPNERA_SAMPLE_VIDEO, or ~/Movies/Clipnera/samples/vlog-20s.mp4).
const SAMPLE = process.env.CLIPNERA_SAMPLE_VIDEO ?? join(homedir(), 'Movies/Clipnera/samples/vlog-20s.mp4')
test.skip(!existsSync(SAMPLE), 'needs a real sample video')

test('real footage with burned-in words goes to the AI marked as subtitled', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [SAMPLE])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 60_000 }).toBe('ready')
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.onScreenText?.share ?? -1)), { timeout: 30_000 }).toBeGreaterThan(0.1)
    const id = await page.evaluate(() => window.clipnera.media.list().then((l) => l[0].id))
    await page.getByLabel('Message the AI').fill('Edit this video for me.')
    await page.getByLabel('Message the AI').press('Enter')
    await expect.poll(() => backend.agentRequests.length, { timeout: 15_000 }).toBeGreaterThan(0)
    expect(backend.agentRequests.at(-1)!.subtitled).toEqual([id])
  } finally {
    await app.close()
    await backend.close()
  }
})
