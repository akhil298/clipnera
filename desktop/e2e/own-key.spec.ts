import { expect, test } from '@playwright/test'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test('Claude in the chat on the person’s own Anthropic API key', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.getByRole('button', { name: 'Use my Claude' }).click()
    const section = page.getByRole('region', { name: 'Your Anthropic API key' })
    await section.getByLabel('Anthropic API key').fill('sk-ant-api03-test-key-ABCD')
    await section.getByRole('button', { name: 'Save' }).click()
    await expect(section).toContainText('Saved · ends in ABCD')
    await page.getByRole('button', { name: 'Done' }).click()

    const menu = page.getByLabel('AI model')
    await expect(menu.locator('option', { hasText: 'Claude Sonnet 5.5 (my API key)' })).toHaveCount(1)
    // Clipnera's own models never carry the key…
    await page.getByLabel('Message the AI').fill('Hello')
    await page.getByLabel('Message the AI').press('Enter')
    await expect.poll(() => backend.agentKeys.length).toBe(1)
    expect(backend.agentKeys[0]).toBeNull()
    // …a Claude model on the person's key does, with that model.
    await menu.selectOption('claude-sonnet-5-5')
    await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeHidden()
    await page.getByLabel('Message the AI').fill('Make it warmer')
    await page.getByLabel('Message the AI').press('Enter')
    await expect.poll(() => backend.agentKeys.length).toBe(2)
    expect(backend.agentKeys[1]).toBe('sk-ant-api03-test-key-ABCD')
    expect(backend.agentRequests[1].model).toBe('claude-sonnet-5-5')
  } finally {
    await app.close()
    await backend.close()
  }
})
