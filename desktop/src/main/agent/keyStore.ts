import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'

/** Encrypts with the Mac's keychain (Electron's safeStorage); replaced in tests. */
export interface Cipher {
  isEncryptionAvailable(): boolean
  encryptString(text: string): Buffer
  decryptString(data: Buffer): string
}

/**
 * The person's own Anthropic API key, kept on this Mac only, encrypted with the keychain. It goes to
 * Clipnera's backend with each chat turn on it (a header, used for that turn, never stored there).
 */
export class AnthropicKeyStore {
  constructor(private readonly file: string, private readonly cipher: Cipher) {}

  async get(): Promise<string | null> {
    try {
      return this.cipher.decryptString(await readFile(this.file))
    } catch {
      return null
    }
  }

  /** What the screen may show of it: whether there is one, and its last four characters. */
  async describe(): Promise<{ saved: boolean; last4: string | null }> {
    const key = await this.get()
    return { saved: Boolean(key), last4: key ? key.slice(-4) : null }
  }

  async set(key: string): Promise<void> {
    const value = key.trim()
    if (!/^sk-ant-[\w-]{12,}$/.test(value)) throw new Error('That doesn’t look like an Anthropic API key (it starts with sk-ant-)')
    if (!this.cipher.isEncryptionAvailable()) throw new Error('This Mac can’t encrypt the key, so it isn’t saved')
    await mkdir(dirname(this.file), { recursive: true })
    await writeFile(this.file, this.cipher.encryptString(value), { mode: 0o600 })
  }

  async clear(): Promise<void> {
    await rm(this.file, { force: true })
  }
}
