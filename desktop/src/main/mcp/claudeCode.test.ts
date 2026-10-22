import { describe, expect, it } from 'vitest'
import { ClaudeCode, SERVER_NAME, STARTER_PROMPT, type ClaudeHost } from './claudeCode'

function host(answers: Record<string, { stdout: string; code: number }>, installed = '/usr/local/bin/claude') {
  const calls: string[][] = []
  const opened: string[] = []
  const fake: ClaudeHost = {
    exec: async (file, args) => {
      calls.push([file, ...args])
      return answers[args.join(' ')] ?? { stdout: '', code: 0 }
    },
    terminal: async (command) => void opened.push(command),
    exists: async (path) => path === installed
  }
  return { fake, calls, opened }
}

describe('the person’s own Claude Code', () => {
  it('says when it is installed and signed in with a Claude plan', async () => {
    const { fake } = host({ '--version': { stdout: '2.1.300 (Claude Code)\n', code: 0 }, 'auth status': { stdout: '{"authMethod":"claude.ai"}', code: 0 } })
    expect(await new ClaudeCode(fake).status()).toEqual({ installed: true, path: '/usr/local/bin/claude', version: '2.1.300', signedIn: true, authMethod: 'claude.ai' })
  })

  it('says when it is not signed in, or not installed', async () => {
    const out = host({ 'auth status': { stdout: '{"authMethod":"none"}', code: 1 } })
    expect((await new ClaudeCode(out.fake).status()).signedIn).toBe(false)
    const missing = host({ 'command -v claude': { stdout: '', code: 1 } }, '/nowhere')
    expect(await new ClaudeCode(missing.fake).status()).toMatchObject({ installed: false, path: null })
  })

  it('connects it to the editor for every folder, replacing an older entry, and opens it ready to edit', async () => {
    const { fake, calls, opened } = host({})
    const claude = new ClaudeCode(fake)
    await claude.connect('/usr/local/bin/claude', 'http://127.0.0.1:47821/mcp', 'tok')
    expect(calls).toEqual([
      ['/usr/local/bin/claude', 'mcp', 'remove', SERVER_NAME, '--scope', 'user'],
      ['/usr/local/bin/claude', 'mcp', 'add', '--transport', 'http', '--scope', 'user', SERVER_NAME, 'http://127.0.0.1:47821/mcp', '--header', 'Authorization: Bearer tok']
    ])
    await claude.open('/usr/local/bin/claude')
    expect(opened[0]).toContain(`'/usr/local/bin/claude' '${STARTER_PROMPT}'`)
  })

  it('says why when Claude Code refuses the connection', async () => {
    const { fake } = host({ [`mcp add --transport http --scope user ${SERVER_NAME} u --header Authorization: Bearer t`]: { stdout: 'bad url', code: 1 } })
    await expect(new ClaudeCode(fake).connect('/usr/local/bin/claude', 'u', 't')).rejects.toThrow('bad url')
  })
})
