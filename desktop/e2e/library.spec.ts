import { expect, test } from '@playwright/test'
import { hasFfmpeg, makeTestMedia } from '../src/main/testMedia'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test.skip(!hasFfmpeg, 'needs ffmpeg to make sample files')

type Doc = { assets: Record<string, { key: string; has_audio: boolean }>; tracks: { id: string; kind: string; items: { type: string; asset?: string; extra: Record<string, unknown>; transition_in?: { type: string } | null }[] }[] }

test('the B-roll and Graphics shelves put shots and graphics over the edit', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.evaluate((paths) => window.clipnera.media.import(paths), [makeTestMedia().video])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 30_000 }).toBe('ready')
    await page.getByRole('listitem').filter({ hasText: 'clip.mp4' }).hover()
    await page.getByRole('button', { name: 'Add clip.mp4 to timeline' }).click()
    const doc = () => [...backend.projects.values()][0].timeline as unknown as Doc

    // B-roll: the shelf's shot is copied into the project and laid over the edit, fading in, silent.
    await page.getByRole('button', { name: 'B-roll', exact: true }).click()
    const shelf = page.getByRole('list', { name: 'B-roll' })
    await expect(shelf.getByRole('listitem')).toContainText('Rocket Launch')
    await shelf.getByRole('button', { name: 'Add Rocket Launch at the playhead' }).click()
    await expect.poll(() => doc().tracks.find((t) => t.kind === 'overlay')?.items.length ?? 0).toBe(1)
    const cutaway = doc().tracks.find((t) => t.kind === 'overlay')!.items[0]
    expect(cutaway.transition_in?.type).toBe('fade')
    expect(doc().assets[cutaway.asset!].has_audio).toBe(false)
    expect(backend.brollAdded).toHaveLength(1)

    // Graphics: one from the shelf, named on the timeline.
    await page.getByRole('button', { name: 'Graphics', exact: true }).click()
    await page.getByRole('list', { name: 'Graphics' }).getByRole('button', { name: 'Add Flash Burst at the playhead' }).click()
    await expect.poll(() => doc().tracks.find((t) => t.kind === 'graphic')?.items[0]?.extra.graphic).toBe('flash_burst')
    await expect(page.getByRole('button', { name: /^Flash burst at/ })).toBeVisible()

    // Music: a bed from Clipnera's own shelf, laid under the edit and named in the Music panel.
    await page.getByRole('button', { name: 'Music', exact: true }).click()
    await page.getByRole('list', { name: 'Music shelf' }).getByRole('button', { name: 'Use Lo-fi Study as music' }).click()
    await expect.poll(() => doc().tracks.find((t) => t.id === 'music')?.items[0]?.extra.name).toBe('Lo-fi Study')
    await expect(page.getByRole('region', { name: 'Music in the edit' })).toContainText('Lo-fi Study')
  } finally {
    await app.close()
    await backend.close()
  }
})
