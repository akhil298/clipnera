import { randomBytes } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'

export interface McpSettings {
  enabled: boolean
  port: number
  token: string
  /** The chat on the person's own Claude (their Claude Code): personal, off until they turn it on. */
  claudeChat: boolean
}

export const DEFAULT_PORT = 47821

/** Whether VS Code and terminal agents may drive the editor, and how they reach it. Off until the person turns it on. */
export class McpSettingsStore {
  constructor(private readonly file: string) {}

  async get(): Promise<McpSettings> {
    try {
      const saved = JSON.parse(await readFile(this.file, 'utf8')) as Partial<McpSettings>
      if (typeof saved.token === 'string' && saved.token.length >= 32) {
        return { enabled: saved.enabled === true, port: Number(saved.port) || DEFAULT_PORT, token: saved.token, claudeChat: saved.claudeChat === true }
      }
    } catch {
      // First run: make a token.
    }
    return this.save({ enabled: false, port: DEFAULT_PORT, token: randomBytes(24).toString('hex'), claudeChat: false })
  }

  async save(settings: McpSettings): Promise<McpSettings> {
    await mkdir(dirname(this.file), { recursive: true })
    await writeFile(this.file, JSON.stringify(settings, null, 2), { mode: 0o600 })
    return settings
  }
}
