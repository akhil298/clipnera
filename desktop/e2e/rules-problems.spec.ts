import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')
test.describe.configure({ mode: 'serial' })

let backend: FakeBackend
let app: ElectronApplication
let page: Page
const clips = () => page.getByRole('group', { name: 'Video 1' }).getByRole('button')

test.beforeAll(async () => {
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
  await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
  await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
  for (let i = 0; i < 2; i++) {
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
    await expect(clips()).toHaveCount(i + 1)
  }
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('Edit Rules go with every request to the AI', async () => {
  await page.getByRole('button', { name: 'Edit Rules', exact: true }).click()
  await page.getByLabel('New rule').fill('Never cut the guest mid-sentence')
  await page.getByLabel('New rule').press('Enter')
  await expect(page.getByRole('list', { name: 'Edit Rules' })).toContainText('Never cut the guest mid-sentence')

  await page.getByLabel('Message the AI').fill('Tighten it')
  await page.getByLabel('Message the AI').press('Enter')
  await expect(page.getByLabel('AI reply').last()).toContainText('I split the clip')
  expect(backend.agentRequests.at(-1)).toMatchObject({ prompt: 'Tighten it', rules: ['Never cut the guest mid-sentence'] })
})

test('what the AI learned can be forgotten', async () => {
  const learned = page.getByRole('region', { name: 'Learned from you' })
  await expect(learned).toContainText('Caption style: Karaoke')
  await page.getByRole('button', { name: 'Forget Caption style' }).click()
  await expect(learned).toContainText('Nothing yet')
})

test('a gap shows as a problem, and its fix closes it', async () => {
  // Undo the AI's split, then lift the first clip to leave a gap.
  await page.keyboard.press('Meta+Z')
  await expect(clips()).toHaveCount(2)
  await clips().first().click()
  await page.keyboard.press('Shift+Backspace')
  await expect(clips()).toHaveCount(1)

  const tab = page.getByRole('tab', { name: /Problems/ })
  await expect(tab).toContainText('1')
  await tab.click()
  const problem = page.getByRole('list', { name: 'Problems list' }).getByRole('listitem').first()
  await expect(problem).toContainText('3.0 s gap at 0:00')
  await problem.getByRole('button', { name: 'Close the gap' }).click()
  await expect(page.getByText('No problems found')).toBeVisible()
  await expect(tab).not.toContainText('1')
  await expect.poll(() => [...backend.projects.values()][0].timeline.tracks[0].items.map((i) => i.at)).toEqual([0])
})
