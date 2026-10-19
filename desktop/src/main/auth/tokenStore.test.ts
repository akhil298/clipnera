import { mkdtemp, readFile, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'
import { TokenStore, type Cipher } from './tokenStore'

// Reversible stand-in for safeStorage, so the test can prove nothing is written in plain text.
const cipher: Cipher = {
  encrypt: (text) => Buffer.from(Buffer.from(text).map((b) => b ^ 0x5a)),
  decrypt: (data) => Buffer.from(data.map((b) => b ^ 0x5a)).toString()
}

describe('TokenStore', () => {
  let file: string
  let store: TokenStore

  beforeEach(async () => {
    file = join(await mkdtemp(join(tmpdir(), 'clipnera-')), 'nested', 'session.bin')
    store = new TokenStore(file, cipher)
  })

  it('round-trips a session, encrypted and private to the user', async () => {
    await store.save({ accessToken: 'secret-token', expiresAt: Date.now() + 60_000 })
    expect((await readFile(file)).toString()).not.toContain('secret-token')
    expect((await stat(file)).mode & 0o777).toBe(0o600)
    expect((await store.load())?.accessToken).toBe('secret-token')
  })

  it('drops an expired session', async () => {
    await store.save({ accessToken: 'old', expiresAt: 1_000 })
    expect(await store.load(2_000)).toBeNull()
    await expect(stat(file)).rejects.toThrow()
  })

  it('treats a missing or unreadable file as signed out', async () => {
    expect(await store.load()).toBeNull()
    const broken = new TokenStore(file, { ...cipher, decrypt: () => { throw new Error('keychain locked') } })
    await store.save({ accessToken: 't', expiresAt: Date.now() + 60_000 })
    expect(await broken.load()).toBeNull()
  })
})
