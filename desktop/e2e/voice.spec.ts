import { expect, test } from '@playwright/test'
import { launch, newProfile, signIn } from './app'
import { startFakeBackend } from './fakeBackend'

test('a voice note lands in the chat box, ready to send', async () => {
  const backend = await startFakeBackend()
  const { app, page } = await launch(backend.url, newProfile())
  try {
    await signIn(page)
    await page.getByRole('button', { name: 'Speak a request' }).click()
    await expect(page.getByText('Listening… click to stop')).toBeVisible()
    await page.waitForTimeout(1200)
    await page.getByRole('button', { name: 'Stop the voice note' }).click()
    await expect(page.getByLabel('Message the AI')).toHaveValue('make it punchier')
    const [note] = backend.voiceNotes
    expect(note.webm).toBe(true)
    expect(note.seconds).toBeGreaterThan(0.8)
    expect(note.bytes).toBeGreaterThan(1000)

    // ⇧⌘V does the same, and a second note adds to what's there.
    await page.keyboard.press('Shift+Meta+V')
    await expect(page.getByText('Listening… click to stop')).toBeVisible()
    await page.waitForTimeout(700)
    await page.keyboard.press('Shift+Meta+V')
    await expect(page.getByLabel('Message the AI')).toHaveValue('make it punchier make it punchier')
  } finally {
    await app.close()
    await backend.close()
  }
})
