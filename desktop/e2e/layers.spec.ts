import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

test('the viewer draws the flashes and animated graphics the export will, and the timeline names them', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
    await expect(page.getByRole('group', { name: 'Video 1' }).getByRole('button')).toHaveCount(1)

    // What the AI places: a graphic track with a white flash and an animated graphic, and a pop.
    await page.evaluate(() => window.clipnera.project.apply([
      { op: 'add_track', id: 'g1', kind: 'graphic' },
      { op: 'add_item', track: 'g1', item: { type: 'graphic', id: 'fl', at: 30, dur: 3, extra: { solid: '#FFFFFF' } } },
      { op: 'add_item', track: 'g1', item: { type: 'graphic', id: 'gr', at: 45, dur: 30, extra: { graphic: 'flash_burst' } } },
      { op: 'add_track', id: 'a9', kind: 'audio' },
      { op: 'add_item', track: 'a9', item: { type: 'sfx', id: 'sp', at: 30, name: 'pop', dur: 9, extra: { url: '/static/sfx/whoosh.wav' } } }
    ] as never))

    // Short items still say what they are.
    const graphics = page.getByRole('group', { name: /Graphics/ })
    await expect(graphics.getByRole('button', { name: /^Flash at/ })).toContainText('Flash')
    await expect(graphics.getByRole('button', { name: /^Flash burst at/ })).toContainText('Flash')
    await expect(page.getByRole('button', { name: /^Pop at/ })).toContainText('Pop')

    const layers = page.getByLabel('Layers')
    await page.getByLabel('Playhead', { exact: true }).fill('1')
    await expect(layers.locator('[data-layer="solid"]')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    await page.getByLabel('Playhead', { exact: true }).fill('2')
    await expect(layers.locator('[data-layer="solid"]')).toHaveCount(0)
    const canvas = layers.locator('canvas[data-layer="graphic"]')
    await expect(canvas).toBeVisible()
    // The graphic's own frames reach the canvas: it is drawn, not just placed.
    await expect.poll(() => page.evaluate(() => (document.querySelector('.layers video') as HTMLVideoElement | null)?.readyState ?? 0)).toBeGreaterThanOrEqual(2)
    await expect.poll(() => canvas.evaluate((el: HTMLCanvasElement) => el.width)).toBeGreaterThan(0)
    await page.getByLabel('Playhead', { exact: true }).fill('3')
    await expect(canvas).toHaveCount(0)
  } finally {
    await app.close()
    await backend.close()
  }
})
