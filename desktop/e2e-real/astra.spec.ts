import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { launch } from '../e2e/app'

/**
 * Edits a real talking video with the real backend and gpt-6-astra-1, through the Mac app.
 * Needs: REAL_API_URL (a running backend), REAL_TOKEN (a session for a user with the AI
 * editor on), REAL_VIDEO (a video with speech), REAL_OUT (where to write what happened).
 */
const { REAL_API_URL, REAL_TOKEN, REAL_VIDEO, REAL_OUT } = process.env
test.skip(!REAL_API_URL || !REAL_TOKEN || !REAL_VIDEO || !REAL_OUT, 'set REAL_API_URL, REAL_TOKEN, REAL_VIDEO and REAL_OUT')

const MINUTE = 60_000

test('the AI edits a real video end to end with gpt-6-astra-1', async () => {
  const out = REAL_OUT!
  const log: Record<string, unknown> = { started: new Date().toISOString() }
  const t0 = Date.now()
  const mark = (step: string, extra: Record<string, unknown> = {}) => {
    log[step] = { seconds: Math.round((Date.now() - t0) / 1000), ...extra }
    writeFileSync(join(out, 'result.json'), JSON.stringify(log, null, 2))
  }
  const errors: string[] = []

  const { app, page } = await launch(REAL_API_URL!, join(out, `profile-${Date.now()}`), { CLIPNERA_DEV_TOKEN: REAL_TOKEN! })
  page.on('pageerror', (e) => errors.push(e.message))
  const shot = (name: string) => page.screenshot({ path: join(out, `${name}.png`) })
  const duration = () => page.getByLabel('Duration').innerText()
  const clipCount = () => page.getByRole('group', { name: 'Video 1' }).getByRole('button').count()

  try {
    await expect(page.getByRole('button', { name: 'Split' })).toBeVisible({ timeout: MINUTE })
    mark('project_open', { title: await page.locator('.titlebar-project').innerText() })
    const startCredits = (/([\d,]+) credits/.exec(await page.locator('.statusbar-account').innerText()) ?? ['', ''])[1] + ' credits'

    // 1. Import: read, 720p copy, upload to the project.
    await page.evaluate((paths) => window.clipnera.media.import(paths), [REAL_VIDEO!])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 10 * MINUTE }).toMatch(/ready|failed/)
    const item = await page.evaluate(() => window.clipnera.media.list().then((l) => l[0]))
    mark('imported', { status: item.status, error: item.error ?? null, info: item.info })
    expect(item.status).toBe('ready')

    // 2. The backend's AI understands it.
    const found = page.getByLabel(`What the AI found in ${item.name}`)
    await expect(found.or(page.locator('.understanding.failed'))).toBeVisible({ timeout: 15 * MINUTE })
    mark('understood', { found: await page.locator('.media-item').first().innerText() })
    await shot('1-understood')

    // 3. Put it on the timeline.
    await page.getByRole('listitem').filter({ hasText: item.name }).hover()
    await page.getByRole('button', { name: `Add ${item.name} to timeline` }).click()
    await expect(page.getByRole('group', { name: 'Video 1' }).getByRole('button')).toHaveCount(1)
    const before = await duration()
    mark('on_timeline', { duration: before })

    // 4. The chat is on astra.
    await expect(page.getByLabel('AI model')).toHaveValue('gpt-6-astra-1')

    // 5. A direct edit by the studio agent.
    const ask = async (prompt: string) => {
      await page.getByLabel('Message the AI').fill(prompt)
      await page.getByLabel('Message the AI').press('Enter')
      await expect(page.locator('.aipanel-banner')).toBeVisible({ timeout: 30_000 })
      await expect(page.locator('.aipanel-banner')).toBeHidden({ timeout: 15 * MINUTE })
      return page.getByLabel('AI reply').last().innerText()
    }
    const reply1 = await ask('Remove the filler words and the long pauses.')
    mark('edit_1', { prompt: 'Remove the filler words and the long pauses.', reply: reply1, duration: await duration(), clips: await clipCount() })
    await shot('2-after-first-request')

    // 6. A whole edit: a plan to approve, then it runs.
    const reply2 = await ask('Edit the video.')
    const plan = page.locator('.plan-card').last()
    let planText = ''
    if (await plan.isVisible()) {
      planText = await plan.innerText()
      const approve = plan.getByRole('button', { name: /Approve/ })
      if (await approve.isVisible()) {
        await approve.click()
        await expect(plan.locator('.plan-status')).toHaveText(/done|failed|stopped/, { timeout: 20 * MINUTE })
      }
      planText = await plan.innerText()
    }
    mark('edit_2', { prompt: 'Edit the video.', reply: reply2, plan: planText, duration: await duration(), clips: await clipCount() })
    await shot('3-after-full-edit')

    // The plan spent credits; the status bar shows the new balance.
    const credits = page.locator('.statusbar-account')
    await expect(credits).not.toContainText(startCredits, { timeout: 15_000 })
    const activity = await page.getByLabel('Bottom panel').innerText()
    mark('finished', { before, after: await duration(), credits: { before: startCredits, after: await credits.innerText() }, errors, activity: activity.slice(0, 3000) })
    expect(errors).toEqual([])
  } finally {
    await shot('final').catch(() => undefined)
    await app.close()
  }
})
