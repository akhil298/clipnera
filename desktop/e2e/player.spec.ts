import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

let backend: FakeBackend
let app: ElectronApplication
let page: Page
let files: ReturnType<typeof makeTestMedia>

const playhead = () => page.getByLabel('Playhead time')
const video = () => page.locator('.viewer video')
const media = <T>(read: (v: HTMLVideoElement) => T) => video().evaluate(read)

test.beforeAll(async () => {
  files = makeTestMedia()
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
  await page.evaluate((paths) => window.clipnera.media.import(paths), [files.video, files.audio])
  await expect(page.getByRole('button', { name: 'Open clip.mp4' })).toBeEnabled({ timeout: 30_000 })
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('opens a file in the viewer with its length', async () => {
  await expect(page.getByText('Put footage on the timeline to see your edit here')).toBeVisible()
  await page.getByRole('button', { name: 'Open clip.mp4' }).click()
  await expect(page.getByRole('button', { name: /Viewing clip.mp4 · Back to timeline/ })).toBeVisible()
  await expect(page.getByLabel('Duration')).toHaveText('00:00:03:00')
  await expect.poll(() => media((v) => v.readyState)).toBeGreaterThanOrEqual(2)
})

test('steps frame by frame with the arrow keys', async () => {
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowRight')
  await expect(playhead()).toHaveText('00:00:00:03')
  await page.keyboard.press('ArrowLeft')
  await expect(playhead()).toHaveText('00:00:00:02')
  // The editing copy really moved to that frame (frame 2 at 30 fps is 0.067–0.1 s).
  await expect.poll(() => media((v) => (v.seeking ? -1 : v.currentTime))).toBeCloseTo(2.5 / 30, 3)
})

test('Space plays and K pauses', async () => {
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible()
  await expect.poll(() => media((v) => v.currentTime)).toBeGreaterThan(0.5)
  await page.keyboard.press('k')
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
  expect(await media((v) => v.paused)).toBe(true)
})

test('L speeds up, J plays backward', async () => {
  await page.keyboard.press('l')
  await page.keyboard.press('l')
  await expect(page.getByText('▶▶ 2×')).toBeVisible()
  expect(await media((v) => v.playbackRate)).toBe(2)
  await page.keyboard.press('k')

  const before = await media((v) => v.currentTime)
  await page.keyboard.press('j')
  await expect(page.getByText('◀◀ 1×')).toBeVisible()
  await expect.poll(() => media((v) => v.currentTime)).toBeLessThan(before - 0.2)
  await page.keyboard.press('k')
})

test('the scrubber moves the playhead', async () => {
  await page.getByLabel('Playhead', { exact: true }).fill('1.5')
  await expect(playhead()).toHaveText('00:00:01:15')
  expect(await media((v) => v.currentTime)).toBeCloseTo(1.5, 1)
  // Shortcuts still work while the scrubber has focus.
  await page.keyboard.press('ArrowRight')
  await expect(playhead()).toHaveText('00:00:01:16')
})

test('plays audio files', async () => {
  await page.getByRole('button', { name: 'Open voice.wav' }).click()
  await expect(page.locator('.viewer-audio')).toContainText('voice.wav')
  await expect(page.getByLabel('Duration')).toHaveText('00:00:02:00')
  await page.keyboard.press('Space')
  await expect.poll(() => media((v) => v.currentTime)).toBeGreaterThan(0.3)
  await page.keyboard.press('k')
})

test('every action went through a command, and removing the open file clears the viewer', async () => {
  const log = page.getByLabel('Activity log')
  for (const id of ['player.open', 'player.stepForward', 'player.togglePlay', 'player.shuttleBack', 'player.seek']) await expect(log).toContainText(id)
  await page.getByRole('listitem').filter({ hasText: 'voice.wav' }).hover()
  await page.getByRole('button', { name: 'Remove voice.wav' }).click()
  await expect(page.getByText('Put footage on the timeline to see your edit here')).toBeVisible()
})
