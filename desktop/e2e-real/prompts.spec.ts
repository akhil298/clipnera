import { copyFileSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import { launch } from '../e2e/app'

/**
 * A person editing a raw video by chat, with the real backend and gpt-6-astra-1: beginner,
 * intermediate and advanced requests in turn, one conversation. For each one it records what the
 * AI did (its to-do list, tools, edits, plan, reply), what changed on the timeline and how long it
 * took, into prompts.json beside a screenshot per request. Needs REAL_* (see run.sh).
 */
const { REAL_API_URL, REAL_TOKEN, REAL_VIDEO, REAL_OUT } = process.env
test.skip(!REAL_API_URL || !REAL_TOKEN || !REAL_VIDEO || !REAL_OUT, 'set REAL_API_URL, REAL_TOKEN, REAL_VIDEO and REAL_OUT')

const MINUTE = 60_000

type Request = { level: 'beginner' | 'intermediate' | 'advanced'; prompt: string; expect: string }

// REAL_PROMPTS names a JSON file of requests written for the video in hand; these suit 57 Years Apart.
const DEFAULT_PROMPTS: Request[] = [
  { level: 'beginner', prompt: 'Edit this video for me.', expect: 'a plan card for the whole video, then the edit' },
  { level: 'beginner', prompt: 'Add captions.', expect: 'captions on' },
  { level: 'beginner', prompt: 'Make it look warmer.', expect: 'a warm look' },
  { level: 'intermediate', prompt: 'Add a pop sound after every question the boy asks.', expect: 'pop sounds on an audio track' },
  { level: 'intermediate', prompt: 'Put a big title at the start that says 57 Years Apart.', expect: 'a title at 0:00' },
  { level: 'intermediate', prompt: 'Zoom in slowly on the old man when he talks about getting old.', expect: 'a scale keyframe move on a clip' },
  { level: 'intermediate', prompt: 'Add a whoosh with a white flash when the conversation changes topic.', expect: 'whoosh sounds and flashes' },
  { level: 'advanced', prompt: 'Make it more dynamic: closer shots on the emotional lines, a glitch effect on the funniest moment and a light leak on the ending.', expect: 'a to-do list, then zooms, a glitch graphic and a light leak' },
  { level: 'advanced', prompt: 'Slow down the moment where they shake hands or hug at the end, and add a soft sound there.', expect: 'slow motion and a sound' },
  { level: 'advanced', prompt: 'Make the first 5 seconds a hook: the strongest question, a snap zoom and a hit sound.', expect: 'a hook at the start' },
]

const PROMPTS: Request[] = process.env.REAL_PROMPTS ? JSON.parse(readFileSync(process.env.REAL_PROMPTS, 'utf8')) : DEFAULT_PROMPTS

type Track = { kind: string; items: { type: string; extra?: Record<string, unknown>; speed?: number; keyframes?: Record<string, unknown[]>; name?: string }[] }

/** What is on the timeline, by kind: what the request changed shows as the difference. */
async function census(page: Page): Promise<Record<string, number | string>> {
  const state = await page.evaluate(() => window.clipnera.project.get())
  const t = (state as { project?: { timeline: { tracks: Track[]; look: string; captions: { enabled: boolean; style: string } | null } } }).project?.timeline
  if (!t) return {}
  const items = t.tracks.flatMap((tr) => tr.items.map((i) => ({ ...i, track: tr.kind })))
  return {
    clips: items.filter((i) => i.type === 'clip' && i.track === 'video').length,
    overlays: items.filter((i) => i.type === 'clip' && i.track === 'overlay').length,
    texts: items.filter((i) => i.type === 'text').length,
    sounds: items.filter((i) => i.type === 'sfx').length,
    sound_names: [...new Set(items.filter((i) => i.type === 'sfx').map((i) => i.name))].join(','),
    flashes: items.filter((i) => i.type === 'graphic' && typeof i.extra?.solid === 'string').length,
    graphics: items.filter((i) => i.type === 'graphic' && typeof i.extra?.graphic === 'string').map((i) => i.extra!.graphic).join(','),
    slowed: items.filter((i) => i.type === 'clip' && (i.speed ?? 1) < 1).length,
    moving_zooms: items.filter((i) => i.type === 'clip' && (i.keyframes?.scale?.length ?? 0) > 1).length,
    look: t.look,
    captions: t.captions?.enabled ? t.captions.style : 'off'
  }
}

test('a person edits a raw video by chat, from beginner to advanced', async () => {
  const out = REAL_OUT!
  const report: Record<string, unknown>[] = []
  const save = () => writeFileSync(join(out, 'prompts.json'), JSON.stringify(report, null, 2))
  const { app, page } = await launch(REAL_API_URL!, join(out, `profile-${Date.now()}`), { CLIPNERA_DEV_TOKEN: REAL_TOKEN!, CLIPNERA_EXPORT_DIR: join(out, 'exports') })
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  test.setTimeout(120 * MINUTE)
  try {
    await expect(page.getByRole('button', { name: 'Split' })).toBeVisible({ timeout: MINUTE })
    await page.evaluate((paths) => window.clipnera.media.import(paths), [REAL_VIDEO!])
    await expect.poll(() => page.evaluate(() => window.clipnera.media.list().then((l) => l[0]?.status)), { timeout: 15 * MINUTE }).toBe('ready')
    const item = await page.evaluate(() => window.clipnera.media.list().then((l) => l[0]))
    await expect(page.getByLabel(`What the AI found in ${item.name}`).first()).toBeVisible({ timeout: 20 * MINUTE })
    await page.getByRole('listitem').filter({ hasText: item.name }).hover()
    await page.getByRole('button', { name: `Add ${item.name} to timeline` }).click()

    for (const [n, step] of PROMPTS.entries()) {
      if (step.prompt === 'EXPORT') {
        // Render the edit as it stands, as a person would press Export, and keep the file.
        const started = Date.now()
        await page.getByRole('button', { name: 'Export', exact: true }).click()
        await expect(page.locator('.export-status.saved').or(page.locator('.export-status.failed'))).toBeVisible({ timeout: 40 * MINUTE })
        const state = await page.evaluate(() => window.clipnera.export.get())
        if (state.file) copyFileSync(state.file, join(out, `export-${n + 1}.mp4`))
        report.push({ n: n + 1, export: state.phase, file: state.file ? `export-${n + 1}.mp4` : null, seconds_total: Math.round((Date.now() - started) / 1000) })
        save()
        continue
      }
      const before = await census(page)
      const started = Date.now()
      await page.getByLabel('Message the AI').fill(step.prompt)
      await page.getByLabel('Message the AI').press('Enter')
      const turn = page.locator('.turn').last()
      await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeHidden({ timeout: 15 * MINUTE })
      const planned = (Date.now() - started) / 1000
      // A whole edit comes as a plan card: approve it, as a person would, and wait for it to run.
      const plan = turn.locator('.plan-card')
      let planText = ''
      if (await plan.count()) {
        planText = await plan.innerText()
        const approve = plan.getByRole('button', { name: /Approve/ })
        if (await approve.count()) await approve.click()
        await expect(plan.locator('.plan-status')).toHaveText(/done|failed|stopped/, { timeout: 20 * MINUTE })
        planText = await plan.innerText()
      }
      await page.waitForTimeout(1500)
      const after = await census(page)
      const changed = Object.fromEntries(Object.entries(after).filter(([k, v]) => before[k] !== v).map(([k, v]) => [k, `${before[k] ?? ''} → ${v}`]))
      report.push({
        n: n + 1, level: step.level, prompt: step.prompt, expected: step.expect,
        seconds_to_reply: Math.round(planned), seconds_total: Math.round((Date.now() - started) / 1000),
        todos: await turn.locator('.turn-todos li').allInnerTexts(),
        tools: await turn.locator('.turn-tools li').allInnerTexts(),
        edits: await turn.locator('.edit-chip').allInnerTexts(),
        reply: (await turn.locator('.turn-reply > p').allInnerTexts()).join('\n'),
        plan: planText, changed
      })
      save()
      await page.screenshot({ path: join(out, `prompt-${String(n + 1).padStart(2, '0')}.png`) })
    }
    report.push({ errors })
    save()
  } finally {
    await app.close()
  }
})
