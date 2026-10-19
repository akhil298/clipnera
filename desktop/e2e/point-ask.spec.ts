import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

test('pointing at a spot asks the AI about it, or zooms in on it', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
    await page.getByLabel('Playhead', { exact: true }).fill('1')

    const frame = (await page.locator('.viewer-frame').boundingBox())!
    await page.mouse.click(frame.x + frame.width * 0.25, frame.y + frame.height * 0.4)
    await expect(page.locator('.point-marker')).toBeVisible()
    await page.getByLabel('Ask the AI about this spot').fill('What is this?')
    await page.getByLabel('Ask the AI about this spot').press('Enter')
    await expect(page.getByLabel('AI reply').last()).toContainText('I split the clip')
    const point = (backend.agentRequests.at(-1) as { point: { x: number; y: number } }).point
    expect(point.x).toBeCloseTo(0.25, 1)
    expect(point.y).toBeCloseTo(0.4, 1)
    await expect(page.locator('.turn-prompt').last()).toContainText('this spot')
    await expect(page.locator('.point-marker')).toHaveCount(0)

    // Zoom in here: the clip under the playhead is framed on the spot, zoomed in.
    await page.mouse.click(frame.x + frame.width * 0.25, frame.y + frame.height * 0.5)
    await page.getByRole('button', { name: 'Zoom in here' }).click()
    // The AI moved the playhead to its cut; the clip there is the one zoomed.
    const zoomed = () => [...backend.projects.values()][0].timeline.tracks[0].items.find((i) => i.type === 'clip' && i.transform.scale > 1) as { transform: { x: number; scale: number } } | undefined
    await expect.poll(() => zoomed()?.transform.scale).toBe(1.3)
    expect(zoomed()!.transform.x).toBeCloseTo(0.25, 1)
  } finally {
    await app.close()
    await backend.close()
  }
})
