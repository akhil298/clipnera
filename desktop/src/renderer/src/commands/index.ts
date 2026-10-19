import { CommandRegistry, type Actor } from './registry'

/** The workbench's one command registry. */
export const commands = new CommandRegistry()

/** Run a command from the UI; failures are already in the Activity log, so they're only reported to the console here. */
export function runCommand(id: string, args?: unknown, actor: Actor = 'user'): void {
  commands.execute(id, args, actor).catch((error: unknown) => console.error(error))
}
