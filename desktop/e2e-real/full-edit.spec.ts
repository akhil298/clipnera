import { copyFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { launch } from '../e2e/app'

/**
 * Raw footage in, finished video out, with the real backend and gpt-6-astra-1:
 * import → the AI understands it → "Edit the video." → approve the plan → Export → MP4.
 * Needs REAL_API_URL, REAL_TOKEN, REAL_VIDEO and REAL_OUT (see run.sh).
 */
const { REAL_API_URL, REAL_TOKEN, REAL_VIDEO, REAL_OUT } = process.env
test.skip(!REAL_API_URL || !REAL_TOKEN || !REAL_VIDEO || !REAL_OUT, 'set REAL_API_URL, REAL_TOKEN, REAL_VIDEO and REAL_OUT')

const MINUTE = 60_000

test('a raw video becomes a finished video', async () => {
  const out = REAL_OUT!
  const log: Record<string, unknown> = { started: new Date().toISOString(), video: REAL_VIDEO }
  const t0 = Date.now()
  const mark = (step: string, extra: Record<string, unknown> = {}) => {
    log[step] = { seconds: Math.round((Date.now() - t0) / 1000), ...extra }
    writeFileSync(join(out, 'result.json'), JSON.stringify(log, null, 2))
  }
  const errors: string[] = []
  const { app, page } = await launch(REAL_API_URL!, join(out, `profile-${Date.now()}`), { CLIPNERA_DEV_TOKEN: REAL_TOKEN!, CLIPNERA_EXPORT_DIR: join(out, 'exports') })
  page.on('pageerror', (e) => errors.push(e.message))
  const shot = (name: string) => page.screenshot({ path: join(out, `${name}.png`) })
  const tracks = () => page.locator('.lane').evaluateAll((lanes) => lanes.map((l) => `${l.querySelector('.lane-label')?.textContent}: ${l.querySelectorAll('.item').length}`))

  try {
    await expect(page.getByRole('button', { name: 'Split' })).toBeVisible({ timeout: MINUTE })
    await page.evaluate((paths) => window.clipnera.media.import(paths), [REAL_VIDEO!])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 15 * MINUTE }).toMatch(/ready|failed/)
    const item = await page.evaluate(() => window.clipnera.media.list().then((l) => l[0]))
    expect(item.status).toBe('ready')
    mark('imported', { info: item.info })

    // Done when it shows what it found, or offers to try again after failing.
    await expect(page.getByLabel(`What the AI found in ${item.name}`).or(page.getByRole('button', { name: 'Try again' })).first()).toBeVisible({ timeout: 20 * MINUTE })
    mark('understood', { found: await page.locator('.media-item').first().innerText() })
    await shot('1-understood')

    await page.getByRole('listitem').filter({ hasText: item.name }).hover()
    await page.getByRole('button', { name: `Add ${item.name} to timeline` }).click()
    await expect(page.getByRole('group', { name: 'Video 1' }).getByRole('button')).toHaveCount(1)
    await expect(page.getByLabel('AI model')).toHaveValue('gpt-6-astra-1')
    const before = await page.getByLabel('Duration').innerText()
    mark('raw_on_timeline', { duration: before })

    await page.getByLabel('Message the AI').fill('Edit the video.')
    await page.getByLabel('Message the AI').press('Enter')
    const plan = page.locator('.plan-card').last()
    await expect(plan).toBeVisible({ timeout: 10 * MINUTE })
    mark('plan', { plan: await plan.innerText() })
    await shot('2-plan')
    await plan.getByRole('button', { name: /Approve/ }).click()
    await expect(plan.locator('.plan-status')).toHaveText(/done|failed|stopped/, { timeout: 30 * MINUTE })
    await expect(page.locator('.aipanel-banner')).toBeHidden({ timeout: 5 * MINUTE })
    mark('edited', { plan: await plan.innerText(), duration: await page.getByLabel('Duration').innerText(), tracks: await tracks() })
    await shot('3-edited')

    await page.getByRole('button', { name: 'Export', exact: true }).click()
    await expect(page.locator('.export-status.saved').or(page.locator('.export-status.failed'))).toBeVisible({ timeout: 40 * MINUTE })
    const state = await page.evaluate(() => window.clipnera.export.get())
    mark('exported', { state })
    expect(state.phase).toBe('saved')
    copyFileSync(state.file!, join(out, 'final.mp4'))
    await shot('4-exported')
    mark('finished', { errors })
    expect(errors).toEqual([])
  } finally {
    await shot('final').catch(() => undefined)
    await app.close()
  }
})
