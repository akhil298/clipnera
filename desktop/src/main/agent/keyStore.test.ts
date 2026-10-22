import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { AnthropicKeyStore, type Cipher } from './keyStore'

// Stands in for the keychain: reversible, and never the key in the clear.
const cipher: Cipher = {
  isEncryptionAvailable: () => true,
  encryptString: (text) => Buffer.from([...text].reverse().join(''), 'utf8'),
  decryptString: (data) => [...data.toString('utf8')].reverse().join('')
}

describe('the person’s own Anthropic API key', () => {
  it('is kept encrypted, shown only by its last four characters, and can be removed', async () => {
    const file = join(mkdtempSync(join(tmpdir(), 'key-')), 'anthropic-key.bin')
    const store = new AnthropicKeyStore(file, cipher)
    expect(await store.describe()).toEqual({ saved: false, last4: null })
    await store.set('  sk-ant-api03-abcdefghijklWXYZ ')
    expect(readFileSync(file, 'utf8')).not.toContain('sk-ant')
    expect(await store.get()).toBe('sk-ant-api03-abcdefghijklWXYZ')
    expect(await store.describe()).toEqual({ saved: true, last4: 'WXYZ' })
    await store.clear()
    expect(await store.get()).toBeNull()
  })

  it('refuses something that isn’t an Anthropic key, or a Mac that can’t encrypt it', async () => {
    const file = join(mkdtempSync(join(tmpdir(), 'key-')), 'k.bin')
    await expect(new AnthropicKeyStore(file, cipher).set('hello')).rejects.toThrow('sk-ant-')
    await expect(new AnthropicKeyStore(file, { ...cipher, isEncryptionAvailable: () => false }).set('sk-ant-api03-abcdefghijkl')).rejects.toThrow('encrypt')
  })
})
