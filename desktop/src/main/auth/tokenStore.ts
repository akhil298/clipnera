import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'

export interface Cipher {
  encrypt(text: string): Buffer
  decrypt(data: Buffer): string
}

export interface StoredSession {
  accessToken: string
  /** Epoch milliseconds. */
  expiresAt: number
}

/**
 * Keeps the session on disk, encrypted with a key held in the macOS Keychain
 * (Electron's safeStorage in the app; any Cipher in tests).
 */
export class TokenStore {
  constructor(
    private readonly file: string,
    private readonly cipher: Cipher
  ) {}

  async save(session: StoredSession): Promise<void> {
    await mkdir(dirname(this.file), { recursive: true })
    await writeFile(this.file, this.cipher.encrypt(JSON.stringify(session)), { mode: 0o600 })
  }

  /** The stored session, or null when there is none, it can't be read, or it has expired. */
  async load(now = Date.now()): Promise<StoredSession | null> {
    let session: StoredSession
    try {
      session = JSON.parse(this.cipher.decrypt(await readFile(this.file))) as StoredSession
    } catch {
      return null
    }
    if (typeof session.accessToken !== 'string' || !(session.expiresAt > now)) {
      await this.clear()
      return null
    }
    return session
  }

  async clear(): Promise<void> {
    await rm(this.file, { force: true })
  }
}
