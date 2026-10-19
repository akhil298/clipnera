import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { blur, launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')
test.describe.configure({ mode: 'serial' })

let backend: FakeBackend
let app: ElectronApplication
let page: Page
const server = () => [...backend.projects.values()][0].timeline
const ready = () => page.evaluate(() => window.clipnera.media.list().then((l) => l.length === 2 && l.every((i) => i.status === 'ready')))

test.beforeAll(async () => {
  const files = makeTestMedia()
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
  await page.evaluate((paths) => window.clipnera.media.import(paths), [files.video, files.audio])
  await expect.poll(ready, { timeout: 30_000 }).toBe(true)
  await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
  await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('the library lists sounds, every one of them in exports', async () => {
  await page.getByRole('button', { name: 'Sounds', exact: true }).click()
  const list = page.getByRole('list', { name: 'Sounds' })
  await expect(list.getByRole('listitem')).toHaveCount(2)
  await expect(list).not.toContainText('viewer only')
  await page.getByLabel('Search sounds').fill('whoo')
  await expect(list.getByRole('listitem')).toHaveCount(1)
})

test('a sound added at the playhead plays when the edit passes it', async () => {
  await page.getByLabel('Playhead', { exact: true }).fill('0.5')
  await page.getByRole('button', { name: 'Add Whoosh at the playhead' }).click()
  await expect.poll(() => server().tracks.find((t) => t.id === 'sfx')?.items[0]).toMatchObject({ type: 'sfx', at: 15, name: 'whoosh', extra: { url: '/static/sfx/whoosh.wav' } })

  await page.getByLabel('Playhead', { exact: true }).fill('0')
  await blur(page)
  await page.keyboard.press('Space')
  await expect.poll(() => page.locator('audio[data-role="sound"]').count(), { intervals: [50] }).toBeGreaterThan(0)
  await page.keyboard.press('k')
})

test('an audio file used as music plays under the edit, ducked under the speech', async () => {
  await page.getByRole('button', { name: 'Music', exact: true }).click()
  await page.getByRole('button', { name: 'Use as music' }).click()
  await expect.poll(() => server().tracks.find((t) => t.id === 'music')?.items[0]).toMatchObject({ type: 'clip', at: 0, volume: 0.2 })

  await page.getByLabel('Playhead', { exact: true }).fill('0')
  await blur(page)
  await page.keyboard.press('Space')
  const music = page.locator('audio[data-role="music"]')
  await expect.poll(() => music.evaluate((a: HTMLAudioElement) => !a.paused && a.currentTime > 0.2)).toBe(true)
  // The clip has speech, so the music sits at its level × the duck.
  expect(await music.evaluate((a: HTMLAudioElement) => a.volume)).toBeCloseTo(0.2 * 0.3, 2)
  await page.keyboard.press('k')
  await expect.poll(() => music.evaluate((a: HTMLAudioElement) => a.paused)).toBe(true)
})
