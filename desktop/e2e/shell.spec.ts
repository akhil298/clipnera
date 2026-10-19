import { expect, test, type ElectronApplication, type Page } from '@playwright/test'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend, type FakeBackend } from './fakeBackend'

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

test('opens the workbench with every region', async () => {
  await expect(page).toHaveTitle('Clipnera Studio')
  const regions = [
    ['navigation', 'Views'],
    ['complementary', 'Media'],
    ['region', 'Viewer'],
    ['region', 'Timeline'],
    ['region', 'Bottom panel'],
    ['complementary', 'AI panel']
  ] as const
  for (const [role, name] of regions) await expect(page.getByRole(role, { name, exact: true })).toBeVisible()
  await expect(page.getByText(/Clipnera Studio 0\.1\.0 · Electron/)).toBeVisible()
})

test('the window is locked down', async () => {
  const exposed = await page.evaluate(() => ({ require: typeof (window as unknown as { require?: unknown }).require, bridge: Object.keys(window.clipnera) }))
  expect(exposed.require).toBe('undefined')
  expect(exposed.bridge.sort()).toEqual(['agent', 'appInfo', 'auth', 'export', 'mcp', 'media', 'onRunCommand', 'project'])
})

test('a shortcut runs a command and it lands in the activity log', async () => {
  await page.keyboard.press('Meta+J')
  await expect(page.getByLabel('Bottom panel', { exact: true })).toBeHidden()
  await page.keyboard.press('Meta+J')
  await expect(page.getByLabel('Activity log')).toContainText('view.toggleBottomPanel')
})

test('the activity bar switches views through commands', async () => {
  await page.getByRole('button', { name: 'Sounds' }).click()
  await expect(page.getByRole('complementary', { name: 'Sounds' }).getByLabel('Search sounds')).toBeVisible()
  await expect(page.getByLabel('Activity log')).toContainText('view.showSideView')
})

test('the View menu runs the same command', async () => {
  await app.evaluate(({ Menu }) => {
    const view = Menu.getApplicationMenu()?.items.find((i) => i.label === 'View')
    view?.submenu?.items.find((i) => i.label === 'Toggle AI Panel')?.click()
  })
  await expect(page.getByLabel('AI panel', { exact: true })).toBeHidden()
})

test('⌘K finds any command and runs it', async () => {
  await page.keyboard.press('Meta+K')
  const palette = page.getByRole('dialog', { name: 'Command palette' })
  await expect(palette).toBeVisible()
  await page.keyboard.type('split')
  await expect(palette.getByRole('option').first()).toContainText('Split at Playhead')
  await expect(palette.getByRole('option').first()).toContainText('⌘B')
  await page.keyboard.press('Escape')
  await expect(palette).toBeHidden()

  await page.keyboard.press('Meta+K')
  await page.keyboard.type('zoom in')
  await page.keyboard.press('Enter')
  await expect(palette).toBeHidden()
  await expect(page.getByLabel('Activity log')).toContainText('timeline.zoomIn')
})
