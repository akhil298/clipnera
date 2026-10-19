import { reason } from '../state/errors'
import { createStore } from '../state/store'

/**
 * Who asked for a command. Everything in the workbench, the AI included, runs through the same
 * registry. external: an agent outside the app (Claude Code, Codex) over MCP.
 */
export type Actor = 'user' | 'ai' | 'external'

export interface Command<A = undefined> {
  id: string
  title: string
  category: string
  /** Plain-language description of what the command does; the AI reads this to decide when to use it. */
  description: string
  /** e.g. "Mod+Shift+A". Mod is ⌘ on macOS. */
  shortcut?: string
  aiCanRun: boolean
  /** True when it can't run without arguments; the ⌘K palette leaves it out. */
  needsArgs?: boolean
  /** When its shortcut applies; a command with a true `when` wins a shared shortcut. */
  when?(): boolean
  run(args: A): void | Promise<unknown>
}

export interface ActivityEntry {
  seq: number
  commandId: string
  title: string
  actor: Actor
  /** For an external agent, its name. */
  by?: string
  at: number
  ok: boolean
  error?: string
}

const ACTIVITY_LIMIT = 500

export class CommandRegistry {
  private readonly commands = new Map<string, Command<unknown>>()
  private seq = 0
  readonly activity = createStore<{ entries: ActivityEntry[] }>({ entries: [] })

  register<A>(command: Command<A>): () => void {
    if (this.commands.has(command.id)) throw new Error(`Command "${command.id}" is already registered`)
    this.commands.set(command.id, command as Command<unknown>)
    return () => this.commands.delete(command.id)
  }

  get(id: string): Command<unknown> | undefined {
    return this.commands.get(id)
  }

  list(): Command<unknown>[] {
    return [...this.commands.values()]
  }

  async execute(id: string, args?: unknown, actor: Actor = 'user', by?: string): Promise<void> {
    const command = this.commands.get(id)
    if (!command) throw new Error(`Unknown command "${id}"`)
    if (actor !== 'user' && !command.aiCanRun) throw new Error(`The AI can't run "${id}"`)

    try {
      await command.run(args)
      this.record(command, actor, true, undefined, by)
    } catch (error) {
      this.record(command, actor, false, reason(error), by)
      throw error
    }
  }

  private record(command: Command<unknown>, actor: Actor, ok: boolean, error?: string, by?: string): void {
    const entry: ActivityEntry = { seq: ++this.seq, commandId: command.id, title: command.title, actor, by, at: Date.now(), ok, error }
    this.activity.set(({ entries }) => ({ entries: [...entries, entry].slice(-ACTIVITY_LIMIT) }))
  }
}
