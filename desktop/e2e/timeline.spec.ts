import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { blur, launch, newProfile, projectOpen, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')
test.describe.configure({ mode: 'serial' })

let backend: FakeBackend
let app: ElectronApplication
let page: Page
let files: ReturnType<typeof makeTestMedia>
const profile = newProfile()

const clips = () => page.getByRole('group', { name: 'Video 1' }).getByRole('button')
const duration = () => page.getByLabel('Duration')
const serverClips = () => [...backend.projects.values()][0].timeline.tracks.find((t) => t.id === 'v1')!.items.length

test.beforeAll(async () => {
  files = makeTestMedia()
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, profile))
  await signIn(page)
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('an imported file is uploaded and added to the project', async () => {
  await page.evaluate((paths) => window.clipnera.media.import(paths), [files.video])
  await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
  const [key, bytes] = [...backend.uploads.entries()][0]
  expect(key).toMatch(/^editor\/user-1\/.+\.mp4$/)
  expect(bytes).toBeGreaterThan(1000)
  const assets = Object.values([...backend.projects.values()][0].timeline.assets)
  expect(assets).toMatchObject([{ kind: 'video', key, frames: 90, width: 1920, height: 1080, has_audio: true }])
})

test('+ puts it on the timeline and the viewer plays the edit', async () => {
  await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
  await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
  await expect(clips()).toHaveCount(1)
  await expect(duration()).toHaveText('00:00:03:00')
  await expect.poll(serverClips).toBe(1)

  await blur(page)
  await page.keyboard.press('Space')
  await expect.poll(() => page.locator('.viewer video').evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(0.5)
  await page.keyboard.press('k')
})

test('⌘B splits at the playhead, ⌫ deletes and closes the gap', async () => {
  await page.getByLabel('Playhead', { exact: true }).fill('1')
  await page.keyboard.press('Meta+B')
  await expect(clips()).toHaveCount(2)
  await clips().nth(1).click()
  await page.keyboard.press('Backspace')
  await expect(clips()).toHaveCount(1)
  await expect(duration()).toHaveText('00:00:01:00')
  await expect.poll(serverClips).toBe(1)
})

test('⌘Z and ⇧⌘Z undo and redo on the project', async () => {
  await page.keyboard.press('Meta+Z')
  await expect(clips()).toHaveCount(2)
  await expect(duration()).toHaveText('00:00:03:00')
  await page.keyboard.press('Shift+Meta+Z')
  await expect(clips()).toHaveCount(1)
})

test('speed changes the length and dragging an edge trims', async () => {
  await clips().first().click()
  await page.getByLabel('Speed').selectOption('0.5')
  await expect(duration()).toHaveText('00:00:02:00')
  await expect(clips().first()).toContainText('0.5×')

  const box = (await clips().first().boundingBox())!
  await page.mouse.move(box.x + box.width - 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 5 })
  await page.mouse.up()
  await expect(duration()).toHaveText('00:00:01:00')
})

test('the project and its media are still there after a restart', async () => {
  await app.close()
  ;({ app, page } = await launch(backend.url, profile))
  await projectOpen(page)
  await expect(clips()).toHaveCount(1)
  await expect(page.getByRole('listitem').filter({ hasText: 'clip.mp4' })).toContainText('0:03 · 1920×1080 · 30 fps')
})
