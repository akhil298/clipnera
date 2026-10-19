import { describe, expect, it } from 'vitest'
import { CommandRegistry, type Command } from './registry'

function command(overrides: Partial<Command<unknown>> = {}): Command<unknown> {
  return { id: 'test.run', title: 'Run test', category: 'Test', description: 'A test command.', aiCanRun: true, run: () => {}, ...overrides }
}

describe('CommandRegistry', () => {
  it('runs a command with its arguments and records it', async () => {
    const registry = new CommandRegistry()
    let received: unknown
    registry.register(command({ run: (args) => void (received = args) }))

    await registry.execute('test.run', { n: 1 })

    expect(received).toEqual({ n: 1 })
    expect(registry.activity.get().entries).toMatchObject([{ commandId: 'test.run', actor: 'user', ok: true }])
  })

  it('refuses duplicate ids', () => {
    const registry = new CommandRegistry()
    registry.register(command())
    expect(() => registry.register(command())).toThrow(/already registered/)
  })

  it('throws on an unknown command', async () => {
    await expect(new CommandRegistry().execute('nope')).rejects.toThrow(/Unknown command/)
  })

  it('stops the AI from running commands that are not open to it', async () => {
    const registry = new CommandRegistry()
    registry.register(command({ aiCanRun: false }))
    await expect(registry.execute('test.run', undefined, 'ai')).rejects.toThrow(/AI can't run/)
    await expect(registry.execute('test.run', undefined, 'user')).resolves.toBeUndefined()
  })

  it('lets an outside agent run only what the AI may, and logs it by name', async () => {
    const registry = new CommandRegistry()
    registry.register(command({ id: 'ok.cmd' }))
    registry.register(command({ id: 'no.cmd', aiCanRun: false }))
    await registry.execute('ok.cmd', undefined, 'external', 'claude-code')
    await expect(registry.execute('no.cmd', undefined, 'external', 'codex')).rejects.toThrow(/AI can't run/)
    expect(registry.activity.get().entries[0]).toMatchObject({ actor: 'external', by: 'claude-code', ok: true })
  })

  it('records failures with the reason', async () => {
    const registry = new CommandRegistry()
    registry.register(command({ run: () => { throw new Error('bad input') } }))

    await expect(registry.execute('test.run', undefined, 'ai')).rejects.toThrow('bad input')
    expect(registry.activity.get().entries[0]).toMatchObject({ actor: 'ai', ok: false, error: 'bad input' })
  })

  it('unregisters', () => {
    const registry = new CommandRegistry()
    const dispose = registry.register(command())
    dispose()
    expect(registry.get('test.run')).toBeUndefined()
  })
})
