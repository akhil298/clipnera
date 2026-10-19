import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { RENDERED, startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

test('Export renders on the backend and saves the MP4 on this Mac', async () => {
  const backend = await startFakeBackend()
  const folder = newProfile()
  const { app, page } = await launch(backend.url, newProfile(), { CLIPNERA_EXPORT_DIR: folder })
  try {
    await signIn(page)
    const exportButton = page.getByRole('button', { name: 'Export', exact: true })
    await expect(exportButton).toBeDisabled()

    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()

    await page.keyboard.press('Meta+E')
    await expect(page.getByText(/Rendering/)).toBeVisible()
    await expect(page.getByText('Saved to Movies/Clipnera')).toBeVisible({ timeout: 15_000 })
    const [file] = readdirSync(folder)
    expect(file).toMatch(/^Untitled project \d{4}-\d{2}-\d{2} \d{2}-\d{2}\.mp4$/)
    expect(readFileSync(join(folder, file)).equals(RENDERED)).toBe(true)
  } finally {
    await app.close()
    await backend.close()
  }
})
