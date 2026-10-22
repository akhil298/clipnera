import { execFile } from 'node:child_process'
import { access } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { promisify } from 'node:util'
import type { ClaudeCodeStatus } from '../../shared/ipc'

const run = promisify(execFile)

/** Where Claude Code's installers put `claude` on a Mac (native installer, Homebrew, npm, the old local install). */
export const CANDIDATES = [
  join(homedir(), '.local/bin/claude'),
  '/opt/homebrew/bin/claude',
  '/usr/local/bin/claude',
  join(homedir(), '.claude/local/claude'),
  join(homedir(), '.npm-global/bin/claude')
]
export const SERVER_NAME = 'clipnera'
// What Claude Code starts with, so it knows the editor is there and what it may do.
export const STARTER_PROMPT =
  'You are connected to Clipnera Studio, the video editor open on this Mac, through the clipnera tools. ' +
  'Work as a professional video editor: read clipnera_editing_playbook, then clipnera_get_project and the footage, ' +
  'then edit the video the way I ask. Each change you make shows in the editor and can be undone there.'

/** Runs a command and opens Terminal; replaced in tests. */
export interface ClaudeHost {
  exec(file: string, args: string[]): Promise<{ stdout: string; code: number }>
  /** Opens a new Terminal window running `command`. */
  terminal(command: string): Promise<void>
  exists(path: string): Promise<boolean>
}

const quote = (value: string) => `'${value.replace(/'/g, `'\\''`)}'`

export const macHost: ClaudeHost = {
  async exec(file, args) {
    try {
      const { stdout } = await run(file, args, { timeout: 20_000 })
      return { stdout, code: 0 }
    } catch (error) {
      const failed = error as { stdout?: string; code?: number | string }
      return { stdout: failed.stdout ?? '', code: typeof failed.code === 'number' ? failed.code : 1 }
    }
  },
  async terminal(command) {
    const script = `tell application "Terminal"\nactivate\ndo script ${JSON.stringify(command)}\nend tell`
    await run('osascript', ['-e', script])
  },
  async exists(path) {
    return access(path).then(() => true, () => false)
  }
}

/**
 * The person's own Claude Code, which they sign in to themselves (with their Pro or Max plan, through
 * Anthropic's own sign-in): Clipnera finds it, connects it to the editor's MCP server and opens it in
 * Terminal. Clipnera never sees or stores their Claude credentials.
 */
export class ClaudeCode {
  /** `path`, when given, is the only place looked (tests point it at a stand-in). */
  constructor(private readonly host: ClaudeHost = macHost, private readonly path?: string) {}

  async find(): Promise<string | null> {
    if (this.path) return (await this.host.exists(this.path)) ? this.path : null
    for (const path of CANDIDATES) if (await this.host.exists(path)) return path
    // An install elsewhere on the PATH of a login shell (the app itself starts without one).
    const found = await this.host.exec('/bin/zsh', ['-lc', 'command -v claude'])
    const path = found.stdout.trim().split('\n').pop() ?? ''
    return found.code === 0 && path.startsWith('/') ? path : null
  }

  async status(): Promise<ClaudeCodeStatus> {
    const path = await this.find()
    if (!path) return { installed: false, path: null, version: null, signedIn: false, authMethod: null }
    const [version, auth] = await Promise.all([this.host.exec(path, ['--version']), this.host.exec(path, ['auth', 'status'])])
    let authMethod: string | null = null
    try {
      authMethod = String((JSON.parse(auth.stdout) as { authMethod?: string }).authMethod ?? '') || null
    } catch {
      // An older Claude Code prints text: the exit code still says whether it's signed in.
    }
    return { installed: true, path, version: version.stdout.trim().split(' ')[0] || null, signedIn: auth.code === 0 && authMethod !== 'none', authMethod }
  }

  /** Points the person's Claude Code at the editor (for every folder), replacing an older entry. */
  async connect(path: string, url: string, token: string): Promise<void> {
    await this.host.exec(path, ['mcp', 'remove', SERVER_NAME, '--scope', 'user'])
    const added = await this.host.exec(path, ['mcp', 'add', '--transport', 'http', '--scope', 'user', SERVER_NAME, url, '--header', `Authorization: Bearer ${token}`])
    if (added.code !== 0) throw new Error(`Claude Code couldn't add Clipnera Studio: ${added.stdout.trim() || 'unknown error'}`)
  }

  /** Opens Claude Code in Terminal, ready to edit; signing in, when needed, happens there on Anthropic's own page. */
  async open(path: string): Promise<void> {
    await this.host.terminal(`cd ${quote(homedir())} && ${quote(path)} ${quote(STARTER_PROMPT)}`)
  }
}
