import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')
test.describe.configure({ mode: 'serial' })

let backend: FakeBackend
let app: ElectronApplication
let page: Page
const errors: string[] = []

const clips = () => page.getByRole('group', { name: 'Video 1' }).getByRole('button')
const ask = async (prompt: string) => {
  await page.getByLabel('Message the AI').fill(prompt)
  await page.getByLabel('Message the AI').press('Enter')
}

test.beforeAll(async () => {
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  page.on('pageerror', (e) => errors.push(e.message))
  await signIn(page)
  await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
  await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
  const id = await page.evaluate(() => window.clipnera.media.list().then((l) => l[0].id))
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
  await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
  await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
  await expect(clips()).toHaveCount(1)
  expect(id).toBeTruthy()
})

test.afterAll(async () => {
  // The window never hit an uncaught error along the way.
  expect(errors).toEqual([])
  await app.close()
  await backend.close()
})

test('the chat uses gpt-6-astra-1 by default, from the models the backend offers', async () => {
  const picker = page.getByLabel('AI model')
  await expect(picker).toHaveValue('gpt-6-astra-1')
  await expect(picker.getByRole('option')).toHaveText(['gpt-4o-mini', 'gpt-6-astra-1'])
})

test('a request streams in, edits the timeline and moves the studio', async () => {
  await ask('Split the clip')
  const reply = page.getByLabel('AI reply').last()
  await expect(reply).toContainText('Reading the timeline')
  await expect(reply).toContainText('I split the clip in the middle')
  await expect(reply.getByRole('button', { name: 'Undo' })).toBeVisible()

  await expect(clips()).toHaveCount(2)
  await expect(page.getByLabel('Playhead time')).toHaveText('00:00:01:15')
  await expect(page.locator('[data-item="ai-piece"]')).toHaveAttribute('aria-pressed', 'true')

  const request = backend.agentRequests[0]
  expect(request).toMatchObject({ prompt: 'Split the clip', model: 'gpt-6-astra-1', auto: false, playhead: 0, questions_asked: 0 })
  // What the AI did in the studio is logged as the AI.
  await expect(page.getByLabel('Activity log').getByRole('listitem').filter({ hasText: 'player.seek' }).first()).toContainText('AI')
})

test("the edit's Undo chip takes it back", async () => {
  await page.getByLabel('AI reply').last().getByRole('button', { name: 'Undo' }).click()
  await expect(clips()).toHaveCount(1)
})

test('a whole edit comes as a plan to approve, then runs step by step', async () => {
  await ask('Do a full edit')
  const plan = page.getByLabel('Plan: Full edit')
  await expect(plan).toContainText('proposed')
  // The plan reads as an edit, part by part: when, what is said, what happens there.
  const outline = plan.getByRole('list', { name: 'The edit, part by part' })
  await expect(outline).toContainText('0:00–0:01')
  await expect(outline).toContainText('“hello there friends”')
  await expect(outline).toContainText('1 cut (2 s of pauses, fillers and retakes out) · Closer shot at 0:01')
  await plan.getByRole('button', { name: /Approve/ }).click()
  await expect(plan).toContainText('done')
  await expect(plan).toContainText('Cut the second half')
  await expect(plan.getByLabel('Editor: 1 of 1 done')).toBeVisible()
  await expect(page.getByLabel('Duration')).toHaveText('00:00:01:15')
  expect(backend.calls).toContain(`GET /api/v1/editor/plans/${[...backend.calls].reverse().find((c) => c.includes('/approve'))!.split('/')[5]}/stream`)
})
