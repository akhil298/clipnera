import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { blur, launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

test('takes keep versions of the edit and bring them back', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  const clips = () => page.getByRole('group', { name: 'Video 1' }).getByRole('button')
  const duration = () => page.getByLabel('Duration')
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
    await expect(duration()).toHaveText('00:00:03:00')

    await page.getByRole('button', { name: 'Takes', exact: true }).click()
    await page.getByLabel('Take name').fill('Full')
    await page.getByLabel('Take name').press('Enter')
    await expect(page.getByRole('list', { name: 'Takes' })).toContainText('Full')

    // Cut it down: split at 1 s and delete the rest.
    await page.getByLabel('Playhead', { exact: true }).fill('1')
    await page.keyboard.press('Meta+B')
    await clips().nth(1).click()
    await page.keyboard.press('Backspace')
    await expect(duration()).toHaveText('00:00:01:00')
    await expect(page.getByRole('list', { name: 'Takes' }).getByRole('listitem').filter({ hasText: 'Full' })).toContainText('+2 s')

    const full = page.getByRole('list', { name: 'Takes' }).getByRole('listitem').filter({ hasText: 'Full' })
    await full.getByRole('button', { name: 'Restore…' }).click()
    await full.getByRole('button', { name: 'Restore', exact: true }).click()
    await expect(duration()).toHaveText('00:00:03:00')
    await expect(clips()).toHaveCount(1)
    // The cut-down edit was kept as a take before the restore.
    await expect(page.getByRole('list', { name: 'Takes' })).toContainText('Before restoring “Full”')

    await blur(page)
    await page.keyboard.press('Meta+Z')
    await expect(duration()).toHaveText('00:00:01:00')

    // Asking the AI keeps the edit before it as a take.
    await page.getByLabel('Message the AI').fill('Tighten it')
    await page.getByLabel('Message the AI').press('Enter')
    await expect(page.getByRole('list', { name: 'Takes' })).toContainText('Before “Tighten it”')
  } finally {
    await app.close()
    await backend.close()
  }
})
