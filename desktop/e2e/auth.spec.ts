import { expect, test } from '@playwright/test'
import { launch, newProfile, signIn, type Launched } from './app'
import { startFakeBackend, USER, type FakeBackend } from './fakeBackend'

test.describe.serial('sign in', () => {
  let backend: FakeBackend
  let launched: Launched
  const profile = newProfile()

  test.beforeAll(async () => {
    backend = await startFakeBackend()
    launched = await launch(backend.url, profile)
  })

  test.afterAll(async () => {
    await launched.app.close()
    await backend.close()
  })

  test('asks for consent before Google sign-in', async () => {
    const { page } = launched
    await expect(page.getByRole('main', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeDisabled()
    await expect(page.getByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', 'https://clipnera.com/terms')
  })

  test('signs in through the browser round trip', async () => {
    const { page } = launched
    await signIn(page)
    await expect(page.getByText(USER.name)).toBeVisible()
    await expect(page.getByText('1,240 credits')).toBeVisible()
    expect(backend.calls.slice(0, 5)).toEqual([
      'POST /api/v1/auth/desktop/start',
      'GET /fake-google',
      'GET /api/v1/auth/desktop/callback',
      'POST /api/v1/auth/desktop/exchange',
      'GET /api/v1/me'
    ])
    // Signing in opens a project: the newest one, or a new one when there is none.
    await expect.poll(() => backend.calls).toContain('POST /api/v1/editor/projects')
  })

  test('stays signed in after a restart', async () => {
    await launched.app.close()
    launched = await launch(backend.url, profile)
    await expect(launched.page.getByRole('region', { name: 'Timeline' })).toBeVisible()
    await expect(launched.page.getByText(USER.name)).toBeVisible()
  })

  test('signs out', async () => {
    const { page } = launched
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page.getByRole('main', { name: 'Sign in' })).toBeVisible()
    expect(backend.calls).toContain('POST /api/v1/auth/logout')
  })
})
