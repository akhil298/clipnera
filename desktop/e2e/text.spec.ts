import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')
test.describe.configure({ mode: 'serial' })

let backend: FakeBackend
let app: ElectronApplication
let page: Page
const server = () => [...backend.projects.values()][0].timeline

test.beforeAll(async () => {
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
  await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
  await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
  await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
  await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
  await page.getByRole('button', { name: 'Text & Captions' }).click()
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('turning captions on shows them in the viewer, with the spoken word lit', async () => {
  await page.getByRole('checkbox', { name: 'Captions' }).check()
  await expect.poll(() => server().captions).toMatchObject({ enabled: true, follow: 'v1' })
  await page.getByLabel('Playhead', { exact: true }).fill('0.3')
  const caption = page.getByLabel('Caption', { exact: true })
  await expect(caption).toHaveText('hello there friends')
  await expect(caption).toHaveCSS('text-transform', 'uppercase')
  await expect(caption.locator('span').first()).toHaveCSS('color', 'rgb(124, 242, 90)')
})

test('picking a style changes the captions', async () => {
  await page.getByRole('button', { name: /Simple/ }).click()
  await expect.poll(() => server().captions?.style).toBe('simple')
  await expect(page.getByRole('button', { name: /Simple/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Caption', { exact: true })).toHaveCSS('font-family', /Roboto/)
})

test('a title added at the playhead shows over the picture, and can be edited and moved', async () => {
  await page.getByLabel('Playhead', { exact: true }).fill('1')
  await page.getByLabel('Title text').fill('Big news')
  await page.getByLabel('Title text').press('Enter')
  await expect(page.getByLabel('Title', { exact: true })).toHaveText('Big news')
  await expect(page.getByRole('group', { name: 'Text 1' }).getByRole('button')).toHaveCount(1)

  const words = page.getByLabel(/^Words of title at/)
  await words.fill('Bigger news')
  await words.press('Enter')
  await expect(page.getByLabel('Title', { exact: true })).toHaveText('Bigger news')
  await page.getByLabel('Where the title sits').selectOption('middle')
  await expect.poll(() => server().tracks.find((t) => t.kind === 'text')?.items[0]).toMatchObject({ text: 'Bigger news', transform: { y: 0.4 } })
  await expect(page.getByLabel('Title', { exact: true })).toHaveCSS('text-transform', 'uppercase')
})
