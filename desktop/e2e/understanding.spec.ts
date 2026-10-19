import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { FINDINGS, startFakeBackend, type FakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

let backend: FakeBackend
let app: ElectronApplication
let page: Page

test.beforeAll(async () => {
  backend = await startFakeBackend()
  ;({ app, page } = await launch(backend.url, newProfile()))
  await signIn(page)
})

test.afterAll(async () => {
  await app.close()
  await backend.close()
})

test('shows the AI understanding a file, then what it found', async () => {
  const files = makeTestMedia()
  await page.evaluate((paths) => window.clipnera.media.import(paths), [files.video])
  const row = page.getByRole('listitem').filter({ hasText: 'clip.mp4' })
  await expect(row).toContainText('AI is', { timeout: 30_000 })
  const found = page.getByLabel('What the AI found in clip.mp4')
  await expect(found).toContainText(FINDINGS.summary, { timeout: 15_000 })
  await expect(found).toContainText('42 words · 3 fillers · 1 shots')

  await found.getByRole('button', { name: /The strongest line/ }).click()
  await expect(page.getByRole('button', { name: /Viewing clip.mp4/ })).toBeVisible()
  await expect(page.getByLabel('Playhead time')).not.toHaveText('00:00:00:00')
  // Polling stops once everything is understood.
  const polls = backend.calls.filter((c) => c.endsWith('/analysis')).length
  await page.waitForTimeout(6000)
  expect(backend.calls.filter((c) => c.endsWith('/analysis')).length).toBe(polls)
})
