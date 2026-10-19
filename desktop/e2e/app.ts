import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { _electron as electron, expect, type ElectronApplication, type Page } from '@playwright/test'

export interface Launched {
  app: ElectronApplication
  page: Page
}

export const newProfile = () => mkdtempSync(join(tmpdir(), 'clipnera-e2e-'))

/** Launches the built app against a backend, with its own throwaway profile. */
export async function launch(apiUrl: string, profile: string, extraEnv: Record<string, string> = {}): Promise<Launched> {
  // Tools running inside VS Code inherit ELECTRON_RUN_AS_NODE, which would start Electron as plain Node.
  const { ELECTRON_RUN_AS_NODE: _, ...env } = process.env
  const app = await electron.launch({
    args: ['.'],
    cwd: join(__dirname, '..'),
    env: { ...(env as Record<string, string>), CLIPNERA_API_URL: apiUrl, CLIPNERA_E2E: '1', CLIPNERA_USER_DATA: profile, ...extraEnv }
  })
  return { app, page: await app.firstWindow() }
}

export async function signIn(page: Page): Promise<void> {
  await page.getByLabel(/I am 18 or older/).check()
  await page.getByRole('button', { name: 'Continue with Google' }).click()
  await expect(page.getByRole('region', { name: 'Timeline' })).toBeVisible()
  await projectOpen(page)
}

/** The project has loaded: the timeline shows its toolbar. */
export async function projectOpen(page: Page): Promise<void> {
  await expect(page.getByRole('button', { name: 'Split' })).toBeVisible({ timeout: 15_000 })
}

/** Takes keyboard focus off any text box, so single-key shortcuts reach the workbench. */
export async function blur(page: Page): Promise<void> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
}
