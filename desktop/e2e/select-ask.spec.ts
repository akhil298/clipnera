import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { blur, launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')
test.describe.configure({ mode: 'serial' })

let backend: FakeBackend
let app: ElectronApplication
let page: Page

/** Screen x of a time on the ruler, from the clip that spans 0–3 s. */
async function xAt(seconds: number): Promise<{ x: number; y: number }> {
  const clip = (await page.getByRole('group', { name: 'Video 1' }).getByRole('button').first().boundingBox())!
  const ruler = (await page.locator('.ticks').boundingBox())!
  return { x: clip.x + (clip.width * seconds) / 3, y: ruler.y + ruler.height / 2 }
}

async function drag(from: number, to: number) {
  const a = await xAt(from)
  const b = await xAt(to)
  await page.mouse.move(a.x, a.y)
  await page.mouse.down()
  await page.mouse.move(b.x, b.y, { steps: 6 })
  await page.mouse.up()
}

test.beforeAll(async () => {
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
  await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
  await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
  await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
  await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
  await expect(page.getByRole('group', { name: 'Video 1' }).getByRole('button')).toHaveCount(1)
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('dragging on the ruler selects a range and offers to ask about it', async () => {
  await drag(0.5, 2.5)
  await expect(page.getByLabel(/^Selected range 0:00–0:02$/)).toBeVisible()
  await expect(page.getByLabel('Ask the AI about 0:00–0:02')).toBeVisible()
  await expect(page.locator('.composer-scope')).toContainText('About 0:00–0:02')
})

test('asking sends the range, in frames, with the request', async () => {
  await page.getByLabel('Ask the AI about 0:00–0:02').fill('Make this part faster')
  await page.getByLabel('Ask the AI about 0:00–0:02').press('Enter')
  await expect(page.getByLabel('AI reply').last()).toContainText('I split the clip')
  const request = backend.agentRequests.at(-1) as { prompt: string; range: { start: number; end: number } }
  expect(request.prompt).toBe('Make this part faster')
  // 0.5–2.5 s at 30 fps, within a few frames of where the mouse landed.
  expect(Math.abs(request.range.start - 15)).toBeLessThan(4)
  expect(Math.abs(request.range.end - 75)).toBeLessThan(4)
  await expect(page.locator('.turn-prompt').last().locator('.scope-chip')).toHaveText('0:00–0:02')
})

test('Esc clears the range, and a click on the ruler only moves the playhead', async () => {
  await blur(page)
  await page.keyboard.press('Escape')
  await expect(page.locator('.range-band')).toHaveCount(0)
  const at = await xAt(1)
  await page.mouse.click(at.x, at.y)
  await expect(page.locator('.range-band')).toHaveCount(0)
  await expect(page.getByLabel('Playhead time')).not.toHaveText('00:00:00:00')
})
