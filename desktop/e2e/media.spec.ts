import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

let backend: FakeBackend
let app: ElectronApplication
let page: Page
let files: ReturnType<typeof makeTestMedia>

test.beforeAll(async () => {
  files = makeTestMedia()
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

const row = (name: string) => page.getByRole('list', { name: 'Media files' }).getByRole('listitem').filter({ hasText: name })

test('imports a video: reads it, shows a thumbnail, prepares it for editing', async () => {
  await page.evaluate((paths) => window.clipnera.media.import(paths), [files.video])
  await expect(row('clip.mp4')).toContainText('0:03 · 1920×1080 · 30 fps')
  await expect(row('clip.mp4')).not.toContainText(/Reading|Preparing/, { timeout: 30_000 })
  const thumbnailWidth = await row('clip.mp4').locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)
  expect(thumbnailWidth).toBe(320)
})

test('imports audio, and explains files macOS cannot open', async () => {
  await page.evaluate((paths) => window.clipnera.media.import(paths), [files.audio, files.webm])
  await expect(row('voice.wav')).toContainText('0:02 · audio')
  await expect(row('clip.webm')).toContainText("macOS can't open this file format.")
})

test('removes a file from the project', async () => {
  await row('voice.wav').hover()
  await page.getByRole('button', { name: 'Remove voice.wav' }).click()
  await expect(row('voice.wav')).toHaveCount(0)
  await expect(page.getByLabel('Activity log')).toContainText('media.remove')
})
