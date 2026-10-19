import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

test('zoom and framing show in the viewer the way the export crops', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
    await page.getByLabel('Playhead', { exact: true }).fill('1')
    await page.getByRole('button', { name: 'Effects', exact: true }).click()

    const picture = page.getByLabel('Viewer picture')
    const frame = page.locator('.viewer-frame')
    // 1×: the 16:9 footage fills the 16:9 frame exactly.
    await expect.poll(async () => Math.round((await picture.boundingBox())!.width - (await frame.boundingBox())!.width)).toBe(0)

    await page.getByRole('button', { name: /Punch-in/ }).click()
    const clip = () => [...backend.projects.values()][0].timeline.tracks[0].items[0] as { transform: { scale: number; x: number } }
    await expect.poll(() => clip().transform.scale).toBe(1.14)
    await expect.poll(async () => (await picture.boundingBox())!.width / (await frame.boundingBox())!.width).toBeCloseTo(1.14, 2)
    await expect(page.getByRole('group', { name: 'Video 1' }).getByRole('button').first()).toContainText('1.14')

    // Framing all the way left: the picture's left edge meets the frame's.
    await page.getByLabel('Framing, left to right').fill('0')
    await expect.poll(() => clip().transform.x).toBe(0)
    await expect.poll(async () => Math.round((await picture.boundingBox())!.x - (await frame.boundingBox())!.x)).toBe(0)

    // A look colours the edit in the viewer, as the export will.
    await expect(page.getByLabel('Look').getByRole('button')).toHaveCount(7)
    await page.getByRole('button', { name: 'Black & white' }).click()
    await expect.poll(() => [...backend.projects.values()][0].timeline.look).toBe('bw_punch')
    await expect(picture).toHaveCSS('filter', /viewer-look-bw_punch/)
    await page.getByRole('button', { name: 'Moody' }).click()
    await expect(page.locator('.vignette')).toBeVisible()
  } finally {
    await app.close()
    await backend.close()
  }
})
